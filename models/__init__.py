"""
Models package - Contiene los modelos de datos y gestión de archivos
"""

from .database import SessionLocal, Schedule, Newsletter, ExecutionLog, User, FileAsset, SystemConfig, EmailList, EmailListItem
from .file_manager import obtener_configuracion_json, obtener_plantilla_html, obtener_imagen_base64, guardar_archivo, listar_archivos
from .cargar_archivos import cargar_archivos

# Alias para mantener compatibilidad
get_json_config = obtener_configuracion_json
get_html_template = obtener_plantilla_html
get_image_base64 = obtener_imagen_base64
save_file_to_db = guardar_archivo

__all__ = [
    'SessionLocal',
    'Schedule', 
    'Newsletter', 
    'ExecutionLog', 
    'User', 
    'FileAsset',
    'SystemConfig',
    'EmailList',
    'EmailListItem',
    'obtener_configuracion_json',
    'obtener_plantilla_html', 
    'obtener_imagen_base64',
    'guardar_archivo',
    'listar_archivos',
    'cargar_archivos',
    # Alias
    'get_json_config',
    'get_html_template', 
    'get_image_base64',
    'save_file_to_db'
]
