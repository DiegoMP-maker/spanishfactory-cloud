#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de corrección de textos
-----------------------------
Este módulo contiene funciones para procesar y corregir textos en español.
"""

import logging
import json
import re
import traceback
import streamlit as st

from core.openai_integration import process_with_assistant_with_rate_limiting
from core.circuit_breaker import circuit_breaker
from core.session_manager import get_user_info, get_session_var
from config.settings import NIVELES_ESPANOL
from config.settings import IS_DEV  

# Importar explícitamente ambas funciones para evitar errores
from core.firebase_client import save_correccion, get_user_data

# Importar el prompt ultra-conciso
from core.prompts_manager import get_optimized_correction_prompt

logger = logging.getLogger(__name__)

# Definición local de get_student_profile para eliminar dependencia externa
def get_student_profile(user_id):
    """
    Obtiene el perfil completo del estudiante desde Firebase.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Perfil del estudiante o diccionario vacío si no está disponible
    """
    if not user_id:
        logger.warning("User ID vacío en get_student_profile")
        return {}
    
    try:
        # Obtener datos del usuario con log detallado
        logger.info(f"Obteniendo datos de usuario para UID: {user_id}")
        user_data = get_user_data(user_id)
        
        # Verificar si se obtuvo algún dato
        if not user_data:
            logger.warning(f"No se encontraron datos para el usuario {user_id} en Firebase")
            return {}
            
        # Log para depuración
        logger.info(f"Datos obtenidos de Firebase: {json.dumps({k: v for k, v in user_data.items() if k not in ['private_key', 'key']})}")
        
        # Verificar campos críticos en datos obtenidos
        if "nivel" not in user_data:
            logger.warning(f"Campo 'nivel' no encontrado en datos de usuario de Firebase")
        if "numero_correcciones" not in user_data:
            logger.warning(f"Campo 'numero_correcciones' no encontrado en datos de usuario de Firebase")
        
        # Extraer información relevante para el perfil con una correlación explícita
        # El mapeo claro entre campos de Firebase y campos del perfil evita confusiones
        profile = {
            # Mapeo explícito de "nivel" a "nivel_mcer"
            "nivel_mcer": user_data.get("nivel", "B1"),
            "idioma_nativo": user_data.get("idioma_nativo", ""),
            "objetivos_aprendizaje": user_data.get("objetivos_aprendizaje", []),
            "areas_interes": user_data.get("areas_interes", []),
            "numero_correcciones": user_data.get("numero_correcciones", 0)
        }
        
        # Log detallado para ver qué valores se están usando (reales o por defecto)
        logger.info(f"Perfil construido: nivel_mcer={profile['nivel_mcer']} (por defecto: {'Sí' if 'nivel' not in user_data else 'No'})")
        logger.info(f"Perfil construido: numero_correcciones={profile['numero_correcciones']} (por defecto: {'Sí' if 'numero_correcciones' not in user_data else 'No'})")
        
        # Añadir estadísticas de errores si están disponibles
        if "errores_por_tipo" in user_data:
            profile["estadisticas_errores"] = user_data["errores_por_tipo"]
            
        # Añadir preferencias de feedback si están disponibles
        if "preferencias_feedback" in user_data:
            profile["preferencias_feedback"] = user_data["preferencias_feedback"]
        
        # Asegurar que el usuario tenga todos los campos necesarios para futuras correcciones
        try:
            from core.firebase_client import ensure_profile_fields
            ensure_profile_fields(user_id)
        except Exception as e:
            logger.warning(f"No se pudieron asegurar campos de perfil: {e}")
            
        return profile
    
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error obteniendo perfil del estudiante: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return {}

def corregir_texto(texto_input, nivel, detalle="Intermedio", user_id=None, idioma="español"):
    """
    Procesa un texto con el asistente de OpenAI para obtener correcciones.
    Versión mejorada con limitación de historial, prompt ultra-conciso y manejo de rate limiting.
    
    Args:
        texto_input (str): Texto a corregir
        nivel (str): Nivel de español del estudiante
        detalle (str): Nivel de detalle para las correcciones
        user_id (str, opcional): ID del usuario
        idioma (str, opcional): Idioma para las explicaciones
        
    Returns:
        dict: Resultado de la corrección o diccionario con información de error
    """
    try:
        # Validación inicial del texto
        if texto_input is None:
            logger.error("El parámetro 'texto_input' es None")
            return {
                "error": True,
                "mensaje": "No se proporcionó texto para corregir",
                "texto_original": ""
            }
        
        # Verificar que el texto no esté vacío
        if not isinstance(texto_input, str):
            logger.error(f"El parámetro 'texto_input' no es una cadena: {type(texto_input)}")
            texto_input = str(texto_input) if texto_input is not None else ""
            
        if not texto_input.strip():
            logger.warning("Texto vacío para corrección")
            return {
                "error": True,
                "mensaje": "No se proporcionó texto para corregir",
                "texto_original": texto_input
            }
        
        # Validación de nivel
        if not nivel or not isinstance(nivel, str):
            logger.warning(f"Nivel inválido: {nivel}")
            nivel = "B1"  # Valor por defecto
        
        # Obtener información adicional del perfil del usuario si está disponible
        perfil_usuario = {}
        if user_id:
            try:
                perfil_usuario = get_student_profile(user_id)
                logger.info(f"Información de perfil recuperada para usuario {user_id}")
            except Exception as profile_error:
                logger.warning(f"No se pudo obtener perfil del usuario: {str(profile_error)}")
        
        # Preparar mensaje para el asistente
        try:
            # Enriquecer el mensaje con información contextual del perfil
            info_contextual = ""
            if perfil_usuario:
                # Añadir solo info relevante directamente en el mensaje
                info_contextual = f"""
