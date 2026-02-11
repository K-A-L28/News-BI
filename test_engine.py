#!/usr/bin/env python3
"""
Prueba simple del SystemEngine
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controllers.engine import SystemEngine

def test_engine():
    """Prueba básica del SystemEngine"""
    try:
        print("🔍 Creando SystemEngine...")
        engine = SystemEngine()
        
        print("✅ SystemEngine creado exitosamente")
        print(f"📋 Métodos disponibles: {[m for m in dir(engine) if not m.startswith('_')]}")
        
        if hasattr(engine, 'execute_bulletin'):
            print("✅ execute_bulletin encontrado")
        else:
            print("❌ execute_bulletin NO encontrado")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_engine()
