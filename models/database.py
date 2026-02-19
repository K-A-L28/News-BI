import uuid
from datetime import datetime, time
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Text, Enum as SQLEnum, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from enum import Enum
from utils.timezone_config import get_local_now

# Configuración de SQLite
DATABASE_URL = "sqlite:///boletines_v2.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# --- ENUMS ---

class UserRole(Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    USER = "USER"

# --- MODELOS ---

class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)  # Email de Microsoft
    full_name = Column(String, nullable=False)  # Nombre completo de Microsoft
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    created_by = Column(ForeignKey("users.user_id"), nullable=True)  # Quién creó este usuario
    updated_by = Column(ForeignKey("users.user_id"), nullable=True)  # Quién actualizó este usuario
    last_login = Column(DateTime, nullable=True)  # Último inicio de sesión
    
    # Relación para auditoría (auto-referencia)
    creator = relationship("User", remote_side=[user_id], foreign_keys=[created_by])
    updater = relationship("User", remote_side=[user_id], foreign_keys=[updated_by])

class AuditLog(Base):
    __tablename__ = "audit_logs"
    audit_id = Column(String, primary_key=True, default=generate_uuid)
    entity_type = Column(String, nullable=False) # 'NEWSLETTER', 'SCHEDULE', etc.
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False) # CREATE, UPDATE, DELETE
    performed_by = Column(ForeignKey("users.user_id"), nullable=False)
    performed_at = Column(DateTime, default=datetime.utcnow)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)

