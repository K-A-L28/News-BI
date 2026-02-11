# ====================================================== 
# Codigo desarrollado por Kevin Acevedo López
# Fecha: 2025-01-20 (copia de main, este codigo ya es completamente funcional)
# Descripción: Script para generar reportes diarios de Power BI desde Power Automate
# ====================================================== 
# Actualizacion hecha 25-01-2026:
# - Se arreglo el prompt de Gemini para que no genere confusion en el prompt

import io
import os
import msal
import json
import unicodedata
import base64
import logging
import requests
from PIL import Image
from datetime import datetime
from dotenv import load_dotenv
from babel.dates import format_date
import google.generativeai as genai
import concurrent.futures
from typing import Dict, List, Tuple, Any

# ======================================================
# CONFIGURACIÓN
# ======================================================

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración de autenticación
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Configuración de Power Automate para reporte 1 y reporte 2
PA_URL_CENSO = "https://default8e36c55d2d9f43179e94b407559453.28.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/f75efe1f34c946f897dc4573f6d6a6d3/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=nTzqI55sFttzvQg33kz0H8s6ilxpq7gtwhuk-5LbO9E"
PA_URL_CENSO_FACTURACION = "https://default8e36c55d2d9f43179e94b407559453.28.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/40ff227c02c548d68f49766a96d3ed8c/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=5DZ0qvX2_hZ3EvnelQ_7N07kDLdAGmf8YuHNSaJp2n0"
PA_URL_SATISFACCION = "https://default8e36c55d2d9f43179e94b407559453.28.environment.api.powerplatform.com/powerautomate/automations/direct/workflows/ac55b4a440f640ae9819f5b85a76e50f/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=tH6lR0sflFrak5mWnb_Gitw4fF5XBpmE-ab7U6PL1O0"

# Configuración de Gemini
GEMINI_API_KEY = [key.strip() for key in os.getenv('GEMINI_API_KEY', '').split(',') if key.strip()]
current_key_index = 0  # Inicializar el contador
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

# Configuración de correo
MAIL_SENDER = os.getenv('MAIL_SENDER')
MAIL_BCC = os.getenv('MAIL_BCC', '') # Todos los correos van en CCO
DESTINATARIOS_CCO = [email.strip() for email in MAIL_BCC.split(',') if email.strip()]

# URLs y constantes
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"

# Función para generar URL de Power BI Report Embed solo para adjuntar los enlaces de los reportes al correo
def build_report_url(report_id: str) -> str:
    """Genera URL de navegación para Power BI Report Embed."""
    return f"https://app.powerbi.com/reportEmbed?reportId={report_id}&autoAuth=true&ctid={TENANT_ID}" if report_id else ""

# URLs de los reportes
REPORT_URL="d65dcefc-49ed-43bf-a3b0-070e9886a403" # Reporte 1 (Censo de pacientes)
REPORT_URL_2="8bfea1ec-7f9d-4725-9369-03da53821cba" # Reporte 2 (Satisfacción)
    
# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

# ======================================================
# AUTENTICACIÓN
# ======================================================
def obtener_token(authority, client_id, client_secret, scope):
    """Obtiene un token de acceso para el servicio especificado."""
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        authority=authority,
        client_credential=client_secret
    )
    result = app.acquire_token_for_client(scopes=[scope])
    if "access_token" not in result:
        raise Exception(f"Error al obtener token: {result.get('error_description', 'Error desconocido')}")
    return result["access_token"]

#  Se obtiene el token para Microsoft Graph (para poder enviar el correo)
def obtener_token_graph():
    """Obtiene token para Microsoft Graph."""
    logger.info("Obteniendo token de Graph...")
    return obtener_token(AUTHORITY, CLIENT_ID, CLIENT_SECRET, GRAPH_SCOPE)

# ======================================================
# Manejo de cambio de llaves GEMINI
# ======================================================
def get_gemini_response(prompt_text):
    global current_key_index
    max_retries = len(GEMINI_API_KEY)
    
    for attempt in range(max_retries):
        try:
            # Configurar la clave actual
            genai.configure(api_key=GEMINI_API_KEY[current_key_index])
            model = genai.GenerativeModel(GEMINI_MODEL)
            
            # Intentar la generación
            response = model.generate_content(prompt_text)
            
            # Verificar si la respuesta es válida
            if not response or not hasattr(response, 'text') or not response.text:
                raise ValueError("La respuesta de la API no contiene texto")
                
            return response.text
            
        except Exception as e:
            logger.warning(f"Error con la clave API #{current_key_index + 1}: {str(e)}")
            
            # Intentar con la siguiente clave si es un error de cuota, límite o respuesta vacía
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["quota", "limit", "finish_reason", "part", "permission", "no contiene texto"]):
                current_key_index = (current_key_index + 1) % len(GEMINI_API_KEY)
                logger.info(f"Cambiando a la siguiente clave API (#{current_key_index + 1})")
                continue
                
            # Para otros errores, registrar y relanzar
            logger.error(f"Error inesperado: {str(e)}")
            raise
    
    raise Exception("Todas las claves API han fallado")

# ======================================================
# Optimización de imágenes
# ======================================================
def optimizar_imagen(ruta_imagen,ancho_max=800,calidad=85,preservar_alpha=True):
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

