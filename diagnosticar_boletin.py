#!/usr/bin/env python3
"""
Script para diagnosticar el problema del boletín
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, FileAsset, Newsletter
from controllers.engine import SystemEngine

def diagnosticar_boletin():
    """Diagnóstico completo del boletín fallido"""
    db = SessionLocal()
    try:
        print("🔍 DIAGNÓSTICO COMPLETO DEL BOLETÍN")
        print("=" * 60)
        
        # 1. Buscar el boletín específico
        newsletter = db.query(Newsletter).filter(
            Newsletter.name == "Prototipo San Rafael BI Daily Insigths"
        ).first()
        
        if not newsletter:
            print("❌ Boletín no encontrado en la base de datos")
            return
        
        print(f"✅ Boletín encontrado: {newsletter.name}")
        print(f"   ID: {newsletter.newsletter_id}")
        print(f"   Creado: {newsletter.created_at}")
        
        # 2. Mostrar todos los archivos disponibles
        assets = db.query(FileAsset).all()
        
        print(f"\n📁 Todos los archivos en la base de datos ({len(assets)}):")
        for asset in assets:
            print(f"   📄 {asset.file_name} ({asset.file_type})")
            print(f"      Tamaño: {asset.file_size} bytes")
            print(f"      ID: {asset.file_id[:8]}...")
            print(f"      Creado: {asset.created_at}")
            print()
        
        # 3. Intentar ejecutar el boletín con diagnóstico
        print(f"\n🚀 Intentando ejecutar el boletín...")
        engine = SystemEngine()
        
        try:
            result = engine.execute_bulletin(
                bulletin_name=newsletter.name,
                manual=True
            )
            
            print(f"📊 Resultado de ejecución:")
            print(f"   Success: {result.get('success')}")
            print(f"   Error: {result.get('error')}")
            print(f"   Execution ID: {result.get('execution_id')}")
            
        except Exception as e:
            print(f"❌ Error crítico en ejecución: {str(e)}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"❌ Error en diagnóstico: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    diagnosticar_boletin()
