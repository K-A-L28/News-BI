#!/usr/bin/env python3
"""
Script de prueba para verificar que la API funcione correctamente
"""

import requests
import json

def test_api():
    """Prueba los endpoints principales de la API"""
    base_url = "http://127.0.0.1:8000"
    
    print("🚀 Probando API del Dashboard...")
    
    # Probar endpoint de stats
    try:
        response = requests.get(f"{base_url}/api/stats")
        print(f"📊 /api/stats - Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Data: {response.json()}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Error en /api/stats: {e}")
    
    # Probar endpoint de próximos
    try:
        response = requests.get(f"{base_url}/api/proximos")
        print(f"📋 /api/proximos - Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Cantidad de boletines: {len(data)}")
            for boletin in data[:3]:  # Mostrar primeros 3
                print(f"   - {boletin.get('boletin', 'N/A')} ({boletin.get('estado', 'N/A')})")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Error en /api/proximos: {e}")
    
    # Probar endpoint de envíos
    try:
        response = requests.get(f"{base_url}/api/envios")
        print(f"📤 /api/envios - Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Cantidad de envíos: {len(data)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Error en /api/envios: {e}")

if __name__ == "__main__":
    test_api()
