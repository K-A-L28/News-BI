# ====================================================== 
# AUTOMATIZACIÓN DE POWER BI (Script creado por Kevin Acevedo Lopez)
# ====================================================== 
# Codigo optimizado, este codigo no depende tanto de gemini, usa una plantilla html para enviar el correo y le pide a gemini que pase los datos para ponerlo en la plantilla
import os
import io
import base64
from PIL import Image
import json
import logging
import requests
import msal
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import concurrent.futures
from typing import Dict, List, Tuple, Any

# ======================================================
# CONFIGURACIÓN
# ======================================================

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# SOlo para mostrar los logger en consola
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
#SOlo para casos de verificar en consola lo valores que se van obteniendo
# logger.setLevel(logging.DEBUG)

# Cargar variables de entorno
load_dotenv()

# Configuración de autenticación
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Configuración de Power BI
WORKSPACE_ID = os.getenv("WORKSPACE_ID")
REPORT_ID = os.getenv("REPORT_ID")

# Configuración de Gemini
GEMINI_API_KEY = [key.strip() for key in os.getenv('GEMINI_API_KEY', '').split(',') if key.strip()]
current_key_index = 0  # Inicializar el contador
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")

# Configuración de correo
MAIL_SENDER = os.getenv('MAIL_SENDER')
MAIL_BCC = os.getenv('MAIL_BCC', '')
DESTINATARIOS = [email.strip() for email in MAIL_BCC.split(',') if email.strip()]

# URLs y constantes
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
REPORT_URL = f"https://app.powerbi.com/reportEmbed?reportId={REPORT_ID}&autoAuth=true&ctid={TENANT_ID}" #URL del reporte de censo de Medicadiz
PA_URL_CENSO="https://default8e36c55d2d9f43179e94b407559453.28.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/5a18aa441d5448dab2aec519e9f04fe1/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=DaLKqsmB3cmwgFAgQ4VAg0hnIDlp_cRtJc03xhoc7Kw"
PA_URL_FACTURACION="https://default8e36c55d2d9f43179e94b407559453.28.environment.api.powerplatform.com/powerautomate/automations/direct/workflows/c8adb322cdbd4a62a3df030912b0ebd6/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=K5AfdTDnkXYZ_C4DhIFR4w_aaJFCZN5WdN7OR_zpMo0"


# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

# ======================================================
# AUTENTICACIÓN
# ======================================================

#  Se obtiene el token para Microsoft Graph (para poder enviar el correo)
def obtener_token_graph():
    """Obtiene token para Microsoft Graph."""
    logger.info("Obteniendo token de Graph...")
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=[GRAPH_SCOPE])
    if "access_token" not in result:
        raise Exception(f"Error al obtener token: {result.get('error_description', 'Error desconocido')}")
    return result["access_token"]

# ======================================================
# FUNCIONES CENSO HOSPITALARIO (Atomizadas para queries.json)
# ======================================================

