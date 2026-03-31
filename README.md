# News BI - Sistema de Gestión de Boletines

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-green.svg)
![SQLite](https://img.shields.io/badge/SQLite-3.x-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 📋 Descripción

News BI es un sistema completo para la gestión y automatización de boletines informativos. Permite crear, programar y enviar boletines por correo electrónico de manera automatizada, con integración con Microsoft Azure Active Directory para autenticación y soporte para plantillas HTML personalizadas.

## 🚀 Características Principales

### ✨ Funcionalidades
- **Gestión de Boletines**: Creación, edición y eliminación de boletines informativos
- **Programación Automática**: Configuración de horarios de envío automáticos
- **Plantillas HTML**: Soporte para plantillas de correo personalizables
- **Gestión de Contactos**: Importación de listas de correos desde archivos CSV
- **Autenticación Segura**: Integración con Microsoft Azure AD
- **Panel de Administración**: Interfaz web moderna y responsiva
- **Sistema de Auditoría**: Registro completo de todas las acciones del sistema
- **Ejecución Manual**: Envío inmediato de boletines cuando se necesite

### 🔧 Características Técnicas
- **Arquitectura Modular**: Separación clara entre componentes
- **Base de Datos SQLite**: Almacenamiento local y ligero
- **API RESTful**: Endpoints bien documentados con FastAPI
- **Worker en Segundo Plano**: Procesamiento asíncrono de tareas
- **Sistema de Configuración**: Gestión centralizada de variables de entorno
- **Encriptación de Datos**: Protección de información sensible

## 📁 Estructura del Proyecto

```
News BI/
├── controllers/           # Lógica de controladores
│   ├── api_server.py     # Servidor API FastAPI
│   ├── engine.py         # Motor de procesamiento
│   └── worker.py         # Worker en segundo plano
├── models/               # Modelos de datos y base de datos
│   ├── database.py       # Definición de modelos SQLAlchemy
│   ├── file_manager.py   # Gestión de archivos
│   └── cargar_archivos.py # Carga de datos
├── utils/                # Utilidades y configuración
│   ├── config.py         # Configuración centralizada
│   ├── encryption.py     # Encriptación de datos
│   └── timezone_config.py # Configuración de zona horaria
├── views/                # Interfaz de usuario
│   └── dashboard/        # Panel de administración
│       ├── index.html    # Interfaz principal
│       ├── dashboard.js  # Lógica del frontend
│       └── dashboard.css # Estilos CSS
├── scripts/              # Scripts de mantenimiento
│   └── dev/              # Scripts de desarrollo
├── docs/                 # Documentación
├── examples_for_bolletin/   # Archivos de ejemplo para boletines
├── images/               # Imágenes del sistema
├── temp/                 # Archivos temporales
├── main.py               # Punto de entrada principal
├── requirements.txt      # Dependencias Python
└── .env                  # Variables de entorno (no incluido en repo)
```

## 🛠️ Instalación y Configuración

### Prerrequisitos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Git

### Pasos de Instalación

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/K-A-L28/News-BI
   cd News-BI
   ```

2. **Crear entorno virtual**
   ```bash
   python -m venv venv
   
   # En Windows
   venv\Scripts\activate
   
   # En Unix/MacOS
   source venv/bin/activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**
   
   Crear un archivo `.env` en la raíz del proyecto con el siguiente contenido:
   ```env
   # Autenticación Microsoft Graph
   TENANT_ID=your_tenant_id
   CLIENT_ID=your_client_id
   CLIENT_SECRET=your_client_secret
   
   
   # Configuración Gemini AI (opcional)
   GEMINI_API_KEY=your_gemini_api_key

   ```

5. **Inicializar la base de datos**
   ```bash
   python -m scripts.dev.init_db
   ```

## 🚀 Ejecución del Sistema

### Método 1: Ejecución Completa (Recomendado)
Inicia tanto el servidor API como el worker en segundo plano:

```bash
python main.py
```

El sistema iniciará:
- 🌐 Servidor API en http://localhost:8001
- 🔄 Worker de tareas en segundo plano
- 📊 Dashboard disponible en http://localhost:8001
- 📝 Documentación API en http://localhost:8001/docs

### Método 2: Ejecución Individual

**Iniciar solo el servidor API:**
```bash
python -m controllers.api_server
```

**Iniciar solo el worker:**
```bash
python -m controllers.worker
```

## 📊 Uso del Sistema

### Acceso al Sistema
1. Abre tu navegador web y navega a `http://localhost:8001`
2. Inicia sesión con tu cuenta Microsoft (configuración Azure AD requerida)
3. Accede al panel de administración

### Funciones Principales

#### 📧 Gestión de Boletines
- **Crear Boletín**: Define nombre, asunto y plantilla HTML
- **Configurar Envío**: Establece hora, zona horaria y frecuencia
- **Gestionar Contactos**: Importa listas de correos desde CSV
- **Programar Envío**: Configura envíos automáticos

#### 📈 Panel de Control
- **Estadísticas**: Visualiza envíos del día, fallidos y próximos
- **Auditoría**: Consulta el registro completo de acciones
- **Ejecuciones**: Revisa el historial de envíos realizados

#### 🔧 Configuración del Sistema
- **Credenciales**: Configura integraciones con servicios externos
- **Dominios Permitidos**: Define dominios autorizados para correos
- **Modo Prueba**: Activa/desactiva el modo de pruebas

## 📝 API Endpoints

La API REST está disponible en `http://localhost:8001/docs` con documentación interactiva.

### Endpoints Principales
- `GET /api/stats` - Estadísticas del sistema
- `GET /api/schedules` - Listar boletines programados
- `POST /api/schedules` - Crear nuevo boletín
- `PUT /api/schedules/{id}` - Actualizar boletín
- `DELETE /api/schedules/{id}` - Eliminar boletín
- `POST /api/execute/{id}` - Ejecutar envío manual
- `GET /api/audit` - Consultar registros de auditoría
- `GET /api/audit/download` - Descargar auditoría en CSV

## 🔐 Seguridad

### Autenticación
- Integración con Microsoft Azure Active Directory
- Tokens JWT para sesiones seguras
- Configuración de dominios permitidos

### Auditoría
- Registro completo de todas las acciones del sistema
- Trazabilidad de cambios en configuraciones
- Logs de ejecución de boletines

### Encriptación
- Datos sensibles encriptados en base de datos
- Variables de entorno protegidas
- Manejo seguro de credenciales

## 🧪 Pruebas

El sistema incluye un conjunto completo de pruebas documentadas en `docs/informe_de_pruebas_profesional.md`.

### Ejecutar Pruebas
```bash
# Inicializar modo de prueba
python -m scripts.dev.init_test_mode

# Limpiar base de datos
python -m scripts.dev.clean_database
```

## 📄 Licencia 

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🤝 Contribución

1. Fork del proyecto
2. Crear una rama de características (`git checkout -b feature/NuevaCaracteristica`)
3. Realizar commits con cambios (`git commit -am 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/NuevaCaracteristica`)
5. Abrir un Pull Request

## 📞 Soporte

Para reportar problemas o solicitar ayuda:
- Crear un issue en el repositorio
- Revisar la documentación en `docs/`
- Consultar los logs del sistema para diagnóstico


## 🔄 Versiones
Ejemplo:
- v1.1.0 (nueva funcionalidad)
- v1.0.1 (corrección de errores)
- v2.0.0 (cambio mayor)

### **v2.0.0** *(Current Version)*
**Fecha:** 2026-03-31  
**Tipo:** Major Release  
**Estado:** Estable - Proyecto completado  
**Cambios:**
- 🚀 **Versión estable**: Proyecto completado con todas las funcionalidades acordadas
- 🔐 **Sistema de gestión por roles**: Implementación completa de permisos según rol de usuario
- 📱 **Dashboard optimizado**: Interfaz adaptativa según permisos del usuario
- 🐛 **Bug fixes**: Corrección de errores críticos reportados
- 📊 **Sistema de auditoría**: Registro completo de todas las acciones

**Nota:** Esta versión marca la finalización del desarrollo principal. Las próximas versiones serán solo correcciones de bugs (patch) o nuevas funcionalidades menores.

### **v1.9.9** *(Previus Version - 2026-03-31)*
**Tipo:** Feature Release  
**Cambios:**
- ✨ **Mejoras de UX**: Nueva interfaz de acuerdo al rol del usuario
- 🔧 **Correcciones de funcionalidad**: Se resolvieron errores críticos del sistema y manejo de información de acuerdo al rol
- 📱 **Optimizaciones de interfaz**: Mejoras en el panel de administración
- 🐛 **Bug fixes**: Corrección de errores reportados

### **v1.0.0** *(Initial Release - 2026-02-11)*
**Fecha:** 2026-02-11  
**Tipo:** Major Release  
**Cambios:**
- 🚀 **Versión inicial** con funcionalidades completas
- 🔐 **Sistema de auditoría** implementado
- 🌐 **Integración con Microsoft Azure AD**
- 📱 **Panel de administración** responsivo

## 📚 Tecnologías Utilizadas

### Backend
- **FastAPI**: Framework web moderno y rápido
- **SQLAlchemy**: ORM para base de datos
- **SQLite**: Base de datos ligera
- **MSAL**: Autenticación Microsoft
- **Python-dotenv**: Gestión de variables de entorno

### Frontend
- **HTML5/CSS3**: Interfaz web moderna
- **JavaScript (ES6+)**: Lógica del cliente

### Integraciones
- **Microsoft Graph API**: Autenticación y servicios
- **Power Automate**: Automatización de flujos
- **Power BI**: Reportes y análisis
- **Gemini AI**: Procesamiento de lenguaje natural

---

**News BI** - Simplificando la gestión de boletines informativos 🚀