CONTEXTO DEL ESTUDIANTE:
- Nivel MCER: {nivel}
- Idioma nativo: {perfil_usuario.get('idioma_nativo', 'No especificado')}
- Correcciones previas: {perfil_usuario.get('numero_correcciones', 0)}
"""
                # Añadir info de errores frecuentes si está disponible
                if "estadisticas_errores" in perfil_usuario:
                    errores = perfil_usuario["estadisticas_errores"]
                    info_contextual += "- Áreas de mejora: "
                    areas_mejora = []
                    for tipo, cantidad in errores.items():
                        if cantidad > 0:
                            areas_mejora.append(f"{tipo} ({cantidad})")
                    if areas_mejora:
                        info_contextual += ", ".join(areas_mejora)
                    else:
                        info_contextual += "No hay datos previos"
            
            # El asistente ya tiene instrucciones configuradas, añadimos instrucciones específicas
            # para la evaluación adaptada al nivel
            user_message = f"""
{info_contextual}

Texto para revisar (nivel declarado del estudiante: {nivel}):
"{texto_input}"

Nivel de detalle deseado: {detalle}
Idioma para explicaciones: {idioma}

IMPORTANTE: Al evaluar, considera que los errores deben penalizarse de manera diferente según el nivel del estudiante. Un error básico en un estudiante de nivel avanzado debe tener mayor impacto en la puntuación que el mismo error en un principiante.