# ======================================================
# OBTENCION DE DATOS DEL PRIMER REPORTE (Censo de pacientes)
# ======================================================
def cargar_configuracion_censo(path='queryCenso.json'):
    """Lee y valida el archivo de configuración."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'report_config' not in config or 'pages' not in config['report_config']:
            raise ValueError("Estructura de configuración inválida")
        return config['report_config']['pages']
    except Exception as e:
        logger.error(f"❌ Error al cargar {path}: {str(e)}")
        return None

def consultar_api_dax(dax_query, url):
    """Maneja la comunicación HTTP con el endpoint DAX."""
    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={"dax_query": dax_query},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        
        logger.warning(f"⚠️ Error API: HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"❌ Error de red/petición: {str(e)}")
        return None

def ejecutar_consulta_concurrente(query_info: Tuple[str, str, str]) -> Tuple[str, Any]:
    """
    Función atómica para ejecutar una consulta DAX individualmente.
    Diseñada para ejecución concurrente.
    
    Args:
        query_info: Tupla (query_id, dax_query, url)
    
    Returns:
        Tupla (query_id, resultado_json)
    """
    query_id, dax_query, url = query_info
    try:
        resultado = consultar_api_dax(dax_query, url)
        return query_id, resultado
    except Exception as e:
        logger.error(f"❌ Error en consulta concurrente {query_id}: {str(e)}")
        return query_id, None

def obtener_datos_censo():
    """
    Versión concurrente de obtener_datos_censo.
    Ejecuta todas las consultas DAX en paralelo usando ThreadPoolExecutor.
    """
    logger.info("🔍 ...Obteniendo datos del censo...")
    resultados = {}
    
    pages = cargar_configuracion_censo()
    if not pages:
        return {}

    # Recolectar todas las consultas a ejecutar
    consultas = []
    for page in pages:
        page_name = page.get('display_name', 'sin_nombre')
        for query in page.get('queries', []):
            query_id = query.get('query_id')
            dax = query.get('dax', '')
            if query_id and dax:
                consultas.append((query_id, dax, PA_URL_CENSO))
    
    # Ejecutar consultas concurrentemente
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(consultas))) as executor:
        # Submit todas las consultas
        future_to_query = {
            executor.submit(ejecutar_consulta_concurrente, consulta): consulta[0] 
            for consulta in consultas
        }
        
        # Recolectar resultados
        for future in concurrent.futures.as_completed(future_to_query):
            query_id = future_to_query[future]
            try:
                resultado_query_id, resultado = future.result()
                if resultado:
                    # Encontrar a qué página pertenece esta consulta
                    for page in pages:
                        page_name = page.get('display_name', 'sin_nombre')
                        if page_name not in resultados:
                            resultados[page_name] = {}
                        if any(q.get('query_id') == resultado_query_id for q in page.get('queries', [])):
                            resultados[page_name][resultado_query_id] = resultado
                            logger.info(f"✔️ Datos obtenidos para {resultado_query_id} en {page_name}")
                            break
            except Exception as e:
                logger.error(f"❌ Error procesando resultado de {query_id}: {str(e)}")
    
    logger.info(f"✅ Datos de censo obtenidos correctamente")
    return resultados

# ANALISIS DE METRICAS DE OCUPACION Y ESTANCIA
def analizar_metricas_ocupacion(datos_censo):
    """
    Analiza métricas de ocupación. 
    Optimización: Usa un diccionario para inhabilitadas para evitar errores de búsqueda
    y asegura que los cálculos globales sean precisos.
    """
    metricas = {
        'promedio_ocupacion': 0,
        'promedio_estancia': 0,
        'sede_mayor_ocupacion': {'sedes': [], 'valor': -1},
        'sede_baja_ocupacion': {'sedes': [], 'valor': (0, 30)},
        'sede_eficiente_ocupacion': {'sedes': [], 'valor': (81, 90)},
        'sede_mayor_estancia': {'sedes': [], 'valor': -1}, 
        'camas_inhabilitadas': [], # Guardaremos la lista original aquí
        'sedes': {},
    }

    try:
        tablero = datos_censo.get('1 - Tablero Camas', {})
        grafica1_data = tablero.get('Grafica1', [])
        camas_data = tablero.get('Camas_inhabilitadas', [])

        # 1. Mapeo rápido de inhabilitadas (Evita el uso de next() que es lento y propenso a errores)
        map_inhabilitadas = {}
        for item in camas_data:
            ciudad = item.get('EstadoCamas[Ciudad]', '').strip().upper()
            if ciudad:
                map_inhabilitadas[ciudad] = int(item.get('[Inhabilitadas]', 0))
        
        # Mantener la estructura original para el reporte de inhabilitadas
        metricas['camas_inhabilitadas'] = [
            {'ciudad': c, 'inhabilitadas': v} for c, v in map_inhabilitadas.items()
        ]

        # 2. Procesamiento de sedes
        for item in grafica1_data:
            try:
                ciudad = item.get('Sedes[Ciudad]', '').strip().upper()
                nombre = item.get('Sedes[Sede]', '').strip().upper()
                if not ciudad or not nombre:
                    continue

                sede_key = f"{ciudad} - {nombre}"
                if sede_key in metricas['sedes']:
                    continue

                camas_ocupadas = int(item.get('[Cant_Pacientes]', 0))
                total_camas = int(item.get('[Cant_Camas]', 0))

                if total_camas <= 0:
                    continue

                # Cálculos por sede
                ocupacion = round((camas_ocupadas / total_camas) * 100)
                estancia = round(float(item.get('[Prom_Días_Estan]', 0)), 1)

                metricas['sedes'][sede_key] = {
                    'ocupacion': ocupacion,
                    'estancia': estancia,
                    'camas_ocupadas': camas_ocupadas,
                    'total_camas': total_camas,
                    'camas_inhabilitadas': map_inhabilitadas.get(ciudad, 0)
                }

                # Categorización de rangos (Inmediata)
                if 91 <= ocupacion <= 100:
                    metricas['sede_mayor_ocupacion']['sedes'].append(sede_key)
                elif 81 <= ocupacion <= 90:
                    metricas['sede_eficiente_ocupacion']['sedes'].append(sede_key)
                elif 0 <= ocupacion <= 30:
                    metricas['sede_baja_ocupacion']['sedes'].append(sede_key)

                # Lógica de mayor estancia
                if estancia > metricas['sede_mayor_estancia']['valor']:
                    metricas['sede_mayor_estancia'] = {'sedes': [sede_key], 'valor': estancia}
                elif estancia == metricas['sede_mayor_estancia']['valor'] and estancia != -1:
                    metricas['sede_mayor_estancia']['sedes'].append(sede_key)

            except (ValueError, TypeError, KeyError):
                continue

        # 3. Cálculos globales (Basados únicamente en los datos procesados)
        sedes_finales = metricas['sedes'].values()
        if sedes_finales:
            total_c = sum(s['total_camas'] for s in sedes_finales)
            total_o = sum(s['camas_ocupadas'] for s in sedes_finales)
            
            # Ocupación promedio real
            metricas['promedio_ocupacion'] = round((total_o / total_c * 100) if total_c > 0 else 0)

            # Estancia promedio ponderada (más precisa)
            suma_estancia_pond = sum(s['estancia'] * s['camas_ocupadas'] for s in sedes_finales)
            metricas['promedio_estancia'] = round((suma_estancia_pond / total_o) if total_o > 0 else 0, 1)

        logger.info(f"✅ Métricas analizadas: {len(metricas['sedes'])} sedes procesadas.")
        return metricas

    except Exception as e:
        logger.error(f"❌ Error crítico en análisis: {str(e)}", exc_info=True)
        return metricas

# Función auxiliar para formatear la lista de sedes
def formatear_sedes(sedes_list, datos_sedes, valor_por_defecto="", es_rango=False):
    # Si no hay sedes, no mostrar nada en el reporte
    if not sedes_list:
        return None

    # Para cada sede, obtener su valor específico
    sedes_con_valores = []
    for sede in sedes_list:
        if sede in datos_sedes:
            valor = datos_sedes[sede]['ocupacion']
            if es_rango:
                # Para rangos, mostramos el valor específico de la sede
                valor_texto = f"{valor}%"
            else:
                valor_texto = f"{valor}%"
            sedes_con_valores.append(f"{sede} ({valor_texto})")
    
    return ", ".join(sedes_con_valores) if sedes_con_valores else None

# Función especial para formatear sedes con estancia
def formatear_sedes_estancia(sedes_list, datos_sedes, valor_por_defecto=""):
    if not sedes_list: # Si no hay sedes, no mostrar nada en el reporte
        return None
    
    sedes_con_valores = []
    for sede in sedes_list:
        if sede in datos_sedes:
            estancia = datos_sedes[sede].get('estancia', 0)
            sedes_con_valores.append(f"{sede} ({estancia} días)")
    
    return ", ".join(sedes_con_valores) if sedes_con_valores else None

# Función especial para formatear sedes con camas inhabilitadas
def formatear_sedes_camas_inhabilitadas(camas_data, valor_por_defecto=""):
    """Formatea las camas inhabilitadas en el formato 'CIUDAD: X - CIUDAD2: Y'."""
    
    if not camas_data:
        return valor_por_defecto or "Ninguna cama inhabilitada"
    
    try:
        # Si es una lista de diccionarios
        if isinstance(camas_data, list):
            # Intentar extraer ciudad e inhabilitadas de cualquier formato
            camas = []
            for item in camas_data:
                if isinstance(item, dict):
                    # Formato 1: {'ciudad': 'PEREIRA', 'inhabilitadas': 93}
                    if 'ciudad' in item and 'inhabilitadas' in item:
                        camas.append(f"{item['ciudad']}({item['inhabilitadas']})")
                    # Formato 2: {'EstadoCamas[Ciudad]': 'PEREIRA', '[Inhabilitadas]': 93}
                    elif 'EstadoCamas[Ciudad]' in item and '[Inhabilitadas]' in item:
                        camas.append(f"{item['EstadoCamas[Ciudad]']}({item['[Inhabilitadas]']})")
            
            return " - ".join(camas) if camas else "Ninguna cama inhabilitada"
        
        return valor_por_defecto or "Ninguna cama inhabilitada"
        
    except Exception as e:
        logger.error(f"Error al formatear camas inhabilitadas: {str(e)}")
        return "Error al formatear datos de camas"

# ======================================================
# GENERACIÓN DE RESUMEN EJECUTIVO (Del primer reporte)
# ======================================================
def generar_resumen_ejecutivo(metricas_ocupacion):
    logger.info("🔍 ...Generando resumen...")
    """ Genera un resumen ejecutivo analítico basado en las métricas de ocupación.
    Siempre devuelve un string, incluso si hay errores con la API. """

    # Texto de respaldo en caso de error
    resumen_respaldo = """
    Análisis de ocupación hospitalaria:
    - Ocupación general: {}%
    - Sede con mayor ocupación: {} ({}%)
    - Sede con menor ocupación: {} ({}%)
    - Estancia promedio: {} días
    """.format(
        metricas_ocupacion.get('promedio_ocupacion', 'N/A'),
        ", ".join(metricas_ocupacion.get('sede_mayor_ocupacion', {}).get('sedes', ['Ninguna'])),
        metricas_ocupacion.get('sede_mayor_ocupacion', {}).get('valor', 'N/A'),
        ", ".join(metricas_ocupacion.get('sede_baja_ocupacion', {}).get('sedes', ['Ninguna'])),
        "0-30%",  # Como es un rango
        metricas_ocupacion.get('promedio_estancia', 'N/A')
    )

    try:
        # Verificar si hay datos para procesar
        if not metricas_ocupacion or 'sedes' not in metricas_ocupacion or not metricas_ocupacion['sedes']:
            logger.warning("No hay datos de ocupación para generar el resumen")
            return resumen_respaldo

        # Crear un prompt más estructurado
        prompt = f"""
        Eres un Consultor Senior de Estrategia Hospitalaria. Analiza estos datos y genera un resumen ejecutivo conciso (máximo 5 renglones) que destaque:
        
        1. Situación general de ocupación ({metricas_ocupacion.get('promedio_ocupacion', 0)}%)
        2. Comparación entre sedes (mayor y menor ocupación)
        3. Puntos de atención clave (estancias inusuales, etc.)
        4. Recomendación principal (si aplica)
        
        Datos:
        - Ocupación promedio: {metricas_ocupacion.get('promedio_ocupacion', 0)}%
        - Sede más ocupada: {", ".join(metricas_ocupacion.get('sede_mayor_ocupacion', {}).get('sedes', ['Ninguna']))} ({metricas_ocupacion.get('sede_mayor_ocupacion', {}).get('valor', 'N/A')}%)
        - Sede con baja ocupación: {", ".join(metricas_ocupacion.get('sede_baja_ocupacion', {}).get('sedes', ['Ninguna']))} (0-30%)
        - Estancia promedio: {metricas_ocupacion.get('promedio_estancia', 0)} días
        
        Resumen conciso:
        """

        # Obtener respuesta de Gemini
        respuesta = get_gemini_response(prompt)
        
        # Verificar que la respuesta sea válida
        if not respuesta or len(respuesta.strip()) < 20:  # Si es muy corta o vacía
            logger.warning("La respuesta de Gemini es muy corta o vacía")
            return resumen_respaldo
        
        logger.info(f"✅ Resumen ejecutivo generado exitosamente con Gemini")
        return respuesta.strip()

    except Exception as e:
        logger.error(f"Error al generar resumen ejecutivo: {str(e)}")
        return resumen_respaldo

def obtener_datos_facturacion():
    """
    Versión concurrente de obtener_datos_facturacion.
    Ejecuta todas las consultas de facturación en paralelo.
    """
    logger.info("🔍 ...Obteniendo datos de facturación...")
    resultados = {'facturacion': {'queries': {}}}
    
    pages = cargar_configuracion_censo('queryCensoFact.json') 
    if not pages:
        return resultados

    # Recolectar todas las consultas de facturación
    consultas_facturacion = []
    for page in pages:
        if page.get('page_id', '').lower() != 'facturacion':
            continue
            
        for query in page.get('queries', []):
            query_id = query.get('query_id', '')
            dax_query = query.get('dax', '')
            
            if query_id and dax_query:
                consultas_facturacion.append({
                    'query_id': query_id,
                    'dax': dax_query,
                    'description': query.get('description', ''),
                    'page': page
                })
    
    # Ejecutar consultas concurrentemente
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(consultas_facturacion))) as executor:
        # Submit todas las consultas
        future_to_query = {
            executor.submit(ejecutar_consulta_concurrente, (q['query_id'], q['dax'], PA_URL_CENSO_FACTURACION)): q 
            for q in consultas_facturacion
        }
        
        # Recolectar resultados
        for future in concurrent.futures.as_completed(future_to_query):
            query_info = future_to_query[future]
            try:
                resultado_query_id, resultado = future.result()
                if resultado:
                    resultados['facturacion']['queries'][resultado_query_id] = {
                        'description': query_info['description'],
                        'dax': query_info['dax'],
                        'data': resultado
                    }
                    logger.info(f"✔️ Datos de facturación obtenidos para {resultado_query_id}")
            except Exception as e:
                logger.error(f"❌ Error en consulta de facturación {query_info['query_id']}: {str(e)}")

    logger.info(f"✅ Datos de facturación obtenidos correctamente")
    return resultados

# Función auxiliar para formatear valores monetarios
def formato_monetario(valor):
    """Formatea un valor numérico como moneda."""
    try:
        if valor is None:
            return "$0"
                    
        # Si el valor es un string, intentar convertirlo a float
        if isinstance(valor, str):
            # Si el string está vacío o es solo espacios
            if not valor.strip():
                return "$0"
            try:
                # Reemplazar comas por puntos y eliminar caracteres no numéricos excepto punto y signo negativo
                valor_limpio = ''.join(c for c in valor if c.isdigit() or c in '.-')
                if not valor_limpio:  # Si después de limpiar no queda nada
                    return "$0"
                valor_float = float(valor_limpio)
            except ValueError:
                logger.error(f"No se pudo convertir a float: {valor}")
                return "$0"
        else:
            valor_float = float(valor)
                    
        # Formatear con separador de miles y sin decimales
        return f"${valor_float:,.0f}".replace(",", ".")
                
    except Exception as e:
        logger.error(f"Error formateando valor monetario '{valor}': {str(e)}")
        return "$0"

# =========================================================================================================================================================================
# GENERACIÓN DE TABLA CONSOLIDADA (se une la información de ocupación y facturación)
# =========================================================================================================================================================================

# Funciones auxiliares para estilos de ocupación
def _obtener_estilo_ocupacion(ocupacion):
    """Lógica atómica para decidir el color del semáforo de ocupación."""
    estilo = "text-align: center;"
    if ocupacion <= 30: return estilo + " background-color: #f8d7da;"
    if ocupacion <= 80: return estilo + " background-color: #D1FFE4;"
    if ocupacion <= 90: return estilo + " background-color: #cce5ff; font-weight: bold;"
    return estilo + " background-color: #d4edda; font-weight: bold;"
#  Función auxiliar para estilos de estancia
def _obtener_estilo_estancia(estancia):
    """Lógica atómica para decidir alertas de estancia."""
    estilo = "text-align: center;"
    if estancia >= 10: return estilo + " color: #dc3545; font-weight: bold; background-color: #f8d7da; border: 2px solid #dc3545;"
    if estancia >= 7: return estilo + " color: #dc3545; font-weight: bold; background-color: #f8d7da;"
    return estilo

# Funciones auxiliares para procesar facturación
def _procesar_totales_facturacion(datos_facturacion, sedes_ocupacion_keys):
    """Extrae la lógica de negocio de sumar dinero y mapear sedes."""
    mapeo_sedes = {
        'MEGACENTRO': 'PEREIRA - MEGACENTRO', 'CASA DE ESPECIALISTAS': 'PEREIRA - MEGACENTRO',
        'K16': 'ARMENIA - K16', 'NOGALES DEL PARQUE': 'ARMENIA - K16', 'CUBA': 'PEREIRA - CUBA'
    }
    totales = {sede: 0.0 for sede in sedes_ocupacion_keys}
    
    queries = datos_facturacion.get('facturacion', {}).get('queries', {})
    data = queries.get('Facturacion total por sede en tiempo real', {}).get('data', [])

    for item in data:
        sede_fact = item.get('Sedes[Sede]', '').strip().upper()
        if sede_fact in mapeo_sedes:
            sede_destino = mapeo_sedes[sede_fact]
            if sede_destino in totales:
                totales[sede_destino] += float(item.get('[Facturacion Total]', 0) or 0)
    return totales

# Función principal para generar la tabla consolidada
def generar_tabla_consolidada(metricas_ocupacion, datos_facturacion):
    """Función Orquestadora: Solo une los puntos y genera el HTML."""
    if not metricas_ocupacion or 'sedes' not in metricas_ocupacion:
        return "<tr><td colspan='5'>No hay datos de ocupación disponibles</td></tr>"

    sedes_data = metricas_ocupacion['sedes']
    facturacion_por_sede = _procesar_totales_facturacion(datos_facturacion, sedes_data.keys())
    
    filas = []
    for sede, datos in sedes_data.items():
        total_money = formato_monetario(facturacion_por_sede.get(sede, 0))
        
        # Invocamos las pequeñas funciones atómicas de estilos
        estilo_ocp = _obtener_estilo_ocupacion(datos.get('ocupacion', 0))
        estilo_est = _obtener_estilo_estancia(datos.get('estancia', 0))

        fila = f"""
        <tr>
            <td style="padding: 10px; border-right: 1px solid #f1f5f9;">{sede}</td>
            <td style="padding: 10px; border-right: 1px solid #f1f5f9; {estilo_ocp}">{datos.get('ocupacion')}%</td>
            <td style="padding: 10px; border-right: 1px solid #f1f5f9; {estilo_est}">{datos.get('estancia')} días</td>
            <td style="padding: 10px; border-right: 1px solid #f1f5f9; text-align: center;">{datos.get('camas_ocupadas')}/{datos.get('total_camas')}</td>
            <td style="padding: 10px; text-align: right;">{total_money}</td>
        </tr>
        """
        filas.append(fila)

    logger.info(" ✅ Generación de tabla de consolidada (datos censo y facturación) exitosa")
    return '\n'.join(filas) if filas else "<tr><td colspan='5'>Sin datos</td></tr>"

# Función para extraer datos de aseguradoras
def _extraer_top_aseguradoras(datos_facturacion):
    """
    Extrae y limpia los datos del JSON. 
    """
    try:
        queries = datos_facturacion.get('facturacion', {}).get('queries', {})
        data = queries.get('TOP 10 Facturacion por aseguradora en tiempo real', {}).get('data', [])
        
        # Devolvemos una lista de diccionarios con nombres de llaves amigables
        return [{
            'entidad': item.get('Entidad[Entidad]', 'N/A'),
            'tipo': item.get('RG_ActProf[Tipo]', 'N/A'),
            'valor': item.get('[TotFact]', 0)
        } for item in data]
    except Exception as e:
        logger.error(f"Error extrayendo datos de aseguradoras: {e}")
        return []
# FUnción para consolidar en una tabla todas las aseguradoras en una sola
def generar_tabla_aseguradoras(datos_facturacion):
    """
    Genera el HTML.
    """
    aseguradoras = _extraer_top_aseguradoras(datos_facturacion)
    
    if not aseguradoras:
        return "<tr><td colspan='3' style='text-align: center;'>No hay datos de aseguradoras disponibles</td></tr>"

    filas = []
    for asig in aseguradoras:
        estilo_fila = "font-weight: normal;" if "PGP" in asig['tipo'].upper() else ""
        
        filas.append(f"""
            <tr style="{estilo_fila}">
                <td style="padding: 8px; border-right: 1px solid #ddd; text-align: left;">{asig['entidad']}</td>
                <td style="padding: 8px; border-right: 1px solid #ddd; text-align: left;">{asig['tipo']}</td>
                <td style="padding: 8px; text-align: right;">{formato_monetario(asig['valor'])}</td>
            </tr>
        """)

    logger.info(" ✅ Generación de tabla de aseguradoras exitosa")
    return '\n'.join(filas)
    
# =========================================================================================================================================================================
# OBTENCIÓN DE DATOS DE SATISFACCIÓN (Segundo reporte)
# =========================================================================================================================================================================
# Función para cargar configuración
def cargar_configuracion(path='queriesSatisfaccion.json'):
    """Carga y valida la configuración desde un archivo JSON."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'report_config' not in config or 'pages' not in config['report_config']:
            raise ValueError("Estructura de configuración inválida")
        return config['report_config']['pages']
    except Exception as e:
        logger.error(f"❌ Error en configuración: {str(e)}")
        return []

