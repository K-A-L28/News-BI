#!/usr/bin/env python3
"""
API Server - Servidor HTTP para el dashboard
Maneja todos los endpoints REST para la interfaz web
"""

import os
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Importaciones del sistema
from models.database import SessionLocal, Schedule, Newsletter, ExecutionLog, RecipientList, FileAsset, User, SystemConfig
from sqlalchemy import extract
from controllers.engine import SystemEngine

# Configuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(title="Dashboard Boletines API", version="1.0.0")

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="views/dashboard"), name="static")

# Modelos Pydantic
class StatsResponse(BaseModel):
    enviosHoy: int
    fallidos: int
    proximos: int
    tareasActivas: int

class EnvioResponse(BaseModel):
    id: str
    fecha: str
    boletin: str
    status: str
    duracion: str
    error: Optional[str] = None
    logs: Optional[str] = None

class ProximoResponse(BaseModel):
    id: str
    boletin: str
    hora: str
    estado: str
    ultimaEjecucion: str

class ExecuteRequest(BaseModel):
    boletin: str

class ScheduleUpdateRequest(BaseModel):
    newsletter_id: str
    send_time: str
    is_enabled: bool
    timezone: str = "America/Bogota"

# Inicializar el engine del sistema
system_engine = SystemEngine()

@app.get("/")
async def serve_dashboard():
    """Servir el dashboard principal"""
    return FileResponse("views/dashboard/index.html")

@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """API para obtener estadísticas generales"""
    db = SessionLocal()
    try:
        today = datetime.now().date()
        
        # Envíos de hoy
        envios_hoy = db.query(ExecutionLog).filter(
            ExecutionLog.started_at >= today
        ).count()
        
        # Fallidos de hoy
        fallidos_hoy = db.query(ExecutionLog).filter(
            ExecutionLog.started_at >= today,
            ExecutionLog.status == 'FAILED'
        ).count()
        
        # Próximos envíos hoy
        now = datetime.now()
        proximos_hoy = db.query(Schedule).filter(
            Schedule.is_enabled == True,
            Schedule.send_time > now.time()
        ).count()
        
        # Tareas activas totales
        tareas_activas = db.query(Schedule).filter(
            Schedule.is_enabled == True
        ).count()
        
        return StatsResponse(
            enviosHoy=envios_hoy,
            fallidos=fallidos_hoy,
            proximos=proximos_hoy,
            tareasActivas=tareas_activas
        )
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")
    finally:
        db.close()

@app.get("/api/envios", response_model=List[EnvioResponse])
async def get_envios():
    """API para obtener envíos recientes"""
    db = SessionLocal()
    try:
        envios = (
            db.query(ExecutionLog, Schedule, Newsletter)
            .join(Schedule, ExecutionLog.schedule_id == Schedule.schedule_id)
            .join(Newsletter, Schedule.newsletter_id == Newsletter.newsletter_id)
            .order_by(ExecutionLog.started_at.desc())
            .limit(20)
            .all()
        )
        
        result = []
        for envio, schedule, newsletter in envios:
            duration = "N/A"
            if envio.finished_at and envio.started_at:
                duration = envio.finished_at - envio.started_at
                duration = f"{duration.seconds // 60}m {duration.seconds % 60}s"
            
            # Convertir hora UTC a hora local para mostrar
            from utils.timezone_config import format_local_datetime
            
            result.append(EnvioResponse(
                id=envio.log_id,
                fecha=format_local_datetime(envio.started_at, '%Y-%m-%d %H:%M') if envio.started_at else 'N/A',
                boletin=newsletter.name if newsletter else 'N/A',
                status=envio.status.lower(),
                duracion=duration,
                error=envio.error_detail,
                logs=envio.execution_logs
            ))
        
        return result
    except Exception as e:
        logger.error(f"Error obteniendo envíos recientes: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo envíos")
    finally:
        db.close()

