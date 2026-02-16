# Guía para Crear Boletines Personalizados - NewsPilot

## 📋 Estructura de un Boletín

Cada boletín personalizado debe tener 3 componentes principales que se almacenan en la base de datos:

### 1. 📄 Script Python (`script.py`)
Contiene toda la lógica para obtener datos, procesarlos y generar el correo.

```python
#!/usr/bin/env python3
"""
Script de Boletín - Mi Boletín Personalizado
Desarrollado por: [Tu Nombre]
Fecha: [Fecha de desarrollo]
"""

import os
import io
import msal
import json
import base64
import logging
import requests
from PIL import Image
from datetime import datetime
from dotenv import load_dotenv
from babel.dates import format_date
import concurrent.futures
from typing import Dict, List, Tuple, Any

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración de autenticación (inyectada por el sistema)
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID") 
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Configuración de Power Automate (definir tus URLs)
PA_URL_PRINCIPAL = "https://default8e36c55d2d9f43179e94b407559453.28.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/TU_WORKFLOW_ID/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=TU_SIGNATURE"

# URLs de reportes Power BI (opcional)
REPORT_URL = os.getenv("REPORT_ID", "")
REPORT_URL_2 = os.getenv("REPORT_ID_2", "")

# Configuración de Gemini (opcional, para IA)
GEMINI_API_KEY = [key.strip() for key in os.getenv('GEMINI_API_KEY', '').split(',') if key.strip()]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

# ======================================================
# FUNCIONES OBLIGATORIAS - ESTRUCTURA BÁSICA
# ======================================================

# Función principal de ejecución (OBLIGATORIA)
def ejecutar_automatizacion():
    """
    Función principal que ejecuta todo el flujo del boletín.
    ESTA FUNCIÓN ES OBLIGATORIA Y ES LLAMADA POR EL SISTEMA NEWSPILOT.
    
    Returns:
        dict: Diccionario con los datos para el correo y el resultado de la ejecución
    """
    try:
        logger.info("🚀 Iniciando ejecución del boletín...")
        
        # 1. Obtener token de autenticación (si necesitas APIs de Microsoft)
        logger.info("🔑 Obteniendo token de autenticación...")
        token_graph = obtener_token_graph()
        
        # 2. Ejecutar todas las llamadas API concurrentemente
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit todas las tareas de obtención de datos
            future_datos_principales = executor.submit(obtener_datos_principales)
            future_datos_secundarios = executor.submit(obtener_datos_secundarios)
            future_datos_extra = executor.submit(obtener_datos_extra)
            
            # Recolectar resultados
            datos_principales = future_datos_principales.result()
            datos_secundarios = future_datos_secundarios.result()
            datos_extra = future_datos_extra.result()
        
        # 3. Procesamiento de datos (secuencial, depende de los resultados)
        logger.info("📊 Analizando métricas...")
        metricas = procesar_metricas(datos_principales)

        logger.info("📊 Generando tablas HTML...")
        tabla_principal = generar_tabla_html(metricas)
        tabla_secundaria = generar_tabla_secundaria(datos_secundarios)

        logger.info("🤖 Generando análisis con IA...")
        resumen_ejecutivo = generar_resumen_con_ia(metricas)
        
        # 4. Preparar datos para la plantilla
        datos_boletin = {
            # Fechas (formatos estándar del sistema)
            "FECHA": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "FECHA_EXPLICITA": format_date(datetime.now(), format="MMMM yyyy", locale="es").capitalize(),
            "MES": format_date(datetime.now(), format="MMMM", locale="es").capitalize(),
            
            # URLs de reportes (el sistema las inyecta)
            "POWERBI_REPORT_URL": REPORT_URL.replace('&', '&amp;') if REPORT_URL else "",
            "POWERBI_REPORT_URL_2": REPORT_URL_2.replace('&', '&amp;') if REPORT_URL_2 else "",
            
            # Datos procesados
            "TABLA_PRINCIPAL": tabla_principal,
            "TABLA_SECUNDARIA": tabla_secundaria,
            "RESUMEN_EJECUTIVO": resumen_ejecutivo,
            "TOTAL_REGISTROS": len(metricas.get('datos', [])),
            
            # Métricas clave
            "PROMEDIO_GENERAL": metricas.get('promedio', 0),
            "VALOR_MAXIMO": metricas.get('maximo', 0),
            "VALOR_MINIMO": metricas.get('minimo', 0),
            
            # Alertas (bloques HTML completos)
            "BLOQUE_ALERTAS": generar_alertas_html(metricas),
            "BLOQUE_ALERTA_ALTA": generar_alerta_alta_html(metricas),
            "BLOQUE_ALERTA_BAJA": generar_alerta_baja_html(metricas),
        }
        
        # 5. Enviar correo (el sistema llama a esta función automáticamente)
        # ESTA FUNCIÓN ES LLAMADA POR EL WORKER DESPUÉS DE TU EJECUCIÓN
        enviar_correo(datos_boletin, token_graph)
        
        logger.info("✅ Boletín procesado exitosamente")
        
        # 6. Retornar resultado para el sistema
        return {
            'success': True,
            'message': 'Boletín ejecutado exitosamente',
            'data': datos_boletin,
            'logs': f"Procesados {len(metricas.get('datos', []))} registros",
            'execution_id': f"boletin_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        
    except Exception as e:
        logger.error(f"❌ Error en la ejecución del boletín: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f'Error en la ejecución: {str(e)}',
            'logs': f"Error: {str(e)}",
            'execution_id': f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }

# ======================================================
# FUNCIONES AUXILIARES - EJEMPLOS
# ======================================================

def obtener_token_graph():
    """Obtiene token para Microsoft Graph."""
    try:
        authority = f"https://login.microsoftonline.com/{TENANT_ID}"
        scope = "https://graph.microsoft.com/.default"
        
        app = msal.ConfidentialClientApplication(
            client_id=CLIENT_ID,
            authority=authority,
            client_credential=CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=[scope])
        
        if "access_token" not in result:
            raise Exception(f"Error al obtener token: {result.get('error_description', 'Error desconocido')}")
        
        return result["access_token"]
    except Exception as e:
        logger.error(f"Error obteniendo token: {str(e)}")
        raise

# Funciones auxiliares (ejemplos)
def obtener_datos_principales():
    """Obtiene datos principales desde tu API."""
    try:
        logger.info("🔍 Obteniendo datos principales...")
        
        # Ejemplo de llamada a API
        response = requests.post(
            PA_URL_PRINCIPAL,
            headers={"Content-Type": "application/json"},
            json={"dax_query": "TU_CONSULTA_DAX"},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"⚠️ Error API: HTTP {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos principales: {str(e)}")
        return {}

def obtener_datos_secundarios():
    """Obtiene datos secundarios desde otra fuente."""
    try:
        logger.info("🔍 Obteniendo datos secundarios...")
        
        response = requests.post(
            PA_URL_PRINCIPAL,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={"dax_query": "TU_CONSULTA_DAX_SECUNDARIA"},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {}
            
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos secundarios: {str(e)}")
        return {}

def obtener_datos_extra():
    """Obtiene datos adicionales."""
    return {}

def procesar_metricas(datos):
    """Procesa los datos y genera métricas."""
    if not datos:
        return {}
    
    # Ejemplo de procesamiento
    valores = [item.get('valor', 0) for item in datos if isinstance(item, dict)]
    
    return {
        'promedio': sum(valores) / len(valores) if valores else 0,
        'maximo': max(valores) if valores else 0,
        'minimo': min(valores) if valores else 0,
        'datos': datos
    }

def generar_analisis(datos):
    """Genera análisis de los datos."""
    # Aquí puedes usar Gemini para generar análisis automáticos
    return {"analisis": "Análisis generado automáticamente"}

def generar_tabla_secundaria(datos):
    """Genera tabla secundaria."""
    return "<p>Tabla secundaria</p>"

def generar_resumen_con_ia(metricas):
    """Genera resumen usando IA (opcional)."""
    return "Resumen generado automáticamente"

def generar_alerta_alta_html(metricas):
    """Genera alerta específica para valores altos."""
    if metricas.get('promedio', 0) > 80:
        return f"""
        <tr>
            <td height="12" style="font-size:1px; line-height:1px;">&nbsp;</td>
        </tr>
        <tr>
            <td bgcolor="#FEF2F2" style="padding: 12px 16px; border-radius: 6px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                    <tr>
                        <td width="28" valign="middle">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td width="16" height="16" bgcolor="#ef4444" style="border-radius: 50%; font-size: 1px; line-height: 1px;">&nbsp;</td>
                                </tr>
                            </table>
                        </td>
                        <td style="font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; color: #E63946; line-height: 1.5;">
                            Alerta Alta: <span style="font-weight: normal; font-size: 13px; color: #E63946;">{metricas['promedio']:.1f}%</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>"""
    return ""

def generar_alerta_baja_html(metricas):
    """Genera alerta específica para valores bajos."""
    if metricas.get('promedio', 0) < 30:
        return f"""
        <tr>
            <td height="12" style="font-size:1px; line-height:1px;">&nbsp;</td>
        </tr>
        <tr>
            <td bgcolor="#FFFBEB" style="padding: 12px 16px; border-radius: 6px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                    <tr>
                        <td width="28" valign="middle">
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td width="16" height="16" bgcolor="#f59e0b" style="border-radius: 50%; font-size: 1px; line-height: 1px;">&nbsp;</td>
                                </tr>
                            </table>
                        </td>
                        <td style="font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; color: #F59E0B; line-height: 1.5;">
                            Alerta Baja: <span style="font-weight: normal; font-size: 13px; color: #F59E0B;">{metricas['promedio']:.1f}%</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>"""
    return ""

def generar_tabla_html(metricas):
    """Genera una tabla HTML con los resultados."""
    if not metricas.get('datos'):
        return "<p>No hay datos disponibles</p>"
    
    filas = ""
    for item in metricas['datos']:
        filas += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{item.get('nombre', 'N/A')}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{item.get('valor', 0)}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{item.get('estado', 'N/A')}</td>
        </tr>
        """
    
    return f"""
    <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
        <thead>
            <tr style="background-color: #f2f2f2;">
                <th style="border: 1px solid #ddd; padding: 8px;">Nombre</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Valor</th>
                <th style="border: 1px solid #ddd; padding: 8px;">Estado</th>
            </tr>
        </thead>
        <tbody>
            {filas}
        </tbody>
    </table>
    """

def generar_resumen_html(analisis):
    """Genera HTML para el resumen ejecutivo."""
    return f"""
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
        <h3 style="color: #333; margin-top: 0;">📊 Resumen Ejecutivo</h3>
        <p style="color: #666;">{analisis.get('analisis', 'No hay análisis disponible')}</p>
    </div>
    """

def generar_alertas_html(metricas):
    """Genera bloques HTML para alertas."""
    alertas = []
    
    # Ejemplo de alerta
    if metricas.get('promedio', 0) > 80:
        alertas.append(f"""
        <div style="background-color: #f8d7da; padding: 12px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #dc3545;">
            <strong>⚠️ Alerta:</strong> El valor promedio ({metricas['promedio']:.1f}%) supera el umbral crítico.
        </div>
        """)
    
    return "".join(alertas)

def enviar_correo(datos_analisis, token_graph):
    """
    FUNCIÓN OBLIGATORIA - El worker la llama automáticamente.
    Envía un correo con el análisis generado.
    
    Args:
        datos_analisis (dict): Datos generados por ejecutar_automatizacion()
        token_graph (str): Token de autenticación de Microsoft Graph
    """
    try:
        # Obtener configuración de correo (inyectada por el sistema)
        mail_sender = get_mail_sender()
        destinatarios_cco = get_mail_bcc()
        
        if not mail_sender or not destinatarios_cco:
            logger.warning("⚠️ No se configuró remitente o destinatarios")
            return

        attachments: list[dict] = []
        html_final = ""

        # Obtener plantilla de correo y pie de página (inyectadas por el sistema)
        email_template = getattr(__builtins__, 'EMAIL_TEMPLATE_CONTENT', None)
        if not email_template:
            email_template = os.getenv('EMAIL_TEMPLATE_CONTENT')
            
        footer_text = getattr(__builtins__, 'FOOTER_TEXT', None)
        if not footer_text:
            footer_text = os.getenv('FOOTER_TEXT')

        # Cargar plantilla HTML del boletín
        try:
            with open("./template/report_template.html", "r", encoding='utf-8') as f:
                html_boletin = f.read()

            # Reemplazar placeholders en el HTML del boletín
            for key, value in datos_analisis.items():
                html_boletin = html_boletin.replace(f"{{{key.upper()}}}", str(value))
                
            # Combinar con plantilla de correo si existe
            if email_template:
                mensaje_intro = email_template
                for key, value in datos_analisis.items():
                    mensaje_intro = mensaje_intro.replace(f"{{{key.upper()}}}", str(value))
                html_final = mensaje_intro + html_boletin
            else:
                html_final = html_boletin
                
        except FileNotFoundError:
            logger.error("Error al cargar plantilla: template/report_template.html no encontrado")
            html_final = "<h1>Error: Archivo de plantilla no encontrado</h1>"
        
        # Agregar pie de página si no está en la plantilla
        if footer_text and '{footer}' not in (email_template or ''):
            html_final += f"<br><br><hr><div style='text-align: center; font-size: 12px; color: #666;'>{footer_text}</div>"
        
        # Procesar avatar inline si existe
        avatar_path = "./template/avatar_logo.png"
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

        # Construir payload para Microsoft Graph
        payload = {
            "message": {
                "subject": f"Reporte de Gestión - {datetime.now().strftime('%d/%m/%Y')}",
                "body": {
                    "contentType": "html",
                    "content": html_final
                },
                "toRecipients": [],
                "bccRecipients": [{"emailAddress": {"address": email}} for email in destinatarios_cco] if destinatarios_cco else [],
                "attachments": attachments
            },
            "saveToSentItems": False
        }

        logger.info(f"📤 Enviando correo desde {mail_sender} a {len(destinatarios_cco)} destinatarios...")
        url = f"https://graph.microsoft.com/v1.0/users/{mail_sender}/sendMail"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token_graph}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        logger.info("👌 Correo enviado correctamente")

    except requests.HTTPError as e:
        logger.error(f"❌ Error HTTP al enviar el correo: {e.response.text if e.response is not None else str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error al enviar el correo: {str(e)}")

# Funciones auxiliares de correo
def get_mail_sender():
    """Obtiene el remitente de correo dinámicamente desde el entorno."""
    return os.getenv('MAIL_SENDER')

def get_mail_bcc():
    """Obtiene los destinatarios BCC dinámicamente desde el entorno."""
    mail_bcc = os.getenv('MAIL_BCC', '')
    return [email.strip() for email in mail_bcc.split(',') if email.strip()]

def optimizar_imagen(ruta_imagen, ancho_max=800, calidad=85, preservar_alpha=True):
    """Optimiza imagen para correo electrónico."""
    with Image.open(ruta_imagen) as img:
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
        
        w, h = img.size
        if w > ancho_max:
            ratio = ancho_max / float(w)
            img = img.resize((ancho_max, int(h * ratio)), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        if preservar_alpha:
            img.save(buf, format='PNG', optimize=True)
            mime_type = 'image/png'
        else:
            img.save(buf, format='JPEG', quality=calidad, optimize=True, progressive=False)
            mime_type = 'image/jpeg'

        return buf.getvalue(), mime_type

# Punto de entrada (obligatorio)
if __name__ == "__main__":
    resultado = ejecutar_automatizacion()
    print(f"Resultado: {resultado}")
```

