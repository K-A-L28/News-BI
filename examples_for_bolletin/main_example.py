#!/usr/bin/env python3
"""
Ejemplo básico de script para generar boletines
Este archivo sirve como tutorial para que los usuarios entiendan
la estructura mínima necesaria para crear sus propios boletines.

Basado en el archivo ejemplo.py del proyecto News BI

=== ¿POR QUÉ VARIABLES INYECTADAS EN VEZ DE .ENV DIRECTO? ===
Este diseño permite:
1. Inyección dinámica desde el sistema worker.py
2. Mayor seguridad: las variables no están hardcodeadas
3. Flexibilidad: diferentes configuraciones por ejecución
4. Testing: se pueden inyectar variables de prueba
5. Escalabilidad: múltiples boletines con diferentes configuraciones
"""

import os
import sys
import logging
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from PIL import Image
import io

# ======================================================
# CONFIGURACIÓN BÁSICA (OBLIGATORIO)
# ======================================================

# Configurar logging para ver qué está pasando
# logging.basicConfig() configura el sistema de registro global de Python
# level=logging.INFO muestra mensajes informativos, advertencias y errores
# format define cómo se ve cada mensaje: timestamp - nivel - mensaje
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde archivo .env
# load_dotenv() busca un archivo .env en el directorio actual y carga las variables
# Esto permite tener credenciales fuera del código por seguridad
# Sin embargo, este script está diseñado para recibir variables inyectadas dinámicamente
load_dotenv()

# ======================================================
# VARIABLES DE ENTORNO REQUERIDAS (OBLIGATORIO)
# ======================================================

# Autenticación Microsoft (requerido para enviar correos)
# TENANT_ID: Identificador único del tenant de Azure AD
# CLIENT_ID: ID de la aplicación registrada en Azure
# CLIENT_SECRET: Secreto de la aplicación para autenticación
# NOTA: Estas variables pueden ser inyectadas dinámicamente por el sistema worker
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID") 
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Configuración de correo (requerido)
# MAIL_SENDER: Correo desde el que se envía el boletín (debe tener permisos en Azure)
# MAIL_BCC: Lista de correos destinatarios (separados por comas) - todos van en CCO por privacidad
MAIL_SENDER = os.getenv('MAIL_SENDER')
MAIL_BCC = os.getenv('MAIL_BCC', '')

# Validación de variables críticas
def validar_variables_entorno():
    """
    Valida que todas las variables necesarias estén configuradas
    
    ¿Por qué esta validación es crítica?
    1. Evita fallos en tiempo de ejecución
    2. Proporciona mensajes de error claros
    3. Detecta problemas de configuración temprano
    4. Asegura que el flujo completo pueda ejecutarse
    
    Esta función se llama al inicio del main() para verificar configuración
    """
    
    if not TENANT_ID:
        logger.error("❌ TENANT_ID no está configurado")
        raise Exception("TENANT_ID requerido")
    
    if not CLIENT_ID:
        logger.error("❌ CLIENT_ID no está configurado")
        raise Exception("CLIENT_ID requerido")
        
    if not CLIENT_SECRET:
        logger.error("❌ CLIENT_SECRET no está configurado")
        raise Exception("CLIENT_SECRET requerido")
        
    if not MAIL_SENDER:
        logger.error("❌ MAIL_SENDER no está configurado")
        raise Exception("MAIL_SENDER requerido")
        
    if not MAIL_BCC:
        logger.error("❌ MAIL_BCC no está configurado")
        raise Exception("MAIL_BCC requerido")
    
    logger.info("✅ Variables de entorno validadas correctamente")

# ======================================================
# OBTENER TOKEN DE AUTENTICACIÓN (OBLIGATORIO)
# ======================================================

import msal

