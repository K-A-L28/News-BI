#!/usr/bin/env python3
"""
Probar la configuración de timezone
"""

from utils.timezone_config import format_local_datetime, get_local_now, get_utc_now
from datetime import datetime, timezone

def test_timezone():
    print('🕐 Probando configuración de timezone:')
    print(f'   UTC now: {get_utc_now()}')
    print(f'   Local now: {get_local_now()}')
    
    # Probar con un datetime UTC
    test_utc = datetime(2026, 2, 10, 19, 45, tzinfo=timezone.utc)
    print(f'   UTC test: {test_utc}')
    print(f'   Local test: {format_local_datetime(test_utc, "%Y-%m-%d %H:%M")}')

if __name__ == "__main__":
    test_timezone()
