#!/usr/bin/env python3
"""
Script para probar el worker con el engine actualizado
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Forzar recarga del módulo engine
import importlib
import controllers.engine
importlib.reload(controllers.engine)

from controllers.engine import SystemEngine
from controllers.worker import ejecutar_tarea_programada
from models.database import SessionLocal, Schedule

def test_worker_actualizado():
    """Probar el worker con el engine actualizado"""
    db = SessionLocal()
    try:
        print("🔍 Probando worker con engine actualizado...")
        
        # Crear una nueva instancia del engine con las mejoras
        system_engine_actualizado = SystemEngine()
        
        # Buscar una tarea para el boletín
        schedule = db.query(Schedule).filter(
            Schedule.newsletter.has(name="Prototipo San Rafael BI Daily Insigths")
        ).first()
        
        if not schedule:
            print("❌ No hay schedule para el boletín")
            return
        
        print(f"✅ Schedule encontrado: {schedule.schedule_id[:8]}...")
        
        # Probar la ejecución con el engine actualizado
        result = ejecutar_tarea_programada(schedule, db, system_engine_actualizado)
        print(f"📊 Resultado: {result}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_worker_actualizado()