@app.get("/api/proximos", response_model=List[ProximoResponse])
async def get_proximos():
    """API para obtener próximos envíos programados"""
    db = SessionLocal()
    try:
        schedules = db.query(Schedule).order_by(Schedule.send_time).all()
        
        result = []
        for schedule in schedules:
            last_execution = db.query(ExecutionLog).filter(
                ExecutionLog.schedule_id == schedule.schedule_id
            ).order_by(ExecutionLog.started_at.desc()).first()
            
            # Convertir hora UTC a hora local para última ejecución
            from utils.timezone_config import format_local_datetime
            
            result.append(ProximoResponse(
                id=schedule.schedule_id,
                boletin=schedule.newsletter.name if schedule.newsletter else 'N/A',
                hora=schedule.send_time.strftime('%H:%M'),
                estado='enabled' if schedule.is_enabled else 'disabled',
                ultimaEjecucion=format_local_datetime(last_execution.started_at, '%Y-%m-%d %H:%M') if last_execution and last_execution.started_at else 'Nunca'
            ))
        
        return result
    except Exception as e:
        logger.error(f"Error obteniendo tareas programadas: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo tareas programadas")
    finally:
        db.close()

@app.post("/api/toggle-schedule/{schedule_id}")
async def toggle_schedule(schedule_id: str):
    """API para alternar el estado de un schedule"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule no encontrado")
        
        # Alternar el estado
        schedule.is_enabled = not schedule.is_enabled
        db.commit()
        
        return {
            "success": True,
            "enabled": schedule.is_enabled,
            "message": f"Schedule {'habilitado' if schedule.is_enabled else 'deshabilitado'} exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error alternando schedule {schedule_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error alternando schedule")
    finally:
        db.close()

@app.post("/api/delete-schedule/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """API para eliminar un schedule"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule no encontrado")
        
        db.delete(schedule)
        db.commit()
        
        return {
            "success": True,
            "message": "Schedule eliminado exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando schedule {schedule_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error eliminando schedule")
    finally:
        db.close()

@app.post("/api/execute")
async def execute_report(request: ExecuteRequest):
    """API para ejecutar un reporte manualmente"""
    try:
        logger.info(f"🚀 Ejecutando reporte manual: {request.boletin}")
        
        # Usar el engine del sistema
        result = system_engine.execute_bulletin(request.boletin, manual=True)
        
        if result['success']:
            return {
                'success': True,
                'message': 'Reporte ejecutado exitosamente',
                'execution_id': result.get('execution_id'),
                'bulletin_name': request.boletin
            }
        else:
            return {
                'success': False,
                'message': result.get('error', 'Error desconocido'),
                'execution_id': result.get('execution_id'),
                'bulletin_name': request.boletin
            }
            
    except Exception as e:
        logger.error(f"❌ Error en ejecución manual: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'Error: {str(e)}',
            'execution_id': f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }

@app.post("/api/upload-bulletin")
async def upload_bulletin(request: Request):
    """API para cargar un nuevo boletín con sus archivos"""
    logger.info(f"🔍 API Server - Received request to /api/upload-bulletin")
    logger.info(f"🔍 API Server - Request method: {request.method}")
    logger.info(f"🔍 API Server - Request headers: {dict(request.headers)}")
    
    try:
        # Usar el engine del sistema para procesar la carga
        logger.info(f"🔍 API Server - Calling system_engine.upload_bulletin...")
        result = await system_engine.upload_bulletin(request)
        logger.info(f"🔍 API Server - upload_bulletin completed: {result}")
        
        if result['success']:
            return result
        else:
            logger.error(f"❌ API Server - Upload failed: {result.get('error')}")
            raise HTTPException(status_code=400, detail=result.get('error', 'Error cargando boletín'))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API Server - Error procesando carga: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error procesando la carga: {str(e)}")

@app.get("/api/upload-bulletin")
async def upload_bulletin_get():
    """Endpoint GET para upload-bulletin - devuelve error informativo"""
    raise HTTPException(status_code=405, detail="Método no permitido. Use POST para cargar boletines.")

