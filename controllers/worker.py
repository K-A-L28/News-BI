#!/usr/bin/env python3
"""
Worker - Proceso dedicado a ejecutar envíos programados
Única responsabilidad: revisar y ejecutar boletines según la base de datos
"""

import os
import sys
import logging
import signal
import time as time_module
from datetime import datetime, timedelta, time, timezone
from sqlalchemy import extract

# Agregar directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import SessionLocal, Schedule, ExecutionLog
from controllers.engine import SystemEngine
from utils.timezone_config import get_local_now

# Crear una instancia fresca del engine con todas las mejoras
system_engine = SystemEngine()

# Configuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variable global para shutdown limpio
running = True

def signal_handler(signum, frame):
    """Maneja señales de shutdown"""
    global running
    logger.info("🛑 Recibida señal de shutdown, deteniendo worker...")
    running = False
    sys.exit(0)

# Registrar señales
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def ejecutar_tarea_programada(tarea, db, engine=None):
    """
    Ejecuta una tarea programada usando el engine del sistema.
    
    Args:
        tarea: Schedule object con la tarea a ejecutar
        db: Sesión de base de datos activa
        engine: SystemEngine instance (opcional, usa system_engine global si no se proporciona)
        
    Returns:
        ExecutionLog: Registro de ejecución actualizado
    """
    
    # Usar el engine proporcionado o el global
    system_engine_to_use = engine or system_engine
    
    # 1. Verificar si ya hay una ejecución RUNNING para esta tarea
    running_log = db.query(ExecutionLog).filter(
        ExecutionLog.schedule_id == tarea.schedule_id,
        ExecutionLog.status == 'RUNNING',
        ExecutionLog.finished_at.is_(None)
    ).order_by(ExecutionLog.started_at.desc()).first()
    
    if running_log:
        logger.warning(f"⚠️ Tarea {tarea.schedule_id[:8]}... ya está en ejecución, omitiendo")
        return None
    
    # 2. Crear registro de ejecución
    log = ExecutionLog(schedule_id=tarea.schedule_id, status="RUNNING")
    db.add(log)
    db.commit()
    db.refresh(log)  # Obtener el ID generado
    
    try:
        logger.info(f"🚀 Ejecutando boletín: {tarea.newsletter.name}")
        
        # 3. Usar el engine del sistema para ejecutar
        result = system_engine_to_use.execute_bulletin(
            bulletin_name=tarea.newsletter.name,
            manual=False
        )
        
        if result['success']:
            logger.info(f"✅ Boletín ejecutado exitosamente: {tarea.newsletter.name}")
            log.status = "SUCCESS"
            
            # Guardar los logs del script si existen
            if 'logs' in result and result['logs']:
                log.execution_logs = result['logs']
                logger.info(f"📝 Logs del script guardados ({len(result['logs'])} caracteres)")
            
            db.commit()  # Guardar inmediatamente
            logger.info(f"💾 Estado guardado: SUCCESS para tarea {tarea.schedule_id}")
        else:
            logger.error(f"❌ Error ejecutando boletín: {tarea.newsletter.name}")
            log.status = "FAILED"
            log.error_detail = result.get('error', 'Error desconocido')
            
            # Guardar los logs del script incluso si falló
            if 'logs' in result and result['logs']:
                log.execution_logs = result['logs']
                logger.info(f"📝 Logs del script guardados en ejecución fallida ({len(result['logs'])} caracteres)")
            
            db.commit()  # Guardar inmediatamente
            logger.info(f"💾 Estado guardado: FAILED para tarea {tarea.schedule_id}")
        
    except Exception as e:
        # 4. Manejar errores
        logger.error(f"❌ Error en tarea {tarea.schedule_id}: {str(e)}", exc_info=True)
        log.status = "FAILED"
        log.error_detail = str(e)
        db.commit()  # Guardar inmediatamente
    
    log.finished_at = datetime.now(timezone.utc)
    db.commit()  # Guardar finished_at
    logger.info(f"⏰ finished_at actualizado para tarea {tarea.schedule_id}")
    return log

