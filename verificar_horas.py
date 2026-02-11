#!/usr/bin/env python3
"""
Script para verificar y corregir las zonas horarias
"""

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, ExecutionLog

def verificar_horas():
    """Verificar las horas guardadas en la base de datos"""
    db = SessionLocal()
    try:
        print("🔍 Verificando zonas horarias...")
        
        # Obtener la última ejecución
        ultimo = db.query(ExecutionLog).order_by(ExecutionLog.started_at.desc()).first()
        
        if not ultimo:
            print("❌ No hay ejecuciones recientes")
            return
        
        print(f"📅 Última ejecución:")
        print(f"   started_at (BD): {ultimo.started_at}")
        print(f"   finished_at (BD): {ultimo.finished_at}")
        
        # Mostrar hora actual en diferentes zonas
        ahora_utc = datetime.now(timezone.utc)
        ahora_local = datetime.now()
        
        print(f"\n🕐 Hora actual:")
        print(f"   UTC: {ahora_utc}")
        print(f"   Local: {ahora_local}")
        
        # Probar diferentes conversiones
        if ultimo.started_at:
            # Opción 1: UTC-5 (America/Bogota)
            bogota = timezone(timedelta(hours=-5))
            hora_bogota = ultimo.started_at.replace(tzinfo=timezone.utc).astimezone(bogota)
            print(f"   Bogota (UTC-5): {hora_bogota}")
            
            # Opción 2: Sin conversión (asumir que ya es local)
            print(f"   Sin conversión: {ultimo.started_at}")
            
            # Opción 3: UTC+5 (si está al revés)
            reversa = timezone(timedelta(hours=5))
            hora_reversa = ultimo.started_at.replace(tzinfo=timezone.utc).astimezone(reversa)
            print(f"   UTC+5: {hora_reversa}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verificar_horas()
