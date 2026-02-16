# App Web de Envío Automático de Boletines

**Proyecto:** Aplicación Web Administrativa de Boletines  
**Responsable:** Kevin Acevedo López  
**Cargo:** (Practicante Tics / Desarrollador de la App web)  
**Área / Departamento:** Tics  
**Versión:** 1.0  
**Fecha:** 14/02/2026  

---

# Introducción

El presente documento describe el funcionamiento operativo de la aplicación web para la gestión y programación automática de boletines electrónicos.

Su finalidad es servir como guía práctica para los usuarios encargados de crear, configurar y supervisar los envíos diarios, detallando los pasos necesarios para utilizar correctamente el sistema.

---

# Objetivo del Manual

Proporcionar instrucciones claras y concisas para:

- Crear y gestionar boletines.
- Administrar listas de destinatarios.
- Programar envíos automáticos.
- Consultar el estado de los envíos y revisar logs.
- Configurar opciones generales del sistema (para usuarios con rol administrador).

Este manual está orientado a usuarios operativos y administradores del sistema.

---

# Tabla de Contenido

1. Manual de Operación – Usuario General  
2. Funciones Exclusivas para Administradores  

---

# 1. Manual de Operación – Usuario General

## Inicio de sesión (pendiente)

---

## Crear boletín

El usuario debe buscar la tabla **“Próximos Envíos”**.

Allí encontrará un botón de color verde.

Al presionar el botón, se abrirá un formulario que solicitará los siguientes archivos y datos:

- Nombre del boletín
- Lista de correos
- Plantilla HTML del correo (mensaje que quiere mostrar en el correo)
- Archivo Python (.py)
- Archivos JSON (.json)
- Plantilla HTML para el boletín
- Imágenes para mostrar en la plantilla del boletín

Para crear el boletín debe presionar el botón correspondiente.

Si desea cancelar la ejecución puede presionar el botón de cancelar.

También puede cerrar el formulario desde el botón ubicado en la parte superior derecha junto al título del formulario.

---

## Crear lista de destinatarios

El usuario debe ubicar el botón **Lista de Correos** en la parte superior izquierda.

Al presionar el botón se abrirá un formulario para la creación de la lista.

Se solicitará:

- Nombre de la Lista
- Descripción
- Archivo CSV con los correos electrónicos

Para crear la lista debe presionar el botón correspondiente.

Para visualizar las listas creadas, debe deslizar hacia abajo hasta la sección **Listas Existentes**.

Podrá ver:

- Cantidad de correos que contiene la lista
- Fecha de creación
- Límite de correos permitidos

---

## Programar una tarea

El usuario debe buscar la tabla **“Próximos Envíos”**.

Allí encontrará el boletín creado anteriormente.  
En la columna **ACCIONES** debe presionar el ícono de edición.

Se abrirá el formulario de edición donde se mostrará:

- Nombre del boletín
- Lista de destinatarios seleccionada
- Hora de ejecución (debe presionar el campo y escribir la hora)
- Zona horaria (por defecto: America/Bogota)
- Nueva plantilla de correo (.html) (opcional para actualizar)

Para que el boletín se ejecute en la hora indicada se debe activar:

- **Desactivado (por defecto):** No se ejecutará.
- **Activado:** La tarea se ejecutará en la hora indicada.

Para actualizar el boletín debe presionar el botón correspondiente.

Para cancelar la edición puede:

- Presionar el botón cancelar.
- Cerrar el formulario desde la parte superior derecha.

---

## Ver estado, logs y reintentos

El usuario debe ubicar la tabla **Últimos Envíos**.

Cuando la tarea se ejecute, se mostrará el estado **Ejecutando**.

Si la tarea finaliza con éxito mostrará el estado correspondiente.

Podrá ver los detalles de la ejecución presionando el botón correspondiente donde se visualizará:

- Boletín
- Fecha
- Estado
- Duración
- Logs de ejecución

Si la ejecución falla, la tarea mostrará estado **Fallido**.

El registro mostrará dos opciones:

- Ver detalles de la ejecución
- Reintentar ejecución

Si presiona **Ver detalles**, podrá visualizar el error.  
Si presiona **Reintentar**, la tarea se ejecutará automáticamente nuevamente.

---

## Widget resumen del día

En el dashboard el usuario puede visualizar:

- Cantidad de boletines enviados en el día
- Cantidad de boletines fallidos en el día
- Cantidad de boletines programados (Próximos)
- Tareas activas

---

# 2. Funciones Exclusivas para Administradores

## 1. Configuración general del sistema

El usuario administrador visualizará el botón **Configuraciones**.

Al presionar el botón se abrirá un formulario donde se puede configurar:

- Dominios permitidos
- Remitente de los correos (qué correo los envía)
- Límite de correos por lista (por defecto 100 correos)
- Pie de página

---

## 2. Asignar roles (Pendiente)