# Función para cargar configuración de censo
def cargar_configuracion_censo(path='queries.json'):
    """Carga y valida la configuración desde el archivo JSON de censo."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'report_config' not in config or 'pages' not in config['report_config']:
            raise ValueError("Estructura de configuración de censo inválida")
        return config['report_config']
    except Exception as e:
        logger.error(f"❌ Error en configuración de censo: {str(e)}")
        return {}

# Función para ejecutar query de censo (thread-safe)
def ejecutar_query_censo(dax: str) -> Tuple[str, Any]:
    """Ejecuta una consulta DAX de censo contra el endpoint de Power Automate y devuelve el resultado JSON."""
    try:
        response = requests.post(
            PA_URL_CENSO,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={"dax_query": dax},
            timeout=30
        )
        return ("success", response.json() if response.status_code == 200 else None)
    except Exception as e:
        logger.error(f"❌ Error ejecutando query de censo: {str(e)}")
        return ("error", None)

# Función para procesar Total Pacientes
def procesar_total_pacientes(full_context, result):
    """Procesa el resultado de Total Pacientes."""
    try:
        if result and len(result) > 0:
            total = result[0].get('total_pacientes', 0)
            full_context += f"\nDatos Total_Pacientes:\nTotal de pacientes: {total}\n"
        else:
            full_context += f"\nDatos Total_Pacientes:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Total Pacientes: {str(e)}")
        full_context += f"\nDatos Total_Pacientes:\nError en el procesamiento\n"
    return full_context

# Función para procesar Porcentaje Ocupación Global
def procesar_porcentaje_ocupacion_global(full_context, result):
    """Procesa el resultado de Porcentaje Ocupación Global."""
    try:
        if result and len(result) > 0:
            total = result[0].get('porcentaje_ocupacion_global', 0)
            full_context += f"\nDatos Porcentaje_Ocupacion_Global: {total}\n"
        else:
            full_context += f"\nDatos Porcentaje_Ocupacion_Global:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Porcentaje Ocupación Global: {str(e)}")
        full_context += f"\nDatos Porcentaje_Ocupacion_Global:\nError en el procesamiento\n"
    return full_context

# Función para procesar Resumen Pisos
def procesar_resumen_pisos(full_context, result):
    """Procesa el resultado de Resumen Pisos."""
    try:
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            full_context += f"\nDatos Resumen_Pisos:\n{df.to_string()}\n"
        else:
            full_context += f"\nDatos Resumen_Pisos:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Resumen Pisos: {str(e)}")
        full_context += f"\nDatos Resumen_Pisos:\nError en el procesamiento\n"
    return full_context

# Función para procesar Estados Registros
def procesar_estados_registros(full_context, result):
    """Procesa el resultado de Estados Registros."""
    try:
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            full_context += f"\nDatos Estados_Registros:\n{df.to_string()}\n"
        else:
            full_context += f"\nDatos Estados_Registros:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Estados Registros: {str(e)}")
        full_context += f"\nDatos Estados_Registros:\nError en el procesamiento\n"
    return full_context

# Función para procesar Estancia Servicios
def procesar_estancia_servicios(full_context, result):
    """Procesa el resultado de Estancia Servicios."""
    try:
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            full_context += f"\nDatos Estancia_Servicios:\n{df.to_string()}\n"
        else:
            full_context += f"\nDatos Estancia_Servicios:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Estancia Servicios: {str(e)}")
        full_context += f"\nDatos Estancia_Servicios:\nError en el procesamiento\n"
    return full_context

# Función para procesar Contratos
def procesar_contratos(full_context, result):
    """Procesa el resultado de Contratos."""
    try:
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            full_context += f"\nDatos Contratos:\n{df.to_string()}\n"
        else:
            full_context += f"\nDatos Contratos:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Contratos: {str(e)}")
        full_context += f"\nDatos Contratos:\nError en el procesamiento\n"
    return full_context

# Función para procesar Top 5 Estancia Servicios
def procesar_top5_estancia_servicios(full_context, result):
    """Procesa el resultado del Top 5 de estancia por servicios."""
    try:
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            full_context += f"\nDatos Top5_estancia_servicios:\n{df.to_string()}\n"
        else:
            full_context += f"\nDatos Top5_estancia_servicios:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Top 5 Estancia Servicios: {str(e)}")
        full_context += f"\nDatos Top5_estancia_servicios:\nError en el procesamiento\n"
    return full_context

# Función para procesar Top 5 Contratos
def procesar_top5_contratos(full_context, result):
    """Procesa el resultado del Top 5 de contratos."""
    try:
        if result and len(result) > 0:
            df = pd.DataFrame(result)
            full_context += f"\nDatos Top5_Contratos_por_Cantidad:\n{df.to_string()}\n"
        else:
            full_context += f"\nDatos Top5_Contratos_por_Cantidad:\nNo hay datos disponibles\n"
    except Exception as e:
        logger.error(f"❌ Error procesando Top 5 Contratos: {str(e)}")
        full_context += f"\nDatos Top5_Contratos_por_Cantidad:\nError en el procesamiento\n"
    return full_context

# Función para procesar todos los resultados de censo (con concurrencia)
def procesar_resultados_censo():
    """Función principal que procesa todos los resultados de censo y construye el contexto para Gemini con concurrencia."""
    config = cargar_configuracion_censo()
    if not config:
        return "", {}
    
    full_context = ""
    datos_censo = {}  # Diccionario para almacenar los datos procesados
    
    # Recolectar todas las consultas de todas las páginas
    all_queries = []
    for page in config.get('pages', []):
        page_name = page.get('display_name', 'Sin nombre')
        queries = page.get('queries', [])
        
        for query in queries:
            query_id = query.get('query_id')
            dax = query.get('dax')
            description = query.get('description', 'Sin descripción')
            
            if dax:
                all_queries.append({
                    'query_id': query_id,
                    'dax': dax,
                    'description': description,
                    'page_name': page_name
                })
    
    # Ejecutar todas las consultas en paralelo
    logger.info(f"🚀 Ejecutando {len(all_queries)} consultas de censo en paralelo...")
    
    def ejecutar_query_con_info(query_info):
        """Ejecuta una query y retorna la información junto con el resultado."""
        query_id = query_info['query_id']
        dax = query_info['dax']
        
        logger.info(f"🔍 Ejecutando consulta de censo: {query_id}")
        status, result = ejecutar_query_censo(dax)
        
        return {
            'query_id': query_id,
            'dax': dax,
            'description': query_info['description'],
            'page_name': query_info['page_name'],
            'status': status,
            'result': result
        }
    
    # Usar ThreadPoolExecutor para ejecutar consultas concurrentemente
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Enviar todas las consultas al executor
        future_to_query = {executor.submit(ejecutar_query_con_info, query): query for query in all_queries}
        
        # Recolectar resultados manteniendo el orden original
        results = []
        for future in concurrent.futures.as_completed(future_to_query):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                query = future_to_query[future]
                logger.error(f"❌ Error en consulta {query['query_id']}: {str(e)}")
                results.append({
                    'query_id': query['query_id'],
                    'dax': query['dax'],
                    'description': query['description'],
                    'page_name': query['page_name'],
                    'status': 'error',
                    'result': None
                })
    
    # Ordenar resultados según el orden original de las consultas
    ordered_results = []
    query_order = {q['query_id']: i for i, q in enumerate(all_queries)}
    results.sort(key=lambda x: query_order.get(x['query_id'], float('inf')))
    
    # Procesar resultados en orden
    current_page = None
    for query_result in results:
        query_id = query_result['query_id']
        result = query_result['result']
        description = query_result['description']
        page_name = query_result['page_name']
        status = query_result['status']
        
        # Cambiar de página si es necesario
        if current_page != page_name:
            current_page = page_name
            full_context += f"\n--- {page_name} ---\n"
        
        if status != 'success' or not result:
            logger.warning(f"La consulta {query_id} no devolvió datos")
            full_context += f"\nDatos {description}:\nNo hay datos disponibles\n"
            datos_censo[query_id] = []
            continue
        
        # Procesar según el tipo de query y guardar datos
        if query_id == "Total_Pacientes":
            full_context = procesar_total_pacientes(full_context, result)
            # Guardar datos para la plantilla
            if result and len(result) > 0:
                datos_censo['total_pacientes'] = result[0].get('[total_pacientes]', 0)
        elif query_id == "Porcentaje_Ocupacion_Global":
            full_context = procesar_porcentaje_ocupacion_global(full_context, result)
            # Guardar datos para la plantilla
            if result and len(result) > 0:
                datos_censo['porcentaje_ocupacion_global'] = result[0].get('[porcentaje_ocupacion_global]', 0)
        elif query_id == "Resumen_Pisos":
            full_context = procesar_resumen_pisos(full_context, result)
            # Guardar datos para la plantilla (contiene location, porcentaje, estancia_promedio)
            if result and len(result) > 0:
                datos_censo['resumen_pisos'] = result
        elif query_id == "Estancia_Servicios":
            full_context = procesar_estancia_servicios(full_context, result)
            # Guardar datos para la plantilla (contiene servicios y estancia)
            if result and len(result) > 0:
                datos_censo['estancia_servicios'] = result
        elif query_id == "Top5_estancia_servicios":
            full_context = procesar_top5_estancia_servicios(full_context, result)
            # Guardar datos para la plantilla
            if result and len(result) > 0:
                datos_censo['top5_estancia_servicios'] = result
        elif query_id == "Top5_Contratos_por_Cantidad":
            full_context = procesar_top5_contratos(full_context, result)
            # Guardar datos para la plantilla
            if result and len(result) > 0:
                datos_censo['top5_contratos'] = result
        elif query_id == "Estados_Registros":
            full_context = procesar_estados_registros(full_context, result)
            # Guardar datos para la plantilla
            if result and len(result) > 0:
                datos_censo['estados_registros'] = result
        elif query_id == "Validacion_UCI_Observacion":
            full_context = procesar_estados_registros(full_context, result)  # Usar mismo procesamiento
            # Guardar datos para la plantilla
            if result and len(result) > 0:
                datos_censo['validacion_uci'] = result
        elif query_id == "Cantidad_por_Contrato":
            full_context = procesar_contratos(full_context, result)
        
        else:
            # Para cualquier otra consulta, procesar genéricamente
            if result and len(result) > 0:
                df = pd.DataFrame(result)
                full_context += f"\nDatos {description}:\n{df.to_string()}\n"
                datos_censo[query_id] = result
            else:
                full_context += f"\nDatos {description}:\nNo hay datos disponibles\n"
                datos_censo[query_id] = []
    
    # Verificar si se obtuvieron datos de censo
    if datos_censo:
        logger.info("✅ Datos de censo obtenidos exitosamente")
    else:
        logger.warning("⚠️ No se pudieron obtener datos de censo")
    
    return full_context, datos_censo

def generar_html_resumen_pisos(resumen_pisos):
    """Genera HTML para la tabla de resumen de pisos con porcentaje de ocupación y estado."""
    if not resumen_pisos:
        return "<tr><td colspan='3'>No hay datos disponibles</td></tr>"
    rows = []
    for i, piso_data in enumerate(resumen_pisos):
        if isinstance(piso_data, dict):
            # Obtener nombre del piso
            piso_nombre = (piso_data.get('[location]') or 
                         piso_data.get('location') or 
                         piso_data.get('Location') or 
                         piso_data.get('Piso') or 
                         piso_data.get('piso') or 'N/A')
            
            # Obtener porcentaje de ocupación
            porcentaje = (piso_data.get('[porcentaje]') or 
                         piso_data.get('porcentaje') or 
                         piso_data.get('Porcentaje') or 
                         piso_data.get('percentage') or 0)
                        
            try:
                # Convertir a float y formatear a 2 decimales
                porcentaje_num = float(porcentaje) if porcentaje else 0
                porcentaje_str = f"{porcentaje_num:.2f}%"
                
                # Determinar estado y color según el porcentaje
                if porcentaje_num <= 30:
                    estado = "✅ Disponible"
                    color_html = "style='color: #28a745; font-weight: bold;'"  # Verde
                elif porcentaje_num <= 80:
                    estado = "� Media"
                    color_html = "style='color: #17a2b8; font-weight: bold;'"  # Azul
                elif porcentaje_num <= 90:
                    estado = "⚠️ Ocupación media-alta"
                    color_html = "style='color: #ffc107; font-weight: bold;'"  # Amarillo
                else:  # 91-100%
                    estado = "🚫 Sin disponibilidad"
                    color_html = "style='color: #dc3545; font-weight: bold;'"  # Rojo
                                
            except (ValueError, TypeError):
                porcentaje_str = "0.00%"
                estado = "Sin datos"
                color_html = "style='color: #6c757d;'"  # Gris
            
            rows.append(f"""
                <tr>
                    <td style='border-right: 0.8px solid #e3e3e4;'>{piso_nombre}</td>
                    <td align="right" style='border-right: 0.8px solid #e3e3e4;'>{porcentaje_str}</td>
                    <td align="right" {color_html}>{estado}</td>
                </tr>""")
        else:
            logger.warning(f"🔍 DEBUG - Registro {i} no es dict: {type(piso_data)}")
    
    return '\n'.join(rows)

def generar_html_estancia_pisos(resumen_pisos):
    """Genera HTML para la tabla estancia por pisos."""
    if not resumen_pisos:
        return "<tr><td colspan='3'>No hay datos disponibles</td></tr>"
    
    rows = []
    for piso_data in resumen_pisos:
        if isinstance(piso_data, dict):
            # Obtener nombre del piso
            piso_nombre = (piso_data.get('[location]') or 
                         piso_data.get('Location') or 
                         piso_data.get('Piso') or 'N/A')
            
            # Obtener estancia promedio
            estancia_promedio = (piso_data.get('[estancia_promedio]') or 
                         piso_data.get('Estancia_promedio') or 0)
            
            try:
                # Convertir a float y formatear a 2 decimales
                estancia_promedio_num = float(estancia_promedio) if estancia_promedio else 0
                estancia_promedio_str = f"{estancia_promedio_num:.2f}"
                
            except (ValueError, TypeError):
                estancia_promedio_str = "0.00"
            
            rows.append(f"""
                <tr>
                    <td style='border-right: 0.8px solid #e3e3e4;'>{piso_nombre}</td>
                    <td align="right">{estancia_promedio_str}</td>
                </tr>""")
    
    return '\n'.join(rows)


def generar_html_top5_estancia_servicios(top5_estancia_servicios):
    """Genera HTML para la tabla de estancia por servicios."""
    if not top5_estancia_servicios:
        return "<tr><td colspan='2'>No hay datos disponibles</td></tr>"
    
    rows = []
    for servicio_data in top5_estancia_servicios:
        if isinstance(servicio_data, dict):
            servicio_nombre = (servicio_data.get('registros[especialidad]') or 
                             servicio_data.get('[especialidad]') or
                             servicio_data.get('Especialidad') or 
                             servicio_data.get('especialidad') or 'N/A')
            
            estancia = (servicio_data.get('[estancia_promedio]') or 
                       servicio_data.get('estancia_promedio') or
                       servicio_data.get('Estancia Promedio') or 0)
            
            try:
                # Convertir coma decimal a punto decimal antes de float
                estancia_limpia = str(estancia).replace(',', '.') if estancia else '0'
                estancia_num = float(estancia_limpia) if estancia and str(estancia).strip() != '' and str(estancia) != 'NaN' else 0
                estancia_str = f"{estancia_num:.1f} días" if estancia_num > 0 else "N/A"
            except (ValueError, TypeError):
                estancia_str = "N/A"
            
            rows.append(f"""
                <tr>
                    <td style='border-right: 0.8px solid #e3e3e4;'>{servicio_nombre}</td>
                    <td align="right">{estancia_str}</td>
                </tr>""")
    
    return '\n'.join(rows)

def generar_html_top5_contratos(top5_contratos):
    """Genera HTML para la tabla del Top 5 de contratos."""
    if not top5_contratos:
        return "<tr><td colspan='2'>No hay datos disponibles</td></tr>"
    
    rows = []
    for i, contrato_data in enumerate(top5_contratos[:5], 1):  # Limitar a 5
        if isinstance(contrato_data, dict):
            contrato_nombre = (contrato_data.get('registros[contrato]') or 
                            contrato_data.get('Contrato') or 
                            contrato_data.get('contrato') or 'N/A')
            
            cantidad = (contrato_data.get('[cantidad]') or 
                       contrato_data.get('Cantidad') or 
                       contrato_data.get('cantidad') or 0)
            
            try:
                cantidad_num = int(cantidad) if cantidad else 0
            except (ValueError, TypeError):
                cantidad_num = 0
            
            rows.append(f"""
                <tr>
                    <td style='border-right: 0.8px solid #e3e3e4;'>{i}. {contrato_nombre}</td>
                    <td align="right">{cantidad_num}</td>
                </tr>""")
    
    return '\n'.join(rows)

# ======================================================
# FUNCIONES FACTURACIÓN (Atomizadas para queriesFact.json)
# ======================================================

# Función para cargar configuración de facturación
def cargar_configuracion_facturacion(path='queriesFact.json'):
    """Carga y valida la configuración desde el archivo JSON de facturación."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        if 'report_config' not in config or 'pages' not in config['report_config']:
            raise ValueError("Estructura de configuración de facturación inválida")
        return config['report_config']
    except Exception as e:
        logger.error(f"❌ Error en configuración de facturación: {str(e)}")
        return {}

