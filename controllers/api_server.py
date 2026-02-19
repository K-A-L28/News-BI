#!/usr/bin/env python3
"""
API Server - Servidor HTTP para el dashboard
Maneja todos los endpoints REST para la interfaz web
"""

import os
import logging
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
import msal
import requests
import secrets
from urllib.parse import urlencode

# Importaciones del sistema
from models.database import SessionLocal, Schedule, Newsletter, ExecutionLog, FileAsset, User, SystemConfig, EmailList, EmailListItem
from sqlalchemy import extract
from controllers.engine import SystemEngine
from utils.encryption import env_encryptor

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

class AuthConfigResponse(BaseModel):
    tenant_id: str
    client_id: str
    redirect_uri: str
    scope: str
    fully_configured: bool

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

class EmailListRequest(BaseModel):
    list_name: str
    description: Optional[str] = None
    max_recipients: Optional[int] = 100  # Límite de correos por lista
    emails: List[str] = []

class EmailListResponse(BaseModel):
    list_id: str
    list_name: str
    description: Optional[str]
    max_recipients: int
    email_count: int
    created_at: str
    created_by: str

# Inicializar el engine del sistema
system_engine = SystemEngine()

def validate_email_domain(email: str, db_session) -> bool:
    """
    Valida que un correo pertenezca a los dominios permitidos globalmente
    
    Args:
        email: Correo electrónico a validar
        db_session: Sesión de base de datos para consultar configuración
    
    Returns:
        True si el dominio está permitido o no hay restricciones, False en caso contrario
    """
    try:
        # Obtener configuración global de dominios permitidos
        from models.database import SystemConfig
        config = db_session.query(SystemConfig).filter(
            SystemConfig.config_key == 'allowed_domains'
        ).first()
        
        allowed_domains = config.config_value if config else ''
        
        if not allowed_domains or not allowed_domains.strip():
            return True  # Sin restricciones de dominio
        
        # Extraer dominio del correo
        try:
            domain = email.split('@')[1].lower().strip()
        except IndexError:
            return False
        
        # Limpiar y procesar dominios permitidos
        allowed = [d.strip().lower() for d in allowed_domains.split(',') if d.strip()]
        
        return domain in allowed
        
    except Exception as e:
        logger.error(f"Error validando dominio del correo {email}: {str(e)}")
        return True  # En caso de error, permitir por defecto

def validate_email_format(email: str) -> bool:
    """
    Valida el formato básico de un correo electrónico
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# --- Funciones de Autenticación Microsoft OAuth2 ---

# Almacenamiento de sesiones (en producción usar Redis o base de datos)
SESSION_STORE = {}

def get_msal_app():
    """Crear instancia de aplicación MSAL"""
    from utils.config import get_settings
    settings = get_settings()
    
    client_secret = settings.get("CLIENT_SECRET")
    
    return msal.ConfidentialClientApplication(
        client_id=settings.get("CLIENT_ID"),
        authority=f"https://login.microsoftonline.com/{settings.get('TENANT_ID')}",
        client_credential=client_secret
    )

def get_auth_config():
    """Obtener configuración de autenticación"""
    from utils.config import get_settings
    settings = get_settings()
    
    tenant_id = settings.get("TENANT_ID")
    client_id = settings.get("CLIENT_ID")
    client_secret = settings.get("CLIENT_SECRET")
    
    fully_configured = bool(tenant_id and client_id and client_secret)
    
    return {
        "tenant_id": tenant_id or "",
        "client_id": client_id or "",
        "redirect_uri": "http://localhost:8001/auth/callback",
        "scope": "openid profile email User.Read",
        "fully_configured": fully_configured
    }

def create_session_token():
    """Crear token de sesión seguro"""
    return secrets.token_urlsafe(32)

def get_user_from_session(token: str):
    """Obtener usuario desde token de sesión"""
    return SESSION_STORE.get(token)

def create_user_session(user_data: dict):
    """Crear sesión de usuario"""
    token = create_session_token()
    SESSION_STORE[token] = {
        "user": user_data,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=8)  # Sesión de 8 horas
    }
    return token

def cleanup_expired_sessions():
    """Limpiar sesiones expiradas"""
    now = datetime.utcnow()
    expired_tokens = [
        token for token, session in SESSION_STORE.items()
        if session.get("expires_at", now) <= now
    ]
    for token in expired_tokens:
        SESSION_STORE.pop(token, None)

def is_session_valid(token: str):
    """Verificar si la sesión es válida"""
    session = SESSION_STORE.get(token)
    if not session:
        return False
    
    expires_at = session.get("expires_at")
    if expires_at and expires_at <= datetime.utcnow():
        SESSION_STORE.pop(token, None)
        return False
    
    return True

# Decorador para proteger endpoints
from functools import wraps

def authenticate_user():
    """Decorador para verificar autenticación en endpoints"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            session_token = request.cookies.get("session_token")
            
            if not session_token or not is_session_valid(session_token):
                raise HTTPException(
                    status_code=401, 
                    detail="Autenticación requerida"
                )
            
            # Agregar usuario al request para uso en el endpoint
            request.state.user = get_user_from_session(session_token).get("user")
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

