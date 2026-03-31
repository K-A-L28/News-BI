"""
version.py
Versionamiento centralizado del aplicativo News BI.

Este archivo contiene la versión actual del sistema.
Se debe actualizar siguiendo Semantic Versioning (SemVer):
- MAJOR: Cambios incompatibles con versiones anteriores
- MINOR: Nuevas funcionalidades compatibles hacia atrás
- PATCH: Correcciones de bugs compatibles hacia atrás

Formato: MAJOR.MINOR.PATCH (ejemplo: 2.0.0)
"""

# Versión actual del sistema
# Siguiendo Semantic Versioning: https://semver.org/lang/es/
VERSION = "2.0.0"

# Información adicional de la versión
VERSION_NAME = "Stable Release"
VERSION_DATE = "2026-03-31"

# Detalles de la versión para API y UI
VERSION_INFO = {
    "version": VERSION,
    "name": VERSION_NAME,
    "release_date": VERSION_DATE,
    "major": 2,
    "minor": 0,
    "patch": 0,
    "stage": "stable",  # stable, beta, alpha, rc
    "changelog_url": None  # URL al changelog si existe
}


def get_version():
    """
    Obtiene la versión actual del sistema como string.
    
    Returns:
        str: Versión en formato MAJOR.MINOR.PATCH
    """
    return VERSION


def get_version_info():
    """
    Obtiene información completa de la versión.
    
    Returns:
        dict: Diccionario con todos los detalles de versión
    """
    return VERSION_INFO.copy()


def get_version_string():
    """
    Obtiene la versión formateada para mostrar en UI.
    
    Returns:
        str: String formateado con nombre y versión
    """
    return f"News BI v{VERSION}"
