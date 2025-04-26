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

from core.openai_integration import process_with_assistant
from core.circuit_breaker import circuit_breaker
from core.session_manager import get_user_info, get_session_var
from config.settings import NIVELES_ESPANOL
from config.settings import IS_DEV  

logger = logging.getLogger(__name__)

def corregir_texto(texto_input, nivel, detalle="Intermedio", user_id=None, idioma="español"):
    """
    Procesa un texto con el asistente de OpenAI para obtener correcciones.
    
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
        
        # Preparar mensaje para el asistente
        try:
            # El asistente ya tiene instrucciones configuradas, añadimos instrucciones específicas
            # para la evaluación adaptada al nivel
            user_message = f"""
Texto para revisar (nivel declarado del estudiante: {nivel}):
"{texto_input}"

Nivel de detalle deseado: {detalle}
Idioma para explicaciones: {idioma}

IMPORTANTE: Al evaluar, considera que los errores deben penalizarse de manera diferente según el nivel del estudiante. Un error básico en un estudiante de nivel avanzado debe tener mayor impacto en la puntuación que el mismo error en un principiante.
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
        
        # Procesar con el asistente
        try:
            # Obtener thread_id actual si existe
            thread_id = get_session_var("thread_id")
            
            # Loguear para debug
            logger.info(f"Enviando texto de longitud {len(texto_input)} a procesar")
            
            # Procesar con el asistente usando la nueva interfaz
            content, data = process_with_assistant(
                system_message="",  # Vacío, ya que el asistente tiene su propio system message
                user_message=user_message,
                task_type="correccion_texto",
                thread_id=thread_id,
                user_id=user_id
            )
            
            # Loguear resultado para debug
            logger.info(f"Recibida respuesta: content={type(content)}, data={type(data) if data is not None else None}")
            
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
                from core.firebase_client import save_correccion
                
                # Contar errores por categoría
                errores_conteo = {}
                errores = json_data.get("errores", {})
                for categoria, lista_errores in errores.items():
                    errores_conteo[categoria] = len(lista_errores) if isinstance(lista_errores, list) else 0
                
                # Guardar en Firebase
                save_correccion(
                    user_id=user_id,
                    texto_original=texto_input,
                    texto_corregido=json_data.get("texto_corregido", ""),
                    nivel=nivel,
                    errores=errores_conteo,
                    puntuacion=json_data.get("puntuacion", 8.0)  # Usar valor del json o valor por defecto
                )
                
                logger.info(f"Corrección guardada para usuario {user_id}")
            except Exception as firebase_error:
                logger.error(f"Error guardando corrección en Firebase: {str(firebase_error)}")
        
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