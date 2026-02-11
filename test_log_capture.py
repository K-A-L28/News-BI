#!/usr/bin/env python3
"""
Script para probar la captura de logs
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controllers.engine import PythonScriptWrapper
from pathlib import Path

def test_log_capture():
    """Probar la captura de logs del script"""
    script_path = Path("user_scripts/prototipo_san_rafael_bi_daily_insigths.py")
    
    if not script_path.exists():
        print(f"❌ Script no encontrado: {script_path}")
        return
    
    print(f"🔍 Probando captura de logs para: {script_path}")
    
    wrapper = PythonScriptWrapper(script_path)
    
    # Configuración de prueba
    config = {
        'bulletin_name': 'Prototipo San Rafael BI Daily Insigths',
        'manual': True,
        'execution_id': 'test_logs',
        'paths': {
            'user_scripts': 'user_scripts',
            'queries': 'views/queries',
            'templates': 'views/template',
            'images': 'views/template/images'
        },
        'tenant_id': 'test',
        'client_id': 'test',
        'client_secret': 'test',
        'mail_sender': 'test@test.com',
        'destinatarios_cco': ['test@test.com'],
        'gemini_api_key': None,
        'gemini_model': 'gemini-pro'
    }
    
    try:
        result = wrapper.execute(config)
        
        print(f"📊 Resultado:")
        print(f"   Success: {result.get('success')}")
        print(f"   Error: {result.get('error', '')}")
        print(f"   Logs length: {len(result.get('logs', ''))}")
        
        if result.get('logs'):
            print(f"📝 Primeros 500 caracteres de logs:")
            print(result['logs'][:500])
            if len(result['logs']) > 500:
                print("...")
        else:
            print("⚠️ No se capturaron logs")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_log_capture()