# Función para ejecutar query
def ejecutar_query(dax):
    """Ejecuta una consulta DAX contra el endpoint y devuelve el resultado JSON."""
    try:
        response = requests.post(
            PA_URL_SATISFACCION,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={"dax_query": dax},
            timeout=30
        )         
        return response.json() if response.status_code == 200 else None
    except Exception:
        return None

# Función para procesar KPI global
def procesar_kpi_global(resultados, ciudad_key, result):
    try:
        valor = float(result[0]['[Value]'].replace(',', '.')) * 100
        resultados[ciudad_key]['satisfaccion_global'] = f"{valor:.1f}%"
    except (KeyError, IndexError, ValueError):
        pass

# Función para procesar encuestas
def procesar_encuestas(resultados, ciudad_key, result):
    try:
        resultados[ciudad_key]['total_encuestas'] = result[0]['[total_encuestas]']
    except (KeyError, IndexError):
        pass

# Función para procesar NPS
def procesar_nps(resultados, ciudad_key, result):
    try:
        nps_items = []
        for item in result:
            if isinstance(item, dict):
                categoria_key = next((k for k in item.keys() if 'recomendaria' in k.lower()), None)
                if categoria_key:
                    porcentaje_str = item.get('[PctRecomendariaPct]', '0').replace(',', '.')
                    porcentaje = float(porcentaje_str) if porcentaje_str else 0
                    nps_items.append(f"{porcentaje:.2f}%")
        resultados[ciudad_key]['nps'] = "  -  ".join(nps_items) if nps_items else "N/A"
    except Exception:
        pass