def obtener_token_graph():
    """
    Obtiene token para Microsoft Graph API - NECESARIO para enviar correos
    
    ¿Por qué necesitamos este token?
    1. Microsoft Graph API requiere autenticación OAuth 2.0
    2. El token permite enviar correos en nombre de la aplicación
    3. Tiene una vida útil limitada (generalmente 1 hora)
    4. Se obtiene usando el flujo "client credentials" para aplicaciones sin usuario
    
    Flujo de autenticación:
    - Usamos MSAL (Microsoft Authentication Library)
    - ConfidentialClientApplication para aplicaciones de servidor
    - acquire_token_for_client() obtiene token sin intervención del usuario
    
    Returns: str - Token de acceso para Graph API
    """
    
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    scope = "https://graph.microsoft.com/.default"
    
    try:
        app = msal.ConfidentialClientApplication(
            client_id=CLIENT_ID,
            authority=authority,
            client_credential=CLIENT_SECRET
        )
        
        result = app.acquire_token_for_client(scopes=[scope])
        
        if "access_token" not in result:
            raise Exception(f"Error obteniendo token: {result.get('error_description', 'Error desconocido')}")
            
        logger.info("✅ Token de Graph obtenido correctamente")
        return result["access_token"]
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo token: {str(e)}")
        raise

# ======================================================
# FUNCIÓN PARA ENVIAR CORREO (OBLIGATORIO)
# ======================================================

def optimizar_imagen(ruta_imagen, ancho_max=800, calidad=85, preservar_alpha=True):
    """
    Optimiza imágenes para adjuntar en correos (idéntica a ejemplo.py)
    
    ¿Por qué optimizar imágenes?
    1. Reducir tamaño del archivo para envío más rápido
    2. Evitar límites de tamaño en correos (generalmente 25MB)
    3. Mejor experiencia del usuario con imágenes más ligeras
    4. Compatible con clientes de correo web y escritorio
    
    Proceso de optimización:
    - Redimensiona si excede ancho_max
    - Convierte a formato óptimo (PNG con transparencia, JPEG sin ella)
    - Comprime con calidad especificada
    - Retorna bytes listos para adjuntar en base64
    
    Args:
        ruta_imagen: Path al archivo de imagen
        ancho_max: Ancho máximo permitido (default: 800px)
        calidad: Calidad de compresión JPEG (default: 85)
        preservar_alpha: Mantener transparencia (default: True)
    
    Returns: tuple - (bytes_imagen, mime_type)
    """
    with Image.open(ruta_imagen) as img:
        # Normalizar modo
        if preservar_alpha:
            if img.mode not in ('RGBA', 'LA'):
                img = img.convert('RGBA')
        else:
            if img.mode in ('RGBA', 'LA'):
                fondo = Image.new('RGB', img.size, (255, 255, 255))
                fondo.paste(img, mask=img.split()[-1])
                img = fondo
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
        # Resize
        w, h = img.size
        if w > ancho_max:
            ratio = ancho_max / float(w)
            img = img.resize(
                (ancho_max, int(h * ratio)),
                Image.Resampling.LANCZOS
            )

        buf = io.BytesIO()

        if preservar_alpha:
            img.save(buf, format='PNG', optimize=True)
            mime_type = 'image/png'
        else:
            img.save(
                buf,
                format='JPEG',
                quality=calidad,
                optimize=True,
                progressive=False
            )
            mime_type = 'image/jpeg'

        return buf.getvalue(), mime_type

def get_mail_sender():
    """
    Obtiene el remitente de correo dinámicamente desde las variables inyectadas
    
    ¿Por qué esta función en vez de usar os.getenv() directamente?
    1. Permite inyección dinámica desde worker.py
    2. Prioriza variables inyectadas sobre variables de entorno
    3. Facilita testing con diferentes remitentes
    4. Implementa el patrón de "dependency injection"
    
    Flujo de búsqueda:
    1. Primero busca en variables globales (inyectadas)
    2. Si no encuentra, busca en variables de entorno
    3. Esto permite sobreescribir valores dinámicamente
    
    Returns: str - Email del remitente
    """
    # Primero intentar variable global inyectada, luego variable de entorno
    return globals().get('MAIL_SENDER') or os.getenv('MAIL_SENDER')

def get_mail_bcc():
    """
    Obtiene los destinatarios BCC dinámicamente desde las variables inyectadas
    
    ¿Por qué BCC (Copia Oculta) en vez de TO o CC?
    1. Privacidad: los destinatarios no ven los correos de otros
    2. Cumplimiento RGPD/LGPD: protege datos personales
    3. Evita "Reply All" accidental
    4. Previene spam entre destinatarios
    
    ¿Por qué esta función?
    1. Permite inyección dinámica desde worker.py
    2. Parsea string separado por comas a lista
    3. Limpia espacios en blanco
    4. Facilita testing con diferentes listas
    
    Returns: list - Lista de emails destinatarios
    """
    # Primero intentar variable global inyectada, luego variable de entorno
    mail_bcc = globals().get('MAIL_BCC') or os.getenv('MAIL_BCC', '') # Todos los correos van en CCO
    return [email.strip() for email in mail_bcc.split(',') if email.strip()]