def marcar_tareas_pasadas_como_failed():
    """Marca como FAILED las tareas que ya pasaron su hora programada y no se ejecutaron"""
    db = SessionLocal()
    try:
        from utils.timezone_config import get_local_now, get_utc_now
        
        current_time_utc = get_utc_now()
        current_time_local = get_local_now()
        current_time_only = current_time_utc.time()
        
        logger.info(f"🕐 Hora actual: {current_time_local.time()}")
        
        # Buscar tareas schedules que ya pasaron su hora de ejecución
        past_schedules = db.query(Schedule).filter(
            Schedule.is_enabled == True,
            Schedule.send_time < current_time_only
        ).all()
        
        logger.info(f"📋 Schedules pasados encontrados: {len(past_schedules)}")
        
        marked_count = 0
        for schedule in past_schedules:
            # Verificar si ya tiene execution log (buscar el más reciente)
            execution_log = db.query(ExecutionLog).filter(
                ExecutionLog.schedule_id == schedule.schedule_id
            ).order_by(ExecutionLog.started_at.desc()).first()
            
            if not execution_log:
                # No tiene execution log, crear uno FAILED
                logger.warning(f"⚠️ Tarea {schedule.schedule_id} ({schedule.newsletter.name}) pasó su hora. Marcando como FAILED...")
                
                # Crear execution log FAILED
                log = ExecutionLog(
                    schedule_id=schedule.schedule_id,
                    status="FAILED",
                    error_detail="Auto-fail: Tarea no ejecutada - hora programada ya pasó",
                    started_at=current_time,
                    finished_at=current_time
                )
                db.add(log)
                marked_count += 1
                
                # Desactivar el schedule para que no vuelva a intentarse
                schedule.is_enabled = False
                logger.info(f"📅 Schedule {schedule.schedule_id} desactivado")
                
            elif execution_log.status == "RUNNING":
                # Está en RUNNING pero ya pasó su hora, marcar como FAILED
                logger.warning(f"⚠️ Tarea {schedule.schedule_id} ({schedule.newsletter.name}) está RUNNING pero pasó su hora. Marcando como FAILED...")
                execution_log.status = "FAILED"
                execution_log.error_detail = "Auto-fail: Tarea RUNNING pero hora programada ya pasó"
                execution_log.finished_at = current_time
                marked_count += 1
                
                # Desactivar el schedule para que no vuelva a intentarse
                schedule.is_enabled = False
                logger.info(f"📅 Schedule {schedule.schedule_id} desactivado")
            else:
                logger.info(f"✅ Schedule {schedule.schedule_id} ya procesado con estado: {execution_log.status}")
        
        if marked_count > 0:
            db.commit()
            logger.info(f"✅ {marked_count} tareas pasadas marcadas como FAILED y desactivadas")
            
    except Exception as e:
        logger.error(f"Error marcando tareas pasadas como FAILED: {str(e)}")
        db.rollback()
    finally:
        db.close()

def limpiar_ejecuciones_atascadas():
    """Marca como FAILED las ejecuciones RUNNING atascadas (más de 2 horas)"""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        stuck = db.query(ExecutionLog).filter(
            ExecutionLog.status == 'RUNNING',
            ExecutionLog.started_at < cutoff
        ).all()

        if stuck:
            logger.warning(f"⚠️ Se encontraron {len(stuck)} ejecuciones RUNNING atascadas. Marcando como FAILED...")
            for log in stuck:
                log.status = 'FAILED'
                log.error_detail = (log.error_detail or '') + ' | Auto-fail: ejecución RUNNING atascada (worker restart)'
                if log.finished_at is None:
                    log.finished_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        logger.error(f"Error en limpieza de RUNNING atascados: {str(e)}")
        db.rollback()
    finally:
        db.close()

