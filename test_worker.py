#!/usr/bin/env python3
"""
Script para probar el worker con el boletín
"""

import os
import sys

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controllers.engine import system_engine
from controllers.worker import ejecutar_tarea_programada
from models.database import SessionLocal, Schedule

def test_worker():
    """Probar el worker con una tarea específica"""
    db = SessionLocal()
    try:
        print("🔍 Probando worker...")
        
        # Buscar una tarea para el boletín
        schedule = db.query(Schedule).filter(
            Schedule.newsletter.has(name="Prototipo San Rafael BI Daily Insigths")
        ).first()
        
        if not schedule:
            print("❌ No hay schedule para el boletín")
            return
        
        print(f"✅ Schedule encontrado: {schedule.schedule_id[:8]}...")
        
        # Probar la ejecución
        result = ejecutar_tarea_programada(schedule, db)
        print(f"📊 Resultado: {result}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_worker()