def enviar_correo(datos_analisis, token_graph):
    """
    Envía un correo con el análisis generado.
    Función idéntica a la de ejemplo.py
    
    ¿Por qué esta estructura?
    1. Modularidad: separa envío de correo de generación de datos
    2. Testabilidad: se puede probar el envío independientemente
    3. Reusabilidad: otros scripts pueden usarla
    4. Manejo robusto de errores con logging detallado
    
    Flujo de envío:
    1. Validar remitente y destinatarios (crítico)
    2. Cargar plantilla HTML y reemplazar variables
    3. Procesar avatar/logo si existe
    4. Construir payload para Microsoft Graph API
    5. Enviar via POST a Graph API
    6. Manejar errores HTTP y generales
    
    Args:
        datos_analisis: dict con variables para reemplazar en plantilla
        token_graph: str token de autenticación para Graph API
    
    Raises:
        ValueError: Si faltan remitente o destinatarios
        requests.HTTPError: Si falla la llamada a Graph API
        sys.exit(1): Si falla críticamente (para que worker lo detecte)
    """
    try:
        # Obtener remitente y destinatarios dinámicamente
        mail_sender = get_mail_sender()
        destinatarios_cco = get_mail_bcc()
        
        # Validación crítica de remitente
        if not mail_sender:
            error_msg = "❌ ERROR CRÍTICO: No se ha configurado un remitente de correo (MAIL_SENDER). La ejecución se detendrá."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validación crítica de destinatarios
        if not destinatarios_cco:
            error_msg = "❌ ERROR CRÍTICO: No se han configurado destinatarios de correo (MAIL_BCC). La ejecución se detendrá."
            logger.error(error_msg)
            raise ValueError(error_msg)

        attachments: list[dict] = []
        html_final = ""

        # Cargar plantilla HTML desde carpeta templates
        # ¿Por qué plantillas HTML?
        # 1. Separación de contenido y presentación
        # 2. Diseño profesional sin código Python
        # 3. Fácil modificación por no-programadores
        # 4. Reusabilidad entre diferentes boletines
        try:
            with open("examples_for_bolletin/boletin_template_example.html", "r", encoding='utf-8') as f:
                html_final = f.read()

            # Reemplazar placeholders en el HTML del boletín
            # Formato: {VARIABLE} - se reemplaza con el valor correspondiente
            # Esto permite personalizar el contenido dinámicamente
            for key, value in datos_analisis.items():
                html_final = html_final.replace(f"{{{key.upper()}}}", str(value))

        except FileNotFoundError:
            logger.error("Error al cargar plantilla: templates/boletin_template.html no encontrado")
            html_final = "<h1>Error: Archivo de plantilla no encontrado</h1>"
        
        # Avatar inline (solo si existe)
        # ¿Por qué avatar inline?
        # 1. Se muestra directamente en el correo (sin adjuntos separados)
        # 2. Mejor experiencia de usuario
        # 3. Branding profesional
        # 4. No requiere descarga adicional
        avatar_path = "templates/avatar_logo.png"
        if os.path.exists(avatar_path):
            try:
                avatar_bytes, avatar_mime = optimizar_imagen(avatar_path, ancho_max=200, preservar_alpha=True)
                avatar_b64 = base64.b64encode(avatar_bytes).decode('utf-8')
                html_final = html_final.replace("{AVATAR_SRC}", "cid:AVATAR_IMG")
                attachments.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": "avatar.png" if avatar_mime == "image/png" else "avatar.jpg",
                    "contentId": "AVATAR_IMG",
                    "isInline": True,
                    "contentType": avatar_mime,
                    "contentBytes": avatar_b64
                })
            except Exception as e:
                logger.error(f"Error al adjuntar avatar: {str(e)}")
                html_final = html_final.replace("{AVATAR_SRC}", "")
        else:
            html_final = html_final.replace("{AVATAR_SRC}", "")

        payload = {
            "message": {
                "subject": f"Boletín Informativo - {datetime.now().strftime('%d/%m/%Y')}",
                "body": {
                    "contentType": "html",
                    "content": html_final
                },
                "toRecipients": [],  # Vacío - usamos BCC para privacidad
                "bccRecipients": [{"emailAddress": {"address": email}} for email in destinatarios_cco] if destinatarios_cco else [],
                "attachments": attachments
            },
            "saveToSentItems": False  # No guardar en enviados para evitar saturación
        }
        
        # ¿Por qué esta estructura de payload?
        # 1. Sigue el formato exacto de Microsoft Graph API
        # 2. toRecipients vacío + bccRecipients = máxima privacidad
        # 3. saveToSentItems False = no saturar la bandeja de enviados
        # 4. attachments con @odata.type = formato correcto para Graph

        logger.info(f"Enviando correo desde {mail_sender} a todos los destinatarios en CCO...")
        # URL de Microsoft Graph API para enviar correos
        # Formato: https://graph.microsoft.com/v1.0/users/{userPrincipalName}/sendMail
        url = f"https://graph.microsoft.com/v1.0/users/{mail_sender}/sendMail"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token_graph}",  # Token OAuth 2.0
                "Content-Type": "application/json"          # Formato JSON
            },
            json=payload,
            timeout=60  # Timeout generoso para evitar cortes
        )
        response.raise_for_status()  # Lanza excepción si hay error HTTP
        logger.info("👌 Correo enviado correctamente")

    except requests.HTTPError as e:
        logger.error(f"❌ Error HTTP al enviar el correo: {e.response.text if e.response is not None else str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error al enviar el correo: {str(e)}")
        # Error crítico - detener ejecución para que worker lo detecte
        logger.error("💥 Fallo crítico al enviar correo - terminando con sys.exit(1)")
        sys.exit(1)