# Función para ejecutar query de facturación (thread-safe)
def ejecutar_query_facturacion(dax: str, mes: int, anio: int) -> Tuple[str, Any]:
    """Ejecuta una consulta DAX de facturación contra el endpoint y devuelve el resultado JSON."""
    try:
        response = requests.post(
            PA_URL_FACTURACION,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={"dax_query": dax, "mes": mes, "anio": anio},
            timeout=30
        )
        return ("success", response.json() if response.status_code == 200 else None)
    except Exception as e:
        logger.error(f"❌ Error ejecutando query de facturación: {str(e)}")
        return ("error", None)

# Función para procesar Top 10 EPS
def procesar_top_10_eps(resultados, result):
    """Procesa el resultado del Top 10 de facturación por EPS."""
    try:
        top_eps = []
        for item in result:
            if isinstance(item, dict):
                nombre_eps = item.get('Medicadiz[Nombre EPS]', 'N/A')
                facturado = item.get('[Facturado]', '0')
                top_eps.append(f"{nombre_eps}: ${facturado}")
        resultados['top_10_eps'] = top_eps[:10]  # Limitar a 10 resultados
    except Exception as e:
        logger.error(f"❌ Error procesando Top 10 EPS: {str(e)}")
        resultados['top_10_eps'] = []

