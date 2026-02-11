# Ejemplo de Reporte Personalizado - Guía para Usuarios

## 📋 Estructura de un Reporte

Cada reporte personalizado debe tener 3 componentes principales que se almacenan en la base de datos:

### 1. 📄 Lógica Python (`logic.py`)
Contiene todo el código para procesar los datos y generar el resultado.

```python
#!/usr/bin/env python3
"""
Lógica del reporte de ejemplo - Mi Reporte Personalizado
"""

import logging
from controllers.query_executor import query_executor

logger = logging.getLogger(__name__)

def procesar_reporte(report_context):
    """
    Función principal que procesa el reporte.
    
    Args:
        report_context (dict): Contexto proporcionado por el sistema
            - report_name: Nombre del reporte
            - config_data: Configuración general del sistema
            - queries_config: Configuración de consultas DAX
            - template_html: Plantilla HTML del correo
            - timestamp: Fecha/hora de ejecución
    
    Returns:
        dict: Datos procesados para el correo
    """
    try:
        logger.info(f"🚀 Iniciando procesamiento del reporte: {report_context['report_name']}")
        
        # 1. Obtener URLs desde la configuración del sistema
        config_data = report_context['config_data']
        endpoint_url = config_data.get('URL_MI_REPORTE')
        
        if not endpoint_url:
            raise ValueError("No se encontró URL del endpoint en la configuración")
        
        # 2. Ejecutar consultas DAX usando el ejecutor del sistema
        queries_config = report_context['queries_config']
        resultados = query_executor.execute_query_batch(queries_config, endpoint_url)
        
        # 3. Procesar los datos según las necesidades del reporte
        datos_procesados = {}
        
        # Ejemplo: Procesar datos de ocupación
        if 'ocupacion_data' in resultados:
            ocupacion = procesar_datos_ocupacion(resultados['ocupacion_data']['data'])
            datos_procesados.update(ocupacion)
        
        # Ejemplo: Procesar datos de facturación
        if 'facturacion_data' in resultados:
            facturacion = procesar_datos_facturacion(resultados['facturacion_data']['data'])
            datos_procesados.update(facturacion)
        
        # 4. Generar contenido HTML específico del reporte
        tabla_html = generar_tabla_html(datos_procesados)
        datos_procesados['TABLA_RESULTADOS'] = tabla_html
        
        # 5. Agregar metadatos del reporte
        datos_procesados.update({
            'NOMBRE_REPORTE': report_context['report_name'],
            'FECHA_GENERACION': report_context['timestamp'].strftime('%d/%m/%Y'),
            'TOTAL_REGISTROS': len(datos_procesados.get('datos', []))
        })
        
        logger.info(f"✅ Reporte procesado exitosamente")
        return datos_procesados
        
    except Exception as e:
        logger.error(f"❌ Error procesando reporte: {str(e)}", exc_info=True)
        return {}

def procesar_datos_ocupacion(datos_crudos):
    """Procesa los datos de ocupación según las reglas del negocio."""
    # Aquí va la lógica específica para procesar ocupación
    return {
        'PROMEDIO_OCUPACION': '85%',
        'SEDE_MAYOR_OCUPACION': 'PEREIRA - MEGACENTRO (92%)',
        'TOTAL_CAMAS': 450,
        'CAMAS_OCUPADAS': 382
    }

def procesar_datos_facturacion(datos_crudos):
    """Procesa los datos de facturación según las reglas del negocio."""
    # Aquí va la lógica específica para procesar facturación
    return {
        'TOTAL_FACTURADO': '$2,500,000',
        'TOP_CLIENTE': 'SURA',
        'FACTURACION_MES': '$1,800,000'
    }

def generar_tabla_html(datos):
    """Genera una tabla HTML con los resultados."""
    return """
    <table style="width: 100%; border-collapse: collapse;">
        <tr>
            <th style="border: 1px solid #ddd; padding: 8px;">Métrica</th>
            <th style="border: 1px solid #ddd; padding: 8px;">Valor</th>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 8px;">Ocupación Promedio</td>
            <td style="border: 1px solid #ddd; padding: 8px;">{PROMEDIO_OCUPACION}</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 8px;">Total Facturado</td>
            <td style="border: 1px solid #ddd; padding: 8px;">{TOTAL_FACTURADO}</td>
        </tr>
    </table>
    """.format(**datos)
```

### 2. 📊 Consultas DAX (`queries.json`)
Define todas las consultas necesarias para obtener datos de Power BI.

