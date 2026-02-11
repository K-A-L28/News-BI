#!/usr/bin/env python3
"""
System Engine - Orquestador principal del sistema de boletines
Responsable de:
- Cargar y gestionar boletines con archivos
- Ejecutar scripts de usuario dinámicamente
- Coordinar todos los componentes del sistema
"""

import os
import io
import base64
import mimetypes
import importlib.util
import logging
import traceback
from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Importaciones del sistema
from models.database import SessionLocal, Schedule, Newsletter, ExecutionLog, FileAsset, User
from fastapi import Request, HTTPException

# Configuración
logger = logging.getLogger(__name__)

# Variables de entorno para autenticación
TENANT_ID = os.getenv('TENANT_ID', '')
CLIENT_ID = os.getenv('CLIENT_ID', '')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '')

# Configuración adicional del sistema
MAIL_SENDER = os.getenv('MAIL_SENDER', '')
DESTINATARIOS_CCO = [email.strip() for email in os.getenv('DESTINATARIOS_CCO', '').split(',') if email.strip()]

# Configuración de Gemini
GEMINI_API_KEY = [key.strip() for key in os.getenv('GEMINI_API_KEY', '').split(',') if key.strip()]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

if GEMINI_API_KEY:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY[0])
    gemini_model = genai.GenerativeModel(GEMINI_MODEL)