# Función para procesar indicadores
def procesar_indicadores(resultados, ciudad_key, result):
    try:
        indicadores = []
        for item in result:
            if isinstance(item, dict):
                categoria = item.get('[Categoria]', 'Indicador')
                pct_bien = item.get('[PctBien]', '0')
                pct_mala = item.get('[PctMala]', '0')

                try:
                    pct_bien = f"{float(pct_bien.replace(',', '.')):.2f}%" if pct_bien else '0.00%'
                    pct_mala = f"{float(pct_mala.replace(',', '.')):.2f}%" if pct_mala else '0.00%'
                except (ValueError, TypeError):
                    pct_bien, pct_mala = '0.00%', '0.00%'

                var_prefix = ''.join(c for c in unicodedata.normalize('NFD', categoria.upper())
                                     if unicodedata.category(c) != 'Mn').split()[0]
                var_prefix = var_prefix.replace('Ó','O').replace('É','E').replace('Í','I')\
                                       .replace('Á','A').replace('Ú','U').replace('Ñ','N')

                resultados[ciudad_key][f"{var_prefix}_BIEN"] = pct_bien
                resultados[ciudad_key][f"{var_prefix}_MALA"] = pct_mala

                indicadores.append(
                    f"<div style='margin-bottom: 5px;'><strong>{categoria}:</strong><br>"
                    f"<ul style='list-style: none; margin: 4px 0 0 0; padding: 0;'>"
                    f"<li>- Bien: <span style='color: #2ecc71;'>{pct_bien}</span></li>"
                    f"<li>- Mala: <span style='color: #e74c3c;'>{pct_mala}</span></li>"
                    f"</ul></div>"
                )
        resultados[ciudad_key]['indicadores_satisfaccion'] = "".join(indicadores) if indicadores else "N/A"
    except Exception:
        pass