# Función para procesar facturación mensual
def procesar_facturacion_mensual(resultados, key, result):
    """Procesa valores de facturación mensual."""
    try:
        if result and len(result) > 0:
            valor = result[0].get('[Value]', '0')
            # Limpiar y formatear el valor
            valor_limpio = str(valor).replace(',', '').replace('$', '')
            try:
                valor_numerico = float(valor_limpio)
                resultados[key] = f"${valor_numerico:,.2f}"
            except ValueError:
                resultados[key] = f"${valor}"
        else:
            resultados[key] = "$0.00"
    except Exception as e:
        logger.error(f"❌ Error procesando facturación mensual para {key}: {str(e)}")
        resultados[key] = "$0.00"

# Función para procesar variación
def procesar_variacion(resultados, result):
    """Procesa la variación de facturación."""
    try:
        if result and len(result) > 0:
            valor = result[0].get('[Value]', '0')
            valor_limpio = str(valor).replace(',', '').replace('$', '')
            try:
                valor_numerico = float(valor_limpio)
                signo = "+" if valor_numerico >= 0 else ""
                valor_formateado = f"{signo}${valor_numerico:,.2f}"
                # Aplicar estilo rojo si es negativo
                if valor_numerico < 0:
                    valor_formateado = f"<span style='color: #dc2626;'>{valor_formateado}</span>"
                resultados['variacion'] = valor_formateado
            except ValueError:
                resultados['variacion'] = f"${valor}"
        else:
            resultados['variacion'] = "$0.00"
    except Exception as e:
        logger.error(f"❌ Error procesando variación en dólares: {str(e)}")
        resultados['variacion'] = "$0.00"

