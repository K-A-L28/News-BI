#!/usr/bin/env python3
"""
Verificar estado actual de ejecuciones
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, ExecutionLog, Schedule
from datetime import datetime, timedelta

def verificar_estado():
    """Verificar las últimas ejecuciones"""
    db = SessionLocal()
    try:
        print("🔍 VERIFICANDO ESTADO ACTUAL")
        print("=" * 50)
        
        # Últimas 24 horas
        desde = datetime.now() - timedelta(hours=24)
        
        logs = db.query(ExecutionLog).filter(
            ExecutionLog.started_at >= desde
        ).order_by(ExecutionLog.started_at.desc()).limit(10).all()
        
        print(f"📋 Últimas {len(logs)} ejecuciones:")
        for log in logs:
            print(f"   🕐 {log.started_at}: {log.status}")
            print(f"      📝 Schedule: {log.schedule_id[:8]}...")
            if log.error_detail:
                print(f"      ❌ Error: {log.error_detail}")
            print()
        
        # Schedules activos
        schedules = db.query(Schedule).filter(Schedule.is_enabled == True).all()
        print(f"📅 Schedules habilitados ({len(schedules)}):")
        for schedule in schedules:
            print(f"   ⏰ {schedule.send_time} - {schedule.newsletter.name}")
            print(f"      🆔 {schedule.schedule_id[:8]}...")
            print()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verificar_estado()
