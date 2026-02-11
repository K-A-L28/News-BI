"""
file_manager.py
Gestor de archivos para obtener configuraciones y plantillas desde la base de datos
"""

import base64
import json
import logging
from .database import SessionLocal, FileAsset

logger = logging.getLogger(__name__)

def obtener_configuracion_json(file_path):
    """
    Obtiene una configuración JSON desde la base de datos
    
    Args:
        file_path (str): Ruta del archivo (ej: 'queryCenso.json')
        
    Returns:
        dict: Configuración parseada o None si hay error
    """
    db = SessionLocal()
    try:
        archivo = db.query(FileAsset).filter(FileAsset.file_path == file_path).first()
        
        if not archivo:
            logger.error(f"❌ Archivo no encontrado en BD: {file_path}")
            return None
        
        if archivo.file_type != "json":
            logger.error(f"❌ Archivo no es JSON: {file_path}")
            return None
        
        try:
            configuracion = json.loads(archivo.file_content)
            logger.info(f"✅ Configuración cargada: {file_path}")
            return configuracion
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando JSON {file_path}: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error obteniendo archivo {file_path}: {str(e)}")
        return None
    finally:
        db.close()

def obtener_plantilla_html(file_path='template/report_template.html'):
    """
    Obtiene una plantilla HTML desde la base de datos
    
    Args:
        file_path (str): Ruta del archivo HTML
        
    Returns:
        str: Contenido HTML o None si hay error
    """
    db = SessionLocal()
    try:
        archivo = db.query(FileAsset).filter(FileAsset.file_path == file_path).first()
        
        if not archivo:
            logger.error(f"❌ Plantilla no encontrada en BD: {file_path}")
            return None
        
        if archivo.file_type != "html":
            logger.error(f"❌ Archivo no es HTML: {file_path}")
            return None
        
        logger.info(f"✅ Plantilla cargada: {file_path}")
        return archivo.file_content
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo plantilla {file_path}: {str(e)}")
        return None
    finally:
        db.close()

def obtener_imagen_base64(file_path='template/avatar_logo.png'):
    """
    Obtiene una imagen en formato base64 desde la base de datos
    
    Args:
        file_path (str): Ruta del archivo de imagen
        
    Returns:
        str: Imagen en formato base64 o None si hay error
    """
    db = SessionLocal()
    try:
        archivo = db.query(FileAsset).filter(FileAsset.file_path == file_path).first()
        
        if not archivo:
            logger.error(f"❌ Imagen no encontrada en BD: {file_path}")
            return None
        
        if archivo.file_type != "image":
            logger.error(f"❌ Archivo no es imagen: {file_path}")
            return None
        
        logger.info(f"✅ Imagen cargada: {file_path}")
        return archivo.file_content
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo imagen {file_path}: {str(e)}")
        return None
    finally:
        db.close()

def guardar_archivo(file_path, file_content, file_type, file_name=None, mime_type=None):
    """
    Guarda o actualiza un archivo en la base de datos
    
    Args:
        file_path (str): Ruta lógica del archivo
        file_content (str): Contenido del archivo
        file_type (str): Tipo de archivo ('json', 'html', 'image')
        file_name (str): Nombre original (opcional)
        mime_type (str): MIME type (opcional)
        
    Returns:
        bool: True si se guardó correctamente
    """
    db = SessionLocal()
    try:
        # Verificar si ya existe
        archivo_existente = db.query(FileAsset).filter(FileAsset.file_path == file_path).first()
        
        if archivo_existente:
            # Actualizar existente
            archivo_existente.file_content = file_content
            archivo_existente.file_size = len(file_content.encode('utf-8')) if file_type != 'image' else len(file_content)
            if mime_type:
                archivo_existente.mime_type = mime_type
            logger.info(f"✅ Archivo actualizado: {file_path}")
        else:
            # Crear nuevo
            nuevo_archivo = FileAsset(
                file_name=file_name or os.path.basename(file_path),
                file_type=file_type,
                file_path=file_path,
                file_content=file_content,
                file_size=len(file_content.encode('utf-8')) if file_type != 'image' else len(file_content),
                mime_type=mime_type
            )
            db.add(nuevo_archivo)
            logger.info(f"✅ Archivo creado: {file_path}")
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error guardando archivo {file_path}: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def listar_archivos():
    """
    Lista todos los archivos almacenados en la base de datos
    
    Returns:
        list: Lista de archivos con su información
    """
    db = SessionLocal()
    try:
        archivos = db.query(FileAsset).all()
        return [{
            'file_path': a.file_path,
            'file_name': a.file_name,
            'file_type': a.file_type,
            'file_size': a.file_size,
            'mime_type': a.mime_type,
            'created_at': a.created_at
        } for a in archivos]
    finally:
        db.close()
