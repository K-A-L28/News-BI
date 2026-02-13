#!/usr/bin/env python3
"""
Script para inicializar la base de datos del sistema de boletines
Crea todas las tablas necesarias si no existen
"""

import sys
from pathlib import Path

# Agregar directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from models.database import init_db

def main():
    """Función principal para inicializar la base de datos"""
    try:
        print("🔧 Inicializando base de datos...")
        init_db()
        print("✅ Base de datos inicializada correctamente!")
        print("📋 Tablas creadas:")
        print("   - users")
        print("   - audit_logs") 
        print("   - newsletters")
        print("   - schedules")
        print("   - execution_logs")
        print("   - system_config")
        print("   - email_lists")
        print("   - email_list_items")
        
    except Exception as e:
        print(f"❌ Error inicializando la base de datos: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