# Función para procesar variación porcentual
def procesar_variacion_porcentual(resultados, result):
    """Procesa la variación de facturación en porcentaje."""
    try:
        if result and len(result) > 0:
            valor = result[0].get('[Value]', '0')
            valor_limpio = str(valor).replace(',', '').replace('%', '')
            try:
                valor_numerico = round(float(valor_limpio) * 100)
                signo = "+" if valor_numerico >= 0 else ""
                valor_formateado = f"{signo}{valor_numerico:.0f}%"
                # Aplicar estilo rojo si es negativo
                if valor_numerico < 0:
                    valor_formateado = f"<span style='color: #dc2626;'>{valor_formateado}</span>"
                resultados['variacion_porcentual'] = valor_formateado
            except ValueError:
                resultados['variacion_porcentual'] = f"{valor}%"
        else:
            resultados['variacion_porcentual'] = "0.00%"
    except Exception as e:
        logger.error(f"❌ Error procesando variación porcentual: {str(e)}")
        resultados['variacion_porcentual'] = "0.00%"

# Función para obtener queries de una página específica
def obtener_queries_pagina_facturacion(config, page_id):
    """Obtiene las queries de una página específica del reporte de facturación."""
    try:
        for page in config.get('pages', []):
            if page.get('page_id') == page_id:
                return page.get('queries', [])
        return []
    except Exception as e:
        logger.error(f"❌ Error obteniendo queries de página {page_id}: {str(e)}")
        return []

def procesar_resultados_facturacion(mes, anio):
    """Función principal que procesa todos los resultados de facturación con concurrencia."""
    config = cargar_configuracion_facturacion()
    if not config:
        return {}
    
    resultados = {
        'hospital_name': config.get('hospital_name', 'Tu Hospital Actual'),
        'mes': mes,
        'anio': anio
    }
    
    # Obtener queries de la página de monitoreo hospitalario
    queries = obtener_queries_pagina_facturacion(config, 'monitoreo_hospitalario')
    
    # Ejecutar todas las consultas en paralelo
    logger.info(f"🚀 Ejecutando {len(queries)} consultas de facturación en paralelo...")
    
    def ejecutar_query_facturacion_con_info(query_info):
        """Ejecuta una query de facturación y retorna la información junto con el resultado."""
        query_id = query_info['query_id']
        dax = query_info['dax']
        
        logger.info(f"🔍 Ejecutando consulta de facturación: {query_id}")
        status, result = ejecutar_query_facturacion(dax, mes, anio)
        
        return {
            'query_id': query_id,
            'dax': dax,
            'status': status,
            'result': result
        }
    
    # Usar ThreadPoolExecutor para ejecutar consultas concurrentemente
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Enviar todas las consultas al executor
        future_to_query = {executor.submit(ejecutar_query_facturacion_con_info, query): query for query in queries}
        
        # Recolectar resultados manteniendo el orden original
        results = []
        for future in concurrent.futures.as_completed(future_to_query):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                query = future_to_query[future]
                logger.error(f"❌ Error en consulta de facturación {query['query_id']}: {str(e)}")
                results.append({
                    'query_id': query['query_id'],
                    'dax': query['dax'],
                    'status': 'error',
                    'result': None
                })
    
    # Ordenar resultados según el orden original de las consultas
    query_order = {q['query_id']: i for i, q in enumerate(queries)}
    results.sort(key=lambda x: query_order.get(x['query_id'], float('inf')))
    
    # Procesar resultados en orden
    for query_result in results:
        query_id = query_result['query_id']
        result = query_result['result']
        status = query_result['status']
        
        if status != 'success' or not result:
            logger.warning(f"La consulta de facturación {query_id} no devolvió datos")
            continue
        
        # Procesar según el tipo de query
        if query_id == "Top_10_EPS":
            procesar_top_10_eps(resultados, result)
        elif query_id == "*Facturado_Mes_Actual":
            procesar_facturacion_mensual(resultados, 'facturado_mes_actual', result)
        elif query_id == "Facturado_Mes_Actual_PGP":
            procesar_facturacion_mensual(resultados, 'facturado_mes_actual_pgp', result)
        elif query_id == "Facturado_Mes_Actual_Evento":
            procesar_facturacion_mensual(resultados, 'facturado_mes_actual_evento', result)
        elif query_id == "*Facturado_Mes_Anterior":
            procesar_facturacion_mensual(resultados, 'facturado_mes_anterior', result)
        elif query_id == "*Facturado_Mes_Anterior_PGP":
            procesar_facturacion_mensual(resultados, 'facturado_mes_anterior_pgp', result)
        elif query_id == "*Facturado_Mes_Anterior_Evento":
            procesar_facturacion_mensual(resultados, 'facturado_mes_anterior_evento', result)
        elif query_id == "Variacion_Facturado_Mes":
            procesar_variacion(resultados, result)
        elif query_id == "*Variacion_Facturado_Mes_%":
            procesar_variacion_porcentual(resultados, result)
    
    # Verificar si se obtuvieron datos de facturación
    if resultados and any(key not in ['hospital_name', 'mes', 'anio'] for key in resultados.keys()):
        logger.info("✅ Datos de facturación obtenidos exitosamente")
    else:
        logger.warning("⚠️ No se pudieron obtener datos de facturación")
    
    return resultados

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

