"""
Script interactivo para gestionar datos de la base de datos SQLite.
Permite listar tablas, ver registros enumerados y eliminar datos.
"""

import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

# Configuración de la base de datos (misma que en database.py)
DATABASE_URL = "sqlite:///boletines_v2.db"

# Crear engine y session
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Definición de tablas y sus columnas de display
TABLES_CONFIG = {
    "users": {
        "display": ["user_id", "email", "nombres", "apellidos", "role", "is_active"],
        "description": "Usuarios del sistema"
    },
    "newsletters": {
        "display": ["newsletter_id", "name", "subject_line", "created_at"],
        "description": "Boletines/Newsletters creados"
    },
    "schedules": {
        "display": ["schedule_id", "newsletter_id", "send_time", "is_enabled", "is_test_mode"],
        "description": "Programaciones de envío"
    },
    "email_lists": {
        "display": ["list_id", "list_name", "description", "email_count", "created_at"],
        "description": "Listas de correos"
    },
    "email_list_items": {
        "display": ["item_id", "list_id", "email_address", "name"],
        "description": "Correos individuales en listas"
    },
    "audit_logs": {
        "display": ["audit_id", "entity_type", "entity_id", "action", "performed_at"],
        "description": "Registros de auditoría"
    },
    "file_assets": {
        "display": ["file_id", "file_name", "file_type", "mime_type", "created_at"],
        "description": "Archivos guardados"
    },
    "execution_logs": {
        "display": ["log_id", "schedule_id", "status", "started_at", "finished_at"],
        "description": "Logs de ejecución de tareas"
    },
    "system_config": {
        "display": ["config_id", "config_key", "config_value", "config_type"],
        "description": "Configuración del sistema"
    },
    "empresas": {
        "display": ["empresa_id", "nombre", "dominio_correo", "activa"],
        "description": "Empresas registradas"
    },
    "sedes": {
        "display": ["sede_id", "empresa_id", "nombre", "ciudad", "activa"],
        "description": "Sedes de empresas"
    },
    "areas": {
        "display": ["area_id", "sede_id", "nombre", "descripcion", "activa"],
        "description": "Áreas/Departamentos"
    }
}


def get_all_tables():
    """Obtiene todas las tablas de la base de datos."""
    inspector = inspect(engine)
    return inspector.get_table_names()


def get_table_data(table_name, limit=50):
    """Obtiene los datos de una tabla específica."""
    session = SessionLocal()
    try:
        # Obtener las columnas configuradas o todas si no está en config
        columns = TABLES_CONFIG.get(table_name, {}).get("display", ["*"])
        columns_str = ", ".join(columns) if columns[0] != "*" else "*"
        
        query = text(f"SELECT {columns_str} FROM {table_name} LIMIT :limit")
        result = session.execute(query, {"limit": limit})
        rows = result.fetchall()
        
        # Obtener nombres de columnas
        if columns[0] == "*":
            column_names = result.keys()
        else:
            column_names = columns
            
        return column_names, rows
    except SQLAlchemyError as e:
        print(f"❌ Error al consultar tabla {table_name}: {e}")
        return None, None
    finally:
        session.close()


def display_table_data(table_name, limit=50):
    """Muestra los datos de una tabla numerados."""
    column_names, rows = get_table_data(table_name, limit)
    
    if rows is None:
        return None, []
    
    if not rows:
        print(f"\n📭 La tabla '{table_name}' está vacía.\n")
        return column_names, []
    
    config = TABLES_CONFIG.get(table_name, {})
    description = config.get("description", "")
    
    print(f"\n{'='*80}")
    print(f"📊 TABLA: {table_name.upper()}")
    if description:
        print(f"📝 {description}")
    print(f"{'='*80}")
    print(f"Total registros mostrados: {len(rows)} (límite: {limit})\n")
    
    # Mostrar encabezados
    print(f"{'N°':<4} | ", end="")
    for col in column_names:
        print(f"{str(col):<25}"[:25], end=" | ")
    print()
    print("-" * 80)
    
    # Mostrar datos numerados
    for idx, row in enumerate(rows, 1):
        print(f"{idx:<4} | ", end="")
        for i, value in enumerate(row):
            # Truncar valores largos
            str_val = str(value) if value is not None else "NULL"
            if len(str_val) > 25:
                str_val = str_val[:22] + "..."
            print(f"{str_val:<25}", end=" | ")
        print()
    
    print("="*80)
    return column_names, rows


def get_row_by_number(table_name, row_number, limit=50):
    """Obtiene una fila específica por su número (1-based)."""
    column_names, rows = get_table_data(table_name, limit)
    
    if not rows or row_number < 1 or row_number > len(rows):
        return None
    
    return rows[row_number - 1]


def delete_row(table_name, primary_key_column, primary_key_value, display_row_num=None):
    """Elimina un registro de la tabla por su clave primaria."""
    session = SessionLocal()
    try:
        query = text(f"DELETE FROM {table_name} WHERE {primary_key_column} = :pk")
        result = session.execute(query, {"pk": primary_key_value})
        session.commit()
        
        if result.rowcount > 0:
            display_num = f"(fila #{display_row_num})" if display_row_num else ""
            print(f"✅ Registro {display_num} con {primary_key_column}='{primary_key_value}' eliminado correctamente.")
            return True
        else:
            print(f"⚠️ No se encontró el registro con {primary_key_column}='{primary_key_value}'")
            return False
            
    except IntegrityError as e:
        session.rollback()
        print(f"❌ No se puede eliminar: El registro tiene dependencias en otras tablas.")
        print(f"   Error: {e}")
        return False
    except SQLAlchemyError as e:
        session.rollback()
        print(f"❌ Error al eliminar registro: {e}")
        return False
    finally:
        session.close()