```json
{
  "report_config": {
    "pages": [
      {
        "display_name": "Ocupación",
        "queries": [
          {
            "query_id": "ocupacion_data",
            "description": "Datos de ocupación por sede",
            "dax": "EVALUATE SUMMARIZE(COLUMNS('Sedes'[Ciudad], 'Sedes'[Sede], \"[Cant_Pacientes]\", SUM('Camas'[Pacientes]), \"[Cant_Camas]\", SUM('Camas'[Total])))"
          },
          {
            "query_id": "camas_inhabilitadas",
            "description": "Camas inhabilitadas por ciudad",
            "dax": "EVALUATE SUMMARIZE(COLUMNS('EstadoCamas'[Ciudad], \"[Inhabilitadas]\", SUM('Camas'[Inhabilitadas])))"
          }
        ]
      },
      {
        "display_name": "Facturación",
        "queries": [
          {
            "query_id": "facturacion_data",
            "description": "Datos de facturación total",
            "dax": "EVALUATE SUMMARIZE(COLUMNS('Entidad'[Entidad], \"[TotFact]\", SUM('Facturacion'[Total])))"
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
    <title>Reporte {NOMBRE_REPORTE}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; text-align: center; }
        .content { margin: 20px 0; }
        .footer { background-color: #f0f0f0; padding: 10px; text-align: center; font-size: 12px; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Reporte {NOMBRE_REPORTE}</h1>
        <p>Fecha: {FECHA_GENERACION}</p>
    </div>
    
    <div class="content">
        <h2>📊 Resumen Ejecutivo</h2>
        <p>Este reporte muestra los indicadores clave de gestión para el día de hoy.</p>
        
        <h3>📈 Métricas Principales</h3>
        {TABLA_RESULTADOS}
        
        <h3>🔗 Acceso a Reportes</h3>
        <p>
            <a href="{POWERBI_REPORT_URL}">Reporte Principal</a> | 
            <a href="{POWERBI_REPORT_URL_2}">Reporte Secundario</a>
        </p>
    </div>
    
    <div class="footer">
        <p>Este reporte fue generado automáticamente el {FECHA_GENERACION} a las {HORA_ACTUAL}</p>
        <p>Para consultas, contacte al equipo de BI de San Rafael</p>
    </div>
</body>
</html>
```

## 🗂️ Estructura en la Base de Datos

Los archivos deben almacenarse en la base de datos con la siguiente estructura:

```
reports/
├── mi_reporte_personalizado/
│   ├── logic.py          # Lógica Python
│   ├── queries.json     # Consultas DAX
│   └── template.html    # Plantilla HTML
├── otro_reporte/
│   ├── logic.py
│   ├── queries.json
│   └── template.html
└── ...
```

## ⚙️ Configuración del Sistema

El archivo `system_config.json` debe especificar qué reporte ejecutar:

```json
{
  "reporte_a_ejecutar": "mi_reporte_personalizado",
  "URL_MI_REPORTE": "https://prod-03.eastus.logic.azure.com:443/workflows/...",
  "REPORT_ID": "...",
  "REPORT_ID_2": "..."
}
```

## 🔄 Flujo de Ejecución

1. **Engine** lee `system_config.json` para saber qué reporte ejecutar
2. **ReportManager** carga la lógica, consultas y plantilla del reporte
3. **QueryExecutor** ejecuta todas las consultas DAX en paralelo
4. **Lógica del Usuario** procesa los datos según sus necesidades
5. **Engine** reemplaza placeholders en la plantilla HTML
6. **Engine** envía el correo con el resultado final

## 📝 Variables Disponibles en la Plantilla

La plantilla HTML puede usar las siguientes variables:

- **Variables del Sistema**: `{POWERBI_REPORT_URL}`, `{POWERBI_REPORT_URL_2}`, `{FECHA_ACTUAL}`, `{HORA_ACTUAL}`
- **Variables del Reporte**: Todas las que devuelve la función `procesar_reporte()`
- **Variables Especiales**: `{AVATAR_SRC}` para el logo inline

## ✅ Buenas Prácticas

1. **Manejo de Errores**: Siempre usar try-except en la lógica
2. **Logging**: Usar `logger.info()` y `logger.error()` para seguimiento
3. **Validación**: Validar que los datos existan antes de procesarlos
4. **Performance**: Usar el `QueryExecutor` para consultas concurrentes
5. **Seguridad**: No incluir información sensible en el código
6. **Documentación**: Comentar las funciones principales

## 🚀 Ejemplo Completo

Para crear un nuevo reporte:

1. **Crear los 3 archivos** con la estructura mostrada
2. **Subirlos a la base de datos** en `reports/mi_reporte/`
3. **Actualizar `system_config.json`** con el nombre del reporte
4. **Ejecutar** el sistema con `ejecutar_automatizacion()`

El sistema se encargará automáticamente de:
- Cargar la lógica dinámicamente
- Ejecutar las consultas en paralelo
- Procesar los datos
- Generar el HTML
- Enviar el correo

¡Así de simple! 🎉