def generate_eps_html(top_eps):
    """Genera HTML para tabla de EPS."""
    rows = []
    for eps_data in top_eps:
        if ':' in eps_data:
            valor = formato_monetario(eps_data.split(':', 1)[1])
            nombre = eps_data.split(':', 1)[0]
            rows.append(f"<tr><td style='border-right: 0.8px solid #e3e3e4;'>{nombre.strip()}</td><td align='right'>{valor.strip()}</td></tr>")
    return '\n'.join(rows) if rows else "<tr><td colspan='2'>No hay datos disponibles</td></tr>"

def get_gemini_prompt():
    """Retorna el prompt completo para Gemini."""
    return """        
    Actúa como un Consultor Senior de Estrategia Hospitalaria y Analista de Datos.

    CONTEXTO DE OCUPACIÓN HOSPITALARIA:
    - 0-30%: Disponible (verde) → Mucha capacidad disponible
    - 31-80%: Media (azul) → Ocupación normal/estable
    - 81-90%: Ocupación media-alta (amarillo) → Eficiente pero con poco espacio
    - 91-100%: Sin disponibilidad (rojo) → Crítico, sin capacidad

    ESTADOS IMPORTANTES A MONITOREAR:
    - Disponible: Buena capacidad de atención
    - Ocupación media-alta: Eficiente pero requiere atención por espacio limitado
    - Sin disponibilidad: Crítico, requiere acción inmediata

    OBJETIVO DEL RESUMEN EJECUTIVO:
    Genera un resumen ejecutivo de máximo 4 renglones sobre ocupación de pisos y estancias promedio; no menciones contratos. EL resumen debe ser conciso y no debe ser de mas de 5 renglones"

    RESTRICCIONES:
    - Máximo 4 renglones concisos
    - Usa datos reales proporcionados
    - No recalcules porcentajes si ya vienen explícitos
    - Devuelve únicamente objeto JSON con clave "resumen_ejecutivo"
    - Sin texto adicional ni markdown

    Datos a analizar:

   """

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
            if not response:
                raise ValueError("La respuesta de la API está vacía")
                
            # Verificar si hay partes en la respuesta
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content.parts:
                    return ''.join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
            
            # Si llegamos aquí, la respuesta no tiene el formato esperado
            logger.warning(f"Respuesta inesperada de la API: {str(response)}")
            raise ValueError("La respuesta de la API no contiene texto válido")
            
        except Exception as e:
            logger.warning(f"Error con la clave API #{current_key_index + 1}: {str(e)}")
            
            # Intentar con la siguiente clave si es un error de cuota, límite o respuesta vacía
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["quota", "limit", "finish_reason", "part", "permission", "no contiene texto", "respuesta inesperada"]):
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
def optimizar_imagen(
    ruta_imagen,
    ancho_max=800,
    calidad=85,
    preservar_alpha=True
):
    import io
    from PIL import Image

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
# ENVÍO DE CORREO ELECTRÓNICO
# ======================================================
def enviar_correo(datos_analisis, token_graph):
    """Envía un correo con imágenes inline (CID) para máxima compatibilidad en clientes de correo."""
    try:
        if not MAIL_SENDER or not DESTINATARIOS:
            logger.warning("⚠️ No se configuró remitente o destinatarios")
            return

        # Generar URL del reporte de Power BI
        report_url = f"https://app.powerbi.com/reportEmbed?reportId={REPORT_ID}&autoAuth=true&ctid={TENANT_ID}"

        # -----------------------------
        # Cargar plantilla HTML
        # -----------------------------
        try:
            with open("./template/report_template.html", "r", encoding='utf-8') as f:
                html_final = f.read()

            # Reemplazar placeholders en la plantilla
            for key, value in {**datos_analisis, 'POWERBI_REPORT_URL': report_url}.items():
                html_final = html_final.replace(f"{{{key.upper()}}}", str(value))
            
            # Insertar el mensaje personalizado al inicio del HTML
            # mensaje_personalizado = "Buen día, espero que se encuentren muy bien. Adjunto el reporte actualizado que incluye la nueva sección de información financiera. Quedo atento a sus comentarios por si requieren algún ajuste o corrección."
            # html_final = f"<p>{mensaje_personalizado}</p>" + html_final

            html_final = html_final
            
        except FileNotFoundError as e:
            logger.error(f"Error al cargar plantilla: {str(e)}")
            html_final = "<h1>Error: Archivo de plantilla no encontrado</h1>"

        # -----------------------------
        # Preparar attachments inline
        # -----------------------------
        attachments = []

        # Avatar inline por CID
        avatar_path = "./template/Prototipo avatar con logo de lenus y Clinica San Rafael.png"

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
            # Si falla, deja el src vacío para evitar un ícono roto
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
                "bccRecipients": [{"emailAddress": {"address": email}} for email in DESTINATARIOS],
                "attachments": attachments
            },
            "saveToSentItems": False  # booleano
        }

        # -----------------------------
        # Envío vía Graph
        # -----------------------------
        logger.info(f"Enviando correo desde {MAIL_SENDER} a {DESTINATARIOS} por CCO...")
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
        logger.info("✉️ Correo enviado correctamente")

    except requests.HTTPError as e:
        logger.error(f"❌ Error HTTP al enviar el correo: {e.response.text if e.response is not None else str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error al enviar el correo: {str(e)}")
        raise

