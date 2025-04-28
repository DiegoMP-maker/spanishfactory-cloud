#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integración Mejorada con OpenAI Assistants v2
---------------------------------------------
Implementa optimizaciones para reducir consumo de tokens y
mejorar la eficiencia de las interacciones con los asistentes.
"""

import logging
import time
import json
import streamlit as st

# Importaciones del proyecto
from core.clean_openai_assistant import get_clean_openai_assistants_client
from core.thread_manager import get_optimized_thread, summarize_thread_context
from config.optimized_prompts import get_optimized_prompt
from core.session_manager import get_user_info, set_session_var, get_session_var

logger = logging.getLogger(__name__)

# Aumentar el timeout para evitar problemas con tareas complejas
DEFAULT_TIMEOUT = 180  # 3 minutos
EXTENDED_TIMEOUT = 300  # 5 minutos

def process_with_optimized_assistant(
    prompt_type, 
    user_message, 
    thread_id=None, 
    user_id=None, 
    max_retries=3,
    optimize_context=True
):
    """
    Procesa un mensaje con un asistente optimizado para reducir consumo de tokens.
    
    Args:
        prompt_type (str): Tipo de prompt ('correction', 'exercises', 'exam', 'study_plan')
        user_message (str): Mensaje del usuario
        thread_id (str, opcional): ID del thread existente
        user_id (str, opcional): ID del usuario
        max_retries (int): Número máximo de reintentos
        optimize_context (bool): Si se debe optimizar el contexto del thread
        
    Returns:
        tuple: (respuesta_raw, resultado_json)
    """
    # Iniciar temporizador para métricas
    start_time = time.time()
    
    # Registrar longitud del mensaje para métricas
    message_length = len(user_message)
    logger.info(f"Procesando mensaje de {message_length} caracteres con prompt optimizado tipo '{prompt_type}'")
    
    # Obtener ID de usuario si no se proporciona
    if not user_id:
        user_info = get_user_info()
        user_id = user_info.get("uid") if user_info else None
    
    # Usar thread optimizado en lugar del thread normal
    if not thread_id:
        thread_id = get_optimized_thread(user_id)
        logger.info(f"Usando thread optimizado: {thread_id}")
    
    # Obtener cliente de OpenAI Assistants
    assistants_client = get_clean_openai_assistants_client()
    if not assistants_client:
        logger.error("No se pudo obtener cliente de OpenAI Assistants")
        return None, {"error": "No se pudo conectar con el servicio de asistentes"}
    
    # Obtener prompt optimizado según tipo
    system_message = get_optimized_prompt(prompt_type)
    
    # Verificar longitud del prompt para evitar consumo excesivo
    prompt_length = len(system_message)
    logger.info(f"Longitud del prompt optimizado: {prompt_length} caracteres")
    
    # Si el prompt es muy largo (más de 10K), usar versión simplificada
    if prompt_length > 10000:
        logger.warning(f"Prompt demasiado largo ({prompt_length} caracteres), generando versión más compacta")
        # Extraer secciones principales y reducir detalles
        import re
        sections = re.findall(r'##\s+([^\n]+)', system_message)
        compact_prompt = f"# Asistente de {prompt_type.capitalize()} para ELE\n\n"
        compact_prompt += "## FORMATO DE RESPUESTA\n"
        
        # Extraer sección de formato JSON
        json_format = re.search(r'```json\s*([\s\S]*?)```', system_message)
        if json_format:
            compact_prompt += f"Responde ÚNICAMENTE con este formato JSON:\n\n```json\n{json_format.group(1).strip()}\n```\n\n"
        
        compact_prompt += "## INSTRUCCIONES RESUMIDAS\n"
        compact_prompt += "- Adapta al nivel MCER del estudiante (A1-C2)\n"
        compact_prompt += "- Sé claro, didáctico y preciso\n"
        compact_prompt += "- Responde SOLO con formato JSON válido\n"
        
        system_message = compact_prompt
        logger.info(f"Prompt compactado a {len(system_message)} caracteres")
    
    try:
        # Verificar validez del thread
        thread_valid = False
        if thread_id:
            thread_valid = assistants_client.verify_thread(thread_id)
        
        # Si no es válido, obtener uno nuevo
        if not thread_valid:
            thread_id = get_optimized_thread(user_id, force_new=True)
            logger.info(f"Creado nuevo thread: {thread_id}")
        
        # Optimizar contexto si es necesario
        if optimize_context and thread_valid:
            # Verificar tamaño del thread
            from core.firebase_client_additions import get_thread_message_count
            message_count = get_thread_message_count(thread_id)
            
            # Si el thread es grande, considerar resumirlo
            if message_count and message_count > 10:
                logger.info(f"Thread tiene {message_count} mensajes, considerando optimización de contexto")
                
                # Calcular umbral según tipo de tarea (corrección más sensible al contexto)
                threshold = 15 if prompt_type == "correction" else 12
                
                if message_count > threshold:
                    logger.info(f"Iniciando resumen de contexto para thread con {message_count} mensajes")
                    summarize_success = summarize_thread_context(thread_id, user_id)
                    
                    if summarize_success:
                        # Obtener nuevo thread_id después de resumir
                        thread_id = get_session_var("thread_id")
                        logger.info(f"Contexto resumido exitosamente, usando nuevo thread: {thread_id}")
                    else:
                        logger.warning("No se pudo resumir contexto, continuando con thread original")
        
        # Añadir mensaje al thread
        message_response = assistants_client.add_message_to_thread(thread_id, user_message)
        if not message_response or "id" not in message_response:
            logger.error("Error añadiendo mensaje al thread")
            return None, {"error": "No se pudo añadir mensaje al thread"}
        
        # Obtener ID de asistente
        try:
            assistant_id = assistants_client.get_assistant_id(prompt_type, system_message)
            logger.info(f"ID de asistente obtenido para {prompt_type}: {assistant_id}")
        except Exception as e:
            logger.error(f"Error obteniendo ID de asistente: {str(e)}")
            return None, {"error": f"Error obteniendo ID de asistente: {str(e)}"}
        
        # Optimización de configuración del asistente
        for attempt in range(max_retries):
            try:
                # Ejecutar asistente con configuración optimizada
                run_response = assistants_client._api_request(
                    "POST", 
                    f"/threads/{thread_id}/runs", 
                    data={
                        "assistant_id": assistant_id,
                        # Uso de herramientas optimizado según tipo de tarea
                        "tools": [
                            {"type": "code_interpreter"},
                            {"type": "file_search"},
                            # Solo incluir funciones si es necesario
                            *get_optimized_tools_for_task(prompt_type)
                        ],
                        # Forzar formato JSON para reducir ambigüedad y facilitar parsing
                        "response_format": {"type": "json_object"}
                    },
                    # Aumentar timeout para tareas complejas
                    timeout=60  # aumentado para iniciar ejecución
                )
                
                if not run_response or "id" not in run_response:
                    raise Exception("Error iniciando ejecución del asistente")
                
                run_id = run_response["id"]
                logger.info(f"Ejecución iniciada: {run_id}")
                
                # Esperar a que la ejecución se complete (con timeout adaptativo)
                timeout = DEFAULT_TIMEOUT
                if prompt_type in ["correction", "study_plan"] or message_length > 1000:
                    timeout = EXTENDED_TIMEOUT  # Extender para tareas complejas
                
                logger.info(f"Usando timeout adaptativo de {timeout}s para tarea tipo '{prompt_type}'")
                
                result_text, result_json = wait_for_completion(
                    assistants_client, thread_id, run_id, timeout
                )
                
                # Si tenemos resultados, registrar métricas y devolver
                if result_text or result_json:
                    elapsed_time = time.time() - start_time
                    logger.info(f"Procesamiento completado en {elapsed_time:.2f}s")
                    
                    # Guardar métricas
                    save_task_metrics(
                        prompt_type=prompt_type,
                        thread_id=thread_id,
                        processing_time=elapsed_time,
                        message_length=message_length,
                        success=(result_json is not None and "error" not in result_json)
                    )
                    
                    # Añadir thread_id al resultado
                    if isinstance(result_json, dict):
                        result_json["thread_id"] = thread_id
                    
                    return result_text, result_json
                
                # Si no hay resultados, reintentar
                logger.warning(f"No se obtuvieron resultados en intento {attempt+1}/{max_retries}, reintentando")
                time.sleep(2 ** attempt)  # Backoff exponencial
                
            except Exception as e:
                logger.error(f"Error en intento {attempt+1}/{max_retries}: {str(e)}")
                
                if attempt == max_retries - 1:
                    # Si es el último intento, registrar fallo y devolver error
                    elapsed_time = time.time() - start_time
                    save_task_metrics(
                        prompt_type=prompt_type,
                        thread_id=thread_id,
                        processing_time=elapsed_time,
                        message_length=message_length,
                        success=False
                    )
                    
                    return None, {
                        "error": f"Error: {str(e)}",
                        "thread_id": thread_id
                    }
                
                # Esperar antes de reintentar
                wait_time = min(60, 2 ** attempt)
                logger.info(f"Esperando {wait_time}s antes de reintentar")
                time.sleep(wait_time)
        
        # Si llegamos aquí, todos los intentos fallaron
        return None, {"error": "Todos los intentos fallaron", "thread_id": thread_id}
        
    except Exception as e:
        # Error general
        logger.error(f"Error general: {e}")
        elapsed_time = time.time() - start_time
        
        save_task_metrics(
            prompt_type=prompt_type,
            thread_id=thread_id,
            processing_time=elapsed_time,
            message_length=message_length,
            success=False
        )
        
        return None, {
            "error": f"Error general: {str(e)}",
            "thread_id": thread_id
        }

def wait_for_completion(client, thread_id, run_id, timeout=DEFAULT_TIMEOUT):
    """
    Espera a que se complete una ejecución con manejo optimizado de polling.
    
    Args:
        client: Cliente de OpenAI Assistants
        thread_id: ID del thread
        run_id: ID de la ejecución
        timeout: Timeout máximo en segundos
        
    Returns:
        tuple: (texto_respuesta, json_respuesta)
    """
    start_time = time.time()
    polling_interval = 1
    max_polling_interval = 5
    polling_count = 0
    
    while True:
        # Verificar timeout
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            logger.warning(f"Timeout después de {timeout}s esperando respuesta")
            return None, {"error": f"Timeout después de {timeout}s esperando respuesta"}
        
        # Ajustar intervalo según tiempo transcurrido (polling adaptativo)
        if elapsed_time < 10:
            current_interval = 1  # Verificar cada segundo al inicio
        elif elapsed_time < 30:
            current_interval = 2  # Cada 2 segundos en fase intermedia
        else:
            # Aumentar gradualmente hasta el máximo
            current_interval = min(polling_interval * 1.5, max_polling_interval)
            polling_interval = current_interval
        
        # Esperar antes de verificar estado
        time.sleep(current_interval)
        
        # Obtener estado de la ejecución
        polling_count += 1
        run_status_response = client.get_run(thread_id, run_id)
        
        if not run_status_response or "status" not in run_status_response:
            logger.error("Error obteniendo estado de la ejecución")
            return None, {"error": "Error obteniendo estado de la ejecución"}
        
        status = run_status_response["status"]
        
        # Log menos frecuente para reducir ruido
        if polling_count % 5 == 0 or status != "in_progress":
            logger.info(f"Estado de ejecución ({polling_count}): {status} (tiempo: {elapsed_time:.1f}s)")
        
        # Verificar si ha terminado
        if status == "completed":
            logger.info(f"Ejecución completada en {elapsed_time:.1f}s después de {polling_count} verificaciones")
            break
        
        # Verificar si ha fallado
        if status in ["failed", "cancelled", "expired"]:
            error_message = run_status_response.get("last_error", {}).get("message", "Unknown error")
            logger.error(f"Ejecución fallida: {status} - {error_message}")
            return None, {"error": f"Ejecución fallida: {status} - {error_message}"}
        
        # Verificar si requiere acción (función)
        if status == "requires_action":
            logger.info("La ejecución requiere acción (function calling)")
            
            # Importar dinámicamente para evitar importación circular
            from core.openai_integration import process_function_calls
            
            # Procesar llamadas a funciones (versión original)
            function_success = process_function_calls(
                assistant_id=run_status_response.get("assistant_id", ""),
                thread_id=thread_id,
                run_id=run_id,
                client=client
            )
            
            if not function_success:
                logger.error("Error procesando llamadas a funciones")
                return None, {"error": "Error procesando llamadas a funciones"}
    
    # Obtener mensajes
    messages_response = client.list_messages(thread_id)
    
    if not messages_response or "data" not in messages_response:
        logger.error("Error obteniendo mensajes del thread")
        return None, {"error": "Error obteniendo mensajes del thread"}
    
    # Buscar el mensaje más reciente del asistente
    assistant_message = None
    for message in messages_response["data"]:
        if message["role"] == "assistant":
            assistant_message = message
            break
    
    if not assistant_message:
        logger.error("No se encontró respuesta del asistente")
        return None, {"error": "No se encontró respuesta del asistente"}
    
    # Extraer contenido del mensaje
    content_text = ""
    for content_item in assistant_message.get("content", []):
        if content_item["type"] == "text":
            content_text += content_item["text"]["value"]
    
    # Extraer JSON del contenido
    from core.clean_openai_assistant import extract_json_safely
    json_data = extract_json_safely(content_text)
    
    return content_text, json_data

def get_optimized_tools_for_task(task_type):
    """
    Obtiene lista optimizada de herramientas según el tipo de tarea.
    
    Args:
        task_type (str): Tipo de tarea
        
    Returns:
        list: Lista de herramientas optimizada
    """
    # Importar dinámicamente para evitar importación circular
    from features.functions_definitions import get_functions_definitions
    
    # Obtener todas las funciones disponibles
    all_functions = get_functions_definitions()
    
    # Mapeo de qué funciones son relevantes para cada tipo de tarea
    task_function_map = {
        "correction": ["get_user_profile", "get_assessment_examples", "get_error_patterns"],
        "exercises": ["get_user_profile", "get_exercise_examples", "get_vocabulary_by_level"],
        "exam": ["get_exam_format", "get_assessment_criteria"],
        "study_plan": ["get_user_profile", "get_learning_resources", "get_error_patterns"],
        "default": ["get_user_profile"]
    }
    
    # Obtener nombres de funciones relevantes para esta tarea
    relevant_function_names = task_function_map.get(task_type, task_function_map["default"])
    
    # Filtrar solo las funciones relevantes
    filtered_functions = []
    for func in all_functions:
        if func["type"] == "function":
            function_name = func["function"].get("name", "")
            if function_name in relevant_function_names:
                filtered_functions.append(func)
    
    return filtered_functions

def save_task_metrics(prompt_type, thread_id, processing_time, message_length, success):
    """
    Guarda métricas de procesamiento para análisis y optimización.
    
    Args:
        prompt_type (str): Tipo de prompt/tarea
        thread_id (str): ID del thread
        processing_time (float): Tiempo de procesamiento en segundos
        message_length (int): Longitud del mensaje
        success (bool): Si el procesamiento fue exitoso
    """
    try:
        # Obtener usuario actual
        user_info = get_user_info()
        user_id = user_info.get("uid") if user_info else None
        
        # Guardar métricas en session_state para análisis local
        metrics_key = f"metrics_{int(time.time())}"
        metrics_data = {
            "prompt_type": prompt_type,
            "thread_id": thread_id,
            "processing_time": processing_time,
            "message_length": message_length,
            "success": success,
            "timestamp": time.time(),
            "user_id": user_id
        }
        
        if not hasattr(st, "session_state"):
            return
        
        # Inicializar lista de métricas si no existe
        if "task_metrics" not in st.session_state:
            st.session_state["task_metrics"] = []
        
        # Añadir métricas actuales
        st.session_state["task_metrics"].append(metrics_data)
        
        # Limitar tamaño de lista de métricas (mantener últimas 50)
        if len(st.session_state["task_metrics"]) > 50:
            st.session_state["task_metrics"] = st.session_state["task_metrics"][-50:]
        
        # Intentar guardar en Firebase si está disponible
        try:
            # Importar dinámicamente para evitar importación circular
            from firebase_admin import firestore
            import firebase_admin
            
            if firebase_admin._apps:
                db = firestore.client()
                db.collection("task_metrics").add(metrics_data)
        except Exception as firebase_error:
            logger.debug(f"No se pudieron guardar métricas en Firebase: {firebase_error}")
            
    except Exception as e:
        logger.debug(f"Error guardando métricas de tarea: {e}")
        # No crítico, continuar sin error
