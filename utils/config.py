"""
config.py
Punto centralizado de configuración y secretos.
Hoy usa .env, mañana usará Key Vault.
"""

import os
from dotenv import load_dotenv

# Cargamos el .env por ahora
load_dotenv()

def get_settings():
    """
    Esta función es el único punto de contacto con los secretos.
    Hoy usa .env, mañana usará Key Vault.
    
    Returns:
        dict: Diccionario con todas las configuraciones y secretos
    """
    return {
        # Autenticación Microsoft Graph
        "TENANT_ID": os.getenv("TENANT_ID"),
        "CLIENT_ID": os.getenv("CLIENT_ID"),
        "CLIENT_SECRET": os.getenv("CLIENT_SECRET"),
        
        # URLs de Power Automate
        "PA_URL_CENSO": os.getenv("URL_CENSO"),
        "PA_URL_CENSO_FACTURACION": os.getenv("URL_CENSO_FACTURACION"),
        "PA_URL_SATISFACCION": os.getenv("URL_SATISFACCION"),
        
        # Report IDs de Power BI
        "REPORT_ID": os.getenv("REPORT_ID"),
        "REPORT_ID_2": os.getenv("REPORT_ID_2"),
        
        # Configuración Gemini AI
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-pro"),
        
        # Configuración de correo
        "MAIL_SENDER": os.getenv("MAIL_SENDER"),
        "MAIL_BCC": os.getenv("MAIL_BCC"),
    }

def get_env_var(key, default=None):
    """
    Función auxiliar para obtener variables de entorno con valor por defecto.
    
    Args:
        key (str): Nombre de la variable de entorno
        default: Valor por defecto si no existe
        
    Returns:
        Valor de la variable de entorno o el default
    """
    return os.getenv(key, default)