def ejecutar_worker():
    """
    Worker dedicado que revisa y ejecuta tareas programadas.
    Única responsabilidad: ejecutar envíos según la base de datos.
    """
    logger.info("🔄 Iniciando worker de boletines...")

    # Limpiar ejecuciones RUNNING antiguas al iniciar
    limpiar_ejecuciones_atascadas()
    
    # Marcar tareas pasadas como FAILED
    marcar_tareas_pasadas_como_failed()
    
    # Cache de última hora verificada para evitar consultas repetitivas
    ultima_verificacion = None
    
    while running:
        ahora = get_local_now()
        hora_actual = ahora.time()
        hora_actual_str = hora_actual.strftime('%H:%M')
        
        # Solo verificar si cambió el minuto (evitar consultas repetitivas)
        if ultima_verificacion != hora_actual_str:
            ultima_verificacion = hora_actual_str
            
            # Verificar tareas pasadas en CADA minuto, no solo en hora
            marcar_tareas_pasadas_como_failed()
            
            db = SessionLocal()
            try:
                logger.info(f"⏰ Hora actual: {hora_actual_str}")
                
                # Buscar programaciones activas para esta hora y minuto exactos
                tareas = db.query(Schedule).filter(
                    Schedule.is_enabled == True,
                    extract('hour', Schedule.send_time) == hora_actual.hour,
                    extract('minute', Schedule.send_time) == hora_actual.minute
                ).all()
                
                # Debug: Mostrar todas las tareas activas
                todas_tareas = db.query(Schedule).filter(Schedule.is_enabled == True).all()
                logger.info(f"📋 Total tareas activas: {len(todas_tareas)}")
                for t in todas_tareas:
                    logger.info(f"   - ID: {t.schedule_id}, Hora: {t.send_time}, Newsletter: {t.newsletter.name}")
                
                if tareas:
                    logger.info(f"📋 Se encontraron {len(tareas)} tareas para ejecutar a las {hora_actual_str}")
                    
                    for tarea in tareas:
                        try:
                            # Verificar si ya hay una ejecución RUNNING para esta tarea
                            running_log = db.query(ExecutionLog).filter(
                                ExecutionLog.schedule_id == tarea.schedule_id,
                                ExecutionLog.status == 'RUNNING',
                                ExecutionLog.finished_at.is_(None)
                            ).order_by(ExecutionLog.started_at.desc()).first()
                            
                            if running_log:
                                logger.warning(f"⚠️ Tarea {tarea.schedule_id[:8]}... ya está en ejecución, omitiendo")
                                continue
                            
                            # Ejecutar la tarea usando la misma sesión
                            ejecutar_tarea_programada(tarea, db)
                            
                        except Exception as e:
                            logger.error(f"❌ Error crítico en tarea programada {tarea.schedule_id}: {str(e)}")
                            db.rollback()
                else:
                    logger.debug(f"⏰ No hay tareas programadas para las {hora_actual_str}")
                    
            except Exception as e:
                logger.error(f"❌ Error en el worker: {str(e)}", exc_info=True)
                db.rollback()
            finally:
                db.close()
        
        # Calcular segundos hasta el próximo minuto
        proximo_minuto = (ahora.replace(second=0, microsecond=0) + 
                          timedelta(minutes=1)).replace(second=0)
        segundos_espera = (proximo_minuto - ahora).total_seconds()
        
        # Esperar inteligente: máximo 60 segundos, pero ajustado al próximo minuto
        if segundos_espera > 0 and segundos_espera <= 60:
            logger.debug(f"⏱️ Esperando {int(segundos_espera)} segundos hasta el próximo minuto...")
            time_module.sleep(segundos_espera)
        else:
            # Fallback de 10 segundos si hay algún problema con el cálculo
            time_module.sleep(10)
    
    logger.info("🛑 Worker detenido correctamente")

if __name__ == "__main__":
    ejecutar_worker()
