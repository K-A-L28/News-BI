#!/usr/bin/env python3
"""
Script para revisar los FileAssets en la base de datos
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, FileAsset

def revisar_file_assets():
    """Revisa qué archivos hay en la tabla FileAsset"""
    db = SessionLocal()
    try:
        print("🔍 Revisando FileAssets en la base de datos...")
        print("=" * 60)
        
        # Buscar todos los FileAssets
        assets = db.query(FileAsset).all()
        
        print(f"\n📁 Total FileAssets encontrados: {len(assets)}")
        print("-" * 60)
        
        # Agrupar por tipo de archivo
        tipos = {}
        for asset in assets:
            tipo = asset.file_type
            if tipo not in tipos:
                tipos[tipo] = []
            tipos[tipo].append(asset)
        
        for tipo, files in tipos.items():
            print(f"\n📂 {tipo.upper()} ({len(files)} archivos):")
            for file in files:
                print(f"   📄 {file.file_name}")
                print(f"      Creado: {file.created_at}")
                print(f"      Tamaño: {file.file_size} bytes")
                print(f"      Content preview: {file.file_content[:100]}...")
                print()
        
        # Buscar archivos específicos que menciona el usuario
        print(f"\n🎯 Búsqueda de archivos específicos:")
        print("-" * 60)
        
        busquedas = [
            "report_template.html",
            "report.html", 
            "avatar.png",
            "avatar_logo.png",
            "query.json",
            "queryCenso.json",
            "queryCensoFact.json",
            "queriesSatisfaccion.json"
        ]
        
        for busqueda in busquedas:
            encontrados = [asset for asset in assets if busqueda.lower() in asset.file_name.lower()]
            print(f"   🔍 '{busqueda}': {'✅ ENCONTRADO' if encontrados else '❌ NO ENCONTRADO'}")
            if encontrados:
                for asset in encontrados:
                    print(f"      → {asset.file_name} (ID: {asset.file_id[:8]}...)")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    revisar_file_assets()
