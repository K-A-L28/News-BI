#!/usr/bin/env python3
"""
Script para cargar archivos JSON y plantillas a la base de datos
"""

import os
import json
import base64
import mimetypes
import logging
from .database import SessionLocal, FileAsset, User

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cargar_archivos():
    """Carga todos los archivos necesarios a la base de datos"""
    db = SessionLocal()
    
    try:
        # Obtener o crear usuario admin
        admin_user = db.query(User).filter(User.email == "admin@system.com").first()
        if not admin_user:
            admin_user = User(
                external_id="system_admin",
                email="admin@system.com",
                nombres="System",
                apellidos="Admin",
                role="ADMIN"
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        
        # Archivos a cargar
        archivos_config = [
            {
                "file_path": "queryCenso.json",
                "file_name": "queryCenso.json",
                "file_type": "json",
                "descripcion": "Configuración de consultas DAX para censo"
            },
            {
                "file_path": "queryCensoFact.json", 
                "file_name": "queryCensoFact.json",
                "file_type": "json",
                "descripcion": "Configuración de consultas DAX para facturación"
            },
            {
                "file_path": "queriesSatisfaccion.json",
                "file_name": "queriesSatisfaccion.json", 
                "file_type": "json",
                "descripcion": "Configuración de consultas DAX para satisfacción"
            },
            {
                "file_path": "template/report_template.html",
                "file_name": "report_template.html",
                "file_type": "html", 
                "descripcion": "Plantilla HTML para correos"
            },
            {
                "file_path": "template/avatar_logo.png",
                "file_name": "avatar_logo.png",
                "file_type": "image",
                "descripcion": "Logo para correos"
            }
        ]
        
        archivos_cargados = 0
        
        for archivo_info in archivos_config:
            file_path = archivo_info["file_path"]
            
            # Verificar si el archivo existe
            if not os.path.exists(file_path):
                logger.warning(f"⚠️ Archivo no encontrado: {file_path}")
                continue
            
            # Verificar si ya existe en la base de datos
            existente = db.query(FileAsset).filter(FileAsset.file_path == file_path).first()
            if existente:
                logger.info(f"📁 Archivo ya existe: {file_path}")
                continue
            
            # Leer archivo según tipo
            try:
                if archivo_info["file_type"] in ["json", "html", "python", "py"]:
                    # Archivos de texto (incluyendo scripts Python)
                    encoding = 'utf-8'
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        file_content = content
                        
                        # Determinar MIME type según el tipo
                        if archivo_info["file_type"] == "json":
                            mime_type = "application/json"
                        elif archivo_info["file_type"] in ["python", "py"]:
                            mime_type = "text/x-python"
                        else:  # html
                            mime_type = "text/html"
                            
                        file_size = len(content.encode('utf-8'))
                
                elif archivo_info["file_type"] == "image":
                    # Archivos de imagen (convertir a base64)
                    with open(file_path, 'rb') as f:
                        image_data = f.read()
                        file_content = base64.b64encode(image_data).decode('utf-8')
                        mime_type, _ = mimetypes.guess_type(file_path)
                        file_size = len(image_data)
                
                else:
                    logger.warning(f"⚠️ Tipo de archivo no soportado: {archivo_info['file_type']}")
                    continue
                
                # Crear registro en la base de datos
                nuevo_archivo = FileAsset(
                    file_name=archivo_info["file_name"],
                    file_type=archivo_info["file_type"],
                    file_path=file_path,
                    file_content=file_content,
                    file_size=file_size,
                    mime_type=mime_type,
                    created_by=admin_user.user_id
                )
                
                db.add(nuevo_archivo)
                archivos_cargados += 1
                
                logger.info(f"✅ Archivo cargado: {file_path} ({file_size} bytes)")
                
            except Exception as e:
                logger.error(f"❌ Error cargando archivo {file_path}: {str(e)}")
                continue
        
        # Guardar cambios
        db.commit()
        
        logger.info(f"🎉 Se cargaron {archivos_cargados} archivos exitosamente")
        
        # Mostrar resumen
        todos_archivos = db.query(FileAsset).all()
        logger.info(f"📋 Total de archivos en la base de datos: {len(todos_archivos)}")
        for archivo in todos_archivos:
            logger.info(f"   - {archivo.file_path} ({archivo.file_type}, {archivo.file_size} bytes)")
        
        return archivos_cargados > 0
        
    except Exception as e:
        logger.error(f"❌ Error general: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def obtener_archivo(file_path):
    """Obtiene un archivo desde la base de datos"""
    db = SessionLocal()
    try:
        archivo = db.query(FileAsset).filter(FileAsset.file_path == file_path).first()
        if archivo:
            if archivo.file_type == "image":
                # Decodificar base64 para imágenes
                content = base64.b64decode(archivo.file_content.encode('utf-8'))
            else:
                # Texto plano para JSON, HTML y Python
                content = archivo.file_content
            return content, archivo.mime_type
        return None, None
    finally:
        db.close()

def cargar_script_python(script_path: str, descripcion: str = None):
    """
    Función específica para cargar un script Python a la base de datos.
    
    Args:
        script_path (str): Ruta al archivo .py
        descripcion (str): Descripción opcional del script
        
    Returns:
        bool: True si se cargó exitosamente
    """
    db = SessionLocal()
    
    try:
        # Obtener usuario admin
        admin_user = db.query(User).filter(User.email == "admin@system.com").first()
        if not admin_user:
            logger.error("❌ Usuario admin no encontrado")
            return False
        
        # Verificar si el archivo existe
        if not os.path.exists(script_path):
            logger.error(f"❌ Script no encontrado: {script_path}")
            return False
        
        # Verificar si ya existe
        existente = db.query(FileAsset).filter(FileAsset.file_path == script_path).first()
        if existente:
            logger.info(f"📁 Script ya existe: {script_path}")
            return True
        
        # Leer el script Python
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Crear registro
        nuevo_script = FileAsset(
            file_name=os.path.basename(script_path),
            file_type="python",
            file_path=script_path,
            file_content=content,
            file_size=len(content.encode('utf-8')),
            mime_type="text/x-python",
            descripcion=descripcion or f"Script Python: {os.path.basename(script_path)}",
            created_by=admin_user.user_id
        )
        
        db.add(nuevo_script)
        db.commit()
        
        logger.info(f"✅ Script Python cargado: {script_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error cargando script {script_path}: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def listar_scripts_python():
    """
    Lista todos los scripts Python almacenados en la base de datos.
    
    Returns:
        list: Lista de diccionarios con información de los scripts
    """
    db = SessionLocal()
    try:
        scripts = db.query(FileAsset).filter(FileAsset.file_type == "python").all()
        return [
            {
                'file_path': script.file_path,
                'file_name': script.file_name,
                'descripcion': script.descripcion,
                'file_size': script.file_size,
                'created_at': script.created_at
            }
            for script in scripts
        ]
    finally:
        db.close()

if __name__ == "__main__":
    print("📁 CARGADOR DE ARCHIVOS A BASE DE DATOS")
    print("=" * 50)
    
    if cargar_archivos():
        print("\n✅ ¡Archivos cargados exitosamente!")
        print("\n📋 Ahora puedes usar las funciones:")
        print("   - obtener_archivo('queryCenso.json')")
        print("   - obtener_archivo('template/report_template.html')")
        print("   - obtener_archivo('user_scripts/mi_script.py')")
        print("\n🐍 Para scripts Python específicos:")
        print("   - cargar_script_python('user_scripts/reporte_diario_prueba.py')")
        print("   - listar_scripts_python()")
    else:
        print("\n❌ No se pudieron cargar los archivos")