# Función para obtener datos de satisfacción
def ejecutar_query_satisfaccion(query_info: Tuple[str, str]) -> Tuple[str, Any]:
    """
    Función atómica para ejecutar una consulta de satisfacción individualmente.
    Diseñada para ejecución concurrente.
    
    Args:
        query_info: Tupla (query_id, dax)
    
    Returns:
        Tupla (query_id, resultado_json)
    """
    query_id, dax = query_info
    try:
        result = ejecutar_query(dax)
        return query_id, result
    except Exception as e:
        logger.error(f"❌ Error en consulta de satisfacción concurrente {query_id}: {str(e)}")
        return query_id, None

def obtener_datos_satisfaccion():
    """
    Versión concurrente de obtener_datos_satisfaccion.
    Ejecuta todas las consultas de satisfacción en paralelo.
    """
    logger.info("🔍 ...Obteniendo datos de satisfacción...")
    resultados = {"Pereira": {}, "Armenia": {}}
    
    pages = cargar_configuracion()
    if not pages:
        return resultados

    # Recolectar todas las consultas de satisfacción por ciudad
    consultas_por_ciudad = {"Pereira": [], "Armenia": []}
    
    for page in pages:
        ciudad = page.get('display_name', '').lower()
        ciudad_key = 'Pereira' if 'pereira' in ciudad else 'Armenia' if 'armenia' in ciudad else None
        if not ciudad_key:
            continue

        # Inicializar estructura para la ciudad
        resultados[ciudad_key] = {
            'satisfaccion_global': 'N/A',
            'total_encuestas': 'N/A',
            'nps': 'N/A',
            'indicadores_satisfaccion': 'N/A'
        }

        # Recolectar consultas para esta ciudad
        for q in page.get('queries', []):
            q_id = q.get('query_id')
            dax = q.get('dax', '')
            if q_id and dax:
                consultas_por_ciudad[ciudad_key].append({
                    'query_id': q_id,
                    'dax': dax,
                    'ciudad_key': ciudad_key
                })

    # Ejecutar consultas concurrentemente por ciudad
    for ciudad_key, consultas in consultas_por_ciudad.items():
        if not consultas:
            continue
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(consultas))) as executor:
            # Preparar tuplas para ejecución
            query_tuples = [(q['query_id'], q['dax']) for q in consultas]
            
            # Submit todas las consultas
            future_to_query = {
                executor.submit(ejecutar_query_satisfaccion, query_tuple): consultas[i]
                for i, query_tuple in enumerate(query_tuples)
            }
            
            # Recolectar resultados
            for future in concurrent.futures.as_completed(future_to_query):
                query_info = future_to_query[future]
                try:
                    resultado_query_id, resultado = future.result()
                    if resultado:
                        # Procesar el resultado según el tipo de query
                        if resultado_query_id.startswith('KPI-Global-bien'):
                            procesar_kpi_global(resultados, ciudad_key, resultado)
                        elif resultado_query_id.startswith('encuesta'):
                            procesar_encuestas(resultados, ciudad_key, resultado)
                        elif resultado_query_id.startswith('nps'):
                            procesar_nps(resultados, ciudad_key, resultado)
                        elif resultado_query_id.startswith('indicadores'):
                            procesar_indicadores(resultados, ciudad_key, resultado)
                        
                        logger.info(f"✔️ Datos de satisfacción obtenidos para {resultado_query_id} en {ciudad_key}")
                except Exception as e:
                    logger.error(f"❌ Error procesando resultado de {query_info['query_id']}: {str(e)}")

    for ciudad, datos in resultados.items():
        if datos:
            logger.info(f"✅ Datos de satisfacción de {ciudad} obtenidos exitosamente")
    return resultados