# ======================================================
# SISTEMA DE PLANTILLAS (OBLIGATORIO)
# ======================================================

def cargar_plantilla_html(nombre_plantilla="boletin_template.html"):
    """
    Carga una plantilla HTML desde la carpeta templates
    Similar al sistema usado en ejemplo.py
    
    ¿Por qué este sistema de plantillas?
    1. Separación de responsabilidades: HTML vs Python
    2. Diseñadores pueden modificar sin tocar código
    3. Versionado independiente de contenido y lógica
    4. Reusabilidad entre diferentes boletines
    5. Internacionalización fácil (múltiples idiomas)
    
    Estructura de archivos esperada:
    templates/
    ├── boletin_template.html (plantilla principal)
    ├── avatar_logo.png (logo opcional)
    └── [otras plantillas]
    
    Args:
        nombre_plantilla: Nombre del archivo HTML a cargar
    
    Returns:
        str - Contenido HTML de la plantilla
    
    Raises:
        FileNotFoundError - Si no existe la plantilla
    """
    try:
        ruta_plantilla = Path(__file__).parent / "templates" / nombre_plantilla
        
        if not ruta_plantilla.exists():
            logger.error(f"❌ Plantilla no encontrada: {ruta_plantilla}")
            raise FileNotFoundError(f"Plantilla {nombre_plantilla} no encontrada")
        
        with open(ruta_plantilla, 'r', encoding='utf-8') as f:
            plantilla = f.read()
        
        logger.info(f"✅ Plantilla {nombre_plantilla} cargada correctamente")
        return plantilla
        
    except Exception as e:
        logger.error(f"❌ Error cargando plantilla: {str(e)}")
        raise

def reemplazar_variables_plantilla(plantilla, variables):
    """
    Reemplaza las variables en la plantilla HTML
    Usa el formato {VARIABLE} (una sola llave)
    
    ¿Por qué este formato de variables?
    1. Simple y legible: {FECHA_ACTUAL}
    2. No conflictúa con JavaScript/Jinja2 (usan {{ }})
    3. Fácil de usar por no-programadores
    4. Compatible con editores de texto
    
    Proceso de reemplazo:
    1. Itera sobre cada variable del diccionario
    2. Busca {CLAVE} en el HTML
    3. Reemplaza con el valor (convertido a string)
    4. Retorna el HTML procesado
    
    Args:
        plantilla: str - HTML con placeholders {VARIABLE}
        variables: dict - Diccionario clave->valor para reemplazar
    
    Returns:
        str - HTML con variables reemplazadas
    """
    try:
        contenido = plantilla
        
        # Reemplazar cada variable
        for clave, valor in variables.items():
            placeholder = f"{{{clave}}}"
            contenido = contenido.replace(placeholder, str(valor))
        
        logger.info(f"✅ Variables reemplazadas correctamente ({len(variables)} variables)")
        return contenido
        
    except Exception as e:
        logger.error(f"❌ Error reemplazando variables: {str(e)}")
        raise