@app.get("/")
async def serve_root(request: Request):
    """Servir página principal según estado de autenticación"""
    try:
        # Verificar si hay una sesión válida
        session_token = request.cookies.get("session_token")
        
        if session_token and is_session_valid(session_token):
            # Si hay sesión válida, redirigir al dashboard
            return RedirectResponse(url="/dashboard")
        else:
            # Si no hay sesión válida, servir login
            return FileResponse("views/login/index.html")
            
    except Exception as e:
        logger.error(f"Error en endpoint principal: {str(e)}")
        return FileResponse("views/login/index.html")

@app.get("/dashboard")
async def serve_dashboard(request: Request):
    """Servir el dashboard principal (requiere autenticación)"""
    try:
        # Verificar si hay una sesión válida
        session_token = request.cookies.get("session_token")
        
        if not session_token or not is_session_valid(session_token):
            return RedirectResponse(url="/")
        # Si hay sesión válida, servir dashboard
        return FileResponse("views/dashboard/index.html")
        
    except Exception as e:
        logger.error(f"Error en endpoint dashboard: {str(e)}")
        return RedirectResponse(url="/")

@app.get("/api/newsletters")
async def get_newsletters():
    """API para obtener todos los newsletters disponibles"""
    db = SessionLocal()
    try:
        newsletters = db.query(Newsletter).all()
        
        result = []
        for newsletter in newsletters:
            result.append({
                'id': newsletter.newsletter_id,
                'name': newsletter.name,
                'subject_line': newsletter.subject_line,
                'email_list_id': newsletter.email_list_id,
                'created_at': newsletter.created_at.isoformat() if newsletter.created_at else None,
                'updated_at': newsletter.updated_at.isoformat() if newsletter.updated_at else None
            })
        
        return result
    except Exception as e:
        logger.error(f"Error obteniendo newsletters: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo newsletters")
    finally:
        db.close()

