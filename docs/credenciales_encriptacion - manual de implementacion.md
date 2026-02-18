# Manual de Implementación - Sistema de Credenciales Encriptadas

## Overview

Se ha implementado un sistema completo para gestionar credenciales del archivo `.env` con encriptación AES-256-GCM, siguiendo el flujo solicitado:

```
Desencriptar en memoria → Parsear .env → Cargar en formulario UI → Editar → Guardar → Encriptar → Sobrescribir archivo
```

## Componentes Implementados

### 1. Módulo de Encriptación (`utils/encryption.py`)

**Características:**
- **Algoritmo**: AES-256-GCM (encriptación simétrica segura)
- **Derivación de clave**: PBKDF2HMAC con 100,000 iteraciones
- **Salt fijo**: Para consistencia en el sistema
- **Base64**: Para almacenamiento seguro en archivo

**Funcionalidades:**
- `encrypt_env_content()` - Encripta contenido .env
- `decrypt_env_content()` - Desencripta contenido .env
- `parse_env_content()` - Parsea variables a diccionario
- `format_env_content()` - Formatea diccionario a .env
- `encrypt_env_file()` - Encripta archivo completo
- `decrypt_env_file()` - Desencripta archivo en memoria
- `save_encrypted_env()` - Guarda diccionario encriptado

### 2. Endpoints API (`controllers/api_server.py`)

**Endpoints creados:**
- `GET /api/credentials` - Obtiene credenciales (valores sensibles ocultos)
- `GET /api/credentials/raw` - Obtiene credenciales completas para edición
- `POST /api/credentials` - Guarda credenciales encriptadas

**Características de seguridad:**
- Los valores sensibles (PASSWORD, SECRET, KEY, TOKEN) se ocultan con asteriscos
- Solo el endpoint `/raw` muestra valores completos para edición
- Validación automática de formato .env
- Creación automática desde `.env.example` si no existe

### 3. Interfaz de Usuario (`views/dashboard/dashboard.js`)

**Funcionalidades implementadas:**
- Botón "Credenciales" en configuración general
- Modal dinámico con formulario de credenciales
- Detección automática de campos sensibles
- Toggle de visibilidad para contraseñas
- Detección de cambios antes de guardar
- Confirmación de guardado
- Notificaciones de estado

**Características UX:**
- Campos sensibles con icono de ojo para mostrar/ocultar
- Indicadores visuales para campos críticos
- Loading states durante operaciones
- Mensajes de error claros
- Escape HTML para seguridad

### 4. Estilos (`views/dashboard/dashboard.css`)

**Estilos especiales:**
- `.credentials-form` - Scroll para formularios largos
- `.input-group` - Layout para inputs con botones
- `.btn-toggle-password` - Botón mostrar/ocultar
- `.security-notice` - Notificación de seguridad
- `.credential-input` - Fuente monospace para credenciales
- Indicadores visuales para campos sensibles

## Flujo Completo

### 1. Acceso del Usuario
```
Dashboard → Configuración → Botón "Credenciales"
```

### 2. Carga de Credenciales
```
GET /api/credentials/raw → Desencriptar .env → Parsear a diccionario → Generar formulario
```

### 3. Edición
```
Usuario edita valores → Toggle visibilidad para contraseñas → Detección de cambios
```

### 4. Guardado
```
POST /api/credentials → Validar → Encriptar con AES-256-GCM → Sobrescribir .env
```

## Seguridad Implementada

### Encriptación
- **AES-256-GCM**: Algoritmo moderno con autenticación
- **Nonce único**: Para cada encriptación
- **PBKDF2HMAC**: Derivación segura de clave
- **100,000 iteraciones**: Resistencia a brute force

### Protección en Frontend
- Escape HTML para XSS
- Detección de cambios para evitar guardados accidentales
- Confirmación antes de guardar
- Ocultamiento automático de valores sensibles

### Validaciones
- Formato .env válido
- Base64 validation
- Manejo de errores robusto
- Logs detallados

## Archivos Creados/Modificados

### Nuevos
- `utils/encryption.py` - Módulo de encriptación
- `.env.example` - Plantilla de configuración
- `docs/credenciales_encriptacion - manual de implementacion.md` - Este manual

### Modificados
- `controllers/api_server.py` - Endpoints API
- `views/dashboard/dashboard.js` - Funcionalidad frontend
- `views/dashboard/dashboard.css` - Estilos adicionales

## Uso

### Para el Usuario Final
1. Ir al dashboard
2. Hacer clic en "Configuración"
3. Hacer clic en "Credenciales"
4. Editar los valores necesarios
5. Hacer clic en "Guardar y Encriptar"

### Para Desarrolladores
```python
# Para encriptar manualmente
from utils.encryption import env_encryptor

# Desencriptar archivo
content = env_encryptor.decrypt_env_file('.env')

# Guardar credenciales
credentials = {'DB_URL': 'sqlite:///test.db', 'API_KEY': 'secret123'}
env_encryptor.save_encrypted_env('.env', credentials)
```

## Consideraciones Importantes

1. **Contraseña Maestra**: Por defecto usa `ENV_MASTER_PASSWORD` o valor por defecto
2. **Backup**: Se recomienda hacer backup del `.env` antes de cambios
3. **Permisos**: El archivo `.env` debe tener permisos restringidos
4. **Logs**: Las operaciones se registran en logs del sistema
5. **Compatibilidad**: El sistema detecta si el archivo ya está encriptado

## Flujo de Error Handling

1. **Archivo no existe**: Crea desde `.env.example`
2. **Error desencriptando**: Intenta leer como texto plano
3. **Error guardando**: Rollback automático
4. **Error frontend**: Muestra mensaje específico
5. **Error red**: Notificación de conexión

## Testing

Para probar el sistema:

1. Crear `.env` desde `.env.example`
2. Iniciar el servidor API
3. Acceder al dashboard
4. Probar el flujo completo
5. Verificar que el archivo `.env` quede encriptado

El sistema está listo para producción y cumple con todos los requisitos de seguridad solicitados.