def limpiar_variables_no_usadas(contenido):
    """
    Elimina variables no reemplazadas para evitar mostrar {VARIABLE}
    
    ¿Por qué esta limpieza?
    1. Profesionalismo: no mostrar {VARIABLE} sin reemplazar
    2. Evitar confusión en el usuario final
    3. Detectar variables faltantes en desarrollo
    4. HTML limpio y válido
    
    Proceso:
    1. Usa expresión regular para encontrar {PATRON}
    2. Identifica variables no reemplazadas
    3. Loggea advertencia para desarrollo
    4. Elimina los placeholders del HTML final
    
    Args:
        contenido: str - HTML con posibles {VARIABLE} sin reemplazar
    
    Returns:
        str - HTML limpio sin placeholders
    """
    import re
    
    try:
        # Buscar patrones {VARIABLE} que no fueron reemplazados
        patron = r'\{([^}]+)\}'
        variables_no_usadas = re.findall(patron, contenido)
        
        if variables_no_usadas:
            logger.warning(f"⚠️ Variables no reemplazadas: {variables_no_usadas}")
            # Opcional: reemplazar con vacío o un valor por defecto
            contenido = re.sub(patron, '', contenido)
        
        return contenido
        
    except Exception as e:
        logger.error(f"❌ Error limpiando variables: {str(e)}")
        return contenido

# ======================================================
# OBTENER DATOS (EJEMPLO SIMPLE - PUEDES REEMPLAZARLO)
# ======================================================

def obtener_precio_dolar():
    """
    Obtiene precio actual del dólar (ejemplo simple)
    
    ¿Por qué este ejemplo?
    1. Demuestra cómo consumir APIs externas
    2. Datos económicos son útiles en boletines
    3. API pública sin autenticación
    4. Manejo robusto de errores
    
    En producción, podrías usar:
    - APIs de bancos centrales
    - Servicios financieros pagos
    - Base de datos propia
    - APIs internas de la empresa
    
    Returns:
        float - Precio del dólar en COP o None si hay error
    """
    try:
        # API gratuita para obtener precio del dólar
        response = requests.get("https://api.exchangerate-api.com/v4/latest/USD")
        if response.status_code == 200:
            data = response.json()
            return data.get('rates', {}).get('COP', 0)
        return None
    except:
        return None

