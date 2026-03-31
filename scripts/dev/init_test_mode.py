#!/usr/bin/env python3
"""
Script para inicializar la configuración del modo prueba
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import SessionLocal, SystemConfig, User
from datetime import datetime, timezone

def init_test_mode_config():
    """Inicializa la configuración del modo prueba en la base de datos"""
    db = SessionLocal()
    
    try:
        # Obtener o crear usuario admin
        admin_user = db.query(User).filter(User.email == "admin@system.com").first()
        if not admin_user:
            admin_user = User(
                external_id="system_admin",
                email="admin@system.com",
                nombres="System",
                apellidos="Admin",
                role="ADMIN"
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        
        # Verificar si ya existe la configuración
        existing_config = db.query(SystemConfig).filter(SystemConfig.config_key == 'is_test_mode').first()
        
        if existing_config:
            print("✅ La configuración del modo prueba ya existe")
            print(f"   Estado actual: {existing_config.config_value}")
        else:
            # Crear configuración por defecto (deshabilitado)
            new_config = SystemConfig(
                config_key='is_test_mode',
                config_value='false',
                config_type='boolean',
                description='Modo prueba para enviar correos solo a dirección de prueba'
            )
            db.add(new_config)
            db.commit()
            print("✅ Configuración del modo prueba creada exitosamente")
            print("   Estado inicial: Desactivado (false)")
        
        print("\n📋 Información del modo prueba:")
        print("   - Correo de prueba: k.acevedo@clinicassanrafael.com")
        print("   - Cuando está activado, todos los correos se envían solo a esta dirección")
        print("   - Los boletines se registran como prueba (prefijo 'test_' en execution_id)")
        print("   - No se actualiza la base de datos con datos de producción")
        
    except Exception as e:
        print(f"❌ Error inicializando configuración: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_test_mode_config()
