import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Boolean, ForeignKey, DateTime, Text, Time, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Configuración de SQLite
DATABASE_URL = "sqlite:///boletines_v2.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# --- MODELOS ---

class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, default=generate_uuid)
    external_id = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    full_name = Column(String)
    role = Column(String, default="ADMIN")
    is_active = Column(Boolean, default=True)

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

class Recipient(Base):
    __tablename__ = "recipients"
    recipient_id = Column(String, primary_key=True, default=generate_uuid)
    list_id = Column(ForeignKey("recipient_lists.list_id"))
    email = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RecipientList(Base):
    __tablename__ = "recipient_lists"
    list_id = Column(String, primary_key=True, default=generate_uuid)
    list_name = Column(String)
    allowed_domains = Column(String)
    max_recipients = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(ForeignKey("users.user_id"))
    
    # Relación con recipients
    recipients = relationship("Recipient", backref="recipient_list_obj", cascade="all, delete-orphan")

class Schedule(Base):
    __tablename__ = "schedules"
    schedule_id = Column(String, primary_key=True, default=generate_uuid)
    newsletter_id = Column(ForeignKey("newsletters.newsletter_id"))
    list_id = Column(ForeignKey("recipient_lists.list_id"))
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
    recipient_list = relationship("RecipientList", backref="schedules")

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

# Función para crear la base de datos
def init_db():
    Base.metadata.create_all(bind=engine)
    print("Base de datos v2 creada!")

if __name__ == "__main__":
    init_db()