def preparar_variables_boletin():
    """
    Prepara todas las variables que se inyectarán en la plantilla HTML
    Este es el equivalente a la función que prepara datos en ejemplo.py
    
    ¿Por qué esta función?
    1. Centraliza la lógica de obtención de datos
    2. Separa datos de presentación
    3. Facilita testing unitario
    4. Permite reutilizar datos en múltiples plantillas
    5. Manejo unificado de errores
    
    Fuentes de datos típicas:
    - APIs externas (clima, finanzas, noticias)
    - Bases de datos (MySQL, PostgreSQL, etc.)
    - Archivos locales (CSV, Excel, JSON)
    - Conexiones a Power BI/Tableau
    - Sistemas ERP/CRM internos
    
    Returns:
        dict - Diccionario con todas las variables para la plantilla
    """
    try:
        logger.info("📊 Preparando variables para el boletín...")
        
        # Obtener fecha y hora actual
        ahora = datetime.now()
        
        # Obtener precio del dólar
        precio_dolar = obtener_precio_dolar()
        precio_dolar_formateado = f"${precio_dolar:,.0f}".replace(",", ".") if precio_dolar else "No disponible"
        
        # Variables básicas (siempre incluidas)
        # ¿Por qué tantas variables de fecha/hora?
        # 1. Flexibilidad: diferentes formatos para diferentes usos
        # 2. Internacionalización: formatos locales
        # 3. Ordenamiento: fechas ISO para sorting
        # 4. Legibilidad: formatos amigables para humanos
        variables = {
            # Fechas y horas
            "FECHA_ACTUAL": ahora.strftime("%d/%m/%Y"),
            "HORA_ACTUAL": ahora.strftime("%I:%M %p"),
            "FECHA_COMPLETA": ahora.strftime("%d de %B de %Y"),
            "HORA_COMPLETA": ahora.strftime("%H:%M:%S"),
            "FECHA_GENERACION": ahora.strftime("%Y-%m-%d"),
            "HORA_GENERACION": ahora.strftime("%H:%M:%S"),
            
            # Identificación
            "ID_BOLETIN": f"BLT-{ahora.strftime('%Y%m%d-%H%M%S')}",
            
            # Datos económicos
            "PRECIO_DOLAR": precio_dolar_formateado,
            "FECHA_ACTUALIZACION_DOLAR": ahora.strftime("%d/%m/%Y %H:%M"),
            
            # Datos personalizados (ejemplo - puedes eliminar o modificar)
            "TITULO_DATOS": "Ejemplo de Datos Personalizados",
            "DESCRIPCION_DATOS": "Aquí puedes agregar tus propios datos de Power BI, bases de datos, APIs, etc.",
        }
        
        # Ejemplo: Agregar datos de tabla (opcional)
        # ¿Por qué este bloque condicional?
        # 1. Demostración de cómo incluir datos tabulares
        # 2. Fácil activación/desactivación
        # 3. Plantilla puede mostrar/ocultar secciones
        # 4. Ejemplo real de datos estructurados
        if False:  # Cambia a True para activar ejemplo de tabla
            variables.update({
                "DATOS_PERSONALES": "true",  # Activa la sección de datos personales
                "CABECERA_TABLA": ["Producto", "Ventas", "Mes"],
                "TABLA_DATOS": [
                    ["Producto A", "$1,000,000", "Enero"],
                    ["Producto B", "$2,500,000", "Enero"],
                    ["Producto C", "$750,000", "Enero"]
                ]
            })
        
        
        
        logger.info(f"✅ Variables preparadas: {len(variables)} variables listas")
        return variables
        
    except Exception as e:
        logger.error(f"❌ Error preparando variables: {str(e)}")
        raise

def generar_contenido_boletin():
    """
    Genera el contenido del boletín usando plantilla HTML
    Esta función ahora usa el sistema de plantillas como ejemplo.py
    
    ¿Por qué esta arquitectura?
    1. Pipeline claro: cargar -> preparar -> reemplazar -> limpiar
    2. Manejo robusto de errores con fallback
    3. Logging detallado para debugging
    4. Separación de responsabilidades
    
    Flujo:
    1. Cargar plantilla HTML desde archivo
    2. Obtener datos de múltiples fuentes
    3. Reemplazar placeholders con datos
    4. Limpiar variables no usadas
    5. Retornar HTML final o fallback
    
    Returns:
        str - HTML final del boletín
    """
    try:
        logger.info("📝 Generando contenido del boletín con plantilla...")
        
        # 1. Cargar plantilla HTML
        plantilla = cargar_plantilla_html("boletin_template.html")
        
        # 2. Preparar variables
        variables = preparar_variables_boletin()
        
        # 3. Reemplazar variables en la plantilla
        contenido = reemplazar_variables_plantilla(plantilla, variables)
        
        # 4. Limpiar variables no usadas
        contenido = limpiar_variables_no_usadas(contenido)
        
        logger.info("✅ Contenido del boletín generado correctamente")
        return contenido
        
    except Exception as e:
        logger.error(f"❌ Error generando contenido: {str(e)}")
        
        # Fallback: generar HTML básico en caso de error
        logger.warning("⚠️ Usando HTML de fallback debido a error")
        return generar_html_fallback()

