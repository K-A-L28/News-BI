# Manual Operativo - News BI

**Código:** 001-OD-001  
**Versión:** 002  
**Responsable:** Kevin Acevedo López  
**Cargo:** Desarrollador  
**Organización:** Sociamedicos S.A.S / Clínica San Rafael  
**Fecha:** 1/04/2026  

---

## 1. Introducción

Este documento describe el funcionamiento operativo de la aplicación web **News BI**, utilizada para la gestión y programación automática de boletines electrónicos.

Su propósito es servir como guía para usuarios encargados de crear, configurar y supervisar envíos diarios.

---

## 2. Objetivo

Proporcionar instrucciones para:

- Crear y gestionar boletines  
- Administrar listas de destinatarios  
- Programar envíos automáticos  
- Consultar estados y logs  
- Configurar el sistema (administradores)  

---

## 3. Alcance

Este manual está dirigido a:

- Usuarios operativos  
- Administradores  
- Desarrolladores  

---

## 4. Inicio de sesión

1. Acceder a la aplicación.
2. Presionar el botón de inicio de sesión.
3. Autenticarse mediante Microsoft.
4. Ingresar credenciales.

> Nota: El usuario debe estar previamente registrado en el sistema.

---

## 5. Administrador

### 5.1 Configuración general

Permite configurar:

- Dominios permitidos  
- Remitente de correos  
- Límite de envíos (por defecto: 100)  
- Pie de página de boletines  

---

### 5.2 Gestionar credenciales

Permite visualizar y editar:

- Tenant ID  
- Client ID  
- Client Secret  
- API Key de Gemini  

Estas credenciales son necesarias para la integración con servicios externos.

---

### 5.3 Auditoría

- Genera un archivo `.csv` con los registros del sistema.

---

### 5.4 Listas de destinatarios

#### Crear lista

Campos requeridos:

- Nombre  
- Descripción  
- Archivo CSV  

#### Visualización

Permite consultar:

- Cantidad de correos  
- Fecha de creación  
- Límite de correos  

---

### 5.5 Gestión de usuarios

#### Registrar usuario

Campos:

- Nombres  
- Apellidos  
- Correo electrónico  
- Teléfono  
- Dirección  
- Departamento  
- Municipio  
- Rol  
- Empresa  
- Sede  
- Área  

#### Listar usuarios

Permite:

- Visualizar usuarios registrados  
- Editar información  
- Filtrar por:
  - ID  
  - Nombre  
  - Correo  
  - Estado (Activo/Inactivo)  

---

### 5.6 Dashboard

Visualiza:

- Boletines enviados  
- Boletines fallidos  
- Próximos envíos  
- Tareas activas  

---

### 5.7 Crear boletín

Ubicación: tabla **Próximos Envíos**

Campos requeridos:

- Nombre del boletín  
- Lista de correos  
- Plantilla HTML  
- Archivo Python (.py)  
- Archivos JSON (.json)  
- Imágenes  

---

### 5.8 Editar boletín

Permite modificar:

- Nombre  
- Lista de destinatarios  
- Hora de ejecución  
- Zona horaria (America/Bogota)  
- Plantilla HTML (opcional)  

#### Estado de ejecución

- Desactivado: no se ejecuta  
- Activado: se ejecuta automáticamente  

---

### 5.9 Deshabilitar boletín

- Cambia el estado del boletín sin eliminarlo.

---

### 5.10 Eliminar boletín

- Elimina el boletín de forma permanente.

---

### 5.11 Estado, logs y reintentos

Estados posibles:

- Ejecutando  
- Exitoso  
- Fallido  

Opciones disponibles:

- Ver detalles  
- Reintentar ejecución  

---

## 6. Desarrollador

El usuario desarrollador tiene acceso a todas las funcionalidades del administrador.

### 6.1 Modo de prueba

Permite:

- Enviar boletines a un correo de prueba  
- Definir destinatario de testing  

---

## 7. Usuario

### 7.1 Panel de administración

Permite visualizar el estado general del sistema.

---

### 7.2 Edición de destinatarios

Ubicación: tabla **Próximos Envíos**

Permite modificar:

- Lista de destinatarios  
- Hora de ejecución  
- Zona horaria  

---

## 8. Recomendaciones

- Validar archivos antes de cargarlos (.csv, .html, .json, .py)  
- Verificar listas de destinatarios  
- Utilizar modo de prueba antes de producción  
- Revisar logs para monitoreo de errores  

---