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
import logging
import requests
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dotenv import load_dotenv

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

# Función principal de ejecución (obligatoria)
def ejecutar_automatizacion():
    """
    Función principal que ejecuta todo el flujo del boletín.
    Esta función es llamada automáticamente por el sistema NewsPilot.
    
    Returns:
        dict: Diccionario con los datos para el correo y el resultado de la ejecución
    """
    try:
        logger.info("🚀 Iniciando ejecución del boletín...")
        
        # 1. Obtener token de autenticación (si es necesario)
        # token_graph = obtener_token_graph()
        
        # 2. Ejecutar consultas a APIs externas en paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_datos_principales = executor.submit(obtener_datos_principales)
            future_datos_secundarios = executor.submit(obtener_datos_secundarios)
            
            # Recolectar resultados
            datos_principales = future_datos_principales.result()
            datos_secundarios = future_datos_secundarios.result()
        
        # 3. Procesar y analizar los datos
        logger.info("📊 Procesando datos...")
        metricas = procesar_metricas(datos_principales)
        analisis = generar_analisis(datos_secundarios)
        
        # 4. Generar contenido HTML
        tabla_html = generar_tabla_html(metricas)
        resumen_html = generar_resumen_html(analisis)
        
        # 5. Preparar datos para la plantilla
        datos_boletin = {
            # Fechas
            "FECHA": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "FECHA_EXPLICITA": datetime.now().strftime("%d de %B de %Y"),
            "MES": datetime.now().strftime("%B").capitalize(),
            
            # URLs de reportes
            "POWERBI_REPORT_URL": REPORT_URL.replace('&', '&amp;') if REPORT_URL else "",
            "POWERBI_REPORT_URL_2": REPORT_URL_2.replace('&', '&amp;') if REPORT_URL_2 else "",
            
            # Datos procesados
            "TABLA_RESULTADOS": tabla_html,
            "RESUMEN_ANALISIS": resumen_html,
            "TOTAL_REGISTROS": len(metricas.get('datos', [])),
            
            # Métricas clave
            "PROMEDIO_GENERAL": metricas.get('promedio', 0),
            "VALOR_MAXIMO": metricas.get('maximo', 0),
            "VALOR_MINIMO": metricas.get('minimo', 0),
            
            # Alertas (bloques HTML completos)
            "BLOQUE_ALERTAS": generar_alertas_html(metricas),
        }
        
        # 6. Enviar correo (el sistema se encarga de esto)
        # enviar_correo(datos_boletin, token_graph)
        
        logger.info("✅ Boletín procesado exitosamente")
        
        # 7. Retornar resultado para el sistema
        return {
            'success': True,
            'message': 'Boletín ejecutado exitosamente',
            'data': datos_boletin,
            'execution_id': f"boletin_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }
        
    except Exception as e:
        logger.error(f"❌ Error en la ejecución del boletín: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f'Error en la ejecución: {str(e)}',
            'execution_id': f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }

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
    # Similar a obtener_datos_principales pero para otros datos
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

# Funciones de autenticación (si son necesarias)
def obtener_token():
    """Obtiene token de autenticación."""
    # Implementar lógica de autenticación si es necesaria
    return "token_ejemplo"

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

1. **Scheduler** activa el boletín a la hora programada
2. **Engine** carga el script, consultas y plantilla desde la BD
3. **Script** ejecuta `ejecutar_automatizacion()` y retorna datos
4. **Engine** combina datos con la plantilla HTML
5. **Engine** envía el correo usando la configuración del sistema

## 📝 Variables Disponibles en la Plantilla HTML

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

### 1. **Estructura del Script**
```python
# Obligatorio: Función principal
def ejecutar_automatizacion():
    try:
        # Tu lógica aquí
        return {
            'success': True,
            'message': 'Boletín ejecutado exitosamente',
            'data': datos_boletin
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error: {str(e)}'
        }
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