# ======================================================
# EJECUCIÓN PRINCIPAL
# ======================================================

def ejecutar_automatizacion():
    """Función principal que orquesta la automatización."""
    try:
        # Obtener tokens
        logger.info("🔑 Obteniendo tokens de autenticación...")
        token_graph = obtener_token_graph()
        
        # Procesar datos de censo usando Power Automate
        logger.info("📊 Procesando datos de censo hospitalario...")
        full_context, datos_censo = procesar_resultados_censo()
        
        if not full_context.strip():
            logger.warning("⚠️ No se encontraron datos de censo. Se usará un análisis genérico.")
        
        # Procesar KPIs de estancia directamente de los datos del censo
        estancia_max_piso = {"piso": "N/A", "dias": 0}
        estancia_min_piso = {"piso": "N/A", "dias": 999999}
        estancia_max_servicio = {"servicio": "N/A", "dias": 0}
        estancia_min_servicio = {"servicio": "N/A", "dias": 999999}  
        
        # Procesar estancia por piso desde resumen_pisos (ya procesado por procesar_resumen_pisos)
        resumen_pisos = datos_censo.get('resumen_pisos', [])
        for piso_data in resumen_pisos:
            if isinstance(piso_data, dict):
                # Buscar el nombre del piso en diferentes campos posibles
                piso_nombre = (piso_data.get('[location]') or 
                             piso_data.get('location') or 
                             piso_data.get('Piso') or 
                             piso_data.get('piso') or 'N/A')
                
                # Buscar la estancia promedio en diferentes campos posibles
                estancia = (piso_data.get('[estancia_promedio]') or 
                          piso_data.get('Estancia Promedio') or 
                          piso_data.get('estancia_promedio') or 0)
                
                try:
                    estancia_num = float(estancia) if estancia else 0
                    if estancia_num > estancia_max_piso['dias']:
                        estancia_max_piso = {"piso": piso_nombre, "dias": estancia_num}
                    if estancia_num < estancia_min_piso['dias'] and estancia_num > 0:
                        estancia_min_piso = {"piso": piso_nombre, "dias": estancia_num}
                except (ValueError, TypeError):
                    continue
        
        # Procesar estancia por servicio desde estancia_servicios (ya procesado por procesar_estancia_servicios)
        estancia_servicios = datos_censo.get('estancia_servicios', [])
        
        for i, servicio_data in enumerate(estancia_servicios):
            if isinstance(servicio_data, dict):
                
                # Buscar el nombre del servicio en diferentes campos posibles
                servicio_nombre = (servicio_data.get('registros[especialidad]') or 
                                 servicio_data.get('[especialidad]') or
                                 servicio_data.get('Especialidad') or 
                                 servicio_data.get('especialidad') or 'N/A')
                
                # Buscar la estancia promedio en diferentes campos posibles
                estancia = (servicio_data.get('[estancia_promedio]') or 
                          servicio_data.get('estancia_promedio') or
                          servicio_data.get('Estancia Promedio') or 0)
                
                try:
                    # Convertir coma decimal a punto decimal antes de float
                    estancia_limpia = str(estancia).replace(',', '.') if estancia else '0'
                    estancia_num = float(estancia_limpia) if estancia and str(estancia).strip() != '' and str(estancia) != 'NaN' else 0
                    if estancia_num > estancia_max_servicio['dias']:
                        estancia_max_servicio = {"servicio": servicio_nombre, "dias": estancia_num} 
                    if estancia_num < estancia_min_servicio['dias'] and estancia_num > 0:
                        estancia_min_servicio = {"servicio": servicio_nombre, "dias": estancia_num}
                except (ValueError, TypeError):
                    continue
        
        # Si no se encontraron valores mínimos válidos, establecer N/A
        if estancia_min_piso['dias'] == 999999:
            estancia_min_piso = {"piso": "N/A", "dias": 0}
        if estancia_min_servicio['dias'] == 999999:
            estancia_min_servicio = {"servicio": "N/A", "dias": 0}
        
        # Formatear valores de KPIs para mostrar
        estancia_max_piso_str = f"{estancia_max_piso['piso']} ({estancia_max_piso['dias']:.1f} días)" if estancia_max_piso['piso'] != "N/A" else "N/A"
        estancia_min_piso_str = f"{estancia_min_piso['piso']} ({estancia_min_piso['dias']:.1f} días)" if estancia_min_piso['piso'] != "N/A" else "N/A"
        estancia_max_servicio_str = f"{estancia_max_servicio['servicio']} ({estancia_max_servicio['dias']:.1f} días)" if estancia_max_servicio['servicio'] != "N/A" else "N/A"
        estancia_min_servicio_str = f"{estancia_min_servicio['servicio']} ({estancia_min_servicio['dias']:.1f} días)" if estancia_min_servicio['servicio'] != "N/A" else "N/A"
        
        # Generar análisis breve con Gemini usando los datos procesados
        resumen_ejecutivo = "No se pudo generar el análisis."
        
        # Construir contexto con los datos ya procesados
        # Formatear los datos de pisos para mejor legibilidad
        resumen_pisos_formateado = ""
        if resumen_pisos:
            for piso in resumen_pisos[:5]:  # Limitar a 5 pisos para no saturar
                if isinstance(piso, dict):
                    nombre = piso.get('[location]', piso.get('location', 'N/A'))
                    porcentaje = piso.get('[porcentaje]', piso.get('porcentaje', 0))
                    resumen_pisos_formateado += f"- {nombre}: {porcentaje}%\n"
        
        contexto_procesado = f"""
            DATOS PROCESADOS PARA ANÁLISIS:
            ===============================
            OCUPACIÓN GENERAL:
            - Total pacientes: {datos_censo.get('total_pacientes', 0)}
            - Ocupación global: {datos_censo.get('porcentaje_ocupacion_global', 0)}%

            OCUPACIÓN POR PISO (principales):
            {resumen_pisos_formateado}

            ESTANCIAS DESTACADAS:
            - Piso con mayor estancia: {estancia_max_piso_str}
            - Piso con menor estancia: {estancia_min_piso_str}
            - Servicio con mayor estancia: {estancia_max_servicio_str}
            - Servicio con menor estancia: {estancia_min_servicio_str}
        """
        
        if contexto_procesado.strip():
            prompt = get_gemini_prompt() + contexto_procesado
            
            try:
                respuesta = get_gemini_response(prompt)
                logger.info(f"🔍 Respuesta cruda de Gemini: {respuesta[:200]}...")  # Log para diagnóstico
                
                if '```json' in respuesta:
                    respuesta = respuesta.split('```json')[1].split('```')[0]
                elif '```' in respuesta:
                    respuesta = respuesta.split('```')[1]
                
                # Limpiar la respuesta antes de parsear
                respuesta = respuesta.strip()
                if respuesta.startswith('{') and respuesta.endswith('}'):
                    datos_gemini = json.loads(respuesta)
                    resumen_ejecutivo = datos_gemini.get("resumen_ejecutivo", "No se encontró resumen_ejecutivo en la respuesta.")
                    logger.info("✅ Análisis breve generado por Gemini exitosamente")
                else:
                    logger.warning(f"⚠️ La respuesta no parece un JSON válido: {respuesta}")
                    resumen_ejecutivo = "La respuesta de Gemini no tiene el formato esperado."
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error decodificando JSON de Gemini: {str(e)}")
                logger.error(f"Respuesta recibida: {respuesta}")
                resumen_ejecutivo = "Error al procesar la respuesta de Gemini (JSON inválido)."
            except Exception as e:
                logger.error(f"❌ Error inesperado con Gemini: {str(e)}")
                logger.error(f"Respuesta recibida: {respuesta if 'respuesta' in locals() else 'No hay respuesta'}")
                resumen_ejecutivo = f"Error en el procesamiento del análisis: {str(e)}"
        else:
            logger.warning("⚠️ No se encontraron datos para el análisis.")
            resumen_ejecutivo = "No hay datos disponibles para el análisis."   
        
        # Procesar datos de facturación
        logger.info("💰 Procesando datos de facturación...")
        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Procesar datos de facturación con el mes y el año actual
        hoy = datetime.now()
        mes, anio = hoy.month, hoy.year
        datos_facturacion = procesar_resultados_facturacion(mes, anio)  

        # Guardar datos de pisos y servicios en variables locales para reutilizar
        resumen_pisos_data = datos_censo.get('resumen_pisos', [])
        top5_estancia_servicios_data = datos_censo.get('top5_estancia_servicios', [])
        top5_contratos_data = datos_censo.get('top5_contratos', [])
        
        
        # Preparar datos para el template
        datos_analisis = {
            "FECHA": fecha_actual,
            
            # Datos de censo hospitalario (directos de las consultas)
            "TOTAL_PACIENTES": datos_censo.get('total_pacientes', 0),
            "PORCENTAJE_OCUPACION_GLOBAL": datos_censo.get('porcentaje_ocupacion_global', 0),

            # KPIs de estancia calculados
            "ESTANCIA_MAX_PISO": estancia_max_piso_str,
            "ESTANCIA_MIN_PISO": estancia_min_piso_str,
            "ESTANCIA_MAX_SERVICIO": estancia_max_servicio_str,
            "ESTANCIA_MIN_SERVICIO": estancia_min_servicio_str,
            
            # Tablas HTML generadas (usando variables locales)
            "ESTADO_PISOS": generar_html_resumen_pisos(resumen_pisos_data),
            "ESTANCIA_PISOS": generar_html_estancia_pisos(resumen_pisos_data),
            "TOP5_ESTANCIA_SERVICIO": generar_html_top5_estancia_servicios(top5_estancia_servicios_data),
            "TOP5_CONTRATOS": generar_html_top5_contratos(top5_contratos_data),
            
            # Análisis breve de Gemini
            "RESUMEN_EJECUTIVO": resumen_ejecutivo,

            # Datos de facturación
            "FACTURADO_MES_ACTUAL": datos_facturacion.get('facturado_mes_actual', '$0.00'),
            "FACTURADO_MES_ANTERIOR": datos_facturacion.get('facturado_mes_anterior', '$0.00'),
            "FACTURADO_MES_ACTUAL_PGP": datos_facturacion.get('facturado_mes_actual_pgp', '$0.00'),
            "FACTURADO_MES_ACTUAL_EVENTO": datos_facturacion.get('facturado_mes_actual_evento', '$0.00'),
            "VARIACION_FACTURACION": datos_facturacion.get('variacion', '$0.00'),
            "VARIACION_PORCENTUAL": datos_facturacion.get('variacion_porcentual', '0.00%'),
            "TOP_EPS_ROWS": generate_eps_html(datos_facturacion.get('top_10_eps', [])),   
        }
        
        # Enviar correo
        if datos_analisis:
            logger.info("📤 Enviando correo con el análisis")
            enviar_correo(datos_analisis, token_graph)
        else:
            logger.warning("⚠️ No hay contenido para enviar por correo")
                
        logger.info("✅ Proceso completado exitosamente.")
                
    except Exception as e:
        logger.error(f"❌ Error en la ejecución: {str(e)}", exc_info=True)

if __name__ == "__main__":
    ejecutar_automatizacion()