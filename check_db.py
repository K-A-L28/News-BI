#!/usr/bin/env python3
"""
Script para verificar la estructura de la base de datos
"""

import sqlite3
from pathlib import Path

def check_database():
    db_path = Path("boletines_v2.db")
    
    if not db_path.exists():
        print("❌ La base de datos no existe")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Obtener todas las tablas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("📋 Tablas en la base de datos:")
    for table in tables:
        print(f"  - {table[0]}")
    
    print("\n" + "="*50)
    
    # Revisar estructura de la tabla newsletters
    if ('newsletters',) in tables:
        print("\n📄 Estructura de la tabla 'newsletters':")
        cursor.execute("PRAGMA table_info(newsletters);")
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"  - {col[1]}: {col[2]} (nullable: {not col[3]}, default: {col[4]})")
    
    print("\n" + "="*50)
    
    # Revisar estructura de la tabla file_assets
    if ('file_assets',) in tables:
        print("\n📄 Estructura de la tabla 'file_assets':")
        cursor.execute("PRAGMA table_info(file_assets);")
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"  - {col[1]}: {col[2]} (nullable: {not col[3]}, default: {col[4]})")
    
    conn.close()

if __name__ == "__main__":
    check_database()
