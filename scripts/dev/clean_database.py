#!/usr/bin/env python3
"""
Script para limpiar la base de datos de datos de prueba/preproducción.
Elimina todos los registros pero mantiene la estructura de la base de datos.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, Schedule, Newsletter, ExecutionLog, FileAsset, User, SystemConfig, EmailList, EmailListItem
from sqlalchemy import text

def clean_database():
    """
    Limpia todas las tablas de datos de prueba.
    Mantiene solo las configuraciones del sistema.
    """
    print("🧹 Iniciando limpieza de la base de datos...")
    
    db = SessionLocal()
    
    try:
        # Confirmación de seguridad
        confirm = input("⚠️  ESTÁS A PUNTO DE BORRAR TODOS LOS DATOS DE LA BASE DE DATOS ⚠️\n"
                     "Esta acción no se puede deshacer.\n"
                     "Escribe 'BORRAR TODO' para confirmar: ")
        
        if confirm != "BORRAR TODO":
            print("❌ Operación cancelada.")
            return
        
        print("\n🗑️  Eliminando datos...")
        
        # Eliminar en orden correcto para evitar conflictos de foreign keys
        
        # 1. Logs de ejecución
        logs_count = db.query(ExecutionLog).count()
        db.query(ExecutionLog).delete()
        print(f"   ✅ {logs_count} logs de ejecución eliminados")
        
        # 2. Schedules
        schedules_count = db.query(Schedule).count()
        db.query(Schedule).delete()
        print(f"   ✅ {schedules_count} schedules eliminados")
        
        # 3. Items de listas de correos
        email_items_count = db.query(EmailListItem).count()
        db.query(EmailListItem).delete()
        print(f"   ✅ {email_items_count} items de listas de correos eliminados")
        
        # 4. Listas de correos
        email_lists_count = db.query(EmailList).count()
        db.query(EmailList).delete()
        print(f"   ✅ {email_lists_count} listas de correos eliminadas")
        
        # 5. Newsletters
        newsletters_count = db.query(Newsletter).count()
        db.query(Newsletter).delete()
        print(f"   ✅ {newsletters_count} newsletters eliminados")
        
        # 6. Archivos (FileAssets)
        files_count = db.query(FileAsset).count()
        db.query(FileAsset).delete()
        print(f"   ✅ {files_count} archivos eliminados")
        
        # 7. Usuarios (excepto admin del sistema si existe)
        users_count = db.query(User).filter(User.email != "admin@system.com").count()
        db.query(User).filter(User.email != "admin@system.com").delete()
        print(f"   ✅ {users_count} usuarios eliminados (manteniendo admin del sistema)")
        
        # NO eliminamos SystemConfig para mantener configuraciones importantes
        
        # Resetear auto-incrementos
        print("\n🔄 Reseteando auto-incrementos...")
        db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('schedule', 'newsletter', 'execution_log', 'file_asset', 'email_list', 'email_list_item', 'user')"))
        
        # Confirmar cambios
        db.commit()
        
        print("\n✅ Base de datos limpiada exitosamente!")
        print("📊 Estado final:")
        
        # Mostrar estado final
        print(f"   - Schedules: {db.query(Schedule).count()}")
        print(f"   - Newsletters: {db.query(Newsletter).count()}")
        print(f"   - Execution Logs: {db.query(ExecutionLog).count()}")
        print(f"   - File Assets: {db.query(FileAsset).count()}")
        print(f"   - Email Lists: {db.query(EmailList).count()}")
        print(f"   - Users: {db.query(User).count()}")
        print(f"   - System Config: {db.query(SystemConfig).count()} (mantenidos)")
        
    except Exception as e:
        print(f"❌ Error durante la limpieza: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def show_database_status():
    """Muestra el estado actual de la base de datos"""
    print("📊 Estado actual de la base de datos:")
    
    db = SessionLocal()
    try:
        print(f"   - Schedules: {db.query(Schedule).count()}")
        print(f"   - Newsletters: {db.query(Newsletter).count()}")
        print(f"   - Execution Logs: {db.query(ExecutionLog).count()}")
        print(f"   - File Assets: {db.query(FileAsset).count()}")
        print(f"   - Email Lists: {db.query(EmailList).count()}")
        print(f"   - Email List Items: {db.query(EmailListItem).count()}")
        print(f"   - Users: {db.query(User).count()}")
        print(f"   - System Config: {db.query(SystemConfig).count()}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🗃️  Herramienta de limpieza de base de datos - NewsPilot")
    print("=" * 60)
    
    # Mostrar estado actual
    show_database_status()
    
    print("\n" + "=" * 60)
    print("Opciones:")
    print("1. Limpiar toda la base de datos")
    print("2. Solo mostrar estado actual")
    print("3. Salir")
    
    opcion = input("\nSelecciona una opción (1-3): ")
    
    if opcion == "1":
        clean_database()
    elif opcion == "2":
        show_database_status()
    elif opcion == "3":
        print("👋 Saliendo...")
    else:
        print("❌ Opción no válida.")