Recuerda responder en formato json según las instrucciones.
"""
        except Exception as format_error:
            logger.error(f"Error formateando mensajes: {str(format_error)}")
            # Incluir más detalles del error para facilitar el debug
            error_details = traceback.format_exc()
            logger.debug(f"Detalles del error de formato:\n{error_details}")
            return {
                "error": True, 
                "mensaje": "Error preparando la solicitud.",
                "texto_original": texto_input
            }
        
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("openai"):
            logger.error("Circuit breaker abierto para OpenAI")
            return {
                "error": True, 
                "mensaje": "Servicio temporalmente no disponible. Por favor, inténtalo de nuevo más tarde.",
                "texto_original": texto_input
            }
        
        # Obtener el prompt ultra-conciso optimizado
        words_count = len(texto_input.split())
        optimized_prompt = get_optimized_correction_prompt(words_count, idioma)
        
        # Procesar con el asistente usando la versión con rate limiting
        try:
            # Obtener thread_id actual si existe
            thread_id = get_session_var("thread_id")
            
            # Loguear para debug
            logger.info(f"Enviando texto de longitud {len(texto_input)} palabras ({len(texto_input)} caracteres) a procesar")
            
            # Procesar con el asistente usando la versión con rate limiting y el prompt optimizado
            content, data = process_with_assistant_with_rate_limiting(
                system_message=optimized_prompt,
                user_message=user_message,
                task_type="correccion_texto",
                thread_id=thread_id,
                user_id=user_id
            )
            
            # Loguear resultado para debug
            logger.info(f"Recibida respuesta: content={type(content)}, data={type(data) if data is not None else None}")
            
            # Verificar si la respuesta tiene la estructura esperada
            if data and isinstance(data, dict):
                estructura_correcta = all(
                    campo in data for campo in ["saludo", "tipo_texto", "errores", "texto_corregido", "analisis_contextual", "consejo_final"]
                )
                if estructura_correcta:
                    logger.info("✅ Verificación exitosa: La respuesta contiene la estructura definida")
                else:
                    campos_faltantes = [campo for campo in ["saludo", "tipo_texto", "errores", "texto_corregido", "analisis_contextual", "consejo_final"] if campo not in data]
                    logger.warning(f"❌ Verificación fallida: Faltan campos en la respuesta: {campos_faltantes}")
            
        except Exception as api_error:
            logger.error(f"Error en API del asistente: {str(api_error)}")
            return {
                "error": True,
                "mensaje": "Error de comunicación con el servicio. Por favor, inténtalo de nuevo.",
                "texto_original": texto_input
            }
        
        # Validar la respuesta del asistente
        if content is None and data is None:
            logger.error("No se obtuvo respuesta del asistente (content y data son None)")
            return {
                "error": True,
                "mensaje": "No se pudo obtener una respuesta del servicio. Por favor, inténtalo de nuevo más tarde.",
                "texto_original": texto_input
            }
        
        # Intentamos extraer la respuesta JSON del contenido
        json_data = None
        
        # Si tenemos data, intentamos usarla primero
        if data is not None and isinstance(data, dict):
            json_data = data
            logger.info("Usando datos del objeto 'data'")
        
        # Si no tenemos data útil pero tenemos content, intentamos extraer JSON de él
        if (json_data is None or json_data == {}) and content:
            try:
                # Intentar extraer JSON con regex
                logger.info("Intentando extraer JSON del content")
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        json_data = json.loads(json_str)
                        logger.info("JSON extraído correctamente del content con regex")
                    except json.JSONDecodeError as je:
                        logger.warning(f"Error decodificando JSON dentro de bloques de código: {str(je)}")
                
                # Si no hay coincidencia, intentar parsear todo el content
                if not json_data:
                    try:
                        json_data = json.loads(content)
                        logger.info("Content completo procesado como JSON")
                    except json.JSONDecodeError as je:
                        logger.warning(f"El content no es un JSON válido: {str(je)}")
                        
                        # Último recurso: buscar cualquier cosa que parezca JSON
                        possible_json = re.search(r'({[\s\S]*})', content)
                        if possible_json:
                            try:
                                json_data = json.loads(possible_json.group(1))
                                logger.info("Extraído posible JSON del content con regex general")
                            except json.JSONDecodeError:
                                logger.warning("No se pudo extraer JSON con regex general")
            except Exception as extract_error:
                logger.error(f"Error extrayendo JSON: {str(extract_error)}")
        
        # Si no pudimos extraer JSON, creamos una respuesta básica
        if not json_data:
            logger.warning("No se pudo extraer JSON válido de la respuesta")
            result = {
                "error": True,
                "mensaje": "No se pudo procesar la respuesta del servicio",
                "texto_original": texto_input,
                "texto_corregido": content if content else "No se generó corrección"
            }
            return result
        
        # Añadir texto original si no está incluido
        if "texto_original" not in json_data:
            json_data["texto_original"] = texto_input
            
        # Verificar que tenemos la estructura esperada del JSON
        # El Assistant debe devolver un objeto con la estructura específica
        if "errores" not in json_data or not isinstance(json_data.get("errores"), dict):
            logger.warning(f"La estructura de errores no es la esperada: {type(json_data.get('errores', None))}")
            
            # Si errores no es un diccionario pero tenemos el texto corregido,
            # generamos una respuesta básica
            if "texto_corregido" in json_data:
                result = {
                    "texto_original": texto_input,
                    "texto_corregido": json_data["texto_corregido"],
                    "errores": {"Gramática": [], "Léxico": [], "Puntuación": [], "Estructura textual": []},
                    "analisis_contextual": {},
                    "consejo_final": json_data.get("consejo_final", "")
                }
                return result
            else:
                # Si no tenemos ni errores ni texto corregido, es un error
                logger.error("JSON sin estructura esperada y sin texto_corregido")
                return {
                    "error": True,
                    "mensaje": "La respuesta del servicio no tiene el formato esperado",
                    "texto_original": texto_input
                }
        
        # A partir de aquí tenemos un JSON válido con la estructura esperada
        # Registrar corrección en Firebase si hay usuario
        if user_id:
            try:
                # Contar errores por categoría
                errores_conteo = {}
                errores = json_data.get("errores", {})
                for categoria, lista_errores in errores.items():
                    errores_conteo[categoria.lower()] = len(lista_errores) if isinstance(lista_errores, list) else 0
                
                # Calcular puntuación si está disponible en el análisis contextual
                puntuacion = 0.0
                num_puntuaciones = 0
                
                if "analisis_contextual" in json_data:
                    analisis = json_data["analisis_contextual"]
                    for seccion in ["coherencia", "cohesion", "registro_linguistico", "adecuacion_cultural"]:
                        if seccion in analisis and "puntuacion" in analisis[seccion]:
                            try:
                                puntuacion += float(analisis[seccion]["puntuacion"])
                                num_puntuaciones += 1
                            except (ValueError, TypeError):
                                pass
                
                # Calcular promedio
                if num_puntuaciones > 0:
                    puntuacion = round(puntuacion / num_puntuaciones, 1)
                else:
                    puntuacion = 5.0  # Valor por defecto
                
                # Guardar en Firebase usando la función importada
                resultado = save_correccion(
                    user_id=user_id,
                    texto_original=texto_input,
                    texto_corregido=json_data.get("texto_corregido", ""),
                    nivel=nivel,
                    errores=errores_conteo,
                    puntuacion=puntuacion
                )
                
                logger.info(f"Corrección guardada para usuario {user_id}: {resultado}")
            except Exception as firebase_error:
                logger.error(f"Error guardando corrección en Firebase: {str(firebase_error)}")
                logger.error(traceback.format_exc())
        
        # Éxito - devolver los datos procesados
        logger.info("Procesamiento completado con éxito")
        return json_data
        
    except Exception as e:
        # Capturar detalles completos del error para diagnóstico
        error_details = traceback.format_exc()
        logger.error(f"Error corrigiendo texto: {str(e)}")
        logger.error(f"Detalles del error:\n{error_details}")
        
        # Crear respuesta de error con información útil
        error_response = {
            "error": True,
            "mensaje": f"Se produjo un error durante la corrección: {str(e)}",
            "texto_original": texto_input if 'texto_input' in locals() else "No disponible"
        }
        
        # Añadir información detallada de depuración
        if IS_DEV:
            error_response["debug_info"] = {
                "error_message": str(e),
                "error_type": str(type(e)),
                "traceback": error_details
            }
            
        return error_response

def mostrar_resultado_correccion(resultado):
    """
    Muestra el resultado de la corrección en la interfaz.
    
    Args:
        resultado (dict): Resultado de la corrección
        
    Returns:
        None
    """
    try:
        # Importación local para evitar importaciones circulares
        from features.correccion_utils import display_correccion_result
        
        # Verificar si hay un error en el resultado
        if not resultado:
            st.error("No se recibió respuesta del servicio de corrección")
            return
            
        if "error" in resultado and resultado["error"]:
            mensaje_error = resultado.get("mensaje", "Error desconocido durante la corrección")
            st.error(mensaje_error)
            
            # Información de depuración (solo en desarrollo)
            if "debug_info" in resultado:
                with st.expander("Información de depuración"):
                    st.json(resultado["debug_info"])
                    
            # Sugerencias de acciones para el usuario
            st.info("Sugerencias: Intenta con un texto más corto o verifica tu conexión a internet.")
            
            # Mostrar el texto original si está disponible
            if "texto_original" in resultado:
                with st.expander("Tu texto original"):
                    st.write(resultado["texto_original"])
            
            return
        
        # Si no hay error, mostrar el resultado normal
        display_correccion_result(resultado)
        
    except Exception as e:
        # Capturar cualquier error en la visualización
        error_details = traceback.format_exc()
        logger.error(f"Error mostrando resultado: {str(e)}")
        logger.error(f"Detalles del error:\n{error_details}")
        
        # Mostrar mensaje al usuario
        st.error(f"Error mostrando el resultado: {str(e)}")
        
        # Si tenemos el resultado original, intentar mostrar al menos el texto
        if isinstance(resultado, dict):
            if "texto_corregido" in resultado:
                st.subheader("Texto corregido")
                st.write(resultado["texto_corregido"])
            elif "texto_original" in resultado:
                with st.expander("Tu texto original"):
                    st.write(resultado["texto_original"])
