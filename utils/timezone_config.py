#!/usr/bin/env python3
"""
Configuración centralizada de zonas horarias
"""

from datetime import datetime, timezone, timedelta

# Configuración de zona horaria local (America/Bogota)
LOCAL_TIMEZONE = timezone(timedelta(hours=-5))

def utc_to_local(utc_datetime):
    """Convertir datetime UTC a hora local"""
    if utc_datetime is None:
        return None
    
    # Si no tiene timezone, asumir que es UTC
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
    
    return utc_datetime.astimezone(LOCAL_TIMEZONE)

def local_to_utc(local_datetime):
    """Convertir datetime local a UTC"""
    if local_datetime is None:
        return None
    
    # Si no tiene timezone, asumir que es local
    if local_datetime.tzinfo is None:
        local_datetime = local_datetime.replace(tzinfo=LOCAL_TIMEZONE)
    
    return local_datetime.astimezone(timezone.utc)

def get_local_now():
    """Obtener hora actual local"""
    return datetime.now(LOCAL_TIMEZONE)

def get_utc_now():
    """Obtener hora actual UTC"""
    return datetime.now(timezone.utc)

def get_local_datetime():
    """Obtener datetime actual local"""
    return datetime.now(LOCAL_TIMEZONE)

def format_local_datetime(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """Formatear datetime a hora local"""
    if dt is None:
        return None
    
    local_dt = utc_to_local(dt)
    return local_dt.strftime(format_str)
