#!/usr/bin/env python3
"""
Verificar los logs guardados en la base de datos
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, ExecutionLog

def verificar_logs_bd():
    """Verificar los logs en la base de datos"""
    db = SessionLocal()
    try:
        print("🔍 Verificando logs en la base de datos...")
        
        # Obtener la última ejecución
        ultimo_log = db.query(ExecutionLog).order_by(ExecutionLog.started_at.desc()).first()
        
        if not ultimo_log:
            print("❌ No hay ejecuciones en la base de datos")
            return
        
        print(f"✅ Última ejecución encontrada:")
        print(f"   ID: {ultimo_log.log_id[:8]}...")
        print(f"   Status: {ultimo_log.status}")
        print(f"   Started: {ultimo_log.started_at}")
        print(f"   Finished: {ultimo_log.finished_at}")
        print(f"   Error: {ultimo_log.error_detail or 'None'}")
        print(f"   Logs length: {len(ultimo_log.execution_logs or '')}")
        
        if ultimo_log.execution_logs:
            print(f"📝 Logs capturados:")
            print(ultimo_log.execution_logs)
        else:
            print("⚠️ No hay logs guardados")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verificar_logs_bd()
