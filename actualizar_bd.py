#!/usr/bin/env python3
"""
Script para agregar el campo execution_logs a la tabla execution_logs
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, engine, Base
from sqlalchemy import text

def actualizar_base_datos():
    """Agregar el campo execution_logs si no existe"""
    db = SessionLocal()
    try:
        # Verificar si la columna ya existe
        result = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM pragma_table_info('execution_logs') 
            WHERE name = 'execution_logs'
        """))
        
        count = result.fetchone()[0]
        
        if count == 0:
            print("🔧 Agregando campo execution_logs a la tabla execution_logs...")
            
            # Agregar la columna
            db.execute(text("""
                ALTER TABLE execution_logs 
                ADD COLUMN execution_logs TEXT
            """))
            
            db.commit()
            print("✅ Campo execution_logs agregado exitosamente")
        else:
            print("✅ El campo execution_logs ya existe")
            
    except Exception as e:
        print(f"❌ Error actualizando la base de datos: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    actualizar_base_datos()
