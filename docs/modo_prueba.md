# Modo Prueba - Sistema de Boletines

## Overview

El modo prueba es una funcionalidad que permite probar el envío de boletines sin afectar los datos de producción. Cuando está activado, todos los correos se envían únicamente a una dirección de prueba y los boletines se registran como pruebas.

## Características

### 🧪 ¿Qué hace el modo prueba?

1. **Envío de correos**: Todos los correos se envían únicamente a `k.acevedo@clinicassanrafael.com`
2. **Registro de pruebas**: Los boletines se registran con prefijo `test_` en el execution_id
3. **Protección de datos**: No se actualiza la base de datos con datos de producción
4. **Indicador visual**: El dashboard muestra un indicador visible cuando el modo está activo

### 🎯 Beneficios

- **Seguridad**: Evita envíos accidentales a listas de producción
- **Pruebas controladas**: Permite validar flujo completo sin impacto real
- **Visibilidad**: Indicador claro en el dashboard para evitar confusiones
- **Trazaabilidad**: Los registros de prueba son fácilmente identificables

## Uso

### Activar/Desactivar Modo Prueba

1. **Desde el Dashboard**:
   - Ir a **Configuración** (botón en el header)
   - Marcar/desmarcar la casilla **"Modo Prueba"**
   - El cambio se aplica inmediatamente

2. **Indicador Visual**:
   - Cuando está activo, aparece un ícono circular morado con 🧪 en el header
   - El indicador tiene una animación de pulso sutil y muestra tooltip al pasar el mouse
   - Diseño minimalista: solo el ícono sin texto para mayor limpieza visual

### Comportamiento

#### Modo Prueba Activado ✅
- **Destinatarios**: Solo `k.acevedo@clinicassanrafael.com`
- **Execution ID**: Prefijo `test_` (ej: `test_manual_20260213_101500`)
- **Logs**: Incluyen emoji 🧪 para identificar operaciones de prueba
- **Base de datos**: No se modifica con datos de producción

#### Modo Producción (Normal) 📧
- **Destinatarios**: Listas configuradas en cada boletín
- **Execution ID**: Formato estándar (ej: `manual_20260213_101500`)
- **Logs**: Sin marcadores especiales
- **Base de datos**: Operación normal

## Implementación Técnica

### Componentes Modificados

1. **Engine** (`controllers/engine.py`):
   - `_get_test_mode_from_db()`: Lee configuración desde SystemConfig
   - `get_auth_config()`: Modifica destinatarios según modo
   - `execute_bulletin()`: Agrega prefijo y logs especiales

2. **API Server** (`controllers/api_server.py`):
   - `GET /api/test-mode`: Obtiene estado actual
   - `POST /api/test-mode`: Cambia estado del modo

3. **Dashboard**:
   - **HTML**: Indicador visual en header
   - **CSS**: Estilos para modo prueba con animación
   - **JavaScript**: Control y actualización del estado

### Base de Datos

```sql
-- Configuración del modo prueba
INSERT INTO system_config (
    config_key, 
    config_value, 
    config_type, 
    description
) VALUES (
    'is_test_mode', 
    'false', 
    'boolean', 
    'Modo prueba para enviar correos solo a dirección de prueba'
);
```

## Instalación

### Inicialización

Ejecutar el script de inicialización:

```bash
python scripts/init_test_mode.py
```

Esto crea la configuración por defecto (desactivado) en la base de datos.

### Verificación

1. Iniciar el servidor: `python main.py`
2. Abrir el dashboard en el navegador
3. Verificar que no haya indicador de modo prueba (estado inicial)
4. Ir a Configuración y activar el modo prueba para probar

## Consideraciones de Seguridad

- ✅ El modo prueba debe estar desactivado en producción
- ✅ Solo se envía a una dirección predefinida
- ✅ Los registros son claramente identificables
- ✅ No hay forma de modificar el correo de prueba desde la interfaz

## Troubleshooting

### Problemas Comunes

1. **El indicador no aparece**:
   - Verificar que el servidor esté corriendo
   - Revisar la consola del navegador por errores de JavaScript
   - Verificar que la configuración exista en la base de datos

2. **Los correos siguen llegando a producción**:
   - Confirmar que el modo prueba esté activado en Configuración
   - Revisar los logs del servidor para ver si muestra "MODO PRUEBA"
   - Verificar la configuración en la tabla `system_config`

3. **No se puede cambiar el estado**:
   - Revisar permisos en la base de datos
   - Verificar que el usuario admin exista
   - Revisar los logs del servidor por errores

## Logs del Sistema

### Logs de Cambio de Configuración

Cuando se activa o desactiva el modo prueba desde el dashboard:

**Activando modo prueba:**
```
🧪 MODO PRUEBA ACTIVADO - Todos los correos se enviarán a: k.acevedo@clinicassanrafael.com
```

**Desactivando modo prueba:**
```
✅ MODO PRUEBA DESACTIVADO - Los correos se enviarán a destinatarios reales
```

### Logs de Ejecución de Boletines

Durante la ejecución de boletines en modo prueba:

**Modo Prueba Activado:**
```
🧪 MODO PRUEBA ACTIVADO - Enviando a: k.acevedo@clinicassanrafael.com
🧪 'Newsletter Test' ejecutado
```

**Modo Producción:**
```
✅ 'Newsletter Mensual' ejecutado
```

### Características de los Logs

- **Limpios y concisos**: Sin información de depuración excesiva
- **Informativos**: Muestran solo la información esencial
- **Identificables**: Usan emojis para distinguir estados
- **Profesionales**: Diseñados para producción sin ruido visual

## Desarrollo

### Para agregar nuevas funcionalidades al modo prueba:

1. **Verificar estado**: Usar `system_engine._get_test_mode_from_db()`
2. **Agregar logs**: Incluir emoji 🧪 para operaciones de prueba (mantener logs limpios)
3. **Modificar comportamientos**: Usar condicionales basadas en `is_test_mode`
4. **Actualizar UI**: Considerar el indicador visual circular en nuevas interfaces

### Buenas Prácticas de Logging

- **Essenciales**: Solo mostrar información crítica (cambio de modo, destinatarios)
- **Limpios**: Evitar logs de depuración en producción
- **Consistentes**: Usar los mismos mensajes en engine y API server
- **Visibles**: Los logs importantes deben ser fáciles de identificar

### Variables de Entorno

No se requieren variables de entorno adicionales. El correo de prueba está hardcoded por seguridad:

```python
TEST_EMAIL = 'k.acevedo@clinicassanrafael.com'
```
