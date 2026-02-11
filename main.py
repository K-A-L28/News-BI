#!/usr/bin/env python3
"""
Punto de entrada principal para el sistema de boletines
Inicia tanto el servidor API como el worker en segundo plano
"""

import os
import sys
import signal
import subprocess
import threading
import time
from pathlib import Path

# Agregar directorio raíz al path
sys.path.append(str(Path(__file__).parent))

def start_api_server():
    """Inicia el servidor API"""
    try:
        print("🌐 Iniciando servidor API...")
        process = subprocess.Popen([
            sys.executable, "-m", "controllers.api_server"
        ], cwd=Path(__file__).parent)
        
        # Esperar un momento para que el servidor inicie
        time.sleep(2)
        
        if process.poll() is None:
            print("✅ Servidor API iniciado correctamente en http://127.0.0.1:8000")
            return process
        else:
            print("❌ Error al iniciar el servidor API")
            return None
            
    except Exception as e:
        print(f"❌ Error iniciando servidor API: {e}")
        return None

def start_worker():
    """Inicia el worker en segundo plano"""
    try:
        print("🔄 Iniciando worker de tareas...")
        process = subprocess.Popen([
            sys.executable, "-m", "controllers.worker"
        ], cwd=Path(__file__).parent)
        
        # Esperar un momento para que el worker inicie
        time.sleep(1)
        
        if process.poll() is None:
            print("✅ Worker iniciado correctamente")
            return process
        else:
            print("❌ Error al iniciar el worker")
            return None
            
    except Exception as e:
        print(f"❌ Error iniciando worker: {e}")
        return None

def signal_handler(signum, frame):
    """Manejador de señales para shutdown limpio"""
    print("\n🛑 Recibida señal de shutdown, deteniendo procesos...")
    if 'api_process' in globals() and globals()['api_process']:
        globals()['api_process'].terminate()
    if 'worker_process' in globals() and globals()['worker_process']:
        globals()['worker_process'].terminate()
    sys.exit(0)

def main():
    """Función principal"""
    print("🚀 Iniciando Sistema de Boletines...")
    print("=" * 50)
    
    # Configurar manejador de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Iniciar servidor API
    global api_process, worker_process
    api_process = start_api_server()
    
    if not api_process:
        print("❌ No se pudo iniciar el servidor API. Abortando.")
        return
    
    # Iniciar worker
    worker_process = start_worker()
    
    if not worker_process:
        print("⚠️  No se pudo iniciar el worker, pero el servidor API sigue activo")
    
    print("=" * 50)
    print("🎉 Sistema iniciado!")
    print("📊 Dashboard: http://127.0.0.1:8000")
    print("📝 API Docs: http://127.0.0.1:8000/docs")
    print("🛑 Presiona Ctrl+C para detener todo")
    print("=" * 50)
    
    try:
        # Mantener el proceso principal vivo
        while True:
            # Verificar si los procesos siguen activos
            if api_process and api_process.poll() is not None:
                print("❌ El servidor API se detuvo inesperadamente")
                break
                
            if worker_process and worker_process.poll() is not None:
                print("⚠️  El worker se detuvo, intentando reiniciar...")
                worker_process = start_worker()
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo sistema...")
    finally:
        # Limpiar procesos
        if api_process:
            api_process.terminate()
            api_process.wait()
        if worker_process:
            worker_process.terminate()
            worker_process.wait()
        print("✅ Sistema detenido correctamente")

if __name__ == "__main__":
    main()