# ======================================================
# ENVÍO DE CORREO ELECTRÓNICO
# ======================================================
def enviar_correo(datos_analisis, token_graph):
    """Envía un correo con el análisis generado."""
    try:
        if not MAIL_SENDER or not DESTINATARIOS_CCO:
            logger.warning("⚠️ No se configuró remitente o destinatarios")
            return

        # Cargar plantilla HTML
        try:
            with open("./template/report_template.html", "r", encoding='utf-8') as f:
                html_final = f.read()

            # Reemplazar placeholders (aseguramos URL con & escapado para HTML)
            datos_template = {
                **datos_analisis,
                'POWERBI_REPORT_URL': REPORT_URL.replace('&', '&amp;') if REPORT_URL else "",
                'POWERBI_REPORT_URL_2': REPORT_URL_2.replace('&', '&amp;') if REPORT_URL_2 else ""
            }

            # Reemplazar placeholders en el HTML básico
            for key, value in datos_template.items():
                html_final = html_final.replace(f"{{{key.upper()}}}", str(value))

            # # Insertar el mensaje personalizado al inicio del HTML
            # mensaje_personalizado = "Buen día, espero que se encuentren muy bien. Adjunto el reporte actualizado con la información financiera del mes en curso de las sedes y aseguradoras. <br><br>Quedo atento a sus comentarios por si requieren algún ajuste o corrección."
            # html_final = f"<p>{mensaje_personalizado}</p>" + html_final

        except FileNotFoundError:
            logger.error("Error al cargar plantilla: template/report_template.html no encontrado")
            html_final = "<h1>Error: Archivo de plantilla no encontrado</h1>"

        attachments: list[dict] = []

        # Avatar inline
        avatar_path = "./template/images/avatar_logo.png"
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

        # -----------------------------
        # Payload del correo
        # -----------------------------
        payload = {
            "message": {
                "subject": f"Reporte de Gestión - {datetime.now().strftime('%d/%m/%Y')}",
                "body": {
                    "contentType": "html",
                    "content": html_final
                },
                "toRecipients": [],
                "bccRecipients": [{"emailAddress": {"address": email}} for email in DESTINATARIOS_CCO] if DESTINATARIOS_CCO else [],
                "attachments": attachments
            },
            "saveToSentItems": False
        }
        # -----------------------------
        # Envío vía Graph
        # -----------------------------
        logger.info(f"Enviando correo desde {MAIL_SENDER} a todos los destinatarios en CCO...")
        url = f"https://graph.microsoft.com/v1.0/users/{MAIL_SENDER}/sendMail"
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