class Newsletter(Base):
    __tablename__ = "newsletters"
    newsletter_id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String)
    subject_line = Column(String)
    html_template = Column(Text)
    dax_queries = Column(JSON)
    email_list_id = Column(ForeignKey("email_lists.list_id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(ForeignKey("users.user_id"))
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.now)
    updated_by = Column(ForeignKey("users.user_id"), nullable=True)
    
    # Relación con lista de correos
    email_list = relationship("EmailList", backref="newsletters")


class Schedule(Base):
    __tablename__ = "schedules"
    schedule_id = Column(String, primary_key=True, default=generate_uuid)
    newsletter_id = Column(ForeignKey("newsletters.newsletter_id"))
    list_id = Column(ForeignKey("email_lists.list_id"))
    send_time = Column(Time)
    timezone = Column(String, default="America/Bogota")
    is_enabled = Column(Boolean, default=False)
    is_test_mode = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(ForeignKey("users.user_id"))
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(ForeignKey("users.user_id"), nullable=True)
    
    # Relaciones
    newsletter = relationship("Newsletter", backref="schedules")
    email_list = relationship("EmailList", backref="schedules")

class FileAsset(Base):
    __tablename__ = "file_assets"
    file_id = Column(String, primary_key=True, default=generate_uuid)
    file_name = Column(String, nullable=False)  # Nombre original del archivo
    file_type = Column(String, nullable=False)  # 'json', 'html', 'image', etc.
    file_path = Column(String, nullable=False)  # Ruta lógica (ej: 'queryCenso.json')
    file_content = Column(Text, nullable=False)  # Contenido del archivo (base64 para imágenes)
    file_size = Column(Integer)  # Tamaño en bytes
    mime_type = Column(String)  # MIME type (ej: 'application/json', 'text/html', 'image/png')
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(ForeignKey("users.user_id"))
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    updated_by = Column(ForeignKey("users.user_id"), nullable=True)

class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    log_id = Column(String, primary_key=True, default=generate_uuid)
    schedule_id = Column(ForeignKey("schedules.schedule_id"))
    status = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    error_detail = Column(Text, nullable=True)
    execution_logs = Column(Text, nullable=True)  # Logs detallados del script
    retry_count = Column(Integer, default=0)
    triggered_by = Column(String, default="SYSTEM")

class SystemConfig(Base):
    __tablename__ = "system_config"
    config_id = Column(String, primary_key=True, default=generate_uuid)
    config_key = Column(String, unique=True, nullable=False)  # 'email_remitente', 'pie_pagina', etc.
    config_value = Column(Text, nullable=False)
    config_type = Column(String, default="string")  # 'string', 'number', 'boolean', 'json'
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    updated_by = Column(ForeignKey("users.user_id"), nullable=True)

class EmailList(Base):
    __tablename__ = "email_lists"
    list_id = Column(String, primary_key=True, default=generate_uuid)
    list_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    max_recipients = Column(Integer, default=100)  # Límite de correos por lista
    email_count = Column(Integer, default=0)
    created_by = Column(ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    
    # Relación con correos individuales
    emails = relationship("EmailListItem", back_populates="email_list", cascade="all, delete-orphan")

class EmailListItem(Base):
    __tablename__ = "email_list_items"
    item_id = Column(String, primary_key=True, default=generate_uuid)
    list_id = Column(String, ForeignKey("email_lists.list_id"), nullable=False)
    email_address = Column(String, nullable=False)
    name = Column(String, nullable=True)  # Nombre opcional del contacto
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación con la lista padre
    email_list = relationship("EmailList", back_populates="emails")

# --- FUNCIONES DE UTILIDAD ---

def create_or_update_user(email: str, full_name: str, session, created_by: str = None):
    """
    Crea o actualiza un usuario desde la autenticación de Microsoft.
    Si el usuario no existe, se crea con rol USER por defecto.
    """
    user = session.query(User).filter(User.email == email).first()
    
    if user:
        # Actualizar último login y nombre si ha cambiado
        user.last_login = datetime.utcnow()
        if user.full_name != full_name:
            user.full_name = full_name
            user.updated_by = created_by
            user.updated_at = datetime.utcnow()
    else:
        # Crear nuevo usuario
        user = User(
            email=email,
            full_name=full_name,
            role=UserRole.USER,
            created_by=created_by,
            last_login=datetime.utcnow()
        )
        session.add(user)
    
    return user

def update_user_role(user_id: str, new_role: UserRole, updated_by: str, session):
    """
    Actualiza el rol de un usuario con auditoría.
    """
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise ValueError(f"Usuario con ID {user_id} no encontrado")
    
    old_role = user.role
    user.role = new_role
    user.updated_by = updated_by
    user.updated_at = datetime.utcnow()
    
    # Crear registro de auditoría
    audit_log = AuditLog(
        entity_type="USER",
        entity_id=user_id,
        action="UPDATE_ROLE",
        performed_by=updated_by,
        old_value={"role": old_role.value},
        new_value={"role": new_role.value}
    )
    session.add(audit_log)
    
    return user

def get_users_by_role(role: UserRole, session):
    """
    Obtiene todos los usuarios con un rol específico.
    """
    return session.query(User).filter(User.role == role, User.is_active == True).all()

def can_manage_roles(user_id: str, session):
    """
    Verifica si un usuario puede gestionar roles (solo SUPER_ADMIN).
    """
    user = session.query(User).filter(User.user_id == user_id).first()
    return user and user.role == UserRole.SUPER_ADMIN

def create_audit_log(entity_type: str, entity_id: str, action: str, performed_by: str, session, old_value=None, new_value=None):
    """
    Crea un registro de auditoría para cualquier acción del sistema.
    
    Args:
        entity_type: Tipo de entidad (NEWSLETTER, SCHEDULE, USER, etc.)
        entity_id: ID de la entidad afectada
        action: Acción realizada (CREATE, UPDATE, DELETE, LOGIN, etc.)
        performed_by: ID del usuario que realizó la acción
        session: Sesión de base de datos
        old_value: Valor anterior (JSON serializable)
        new_value: Nuevo valor (JSON serializable)
    """
    audit_log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        performed_by=performed_by,
        performed_at=get_local_now(),  # Usar hora local correcta
        old_value=old_value,
        new_value=new_value
    )
    session.add(audit_log)
    session.commit()  # ¡Importante! Guardar el registro en la base de datos
    return audit_log

# Función para crear la base de datos
def init_db():
    Base.metadata.create_all(bind=engine)
    print("Base de datos v2 creada!")

if __name__ == "__main__":
    init_db()