def generar_html_fallback():
    """
    HTML de emergencia si falla la plantilla
    
    ¿Por qué este fallback?
    1. Resiliencia: el boletín siempre se envía
    2. Diagnóstico: informa del problema
    3. Experiencia usuario: recibe algo vs nada
    4. Debugging: incluye timestamp para rastreo
    
    Características:
    - HTML mínimo válido
    - Estilos inline para compatibilidad
    - Información de diagnóstico
    - Timestamp para identificación
    
    Returns:
        str - HTML básico de emergencia
    """
    ahora = datetime.now()
    return f"""
    <html>
    <head><style>body{{font-family:Arial;padding:20px;}}</style></head>
    <body>
        <h2>📊 Boletín Informativo</h2>
        <p><strong>Fecha:</strong> {ahora.strftime('%d/%m/%Y')}</p>
        <p><strong>Hora:</strong> {ahora.strftime('%H:%M')}</p>
        <p><strong>ID:</strong> BLT-{ahora.strftime('%Y%m%d-%H%M%S')}</p>
        <hr>
        <p>⚠️ Se usó el HTML de emergencia debido a un error con la plantilla.</p>
        <p>Por favor, contacta al administrador del sistema.</p>
    </body>
    </html>
    """

# ======================================================
# FUNCIÓN PRINCIPAL (OBLIGATORIO)
# ======================================================

def ejecutar_boletin():
    """
    Función principal que ejecuta todo el flujo del boletín
    Estructura idéntica a ejemplo.py
    
    ¿Por qué esta estructura?
    1. Orquestación clara del flujo completo
    2. Manejo unificado de errores
    3. Logging detallado para monitoreo
    4. Retorno booleano para sistemas externos
    5. Testabilidad de todo el flujo
    
    Secuencia crítica (orden importante):
    1. Obtener token (sin esto no se puede enviar correo)
    2. Preparar datos (depende de fuentes externas)
    3. Enviar correo (acción final que puede fallar)
    
    Returns:
        bool - True si éxito, False si error
    """
    try:
        logger.info("🚀 Iniciando generación de boletín...")
        
        # Obtener token (operación secuencial necesaria)
        logger.info("🔑 Obteniendo token de autenticación...")
        token_graph = obtener_token_graph()
        
        # Preparar datos para el boletín
        logger.info("� Preparando datos del boletín...")
        datos_analisis = preparar_variables_boletin()
        
        # Enviar correo con los datos
        logger.info("📧 Enviando boletín por correo...")
        enviar_correo(datos_analisis, token_graph)
        
        logger.info("✅ Boletín procesado y enviado exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en ejecutar_boletin(): {str(e)}")
        return False

def main():
    """
    Función principal - ESTA ESTRUCTURA DEBE MANTENERSE
    
    ¿Por qué esta estructura específica?
    1. Punto de entrada estándar para scripts Python
    2. Validación inicial antes de cualquier operación
    3. Manejo de errores a nivel superior
    4. Retorno claro para sistemas externos
    5. Compatible con ejecución manual y automatizada
    
    Flujo principal:
    1. Validar configuración (variables de entorno)
    2. Ejecutar flujo completo del boletín
    3. Retornar resultado para sistemas externos
    
    Importante: worker.py espera esta estructura para
    - Detectar errores
    - Reintentar ejecución
    - Logging centralizado
    
    Returns:
        bool - True si éxito, False si error
    """
    try:
        logger.info("� Iniciando generación de boletín...")
        
        # 1. Validar variables de entorno
        validar_variables_entorno()
        
        # 2. Ejecutar el flujo completo del boletín
        resultado = ejecutar_boletin()
        
        if resultado:
            logger.info("✅ Boletín enviado exitosamente")
        else:
            logger.error("❌ Falló el envío del boletín")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en main(): {str(e)}")
        return False

# ======================================================
# PUNTO DE ENTRADA (OBLIGATORIO)
# ======================================================

if __name__ == "__main__":
    """
    Punto de entrada cuando se ejecuta el script directamente
    
    ¿Por qué este bloque?
    1. Permite ejecución directa: python main_example.py
    2. No se ejecuta cuando se importa como módulo
    3. Facilita testing y desarrollo
    4. Interfaz amigable para usuarios
    
    Uso:
    - Desarrollo: python main_example.py
    - Testing: import main_example y llamar funciones
    - Producción: worker.py importa y ejecuta main()
    
    Este bloque NO se ejecuta cuando worker.py importa el script,
    solo cuando se corre directamente desde línea de comandos.
    """
    
    print("=" * 60)
    print("📊 SISTEMA DE BOLETINES - EJEMPLO")
    print("=" * 60)
    
    # Ejecutar función principal
    resultado = main()
    
    if resultado:
        print("\n✅ Boletín procesado exitosamente")
    else:
        print("\n❌ Falló el procesamiento del boletín")
    
    print("=" * 60)