def get_primary_key_column(table_name):
    """Obtiene el nombre de la columna clave primaria."""
    inspector = inspect(engine)
    pk_columns = inspector.get_pk_constraint(table_name)
    if pk_columns and pk_columns['constrained_columns']:
        return pk_columns['constrained_columns'][0]
    return None


def show_main_menu():
    """Muestra el menú principal."""
    print("\n" + "="*80)
    print("🗄️  GESTOR DE BASE DE DATOS - NEWS BI")
    print("="*80)
    print("\n📋 TABLAS DISPONIBLES:\n")
    
    tables = get_all_tables()
    
    for idx, table in enumerate(tables, 1):
        config = TABLES_CONFIG.get(table, {})
        desc = config.get("description", "")
        print(f"   {idx:2}. {table:<25} {desc}")
    
    print(f"\n   0. Salir")
    print("\n" + "="*80)
    return tables


def main():
    """Función principal del script interactivo."""
    print("\n🚀 Iniciando gestor de base de datos...")
    
    while True:
        tables = show_main_menu()
        
        try:
            choice = input("\n👉 Selecciona una tabla (número) o 0 para salir: ").strip()
            
            if choice == "0":
                print("\n👋 Saliendo del gestor. ¡Hasta luego!\n")
                break
            
            table_idx = int(choice) - 1
            if table_idx < 0 or table_idx >= len(tables):
                print("❌ Opción inválida. Intenta de nuevo.")
                continue
            
            selected_table = tables[table_idx]
            
        except ValueError:
            print("❌ Por favor ingresa un número válido.")
            continue
        
        # Menú de acciones para la tabla seleccionada
        while True:
            print(f"\n📂 Tabla seleccionada: {selected_table.upper()}")
            print("\n   1. Ver registros")
            print("   2. Eliminar registro(s)")
            print("   3. Volver al menú principal")
            print("   0. Salir")
            
            action = input("\n👉 Selecciona una acción: ").strip()
            
            if action == "0":
                print("\n👋 Saliendo del gestor. ¡Hasta luego!\n")
                return
            
            elif action == "1":
                try:
                    limit = input("   Límite de registros (default 50): ").strip()
                    limit = int(limit) if limit else 50
                except ValueError:
                    limit = 50
                
                display_table_data(selected_table, limit)
            
            elif action == "2":
                try:
                    limit = input("   Límite de registros a mostrar (default 50): ").strip()
                    limit = int(limit) if limit else 50
                except ValueError:
                    limit = 50
                
                column_names, rows = display_table_data(selected_table, limit)
                
                if not rows:
                    continue
                
                pk_column = get_primary_key_column(selected_table)
                if not pk_column:
                    print("❌ No se pudo determinar la clave primaria de esta tabla.")
                    continue
                
                print(f"\n🗑️  MODO ELIMINACIÓN")
                print(f"   - Ingresa números de fila separados por comas (ej: 1,3,5)")
                print(f"   - O un rango (ej: 2-10)")
                print(f"   - O escribe 'all' para eliminar TODOS los registros mostrados")
                print(f"   - Clave primaria: {pk_column}")
                
                delete_input = input("\n👉 Registros a eliminar (o 'cancel' para volver): ").strip()
                
                if delete_input.lower() == 'cancel':
                    continue
                
                # Confirmación
                confirm = input("⚠️  ¿Estás seguro? Esta acción NO se puede deshacer (si/no): ").strip().lower()
                if confirm != 'si':
                    print("❌ Operación cancelada.")
                    continue
                
                deleted_count = 0
                
                if delete_input.lower() == 'all':
                    # Eliminar todos los registros mostrados
                    for row_num, row in enumerate(rows, 1):
                        pk_value = row[0]  # Asumiendo que la primera columna es el PK
                        if delete_row(selected_table, pk_column, pk_value, row_num):
                            deleted_count += 1
                
                elif '-' in delete_input:
                    # Rango
                    try:
                        start, end = map(int, delete_input.split('-'))
                        for row_num in range(start, end + 1):
                            row = get_row_by_number(selected_table, row_num, limit)
                            if row:
                                pk_value = row[0]
                                if delete_row(selected_table, pk_column, pk_value, row_num):
                                    deleted_count += 1
                            else:
                                print(f"⚠️  Fila #{row_num} no existe.")
                    except ValueError:
                        print("❌ Formato de rango inválido. Usa: inicio-fin (ej: 2-10)")
                
                else:
                    # Lista separada por comas
                    try:
                        row_numbers = [int(x.strip()) for x in delete_input.split(',')]
                        for row_num in row_numbers:
                            row = get_row_by_number(selected_table, row_num, limit)
                            if row:
                                pk_value = row[0]
                                if delete_row(selected_table, pk_column, pk_value, row_num):
                                    deleted_count += 1
                            else:
                                print(f"⚠️  Fila #{row_num} no existe.")
                    except ValueError:
                        print("❌ Formato inválido. Usa números separados por comas.")
                
                print(f"\n📊 Total de registros eliminados: {deleted_count}")
            
            elif action == "3":
                break
            
            else:
                print("❌ Opción inválida.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrumpido por el usuario. Saliendo...\n")
        sys.exit(0)