@app.get("/api/stats", response_model=StatsResponse)
@authenticate_user()
async def get_stats(request: Request):
    """API para obtener estadísticas generales"""
    db = SessionLocal()
    try:
        # Obtener fecha actual en la zona horaria correcta
        from utils.timezone_config import get_local_datetime, utc_to_local
        now_local = get_local_datetime()
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Convertir a UTC para comparación con la base de datos
        from datetime import timezone
        utc = timezone.utc
        today_start_utc = today_start.astimezone(utc)
        today_end_utc = today_end.astimezone(utc)
        
        # Envíos de hoy (filtrar por rango del día actual, solo con schedule y newsletter asociados)
        envios_hoy = db.query(ExecutionLog).filter(
            ExecutionLog.started_at >= today_start_utc,
            ExecutionLog.started_at <= today_end_utc,
            ExecutionLog.schedule_id.isnot(None)
        ).join(Schedule, ExecutionLog.schedule_id == Schedule.schedule_id).join(
            Newsletter, Schedule.newsletter_id == Newsletter.newsletter_id
        ).count()
        
        # Fallidos de hoy (filtrar por rango del día actual, solo con schedule y newsletter asociados)
        fallidos_hoy = db.query(ExecutionLog).filter(
            ExecutionLog.started_at >= today_start_utc,
            ExecutionLog.started_at <= today_end_utc,
            ExecutionLog.status == 'FAILED',
            ExecutionLog.schedule_id.isnot(None)
        ).join(Schedule, ExecutionLog.schedule_id == Schedule.schedule_id).join(
            Newsletter, Schedule.newsletter_id == Newsletter.newsletter_id
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
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")
    finally:
        db.close()

@app.get("/api/envios", response_model=List[EnvioResponse])
@authenticate_user()
async def get_envios(request: Request):
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
        raise HTTPException(status_code=500, detail="Error obteniendo envíos")
    finally:
        db.close()

@app.get("/api/proximos", response_model=List[ProximoResponse])
@authenticate_user()
async def get_proximos(request: Request):
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
@authenticate_user()
async def toggle_schedule(request: Request, schedule_id: str):
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
@authenticate_user()
async def delete_schedule(request: Request, schedule_id: str):
    """API para eliminar un schedule y su newsletter asociado"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule no encontrado")
        
        # Buscar el newsletter asociado usando newsletter_id
        newsletter = db.query(Newsletter).filter(Newsletter.newsletter_id == schedule.newsletter_id).first()
        if newsletter:
            # Eliminar otros schedules relacionados con este newsletter
            other_schedules = db.query(Schedule).filter(Schedule.newsletter_id == newsletter.newsletter_id).all()
            for other_schedule in other_schedules:
                db.delete(other_schedule)
            
            # Eliminar el newsletter
            db.delete(newsletter)
        else:
            # Si no hay newsletter, eliminar solo el schedule
            db.delete(schedule)
        
        db.commit()
        
        return {
            "success": True,
            "message": "Boletín y sus tareas programadas eliminados exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando schedule {schedule_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error eliminando schedule")
    finally:
        db.close()

@app.post("/api/execute")
@authenticate_user()
async def execute_report(http_request: Request, request: ExecuteRequest):
    """API para ejecutar un reporte manualmente"""
    try:
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
    try:
        # Usar el engine del sistema para procesar la carga
        result = await system_engine.upload_bulletin(request)
        
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('error', 'Error procesando la carga'))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload_bulletin: {str(e)}")
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
        email_lists = db.query(EmailList).all()
        
        # Get current template info
        current_template = None
        if schedule.newsletter and schedule.newsletter.html_template:
            current_template = "Plantilla HTML asignada"
        
        # Get current email list info
        current_email_list = None
        email_list_id = None
        if schedule.newsletter and schedule.newsletter.email_list:
            current_email_list = schedule.newsletter.email_list.list_name
            email_list_id = schedule.newsletter.email_list_id
        elif schedule.recipient_list:
            current_email_list = schedule.recipient_list.list_name
            email_list_id = schedule.list_id
        
        return {
            'id': schedule.schedule_id,
            'newsletter_id': schedule.newsletter_id,
            'newsletter_name': schedule.newsletter.name if schedule.newsletter else 'N/A',
            'email_list_id': email_list_id,
            'send_time': schedule.send_time.strftime('%H:%M'),
            'is_enabled': schedule.is_enabled,
            'timezone': schedule.timezone,
            'current_template': current_template,
            'current_email_list': current_email_list,
            'newsletters': [{'id': n.newsletter_id, 'name': n.name} for n in newsletters],
            'emailLists': [{'list_id': el.list_id, 'list_name': el.list_name, 'email_count': el.email_count} for el in email_lists]
        }
    except Exception as e:
        logger.error(f"Error obteniendo tarea: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo tarea")
    finally:
        db.close()

@app.put("/api/schedule/{schedule_id}")
async def update_schedule(schedule_id: str, request: Request):
    """API para actualizar una tarea programada"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
        # Parse form data
        form_data = await request.form()
        
        # Get basic fields
        newsletter_id = form_data.get('newsletter_id')
        email_list_id = form_data.get('email_list_id')
        send_time = form_data.get('send_time')
        timezone = form_data.get('timezone', 'America/Bogota')
        is_enabled = form_data.get('is_enabled', 'false').lower() == 'true'
        
        # Get uploaded files
        email_template_file = form_data.get('email_template')
        email_csv_file = form_data.get('email_csv')
        
        # Validate required fields
        if not newsletter_id or not send_time:
            raise HTTPException(status_code=400, detail="newsletter_id y send_time son requeridos")
        
        # Parse hour
        try:
            hour, minute = map(int, send_time.split(':'))
            schedule.send_time = time(hour, minute)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de hora inválido. Use HH:MM")
        
        # Update basic schedule fields
        schedule.newsletter_id = newsletter_id
        schedule.is_enabled = is_enabled
        schedule.timezone = timezone
        schedule.updated_at = datetime.utcnow()
        
        # Update email list if provided
        if email_list_id:
            # Update newsletter's email list
            newsletter = db.query(Newsletter).filter(Newsletter.newsletter_id == newsletter_id).first()
            if newsletter:
                newsletter.email_list_id = email_list_id
                newsletter.updated_at = datetime.utcnow()
        
        # Handle email template upload
        if email_template_file and email_template_file.filename:
            try:
                template_content = await email_template_file.read()
                template_content = template_content.decode('utf-8')
                
                # Update newsletter's HTML template
                newsletter = db.query(Newsletter).filter(Newsletter.newsletter_id == newsletter_id).first()
                if newsletter:
                    old_template = newsletter.html_template
                    newsletter.html_template = template_content
                    newsletter.updated_at = datetime.utcnow()
                else:
                    raise HTTPException(status_code=404, detail="Newsletter no encontrado")
                    
            except Exception as e:
                logger.error(f"Error procesando plantilla de correo: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error procesando plantilla: {str(e)}")
        
        # Handle email CSV upload
        if email_csv_file and email_csv_file.filename:
            try:
                csv_content = await email_csv_file.read()
                csv_content = csv_content.decode('utf-8')
                
                # Parse CSV and create/update email list
                import io
                import csv
                
                emails = []
                csv_reader = csv.reader(io.StringIO(csv_content))
                for row in csv_reader:
                    if row and len(row) > 0:
                        email = row[0].strip()
                        if email and '@' in email:
                            emails.append(email)
                
                if emails:
                    # Create new email list
                    import uuid
                    admin_user = system_engine._get_or_create_admin_user(db)
                    new_list_name = f"Lista {newsletter_id} - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    new_list = EmailList(
                        list_name=new_list_name,
                        description=f"Lista de correos importada para newsletter {newsletter_id}",
                        created_by=admin_user.user_id
                    )
                    db.add(new_list)
                    db.flush()  # Get the ID without committing
                    
                    new_list_id = new_list.list_id
                    
                    # Add email items
                    for email in emails:
                        email_item = EmailListItem(
                            list_id=new_list_id,
                            email_address=email
                        )
                        db.add(email_item)
                    
                    # Update newsletter to use new list
                    newsletter = db.query(Newsletter).filter(Newsletter.newsletter_id == newsletter_id).first()
                    if email_list_id:
                        newsletter.email_list_id = new_list_id
                        newsletter.updated_at = datetime.utcnow()
                    
            except Exception as e:
                logger.error(f"Error procesando CSV de correos: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Error procesando CSV: {str(e)}")
        
        db.commit()
        db.refresh(schedule)
        
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