#=======================================================    
# EJECUCIÓN PRINCIPAL
# ======================================================
def ejecutar_automatizacion(): 
    """Función principal que ejecuta todo el flujo de automatización."""
    try:
        logger.info("🚀 Iniciando San Rafael BI Daily Insights...")
        
        # Obtener token (operación secuencial necesaria)
        logger.info("🔑 Obteniendo token de autenticación...")
        token_graph = obtener_token_graph()
        
        # Ejecutar todas las llamadas API concurrentemente
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit todas las tareas de obtención de datos
            future_censo = executor.submit(obtener_datos_censo)
            future_facturacion = executor.submit(obtener_datos_facturacion)
            future_satisfaccion = executor.submit(obtener_datos_satisfaccion)
            
            # Recolectar resultados
            datos_censo = future_censo.result()
            datos_facturacion = future_facturacion.result()
            datos_satisfaccion = future_satisfaccion.result()
        
        # Procesamiento de datos (secuencial, depende de los resultados)
        logger.info("📊 Analizando métricas de ocupación...")
        metricas = analizar_metricas_ocupacion(datos_censo)

        logger.info("📊 Generando tabla consolidada...")
        tabla_consolidada = generar_tabla_consolidada(metricas, datos_facturacion)

        logger.info("📊 Generando tabla de aseguradoras...")
        tabla_aseguradoras = generar_tabla_aseguradoras(datos_facturacion)

        # Generar resumen ejecutivo con Gemini
        logger.info("🤖 Generando resumen con Gemini...")
        resumen_ejecutivo = generar_resumen_ejecutivo(metricas)
        # resumen_ejecutivo = ""
        
        # Extraer datos de satisfacción por ciudad
        datos_satisfaccion_pereira = datos_satisfaccion.get('Pereira', {})
        datos_satisfaccion_armenia = datos_satisfaccion.get('Armenia', {})

        # Crear estructura de datos para el análisis
        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
        datos_analisis = {
            # Diferentes formas de mostrar la fecha: fecha completa (DD/MM/AA), fecha explícita (mes y año), mes
            "FECHA": fecha_actual,
            "FECHA_EXPLICITA" : format_date(datetime.now(),format="MMMM yyyy",locale="es").capitalize(),
            "MES": format_date(datetime.now(),format="MMMM",locale="es").capitalize(),

            "RESUMEN_EJECUTIVO": resumen_ejecutivo,
            "PROMEDIO_OCUPACION": metricas.get('promedio_ocupacion', 0),
            "PROMEDIO_ESTANCIA": metricas.get('promedio_estancia', 0),
            "CAMAS_INHABILITADAS": formatear_sedes_camas_inhabilitadas(metricas.get('camas_inhabilitadas', {})),
            # Tabla para consolidar ocupación y facturación
            "TABLA_HTML_OCUPACION_Y_FACTURACION": tabla_consolidada,
            # Tablas para mostrar top aseguradoras
            "TABLA_HTML_ASEGURADORAS": tabla_aseguradoras
        }
            
        # Alertas (generar bloques HTML completos solo si hay valores)
        alerta_alta = formatear_sedes(
            metricas.get('sede_mayor_ocupacion', {}).get('sedes', []),
            metricas.get('sedes', {}),
            'alta'
        )
        alerta_baja = formatear_sedes(
            metricas.get('sede_baja_ocupacion', {}).get('sedes', []),
            metricas.get('sedes', {}),
            'baja',
            es_rango=True
        )
        alerta_estancia = formatear_sedes_estancia(
            metricas.get('sede_mayor_estancia', {}).get('sedes', []),
            metricas.get('sedes', {}),
            'N/A'
        )
        
        # Generar bloques HTML completos para alertas
        bloque_alerta_alta = ""
        if alerta_alta:
            bloque_alerta_alta = f"""
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
                                    <td width="16" height="16" bgcolor="#ef4444"
                                      style="border-radius: 50%; font-size: 1px; line-height: 1px;">&nbsp;</td>
                                  </tr>
                                </table>
                              </td>
                              <td
                                style="font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; color: #E63946; line-height: 1.5;">
                                Alta Ocupación: <span
                                  style="font-weight: normal; font-size: 13px; color: #E63946;">{alerta_alta}</span>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>"""
        
        bloque_alerta_baja = ""
        if alerta_baja:
            bloque_alerta_baja = f"""
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
                                    <td width="16" height="16" bgcolor="#f59e0b"
                                      style="border-radius: 50%; font-size: 1px; line-height: 1px;">&nbsp;</td>
                                  </tr>
                                </table>
                              </td>
                              <td
                                style="font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; color: #F59E0B; line-height: 1.5;">
                                Baja Ocupación: <span
                                  style="font-weight: normal; font-size: 13px; color: #F59E0B;">{alerta_baja}</span>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                      <tr>
                        <td height="20" style="font-size:1px; line-height:1px;">&nbsp;</td>
                      </tr>"""
        
        bloque_alerta_estancia = ""
        if alerta_estancia:
            bloque_alerta_estancia = f"""
                      <tr>
                        <td bgcolor="#FEF2F2" style="padding: 12px 16px; border-radius: 6px;">
                          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                            <tr>
                              <td width="32" valign="middle">
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                  <tr>
                                    <td width="20" height="20" bgcolor="#ef4444"
                                      style="border-radius: 50%; font-size: 1px; line-height: 1px;">&nbsp;</td>
                                  </tr>
                                </table>
                              </td>
                              <td
                                style="font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; color: #E63946; line-height: 1.5;">
                                Estancia Prolongada: <span
                                  style="font-weight: normal; font-size: 13px; color: #E63946;">{alerta_estancia}</span>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>"""
            
        # Agregar bloques de alertas al diccionario
        datos_analisis["BLOQUE_ALERTA_ALTA"] = bloque_alerta_alta
        datos_analisis["BLOQUE_ALERTA_BAJA"] = bloque_alerta_baja
        datos_analisis["BLOQUE_ALERTA_ESTANCIA"] = bloque_alerta_estancia
            
        # Añadir datos de satisfacción
        if datos_satisfaccion_pereira:
            # Asegurarse de que todas las claves estén en mayúsculas
            datos_satisfaccion_pereira = {k.upper(): v for k, v in datos_satisfaccion_pereira.items()}

            datos_analisis.update({
                "SATISFACCION_PEREIRA": datos_satisfaccion_pereira.get("SATISFACCION_GLOBAL", "N/A"),
                "NPS_PEREIRA": datos_satisfaccion_pereira.get("NPS", "N/A"),
                "TOTAL_ENCUESTAS_PEREIRA": datos_satisfaccion_pereira.get("TOTAL_ENCUESTAS", "N/A"),
                # Se obtiene los indicadores de manera individual debido al diseño de la plantilla
                "INDICADORES_PEREIRA": datos_satisfaccion_pereira.get("INDICADORES_SATISFACCION", "N/A"),
                "ACTITUD_BIEN_PEREIRA": datos_satisfaccion_pereira.get("ACTITUD_BIEN", "0.00%"),
                "ACTITUD_MALA_PEREIRA": datos_satisfaccion_pereira.get("ACTITUD_MALA", "0.00%"),
                "COMUNICACION_BIEN_PEREIRA": datos_satisfaccion_pereira.get("COMUNICACIÓN_BIEN") or datos_satisfaccion_pereira.get("COMUNICACION_BIEN") or datos_satisfaccion_pereira.get("COMUNICACIÓN_Y_TRANSPARENCIA_BIEN", "0.00%"),
                "COMUNICACION_MALA_PEREIRA": datos_satisfaccion_pereira.get("COMUNICACIÓN_MALA") or datos_satisfaccion_pereira.get("COMUNICACION_MALA") or datos_satisfaccion_pereira.get("COMUNICACIÓN_Y_TRANSPARENCIA_MALA", "0.00%"),
                "EXCELENCIA_BIEN_PEREIRA": datos_satisfaccion_pereira.get("EXCELENCIA_BIEN", "0.00%"),
                "EXCELENCIA_MALA_PEREIRA": datos_satisfaccion_pereira.get("EXCELENCIA_MALA", "0.00%"),
                "RESPETO_BIEN_PEREIRA": datos_satisfaccion_pereira.get("RESPETO_BIEN", "0.00%"),
                "RESPETO_MALA_PEREIRA": datos_satisfaccion_pereira.get("RESPETO_MALA", "0.00%")
            })
            
        if datos_satisfaccion_armenia:
            # Asegurarse de que todas las claves estén en mayúsculas
            datos_satisfaccion_armenia = {k.upper(): v for k, v in datos_satisfaccion_armenia.items()}

            datos_analisis.update({
                "SATISFACCION_ARMENIA": datos_satisfaccion_armenia.get("SATISFACCION_GLOBAL", "N/A"),
                "NPS_ARMENIA": datos_satisfaccion_armenia.get("NPS", "N/A"),
                "TOTAL_ENCUESTAS_ARMENIA": datos_satisfaccion_armenia.get("TOTAL_ENCUESTAS", "N/A"),
                # Se obtiene los indicadores de manera individual debido al diseño de la plantilla
                "INDICADORES_ARMENIA": datos_satisfaccion_armenia.get("INDICADORES_SATISFACCION", "N/A"),
                "ACTITUD_BIEN_ARMENIA": datos_satisfaccion_armenia.get("ACTITUD_BIEN", "0.00%"),
                "ACTITUD_MALA_ARMENIA": datos_satisfaccion_armenia.get("ACTITUD_MALA", "0.00%"),
                "COMUNICACION_BIEN_ARMENIA": datos_satisfaccion_armenia.get("COMUNICACIÓN_BIEN") or datos_satisfaccion_armenia.get("COMUNICACION_BIEN") or datos_satisfaccion_armenia.get("COMUNICACIÓN_Y_TRANSPARENCIA_BIEN", "0.00%"),
                "COMUNICACION_MALA_ARMENIA": datos_satisfaccion_armenia.get("COMUNICACIÓN_MALA") or datos_satisfaccion_armenia.get("COMUNICACION_MALA") or datos_satisfaccion_armenia.get("COMUNICACIÓN_Y_TRANSPARENCIA_MALA", "0.00%"),
                "EXCELENCIA_BIEN_ARMENIA": datos_satisfaccion_armenia.get("EXCELENCIA_BIEN", "0.00%"),
                "EXCELENCIA_MALA_ARMENIA": datos_satisfaccion_armenia.get("EXCELENCIA_MALA", "0.00%"),
                "RESPETO_BIEN_ARMENIA": datos_satisfaccion_armenia.get("RESPETO_BIEN", "0.00%"),
                "RESPETO_MALA_ARMENIA": datos_satisfaccion_armenia.get("RESPETO_MALA", "0.00%")
            })

        # Enviar correo con los datos
        logger.info("📤 Enviando correo con el análisis...")
        enviar_correo(datos_analisis, token_graph)
        logger.info("✅ Proceso concurrente completado exitosamente.")
                
    except Exception as e:
        logger.error(f"❌ Error en la ejecución concurrente: {str(e)}", exc_info=True)

if __name__ == "__main__":
    ejecutar_automatizacion()