@app.get("/api/schedule/{schedule_id}")
async def get_schedule(schedule_id: str):
    """API para obtener detalles de una tarea programada"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
        newsletters = db.query(Newsletter).all()
        
        return {
            'id': schedule.schedule_id,
            'newsletter_id': schedule.newsletter_id,
            'newsletter_name': schedule.newsletter.name if schedule.newsletter else 'N/A',
            'send_time': schedule.send_time.strftime('%H:%M'),
            'is_enabled': schedule.is_enabled,
            'timezone': schedule.timezone,
            'newsletters': [{'id': n.newsletter_id, 'name': n.name} for n in newsletters]
        }
    except Exception as e:
        logger.error(f"Error obteniendo tarea: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo tarea")
    finally:
        db.close()

@app.put("/api/schedule/{schedule_id}")
async def update_schedule(schedule_id: str, request: ScheduleUpdateRequest):
    """API para actualizar una tarea programada"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
        # Parsear hora
        try:
            hour, minute = map(int, request.send_time.split(':'))
            schedule.send_time = time(hour, minute)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de hora inválido. Use HH:MM")
        
        schedule.newsletter_id = request.newsletter_id
        schedule.is_enabled = request.is_enabled
        schedule.timezone = request.timezone
        schedule.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(schedule)
        
        logger.info(f"✅ Tarea {schedule_id} actualizada correctamente")
        return {
            'success': True,
            'message': 'Tarea actualizada exitosamente'
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando tarea: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error actualizando tarea")
    finally:
        db.close()

@app.get("/api/settings")
async def get_settings():
    """API para obtener configuración del sistema"""
    db = SessionLocal()
    try:
        # Obtener todas las configuraciones
        configs = db.query(SystemConfig).all()
        
        # Convertir a diccionario
        settings = {}
        for config in configs:
            # Convertir valor según tipo
            if config.config_type == 'number':
                settings[config.config_key] = int(config.config_value)
            elif config.config_type == 'boolean':
                settings[config.config_key] = config.config_value.lower() == 'true'
            else:
                settings[config.config_key] = config.config_value
        
        # Valores por defecto si no existen
        default_values = {
            'emailRemitente': os.getenv('MAIL_SENDER', 'noreply@empresa.com'),
            'piePagina': '© 2026 Clínicas San Rafael. Todos los derechos reservados.',
            'logsRetencion': 30,
            'guardarBackups': True,
            'logsDetallados': True
        }
        
        # Combinar con valores por defecto
        for key, default_value in default_values.items():
            if key not in settings:
                settings[key] = default_value
        
        return settings
        
    except Exception as e:
        logger.error(f"Error obteniendo configuración: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo configuración")
    finally:
        db.close()

@app.post("/api/settings")
async def save_settings(request: Request):
    """API para guardar configuración del sistema"""
    db = SessionLocal()
    try:
        # Obtener datos del request
        data = await request.json()
        
        # Obtener usuario admin
        admin_user = system_engine._get_or_create_admin_user(db)
        
        # Configuraciones permitidas
        allowed_configs = {
            'emailRemitente': {'type': 'string', 'description': 'Email remitente de boletines'},
            'piePagina': {'type': 'string', 'description': 'Pie de página de boletines'},
            'logsRetencion': {'type': 'number', 'description': 'Días de retención de logs'},
            'guardarBackups': {'type': 'boolean', 'description': 'Guardar respaldos automáticos'},
            'logsDetallados': {'type': 'boolean', 'description': 'Generar logs detallados'}
        }
        
        # Guardar cada configuración
        for key, value in data.items():
            if key in allowed_configs:
                config_info = allowed_configs[key]
                
                # Convertir valor a string para guardar en BD
                if config_info['type'] == 'boolean':
                    str_value = str(value).lower()
                else:
                    str_value = str(value)
                
                # Buscar configuración existente
                existing_config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
                
                if existing_config:
                    # Actualizar existente
                    existing_config.config_value = str_value
                    existing_config.updated_at = datetime.utcnow()
                    existing_config.updated_by = admin_user.user_id
                else:
                    # Crear nueva
                    new_config = SystemConfig(
                        config_key=key,
                        config_value=str_value,
                        config_type=config_info['type'],
                        description=config_info['description'],
                        created_by=admin_user.user_id
                    )
                    db.add(new_config)
        
        db.commit()
        
        return {
            'success': True,
            'message': 'Configuración guardada exitosamente'
        }
        
    except Exception as e:
        logger.error(f"Error guardando configuración: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error guardando configuración")
    finally:
        db.close()

def start_api_server():
    """Iniciar servidor API"""
    # logger.info("🌐 Iniciando servidor API en http://127.0.0.1:8000")
    # logger.info("📊 Dashboard disponible en: http://127.0.0.1:8000")
    
    # import uvicorn
    # uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

    logger.info("🌐 Iniciando servidor API en http://127.0.0.1:8001")
    logger.info("📊 Dashboard disponible en: http://127.0.0.1:8001")
    
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")

if __name__ == "__main__":
    start_api_server()