class ScriptUserInterface:
    """Interfaz estándar que deben cumplir los scripts de usuario"""
    
    def get_name(self) -> str:
        """Nombre del script/boletín"""
        raise NotImplementedError
    
    def get_config_requirements(self) -> Dict[str, Any]:
        """Requisitos de configuración del script"""
        return {}
    
    def execute(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecutar el script con la configuración proporcionada
        
        Returns:
            Dict con:
            - success: bool
            - data: Any (datos procesados)
            - template_html: str (HTML para correo)
            - error: str (mensaje de error si falla)
        """
        raise NotImplementedError

class SystemEngine:
    """
    Motor central que orquesta todos los procesos del sistema de boletines.
    Gestiona carga, ejecución y administración de todo el sistema.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scripts_cache = {}  # Cache de scripts cargados
        self.user_scripts_dir = Path("user_scripts")
        self.queries_dir = Path("queries")
        self.templates_dir = Path("templates")
        self.images_dir = Path("images")
        
        # Asegurar que los directorios existan
        for directory in [self.user_scripts_dir, self.queries_dir, 
                         self.templates_dir, self.images_dir]:
            directory.mkdir(exist_ok=True)
    
    def discover_user_scripts(self) -> Dict[str, Any]:
        """
        Descubre dinámicamente todos los scripts de usuario disponibles.
        
        Returns:
            Dict con scripts encontrados y sus metadatos
        """
        scripts = {}
        
        if not self.user_scripts_dir.exists():
            self.logger.warning(f"Directorio {self.user_scripts_dir} no encontrado")
            return scripts
        
        for script_path in self.user_scripts_dir.glob("*.py"):
            if script_path.name.startswith("__"):
                continue
                
            try:
                # Intentar cargar el script para validar la interfaz
                script_info = self._load_script_info(script_path)
                if script_info:
                    scripts[script_path.stem] = script_info
                    
            except Exception as e:
                self.logger.error(f"Error cargando script {script_path}: {str(e)}")
                continue
        
        self.logger.info(f"📋 Scripts descubiertos: {list(scripts.keys())}")
        return scripts
    
    def _load_script_info(self, script_path: Path) -> Optional[Dict[str, Any]]:
        """Carga información de un script sin ejecutarlo"""
        try:
            # Para scripts normales de Python (como los del usuario), 
            # simplemente verificar que el archivo existe y es válido
            if script_path.exists() and script_path.suffix == '.py':
                # Leer el contenido para validar que es un script Python válido
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Validación básica de que es un script Python
                if content.strip():
                    return {
                        'class_name': 'PythonScript',  # Clase genérica
                        'module_path': str(script_path),
                        'instance': PythonScriptWrapper(script_path)
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error cargando script {script_path}: {str(e)}")
            return None

    def get_auth_config(self) -> Dict[str, Any]:
        """
        Obtiene la configuración de autenticación desde variables de entorno.
        
        Returns:
            Dict con configuración de autenticación y sistema
        """
        return {
            'tenant_id': TENANT_ID,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'mail_sender': MAIL_SENDER,
            'destinatarios_cco': DESTINATARIOS_CCO,
            'gemini_api_key': GEMINI_API_KEY[0] if GEMINI_API_KEY else None,
            'gemini_model': GEMINI_MODEL
        }
    
    def execute_bulletin(self, bulletin_name: str, config: Optional[Dict[str, Any]] = None, manual: bool = False) -> Dict[str, Any]:
        """
        Ejecuta un boletín específico usando el engine genérico.
        
        Args:
            bulletin_name: Nombre del boletín a ejecutar
            config: Configuración adicional (opcional)
            manual: Si es ejecución manual
            
        Returns:
            Dict con resultado de la ejecución
        """
        try:
            self.logger.info(f"🚀 Ejecutando boletín: {bulletin_name} ({'manual' if manual else 'programado'})")
            
            # Buscar el script correspondiente
            script_name = bulletin_name.lower().replace(' ', '_')
            script_path = self.user_scripts_dir / f"{script_name}.py"
            
            self.logger.info(f"🔍 Buscando script: {script_path}")
            self.logger.info(f"🔍 Nombre del boletín: '{bulletin_name}' → '{script_name}'")
            
            # Mostrar archivos disponibles para debug
            if self.user_scripts_dir.exists():
                available_scripts = list(self.user_scripts_dir.glob("*.py"))
                self.logger.info(f"📁 Scripts disponibles: {[f.name for f in available_scripts]}")
            else:
                self.logger.warning(f"⚠️ Directorio user_scripts no existe: {self.user_scripts_dir}")
            
            if not script_path.exists():
                return {
                    'success': False,
                    'error': f'Script no encontrado: {script_path}',
                    'execution_id': f"{'manual' if manual else 'auto'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                }
            
            # Cargar y ejecutar el script
            script_info = self._load_script_info(script_path)
            if not script_info:
                return {
                    'success': False,
                    'error': f'Error cargando script: {script_path}',
                    'execution_id': f"{'manual' if manual else 'auto'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                }
            
            # Preparar configuración de ejecución
            execution_config = {
                'bulletin_name': bulletin_name,
                'manual': manual,
                'execution_id': f"{'manual' if manual else 'auto'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'paths': {
                    'user_scripts': str(self.user_scripts_dir),
                    'queries': str(self.queries_dir),
                    'templates': str(self.templates_dir),
                    'images': str(self.images_dir / bulletin_name.lower().replace(' ', '_'))
                }
            }
            
            # Agregar configuración de autenticación y sistema
            execution_config.update(self.get_auth_config())
            
            # Ejecutar el script usando el wrapper
            result = script_info['instance'].execute(execution_config)
            
            # Validar resultado
            if not isinstance(result, dict):
                return {
                    'success': False,
                    'error': 'El script no devolvió un diccionario válido',
                    'execution_id': execution_config['execution_id']
                }
            
            # Asegurar campos requeridos
            result.setdefault('success', False)
            result.setdefault('error', '')
            result['execution_id'] = execution_config['execution_id']
            
            if result['success']:
                self.logger.info(f"✅ Boletín '{bulletin_name}' ejecutado exitosamente")
            else:
                self.logger.error(f"❌ Error ejecutando boletín '{bulletin_name}': {result.get('error', 'Error desconocido')}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error crítico en execute_bulletin: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Error crítico: {str(e)}',
                'execution_id': f"{'manual' if manual else 'auto'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            }
    
    async def upload_bulletin(self, request: Request) -> Dict[str, Any]:
        """
        Procesa la carga de un nuevo boletín con todos sus archivos.
        
        Args:
            request: Request de FastAPI con los archivos
            
        Returns:
            Dict con resultado de la carga
        """
        try:
            # Obtener datos del formulario
            form = await request.form()
            bulletin_name = form.get("bulletin_name")
            
            # Debug logging
            self.logger.info(f"🔍 Debug - Form data keys: {list(form.keys())}")
            self.logger.info(f"🔍 Debug - bulletin_name: {repr(bulletin_name)}")
            self.logger.info(f"🔍 Debug - bulletin_name type: {type(bulletin_name)}")
            
            if not bulletin_name or bulletin_name.strip() == "":
                self.logger.error(f"❌ bulletin_name is empty or None: {repr(bulletin_name)}")
                return {
                    'success': False,
                    'error': 'El nombre del boletín es requerido'
                }
            
            # Obtener archivos
            script_file = form.get("script_file")
            query_files = form.getlist("query_files")
            template_file = form.get("template_file")
            image_files = form.getlist("image_files")
            
            # Debug logging para archivos
            self.logger.info(f"🔍 Debug - script_file: {script_file}")
            self.logger.info(f"🔍 Debug - script_file type: {type(script_file)}")
            self.logger.info(f"🔍 Debug - query_files: {query_files}")
            self.logger.info(f"🔍 Debug - query_files type: {type(query_files)}")
            self.logger.info(f"🔍 Debug - template_file: {template_file}")
            self.logger.info(f"🔍 Debug - image_files: {image_files}")
            
            if not script_file:
                self.logger.error(f"❌ script_file is None or empty: {script_file}")
                return {
                    'success': False,
                    'error': 'El script Python es requerido'
                }
            
            self.logger.info(f"📤 Procesando carga de boletín: {bulletin_name}")
            
            # Conectar a la base de datos
            db = SessionLocal()
            
            try:
                # Obtener o crear usuario admin
                admin_user = self._get_or_create_admin_user(db)
                
                # Crear newsletter
                new_newsletter = Newsletter(
                    name=bulletin_name,
                    subject_line=f"Boletín: {bulletin_name}",
                    created_by=admin_user.user_id
                )
                db.add(new_newsletter)
                db.commit()
                db.refresh(new_newsletter)
                
                # Guardar archivos
                files_loaded = {
                    'script': await self._save_script_file(db, script_file, bulletin_name, admin_user.user_id),
                    'queries': await self._save_query_files(db, query_files, bulletin_name, admin_user.user_id),
                    'template': await self._save_template_file(db, template_file, bulletin_name, admin_user.user_id),
                    'images': await self._save_image_files(db, image_files, bulletin_name, admin_user.user_id)
                }
                
                # Crear schedule por defecto
                default_schedule = Schedule(
                    newsletter_id=new_newsletter.newsletter_id,
                    send_time=time(9, 0),  # 9:00 AM por defecto
                    is_enabled=False,  # Desactivado por defecto
                    timezone="America/Bogota"
                )
                db.add(default_schedule)
                db.commit()
                
                # Limpiar cache de scripts
                self.scripts_cache.clear()
                
                self.logger.info(f"✅ Boletín '{bulletin_name}' cargado exitosamente")
                
                return {
                    'success': True,
                    'message': f"Boletín '{bulletin_name}' cargado exitosamente",
                    'newsletter_id': new_newsletter.newsletter_id,
                    'files_loaded': files_loaded
                }
                
            except Exception as e:
                db.rollback()
                self.logger.error(f"❌ Error en base de datos: {str(e)}")
                return {
                    'success': False,
                    'error': f'Error guardando en base de datos: {str(e)}'
                }
            finally:
                db.close()
                
        except Exception as e:
            self.logger.error(f"❌ Error procesando carga: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Error procesando la carga: {str(e)}'
            }
    
    def _get_or_create_admin_user(self, db):
        """Obiene o crea usuario admin"""
        admin_user = db.query(User).filter(User.email == "admin@system.com").first()
        if not admin_user:
            admin_user = User(
                external_id="system_admin",
                email="admin@system.com",
                full_name="System Admin",
                role="ADMIN"
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        return admin_user
    
    async def _save_script_file(self, db, script_file, bulletin_name, user_id):
        """Guarda el script Python en filesystem y BD"""
        script_content = await script_file.read()
        script_path = self.user_scripts_dir / f"{bulletin_name.lower().replace(' ', '_')}.py"
        
        # Guardar en filesystem
        with open(script_path, 'wb') as f:
            f.write(script_content)
        
        # Guardar en BD
        script_asset = FileAsset(
            file_name=script_file.filename,
            file_content=script_content.decode('utf-8'),
            file_type='script',
            file_path=f"{bulletin_name.lower().replace(' ', '_')}.py",
            created_by=user_id
        )
        db.add(script_asset)
        return 1
    
    async def _save_query_files(self, db, query_files, bulletin_name, user_id):
        """Guarda archivos JSON de consulta"""
        count = 0
        for query_file in query_files:
            query_content = await query_file.read()
            
            # Guardar en BD
            query_asset = FileAsset(
                file_name=query_file.filename,
                file_content=query_content.decode('utf-8'),
                file_type='query',
                file_path=query_file.filename,
                created_by=user_id
            )
            db.add(query_asset)
            count += 1
        return count
    
    async def _save_template_file(self, db, template_file, bulletin_name, user_id):
        """Guarda plantilla HTML si existe"""
        if not template_file:
            return 0
        
        template_content = await template_file.read()
        
        # Guardar en BD
        template_asset = FileAsset(
            file_name=template_file.filename,
            file_content=template_content.decode('utf-8'),
            file_type='template',
            file_path=template_file.filename,
            created_by=user_id
        )
        db.add(template_asset)
        return 1
    
    async def _save_image_files(self, db, image_files, bulletin_name, user_id):
        """Guarda archivos de imagen"""
        count = 0
        bulletin_dir = self.images_dir / bulletin_name.lower().replace(' ', '_')
        bulletin_dir.mkdir(exist_ok=True)
        
        for image_file in image_files:
            image_content = await image_file.read()
            
            # Guardar en filesystem
            image_path = bulletin_dir / image_file.filename
            with open(image_path, 'wb') as f:
                f.write(image_content)
            
            # Guardar en BD
            image_asset = FileAsset(
                file_name=image_file.filename,
                file_content=base64.b64encode(image_content).decode('utf-8'),
                file_type='image',
                file_path=f"{bulletin_name.lower().replace(' ', '_')}/{image_file.filename}",
                created_by=user_id
            )
            db.add(image_asset)
            count += 1
        return count


class PythonScriptWrapper:
    """Wrapper para ejecutar scripts normales de Python"""
    
    def __init__(self, script_path: Path):
        self.script_path = script_path
        self.logger = logging.getLogger(f"PythonScript.{script_path.stem}")
    
    def execute(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el script Python y devuelve el resultado"""
        import logging
        import io
        
        # Crear un capturador de logs
        log_capture = io.StringIO()
        log_handler = logging.StreamHandler(log_capture)
        log_handler.setLevel(logging.DEBUG)
        
        # Configurar el formato de los logs
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(formatter)
        
        # Obtener TODOS los loggers existentes y agregar el capturador
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        
        # Agregar el capturador al logger raíz
        root_logger.addHandler(log_handler)
        root_logger.setLevel(logging.DEBUG)
        
        # También agregar a loggers específicos que el script podría usar
        loggers_to_capture = [
            'user_script',
            'prototipo_san_rafael_bi_daily_insigths',
            '__main__',
            'google.generativeai',
            'requests',
            'urllib3',
            'PIL',
            'matplotlib'
        ]
        
        for logger_name in loggers_to_capture:
            try:
                specific_logger = logging.getLogger(logger_name)
                specific_logger.addHandler(log_handler)
                specific_logger.setLevel(logging.DEBUG)
            except:
                pass
        
        # Forzar la propagación de logs
        logging.getLogger().propagate = True
        
        try:
            # Importar el script dinámicamente
            spec = importlib.util.spec_from_file_location("user_script", self.script_path)
            if spec is None or spec.loader is None:
                return {
                    'success': False,
                    'error': f"No se pudo cargar el script: {self.script_path}",
                    'logs': log_capture.getvalue()
                }
            
            module = importlib.util.module_from_spec(spec)
            
            # Preparar el entorno con las rutas resueltas
            import os
            import builtins
            
            # Guardar funciones originales
            original_exists = os.path.exists
            original_open = open
            
            def smart_open(path, *args, **kwargs):
                """Función open que resuelve rutas desde la base de datos"""
                # Primero buscar en la base de datos
                from models.database import SessionLocal, FileAsset
                db = SessionLocal()
                try:
                    # Extraer nombre del archivo
                    file_name = path.replace('./', '').replace('\\', '').replace('template/', '').replace('images/', '')
                    
                    # Buscar en FileAssets
                    asset = db.query(FileAsset).filter(
                        FileAsset.file_name.like(f"%{file_name}%")
                    ).order_by(FileAsset.created_at.desc()).first()
                    
                    if asset:
                        # Devolver el contenido desde la base de datos
                        if 'r' in args and 'b' not in args:
                            return io.StringIO(asset.file_content)
                        else:
                            return io.BytesIO(base64.b64decode(asset.file_content))
                    
                except Exception as e:
                    self.logger.error(f"Error buscando archivo en BD: {str(e)}")
                finally:
                    db.close()
                
                # Si no se encuentra en BD, usar la función original
                return original_open(path, *args, **kwargs)
            
            def smart_exists(path):
                """Función exists que resuelve rutas desde la base de datos"""
                # Similar a smart_open pero para exists
                from models.database import SessionLocal, FileAsset
                db = SessionLocal()
                try:
                    file_name = path.replace('./', '').replace('\\', '').replace('template/', '').replace('images/', '')
                    asset = db.query(FileAsset).filter(
                        FileAsset.file_name.like(f"%{file_name}%")
                    ).order_by(FileAsset.created_at.desc()).first()
                    
                    if asset:
                        return True
                    
                except Exception:
                    pass
                finally:
                    db.close()
                
                return original_exists(path)
            
            # Aplicar los patches
            os.path.exists = smart_exists
            builtins.open = smart_open
            
            try:
                # Ejecutar el script con captura de errores detallada
                self.logger.info("🔧 Cargando y ejecutando módulo...")
                spec.loader.exec_module(module)
                self.logger.info("🔧 Módulo ejecutado, verificando resultados...")
                
                # Si el script tiene una función main, ejecutarla
                if hasattr(module, 'main'):
                    self.logger.info("🔧 Ejecutando función main() del script")
                    result = module.main()
                    return {
                        'success': True,
                        'message': 'Script ejecutado exitosamente (main)',
                        'result': result,
                        'logs': log_capture.getvalue()
                    }
                else:
                    # Si no hay main, buscar funciones principales comunes y ejecutarlas
                    self.logger.info("🔧 Script ejecutado al cargar módulo (sin main)")
                    
                    # Buscar funciones principales que el script podría tener
                    main_functions = ['main', 'ejecutar', 'run', 'start', 'ejecutar_automatizacion', 'enviar_correo']
                    executed = False
                    
                    for func_name in main_functions:
                        if hasattr(module, func_name):
                            func = getattr(module, func_name)
                            if callable(func):
                                self.logger.info(f"🔧 Ejecutando función {func_name}() del script")
                                try:
                                    result = func()
                                    executed = True
                                    self.logger.info(f"✅ Función {func_name}() ejecutada correctamente")
                                    break
                                except Exception as e:
                                    self.logger.error(f"❌ Error ejecutando {func_name}(): {str(e)}")
                                    success = False
                                    error = str(e)
                                    break
                    
                    if not executed:
                        self.logger.warning("⚠️ No se encontró función principal para ejecutar")
                    
                    # Buscar variables globales que indiquen el resultado
                    success = getattr(module, 'success', True)
                    error = getattr(module, 'error', '')
                    result = getattr(module, 'result', None)
                    
                    # Verificar si hay variables de error específicas
                    if hasattr(module, 'exception'):
                        error = str(getattr(module, 'exception'))
                        success = False
                        self.logger.error(f"❌ El script capturó una excepción: {error}")
                    
                    # Verificar si hay logs o mensajes del script
                    if hasattr(module, 'logs'):
                        self.logger.info(f"📝 Logs del script: {getattr(module, 'logs')}")
                    
                    self.logger.info(f"📊 Resultado del script: success={success}, error='{error}', result={result}")
                    
                    # Capturar logs adicionales que pueda haber generado el script
                    all_logs = log_capture.getvalue()
                    
                    return {
                        'success': success,
                        'message': f'Script ejecutado exitosamente (módulo{f" - {func_name}()" if executed else ""})',
                        'error': error,
                        'result': result,
                        'logs': all_logs
                    }
                    
            finally:
                # Restaurar funciones originales
                os.path.exists = original_exists
                builtins.open = original_open
                
        except Exception as e:
            self.logger.error(f"Error ejecutando script: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'logs': log_capture.getvalue()
            }
        finally:
            # Restaurar los handlers originales del logger
            try:
                root_logger.handlers.clear()
                for handler in original_handlers:
                    root_logger.addHandler(handler)
                    
                # Restaurar niveles originales
                for logger_name in loggers_to_capture:
                    try:
                        specific_logger = logging.getLogger(logger_name)
                        specific_logger.removeHandler(log_handler)
                    except:
                        pass
            except:
                pass
    
    def _resolve_file_path(self, relative_path: str, bulletin_name: str) -> str:
        """
        Resuelve rutas relativas del usuario a las ubicaciones reales de los archivos.
        
        Args:
            relative_path: Ruta relativa usada por el usuario (ej: "./template/images/avatar.png")
            bulletin_name: Nombre del boletín para construir rutas
            
        Returns:
            str: Ruta real al archivo o None si no se encuentra
        """
        from pathlib import Path
        import os
        
        # Normalizar la ruta
        normalized_path = relative_path.replace('\\', '/').lstrip('./')
        
        # Directorios base donde buscar
        base_dirs = [
            (self.templates_dir, "template", "templates"),
            (self.images_dir / bulletin_name.lower().replace(' ', '_'), "images", "images"),
            (self.queries_dir, "query", "queries"),
            (self.user_scripts_dir, "script", "user_scripts")
        ]
        
        # Intentar diferentes patrones de mapeo
        patterns_to_try = [
            # Patrones directos
            normalized_path,
            
            # Patrones con template/ -> templates/
            normalized_path.replace('template/', 'templates/'),
            normalized_path.replace('templates/', 'template/'),
            
            # Patrones con images/ -> images/
            normalized_path.replace('images/', 'images/'),
            
            # Quitar prefijos comunes
            normalized_path.replace('template/', ''),
            normalized_path.replace('templates/', ''),
            normalized_path.replace('images/', ''),
            normalized_path.replace('query/', ''),
            normalized_path.replace('queries/', ''),
        ]
        
        # Buscar en cada directorio base
        for base_dir, *aliases in base_dirs:
            for pattern in patterns_to_try:
                file_path = base_dir / pattern
                
                if file_path.exists() and file_path.is_file():
                    self.logger.info(f"🔍 Path resolved: {relative_path} -> {file_path}")
                    return str(file_path)
        
        # Si no se encuentra, intentar búsqueda más amplia
        for base_dir, *aliases in base_dirs:
            if any(alias in normalized_path for alias in aliases):
                # Extraer solo el nombre del archivo
                filename = Path(normalized_path).name
                file_path = base_dir / filename
                
                if file_path.exists() and file_path.is_file():
                    self.logger.info(f"🔍 Path resolved (by filename): {relative_path} -> {file_path}")
                    return str(file_path)
        
        self.logger.warning(f"❌ Path not found: {relative_path}")
        return None
    
    def _get_or_create_admin_user(self, db):
        """Obiene o crea usuario admin"""
        admin_user = db.query(User).filter(User.email == "admin@system.com").first()
        if not admin_user:
            admin_user = User(
                external_id="system_admin",
                email="admin@system.com",
                full_name="System Admin",
                role="ADMIN"
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        return admin_user
    
    async def _save_script_file(self, db, script_file, bulletin_name, user_id):
        """Guarda el script Python en filesystem y BD"""
        script_content = await script_file.read()
        script_path = self.user_scripts_dir / f"{bulletin_name.lower().replace(' ', '_')}.py"
        
        # Guardar en filesystem
        with open(script_path, "wb") as f:
            f.write(script_content)
        
        # Guardar en base de datos
        script_asset = FileAsset(
            file_name=script_file.filename,
            file_type="python",
            file_path=str(script_path),
            file_content=script_content.decode('utf-8'),
            file_size=len(script_content),
            mime_type="text/x-python",
            created_by=user_id
        )
        db.add(script_asset)
        return 1
    
    async def _save_query_files(self, db, query_files, bulletin_name, user_id):
        """Guarda archivos JSON de consulta"""
        count = 0
        for query_file in query_files:
            query_content = await query_file.read()
            query_path = self.queries_dir / query_file.filename
            
            with open(query_path, "wb") as f:
                f.write(query_content)
            
            query_asset = FileAsset(
                file_name=query_file.filename,
                file_type="json",
                file_path=str(query_path),
                file_content=query_content.decode('utf-8'),
                file_size=len(query_content),
                mime_type="application/json",
                created_by=user_id
            )
            db.add(query_asset)
            count += 1
        return count
    
    async def _save_template_file(self, db, template_file, bulletin_name, user_id):
        """Guarda plantilla HTML si existe"""
        if not template_file:
            return 0
            
        template_content = await template_file.read()
        template_path = self.templates_dir / template_file.filename
        
        with open(template_path, "wb") as f:
            f.write(template_content)
        
        template_asset = FileAsset(
            file_name=template_file.filename,
            file_type="html",
            file_path=str(template_path),
            file_content=template_content.decode('utf-8'),
            file_size=len(template_content),
            mime_type="text/html",
            created_by=user_id
        )
        db.add(template_asset)
        return 1
    
    async def _save_image_files(self, db, image_files, bulletin_name, user_id):
        """Guarda archivos de imagen"""
        count = 0
        bulletin_dir = self.images_dir / bulletin_name.lower().replace(' ', '_')
        bulletin_dir.mkdir(exist_ok=True)
        
        for image_file in image_files:
            image_content = await image_file.read()
            image_path = bulletin_dir / image_file.filename
            
            with open(image_path, "wb") as f:
                f.write(image_content)
            
            # Guardar en base de datos como base64
            mime_type, _ = mimetypes.guess_type(image_file.filename)
            
            image_asset = FileAsset(
                file_name=image_file.filename,
                file_type="image",
                file_path=str(image_path),
                file_content=base64.b64encode(image_content).decode('utf-8'),
                file_size=len(image_content),
                mime_type=mime_type or "image/jpeg",
                created_by=user_id
            )
            db.add(image_asset)
            count += 1
        return count
    
    def get_system_status(self) -> Dict[str, Any]:
        """Obtiene el estado general del sistema"""
        try:
            scripts = self.discover_user_scripts()
            
            return {
                'status': 'running',
                'scripts_loaded': len(scripts),
                'available_scripts': list(scripts.keys()),
                'directories': {
                    'user_scripts': str(self.user_scripts_dir),
                    'queries': str(self.queries_dir),
                    'templates': str(self.templates_dir),
                    'images': str(self.images_dir)
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo estado del sistema: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# Instancia global del engine
system_engine = SystemEngine()