### 2. 📊 Consultas DAX (`queries.json`)
Define las consultas necesarias para obtener datos de Power BI.

```json
{
  "report_config": {
    "pages": [
      {
        "display_name": "Datos Principales",
        "queries": [
          {
            "query_id": "ocupacion_diaria",
            "description": "Ocupación hospitalaria diaria",
            "dax": "EVALUATE SUMMARIZE(COLUMNS('Sedes'[Ciudad], 'Sedes'[Sede], \"[Cant_Pacientes]\", SUM('Camas'[Pacientes]), \"[Cant_Camas]\", SUM('Camas'[Total])))"
          },
          {
            "query_id": "metricas_kpi",
            "description": "KPIs principales del día",
            "dax": "EVALUATE SUMMARIZE(COLUMNS('KPI'[Nombre], \"[Valor]\", SUM('KPI'[Valor])))"
          }
        ]
      },
      {
        "display_name": "Datos Secundarios",
        "queries": [
          {
            "query_id": "facturacion_diaria",
            "description": "Facturación del día",
            "dax": "EVALUATE SUMMARIZE(COLUMNS('Facturacion'[Concepto], \"[Total]\", SUM('Facturacion'[Valor])))"
          }
        ]
      }
    ]
  }
}
```

### 3. 🎨 Plantilla HTML (`template.html`)
Define la estructura del correo electrónico.

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Boletín {FECHA}</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header { 
            background-color: #2c3e50; 
            color: white;
            padding: 20px; 
            text-align: center; 
            border-radius: 8px 8px 0 0;
        }
        .content { 
            margin: 20px 0; 
            padding: 0 20px;
        }
        .footer { 
            background-color: #ecf0f1; 
            padding: 15px; 
            text-align: center; 
            font-size: 12px; 
            border-radius: 0 0 8px 8px;
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 10px 0; 
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left; 
        }
        th { 
            background-color: #3498db; 
            color: white;
        }
        .metric-card {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
            border-left: 4px solid #3498db;
        }
        .alert {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            padding: 12px;
            border-radius: 5px;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Boletín de Gestión</h1>
            <p>Fecha: {FECHA_EXPLICITA}</p>
        </div>
        
        <div class="content">
            <!-- Resumen Ejecutivo -->
            {RESUMEN_ANALISIS}
            
            <!-- Métricas Principales -->
            <h2>📈 Métricas Clave</h2>
            <div class="metric-card">
                <strong>Promedio General:</strong> {PROMEDIO_GENERAL}%
            </div>
            <div class="metric-card">
                <strong>Valor Máximo:</strong> {VALOR_MAXIMO}
            </div>
            <div class="metric-card">
                <strong>Valor Mínimo:</strong> {VALOR_MINIMO}
            </div>
            
            <!-- Tabla de Resultados -->
            <h2>📋 Detalle de Resultados</h2>
            {TABLA_RESULTADOS}
            
            <!-- Alertas -->
            {BLOQUE_ALERTAS}
            
            <!-- Enlaces a Reportes -->
            <h2>🔗 Acceso a Reportes</h2>
            <p>
                <a href="{POWERBI_REPORT_URL}" style="color: #3498db; text-decoration: none;">📊 Reporte Principal</a>
                {POWERBI_REPORT_URL_2 ? f'| <a href="{POWERBI_REPORT_URL_2}" style="color: #3498db; text-decoration: none;">📈 Reporte Secundario</a>' : ''}
            </p>
        </div>
        
        <div class="footer">
            <p>Este boletín fue generado automáticamente el {FECHA}</p>
            <p>Total de registros procesados: {TOTAL_REGISTROS}</p>
            <hr style="margin: 10px 0; border: none; border-top: 1px solid #ddd;">
            <p style="color: #666; font-size: 11px;">Sistema de Boletines - NewsPilot</p>
        </div>
    </div>
</body>
</html>
```

## 🗂️ Estructura en la Base de Datos

Los archivos deben almacenarse en la base de datos usando el dashboard:

1. **Ve a "Cargar Boletín"** en el dashboard
2. **Ingresa los 3 componentes**:
   - **Nombre del Boletín**: `mi_boletin_personalizado`
   - **Script Python**: Contenido del archivo `script.py`
   - **Consultas DAX**: Contenido del archivo `queries.json`
   - **Plantilla HTML**: Contenido del archivo `template.html`
3. **Configura la programación**:
   - **Hora de envío**: Por ejemplo `08:00`
   - **Lista de correos**: Selecciona o crea una lista
   - **Activa el boletín**: Marca como habilitado

## ⚙️ Variables del Sistema Disponibles

El sistema inyecta automáticamente estas variables en tu script:

### Variables de Entorno
- `TENANT_ID`: ID del tenant de Azure
- `CLIENT_ID`: ID del cliente de la aplicación
- `CLIENT_SECRET`: Secreto del cliente
- `GEMINI_API_KEY`: Claves API de Gemini (separadas por comas)
- `GEMINI_MODEL`: Modelo de Gemini a usar
- `REPORT_ID`: ID del reporte Power BI principal
- `REPORT_ID_2`: ID del reporte Power BI secundario

### Variables Inyectadas en Tiempo de Ejecución
- `EMAIL_TEMPLATE_CONTENT`: Plantilla de correo personalizada (si existe)
- `FOOTER_TEXT`: Pie de página configurado
- `MAIL_SENDER`: Remitente de correos
- `MAIL_BCC`: Destinatarios en BCC

## 🔄 Flujo de Ejecución

1. **Worker** detecta hora programada del boletín
2. **Engine** carga el script, consultas y plantilla desde la BD
3. **Script** ejecuta `ejecutar_automatizacion()` y retorna datos
4. **Script** llama `enviar_correo(datos, token)` para enviar el correo
5. **Engine** registra el resultado en la base de datos

## ⚙️ Variables del Sistema Disponibles

El sistema inyecta automáticamente estas variables en tu script:

### Variables de Entorno (Configuración Global)
- `TENANT_ID`: ID del tenant de Azure
- `CLIENT_ID`: ID del cliente de la aplicación
- `CLIENT_SECRET`: Secreto del cliente
- `GEMINI_API_KEY`: Claves API de Gemini (separadas por comas)
- `GEMINI_MODEL`: Modelo de Gemini a usar
- `REPORT_ID`: ID del reporte Power BI principal
- `REPORT_ID_2`: ID del reporte Power BI secundario

### Variables Inyectadas en Tiempo de Ejecución
- `EMAIL_TEMPLATE_CONTENT`: Plantilla de correo personalizada (si existe)
- `FOOTER_TEXT`: Pie de página configurado
- `MAIL_SENDER`: Remitente de correos
- `MAIL_BCC`: Destinatarios en BCC

## � Variables Disponibles en la Plantilla HTML

La plantilla puede usar todas las variables retornadas por `ejecutar_automatizacion()`:

### Variables del Sistema
- `{POWERBI_REPORT_URL}`: URL del reporte principal
- `{POWERBI_REPORT_URL_2}`: URL del reporte secundario
- `{FECHA}`: Fecha y hora actual
- `{FECHA_EXPLICITA}`: Fecha en formato legible
- `{MES}`: Nombre del mes actual
- `{AVATAR_SRC}`: Logo inline (si existe)

### Variables del Boletín
- Todas las que incluyas en el diccionario `datos_boletin`
- `{TOTAL_REGISTROS}`, `{PROMEDIO_GENERAL}`, etc.

## ✅ Buenas Prácticas

### 1. **Estructura del Script (OBLIGATORIO)**
```python
def ejecutar_automatizacion():
    """FUNCIÓN OBLIGATORIA - Punto de entrada del sistema"""
    try:
        # 1. Obtener token si necesitas APIs
        token_graph = obtener_token_graph()
        
        # 2. Obtener datos concurrentemente
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # ... tus llamadas API
            
        # 3. Procesar datos
        datos_boletin = {...}
        
        # 4. Enviar correo (OBLIGATORIO)
        enviar_correo(datos_boletin, token_graph)
        
        # 5. Retornar resultado
        return {
            'success': True,
            'message': 'Boletín ejecutado exitosamente',
            'data': datos_boletin,
            'logs': "Logs de ejecución"
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error: {str(e)}',
            'logs': f"Error: {str(e)}"
        }

def enviar_correo(datos_analisis, token_graph):
    """FUNCIÓN OBLIGATORIA - El worker la llama automáticamente"""
    # Implementación del envío de correo
```

### 2. **Manejo de Errores**
- Siempre usar try-except en la función principal
- Loggear errores con `logger.error()`
- Retornar estructura consistente

### 3. **Performance**
- Usar `concurrent.futures` para llamadas API en paralelo
- Implementar timeouts en las llamadas HTTP
- Validar datos antes de procesarlos

### 4. **Seguridad**
- No incluir credenciales en el código
- Usar variables de entorno para configuración sensible
- Validar datos de entrada

### 5. **Logging**
```python
logger.info("🚀 Iniciando proceso...")
logger.info("✅ Datos obtenidos correctamente")
logger.warning("⚠️ Alerta: valor fuera de rango")
logger.error("❌ Error procesando datos")
```

## 🚀 Ejemplo Completo - Paso a Paso

### Paso 1: Crear el Script Python
Crea `mi_boletin.py` con la estructura mostrada arriba.

### Paso 2: Definir Consultas DAX
Crea `queries.json` con tus consultas a Power BI.

### Paso 3: Diseñar Plantilla HTML
Crea `template.html` con el diseño del correo.

### Paso 4: Cargar al Sistema
1. Abre el dashboard de NewsPilot
2. Ve a "Cargar Boletín"
3. Ingresa nombre: `mi_boletin_diario`
4. Pega el contenido de cada archivo en su campo correspondiente
5. Configura hora de envío: `08:00`
6. Selecciona lista de correos
7. Activa el boletín

### Paso 5: Probar
1. Ve a "Envíos Recientes"
2. Haz clic en "Ejecutar Ahora" para probar
3. Revisa los logs y el correo recibido

## 🎯 Modo Prueba

Para probar sin enviar correos reales:

1. **Activa el Modo Prueba** en Configuración
2. **Todos los correos** se enviarán a: `k.acevedo@clinicassanrafael.com`
3. **Los boletines** se marcarán como prueba en el sistema
4. **Puedes probar** tantas veces como necesites

## 📞 Soporte

Si tienes problemas:

1. **Revisa los logs** en la terminal
2. **Verifica la sintaxis** de tu script Python
3. **Valida el JSON** de las consultas
4. **Prueba el HTML** en un navegador
5. **Usa el Modo Prueba** antes de enviar a producción

¡Listo! Con esta guía puedes crear boletines personalizados que se integren perfectamente con NewsPilot. 🎉