@app.get("/api/test-mode")
async def get_test_mode():
    """API para obtener estado del modo prueba"""
    db = SessionLocal()
    try:
        # Buscar configuración del modo prueba
        config = db.query(SystemConfig).filter(SystemConfig.config_key == 'is_test_mode').first()
        
        if config and config.config_value:
            is_test_mode = config.config_value.lower() == 'true'
        else:
            is_test_mode = False
        
        return {
            'is_test_mode': is_test_mode,
            'test_email': 'k.acevedo@clinicassanrafael.com'
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo modo prueba: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo modo prueba")
    finally:
        db.close()

@app.post("/api/config/allowed-domains")
async def set_allowed_domains(request: Request):
    """Configurar dominios permitidos globalmente"""
    db = SessionLocal()
    try:
        # Obtener datos del request
        data = await request.json()
        allowed_domains = data.get('allowed_domains', '')
        
        admin_user = system_engine._get_or_create_admin_user(db)
        
        # Buscar configuración existente
        existing_config = db.query(SystemConfig).filter(
            SystemConfig.config_key == 'allowed_domains'
        ).first()
        
        if existing_config:
            # Actualizar existente
            existing_config.config_value = allowed_domains.strip()
            existing_config.updated_at = datetime.utcnow()
            existing_config.updated_by = admin_user.user_id
        else:
            # Crear nueva configuración
            new_config = SystemConfig(
                config_key='allowed_domains',
                config_value=allowed_domains.strip(),
                config_type='string',
                description='Dominios permitidos para correos electrónicos (separados por coma)'
            )
            db.add(new_config)
        
        db.commit()
        
        logger.info(f"🌐 Dominios permitidos actualizados: {allowed_domains}")
        
        return {
            'success': True,
            'allowed_domains': allowed_domains.strip(),
            'message': f"Dominios permitidos configurados exitosamente"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error configurando dominios permitidos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error configurando dominios: {str(e)}")
    finally:
        db.close()

@app.get("/api/config/allowed-domains")
async def get_allowed_domains():
    """Obtener dominios permitidos configurados"""
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == 'allowed_domains'
        ).first()
        
        return {
            'allowed_domains': config.config_value if config else '',
            'message': 'Dominios permitidos obtenidos exitosamente'
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo dominios permitidos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo dominios: {str(e)}")
    finally:
        db.close()

@app.post("/api/test-mode")
async def set_test_mode(request: Request):
    """API para activar o desactivar el modo prueba"""
    db = SessionLocal()
    try:
        # Obtener datos del request
        data = await request.json()
        is_test_mode = data.get('is_test_mode', False)
        
        # Obtener usuario admin
        admin_user = system_engine._get_or_create_admin_user(db)
        
        # Buscar configuración existente
        existing_config = db.query(SystemConfig).filter(SystemConfig.config_key == 'is_test_mode').first()
        
        if existing_config:
            # Actualizar existente
            existing_config.config_value = str(is_test_mode).lower()
            existing_config.updated_at = datetime.utcnow()
            existing_config.updated_by = admin_user.user_id
        else:
            # Crear nueva configuración
            new_config = SystemConfig(
                config_key='is_test_mode',
                config_value=str(is_test_mode).lower(),
                config_type='boolean',
                description='Modo prueba para enviar correos solo a dirección de prueba'
            )
            db.add(new_config)
        
        db.commit()
        
        # Logger claro y visible del cambio de modo prueba
        if is_test_mode:
            logger.info("🧪 MODO PRUEBA ACTIVADO - Todos los correos se enviarán a: k.acevedo@clinicassanrafael.com")
        else:
            logger.info("✅ MODO PRUEBA DESACTIVADO - Los correos se enviarán a destinatarios reales")
        
        return {
            'success': True,
            'is_test_mode': is_test_mode,
            'message': f"Modo prueba {'activado' if is_test_mode else 'desactivado'} exitosamente"
        }
        
    except Exception as e:
        logger.error(f"Error guardando modo prueba: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error guardando modo prueba: {str(e)}")
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
            'limiteCorreos': 100,
            'is_test_mode': False
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
            'limiteCorreos': {'type': 'number', 'description': 'Límite de correos por lista'}
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
            else:
                logger.warning(f"Configuración no permitida: {key}")
        
        db.commit()
        
        return {
            'success': True,
            'message': 'Configuración guardada exitosamente'
        }
        
    except Exception as e:
        logger.error(f"Error guardando configuración: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error guardando configuración: {str(e)}")
    finally:
        db.close()

@app.post("/api/retry-execution/{log_id}")
async def retry_execution(log_id: str):
    """API para reintentar una ejecución fallida"""
    db = SessionLocal()
    try:
        # Buscar la ejecución original por log_id
        execution = db.query(ExecutionLog).filter(ExecutionLog.log_id == log_id).first()
        
        if not execution:
            raise HTTPException(status_code=404, detail="Ejecución no encontrada")
        
        # Obtener el schedule asociado
        schedule = db.query(Schedule).filter(Schedule.schedule_id == execution.schedule_id).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Programación no encontrada")
        
        # Obtener el newsletter asociado al schedule
        newsletter = db.query(Newsletter).filter(Newsletter.newsletter_id == schedule.newsletter_id).first()
        
        if not newsletter:
            raise HTTPException(status_code=404, detail="Boletín no encontrado")
        
        # Incrementar contador de reintentos en la ejecución original
        execution.retry_count += 1
        db.commit()
        
        # Crear un nuevo registro de ejecución para el reintento
        new_execution = ExecutionLog(
            schedule_id=schedule.schedule_id,
            status='RUNNING',
            started_at=datetime.utcnow(),
            retry_count=0,
            triggered_by='MANUAL_RETRY'
        )
        db.add(new_execution)
        db.commit()
        db.refresh(new_execution)
        
        # Ejecutar el boletín nuevamente
        result = system_engine.execute_bulletin(newsletter.name, manual=True)
        
        # Actualizar el estado de la nueva ejecución
        if result['success']:
            new_execution.status = 'SUCCESS'
            new_execution.finished_at = datetime.utcnow()
            db.commit()
            
            return {
                'success': True,
                'message': f'Ejecución de "{newsletter.name}" completada exitosamente',
                'execution_id': new_execution.log_id,
                'status': 'success'
            }
        else:
            new_execution.status = 'FAILED'
            new_execution.finished_at = datetime.utcnow()
            new_execution.error_detail = result.get('error', 'Error desconocido')
            db.commit()
            
            return {
                'success': False,
                'message': f'Error en ejecución: {result.get("error", "Error desconocido")}',
                'execution_id': new_execution.log_id,
                'status': 'failed'
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reintentando ejecución {log_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error reintentando ejecución")
    finally:
        db.close()

@app.get("/api/execution-status/{log_id}")
async def get_execution_status(log_id: str):
    """API para obtener el estado de una ejecución"""
    db = SessionLocal()
    try:
        # Buscar la ejecución por log_id
        execution = db.query(ExecutionLog).filter(ExecutionLog.log_id == log_id).first()
        
        if not execution:
            raise HTTPException(status_code=404, detail="Ejecución no encontrada")
        
        # Determinar el estado
        status = 'running'
        message = 'Ejecución en progreso'
        
        if execution.finished_at:
            if execution.status == 'SUCCESS':
                status = 'success'
                message = 'Ejecución completada exitosamente'
            else:
                status = 'failed'
                message = execution.error_detail or 'Ejecución fallida'
        
        return {
            'status': status,
            'message': message,
            'execution_id': execution.log_id,
            'started_at': execution.started_at.isoformat() if execution.started_at else None,
            'finished_at': execution.finished_at.isoformat() if execution.finished_at else None,
            'success': execution.status == 'SUCCESS',
            'error_detail': execution.error_detail
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo estado de ejecución {log_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo estado de ejecución")
    finally:
        db.close()

# Endpoints para gestión de listas de correos
@app.post("/api/email-lists", response_model=dict)
async def create_email_list(request: EmailListRequest):
    """Crear una nueva lista de correos desde CSV"""
    db = SessionLocal()
    try:
        # Validar límite de correos
        if len(request.emails) > (request.max_recipients or 100):
            raise HTTPException(
                status_code=400, 
                detail=f"La lista contiene {len(request.emails)} correos, pero el límite es de {request.max_recipients or 100}"
            )
        
        # Validar correos y filtrar por dominio si es necesario
        valid_emails = []
        invalid_emails = []
        domain_rejected_emails = []
        
        for email in request.emails:
            email = email.strip()
            
            # Validar formato
            if not validate_email_format(email):
                invalid_emails.append(email)
                continue
            
            # Validar dominio usando configuración global
            if not validate_email_domain(email, db):
                domain_rejected_emails.append(email)
                continue
            
            valid_emails.append(email)
        
        # Si hay correos inválidos, retornar error
        if invalid_emails:
            raise HTTPException(
                status_code=400,
                detail=f"Los siguientes correos tienen formato inválido: {', '.join(invalid_emails[:5])}{'...' if len(invalid_emails) > 5 else ''}"
            )
        
        if not valid_emails:
            raise HTTPException(
                status_code=400,
                detail="No hay correos válidos para crear la lista"
            )
        
        # Crear la lista (sin allowed_domains, ahora es global)
        email_list = EmailList(
            list_name=request.list_name,
            description=request.description,
            max_recipients=request.max_recipients or 100,
            email_count=len(valid_emails),
            created_by="system_admin"  # TODO: Obtener del usuario autenticado
        )
        db.add(email_list)
        db.flush()  # Para obtener el ID
        
        # Guardar los correos individuales
        for email in valid_emails:
            email_item = EmailListItem(
                list_id=email_list.list_id,
                email_address=email
            )
            db.add(email_item)
        
        db.commit()
        
        # Construir mensaje con notificación de correos rechazados si hay
        message = f"Lista '{request.list_name}' creada exitosamente con {len(valid_emails)} correos"
        
        if domain_rejected_emails:
            # Obtener dominios permitidos para mostrarlos
            config = db.query(SystemConfig).filter(
                SystemConfig.config_key == 'allowed_domains'
            ).first()
            
            allowed_domains_text = ""
            if config and config.config_value:
                allowed_domains_text = f"\n\nDominios permitidos: {config.config_value}"
            
            message += f". ⚠️ {len(domain_rejected_emails)} rechazados por dominio.{allowed_domains_text}"
            
            # Log detallado para admin
            logger.warning(f"Correos rechazados por dominio: {', '.join(domain_rejected_emails[:10])}{'...' if len(domain_rejected_emails) > 10 else ''}")
        
        return {
            'success': True,
            'message': message,
            'list_id': email_list.list_id,
            'valid_emails': len(valid_emails),
            'domain_rejected': len(domain_rejected_emails),
            'domain_rejected_emails': domain_rejected_emails[:10] if domain_rejected_emails else []  # Mostrar hasta 10 ejemplos
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creando lista de correos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creando lista: {str(e)}")
    finally:
        db.close()

@app.get("/api/email-lists", response_model=List[EmailListResponse])
async def get_email_lists():
    """Obtener todas las listas de correos"""
    db = SessionLocal()
    try:
        lists = db.query(EmailList).all()
        return [
            EmailListResponse(
                list_id=email_list.list_id,
                list_name=email_list.list_name,
                description=email_list.description,
                max_recipients=email_list.max_recipients or 100,
                email_count=email_list.email_count,
                created_at=email_list.created_at.isoformat(),
                created_by=email_list.created_by
            )
            for email_list in lists
        ]
    except Exception as e:
        logger.error(f"Error obteniendo listas de correos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo listas: {str(e)}")
    finally:
        db.close()

@app.delete("/api/email-lists/{list_id}")
async def delete_email_list(list_id: str):
    """Eliminar una lista de correos"""
    db = SessionLocal()
    try:
        email_list = db.query(EmailList).filter(EmailList.list_id == list_id).first()
        if not email_list:
            raise HTTPException(status_code=404, detail="Lista no encontrada")
        
        db.delete(email_list)
        db.commit()
        
        return {
            'success': True,
            'message': f"Lista '{email_list.list_name}' eliminada exitosamente"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error eliminando lista de correos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error eliminando lista: {str(e)}")
    finally:
        db.close()

# Endpoints de Autenticación Microsoft OAuth2

@app.get("/api/auth/config", response_model=AuthConfigResponse)
async def get_auth_config_endpoint():
    """API para obtener configuración de autenticación"""
    try:
        config = get_auth_config()
        return AuthConfigResponse(**config)
    except Exception as e:
        logger.error(f"Error obteniendo configuración de autenticación: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo configuración de autenticación")

@app.get("/auth/login")
async def microsoft_login():
    """Redirigir a Microsoft para autenticación"""
    try:
        config = get_auth_config()
        
        if not config["fully_configured"]:
            raise HTTPException(
                status_code=503, 
                detail="La autenticación no está configurada. Contacta al administrador."
            )
        
        # Construir URL de autorización
        # Intentar primero con el tenant específico, si falla usar el común
        auth_url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/authorize?" + \
                   urlencode({
                       'client_id': config['client_id'],
                       'response_type': 'code',
                       'redirect_uri': config['redirect_uri'],
                       'scope': config['scope'],
                       'response_mode': 'query',
                       'state': create_session_token()  # Token para seguridad CSRF
                   })

        
        return RedirectResponse(url=auth_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en login de Microsoft: {str(e)}")
        raise HTTPException(status_code=500, detail="Error iniciando autenticación")

@app.get("/auth/callback")
async def microsoft_callback(request: Request):
    """Procesar callback de Microsoft OAuth2"""
    try:
        # Obtener parámetros de la URL
        code = request.query_params.get('code')
        error = request.query_params.get('error')
        error_description = request.query_params.get('error_description')
        
        if error:
            logger.error(f"Error de autenticación Microsoft: {error} - {error_description}")
            # Redirigir a login con error
            error_params = urlencode({'error': error or 'authentication_failed'})
            return RedirectResponse(url=f"/?{error_params}")
        
        if not code:
            logger.error("No se recibió código de autorización")
            error_params = urlencode({'error': 'no_code_received'})
            return RedirectResponse(url=f"/?{error_params}")
        
        # Intercambiar código por token de acceso
        msal_app = get_msal_app()
        config = get_auth_config()
        
        # Obtener token de acceso
        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=["User.Read"],
            redirect_uri=config['redirect_uri']
        )
        
        if "error" in result:
            logger.error(f"Error obteniendo token: {result.get('error_description')}")
            error_params = urlencode({'error': 'token_exchange_failed'})
            return RedirectResponse(url=f"/?{error_params}")
        
        # Extraer información del usuario desde id_token (JWT)
        id_token = result.get('id_token')
        if not id_token:
            logger.error("No se recibió id_token")
            error_params = urlencode({'error': 'no_id_token'})
            return RedirectResponse(url=f"/?{error_params}")
        
        # Decodificar el JWT sin verificar firma (para obtener datos básicos)
        import base64
        import json
        
        try:
            # El JWT tiene 3 partes: header.payload.signature
            token_parts = id_token.split('.')
            if len(token_parts) != 3:
                raise ValueError("Token JWT inválido")
            
            # Decodificar el payload (segunda parte)
            payload = token_parts[1]
            # Agregar padding si es necesario
            padding = '=' * (-len(payload) % 4)
            decoded_payload = base64.urlsafe_b64decode(payload + padding)
            user_data = json.loads(decoded_payload)
            
            # Datos del usuario obtenidos (no mostrar datos sensibles)
            logger.info("Usuario autenticado exitosamente")
            
        except Exception as e:
            logger.error(f"Error decodificando id_token: {str(e)}")
            error_params = urlencode({'error': 'token_decode_failed'})
            return RedirectResponse(url=f"/?{error_params}")
        
        # Guardar o actualizar usuario en la base de datos
        db = SessionLocal()
        try:
            from models.database import create_or_update_user
            
            user = create_or_update_user(
                email=user_data.get('preferred_username') or user_data.get('email'),
                full_name=user_data.get('name', 'Usuario'),
                session=db
            )
            
            db.commit()
            
            # Crear sesión de usuario
            session_token = create_user_session({
                'user_id': user.user_id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role.value
            })
            
            # Establecer cookie de sesión
            response = RedirectResponse(url="/dashboard")
            response.set_cookie(
                key="session_token",
                value=session_token,
                max_age=8 * 3600,  # 8 horas
                httponly=True,
                secure=False,  # En producción usar True con HTTPS
                samesite="lax"
            )
            
            # Usuario autenticado (no mostrar datos sensibles)
            logger.info("Sesión de usuario creada exitosamente")
            return response
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error guardando usuario: {str(e)}")
            error_params = urlencode({'error': 'user_save_failed'})
            return RedirectResponse(url=f"/?{error_params}")
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en callback de Microsoft: {str(e)}")
        error_params = urlencode({'error': 'callback_error'})
        return RedirectResponse(url=f"/?{error_params}")

@app.get("/auth/logout")
async def microsoft_logout(request: Request):
    """Cerrar sesión del usuario completamente"""
    try:
        # Obtener token de sesión de la cookie
        session_token = request.cookies.get("session_token")
        
        if session_token:
            # Eliminar sesión
            SESSION_STORE.pop(session_token, None)
            
            # Obtener usuario para logging
            session = get_user_from_session(session_token)
            if session and session.get("user"):
                # Cierre de sesión (no mostrar datos sensibles)
                logger.info("Sesión de usuario cerrada")
        
        # Obtener configuración para logout de Microsoft
        config = get_auth_config()
        
        # Construir URL de logout de Microsoft
        post_logout_redirect_uri = "http://localhost:8001/"  # Redirigir a login después del logout de Microsoft
        logout_url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/logout"
        logout_params = {
            'post_logout_redirect_uri': post_logout_redirect_uri
        }
        
        from urllib.parse import urlencode
        microsoft_logout_url = f"{logout_url}?{urlencode(logout_params)}"
        
        # Primero eliminar cookie local
        response = RedirectResponse(url=microsoft_logout_url)
        response.delete_cookie(
            key="session_token",
            path="/",
            domain=None,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error en logout: {str(e)}")
        # Aun si hay error, redirigir a login
        response = RedirectResponse(url="/")
        
        # Eliminar cookie completamente
        response.delete_cookie(
            key="session_token",
            path="/",
            domain=None,
            samesite="lax"
        )
        
        return response

@app.get("/api/auth/me")
async def get_current_user(request: Request):
    """Obtener información del usuario autenticado"""
    try:
        session_token = request.cookies.get("session_token")
        
        if not session_token or not is_session_valid(session_token):
            raise HTTPException(status_code=401, detail="No autenticado")
        
        session = get_user_from_session(session_token)
        user_data = session.get("user")
        
        if not user_data:
            raise HTTPException(status_code=401, detail="Sesión inválida")
        
        return {
            'user_id': user_data.get('user_id'),
            'email': user_data.get('email'),
            'full_name': user_data.get('full_name'),
            'role': user_data.get('role')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo usuario actual: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo información de usuario")

# Endpoints para gestión de credenciales .env
class CredentialsResponse(BaseModel):
    credentials: Dict[str, str]
    is_encrypted: bool

class CredentialsUpdateRequest(BaseModel):
    credentials: Dict[str, str]

@app.get("/api/credentials/status")
async def get_credentials_status():
    """API para verificar el estado de las credenciales cargadas"""
    try:
        from controllers.engine import reload_env_variables, TENANT_ID, CLIENT_ID, GEMINI_API_KEY
        
        # Forzar recarga para obtener estado actual
        reload_success = reload_env_variables()
        
        return {
            'success': True,
            'env_file_exists': os.path.exists(os.path.join(os.getcwd(), '.env')),
            'reload_success': reload_success,
            'loaded_variables': {
                'TENANT_ID': f"{TENANT_ID[:20]}..." if TENANT_ID else None,
                'CLIENT_ID': f"{CLIENT_ID[:20]}..." if CLIENT_ID else None,
                'CLIENT_SECRET': "****" if os.getenv('CLIENT_SECRET') else None,
                'GEMINI_API_KEYS_COUNT': len(GEMINI_API_KEY) if GEMINI_API_KEY else 0,
                'GEMINI_MODEL': 'gemini-pro (fijo)'  # Valor fijo, no variable de entorno
            },
            'message': 'Variables recargadas exitosamente' if reload_success else 'Error recargando variables'
        }
    except Exception as e:
        logger.error(f"Error obteniendo estado de credenciales: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': 'Error verificando estado de credenciales'
        }

@app.get("/api/credentials", response_model=CredentialsResponse)
async def get_credentials():
    """API para obtener credenciales del archivo .env (desencriptadas en memoria)"""
    try:
        env_path = os.path.join(os.getcwd(), '.env')
        
        # Verificar si existe el archivo
        if not os.path.exists(env_path):
            # Si no existe, crear desde el archivo example
            example_path = os.path.join(os.getcwd(), '.env.example')
            if os.path.exists(example_path):
                with open(example_path, 'r', encoding='utf-8') as f:
                    example_content = f.read()
                env_encryptor.save_encrypted_env(env_path, env_encryptor.parse_env_content(example_content))
                logger.info("📄 Archivo .env creado desde .env.example")
            else:
                raise HTTPException(status_code=404, detail="Archivo .env no encontrado")
        
        # Desencriptar contenido en memoria
        decrypted_content = env_encryptor.decrypt_env_file(env_path)
        if decrypted_content is None:
            raise HTTPException(status_code=500, detail="Error desencriptando archivo .env")
        
        # Parsear a diccionario
        credentials = env_encryptor.parse_env_content(decrypted_content)
        
        # Ocultar valores sensibles para seguridad (mostrar solo primeros caracteres)
        safe_credentials = {}
        sensitive_keys = ['PASSWORD', 'SECRET', 'KEY', 'TOKEN']
        
        for key, value in credentials.items():
            if any(sensitive in key.upper() for sensitive in sensitive_keys) and value:
                # Mostrar solo primeros 4 caracteres + asteriscos
                safe_credentials[key] = value[:4] + '*' * (len(value) - 4) if len(value) > 4 else '*' * len(value)
            else:
                safe_credentials[key] = value
        
        # Verificar si el archivo está encriptado
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        try:
            import base64
            base64.b64decode(content.encode('utf-8'))
            is_encrypted = True
        except Exception:
            is_encrypted = False
        
        return CredentialsResponse(
            credentials=safe_credentials,
            is_encrypted=is_encrypted
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo credenciales: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo credenciales: {str(e)}")

@app.post("/api/credentials")
async def update_credentials(request: CredentialsUpdateRequest):
    """API para actualizar credenciales del archivo .env (encriptar y guardar)"""
    try:
        env_path = os.path.join(os.getcwd(), '.env')
        
        # Guardar credenciales encriptadas
        success = env_encryptor.save_encrypted_env(env_path, request.credentials)
        
        if not success:
            raise HTTPException(status_code=500, detail="Error guardando credenciales")
        
        logger.info("✅ Credenciales actualizadas y encriptadas exitosamente")
        
        return {
            'success': True,
            'message': 'Credenciales guardadas y encriptadas exitosamente'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando credenciales: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error actualizando credenciales: {str(e)}")

@app.get("/api/credentials/raw")
async def get_raw_credentials():
    """API para obtener credenciales completas (sin ocultar) - solo para edición"""
    try:
        env_path = os.path.join(os.getcwd(), '.env')
        
        # Verificar si existe el archivo
        if not os.path.exists(env_path):
            # Si no existe, crear desde el archivo example
            example_path = os.path.join(os.getcwd(), '.env.example')
            if os.path.exists(example_path):
                with open(example_path, 'r', encoding='utf-8') as f:
                    example_content = f.read()
                env_encryptor.save_encrypted_env(env_path, env_encryptor.parse_env_content(example_content))
                logger.info("📄 Archivo .env creado desde .env.example para endpoint raw")
            else:
                raise HTTPException(status_code=404, detail="Archivo .env no encontrado")
        
        # Desencriptar contenido en memoria
        decrypted_content = env_encryptor.decrypt_env_file(env_path)
        if decrypted_content is None:
            raise HTTPException(status_code=500, detail="Error desencriptando archivo .env")
        
        # Parsear a diccionario completo
        credentials = env_encryptor.parse_env_content(decrypted_content)
        
        return {
            'credentials': credentials,
            'raw_content': decrypted_content
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo credenciales completas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo credenciales: {str(e)}")

def start_api_server():
    """Iniciar servidor API"""
    logger.info("🌐 Iniciando servidor API en http://localhost:8001")
    logger.info("📊 Dashboard disponible en: http://localhost:8001")
    
    import uvicorn
    uvicorn.run(app, host="localhost", port=8001, log_level="info", access_log=False)
    # uvicorn.run(app, host="localhost", port=8001, log_level="warning", access_log=False)

if __name__ == "__main__":
    start_api_server()
