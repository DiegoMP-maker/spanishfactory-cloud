#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de integración con OpenAI Assistants v2
----------------------------------------------
Este módulo proporciona funciones mejoradas para integrar con la API de OpenAI Assistants v2,
incluyendo soporte para Function Calling, gestión robusta de threads, y manejo de errores.
"""

import logging
import streamlit as st
import time
import json
import traceback
import re

# Importaciones de módulos del proyecto
from core.clean_openai_assistant import get_clean_openai_assistants_client
from core.session_manager import get_user_info, set_session_var, get_session_var
from features.functions_definitions import get_functions_definitions, execute_function
from core.prompts_manager import get_optimized_correction_prompt
from core.thread_manager import limit_thread_history, should_limit_thread

logger = logging.getLogger(__name__)

# Constantes para gestión de threads
MAX_THREAD_MESSAGES = 6  # Número máximo de mensajes en un thread
THREAD_MESSAGE_THRESHOLD = 10  # Umbral a partir del cual se debe considerar limitar el thread

def get_thread_for_user(user_id=None):
    """
    Obtiene un hilo (thread) existente para el usuario o crea uno nuevo.
    Versión mejorada con mejor validación y manejo de errores.
    
    Args:
        user_id (str, opcional): ID del usuario
        
    Returns:
        str: ID del thread para el usuario o None si hay error
    """
    if not user_id:
        user_info = get_user_info()
        user_id = user_info.get("uid") if user_info else None
    
    if not user_id:
        logger.warning("No hay ID de usuario para obtener thread")
        return None
    
    try:
        logger.info(f"Obteniendo thread para usuario {user_id}")
        
        # Intentar obtener thread_id de Firebase
        from core.firebase_client import get_user_thread, save_user_thread
        
        # Obtener cliente de OpenAI Assistants
        assistants_client = get_clean_openai_assistants_client()
        if not assistants_client:
            logger.error("No se pudo obtener cliente de OpenAI Assistants")
            return None
        
        # Primero verificar si hay thread_id en session_state
        thread_id_session = get_session_var("thread_id")
        if thread_id_session:
            logger.info(f"Thread encontrado en session_state: {thread_id_session}")
            
            # Verificar que el thread existe y es válido
            if assistants_client.verify_thread(thread_id_session):
                logger.info(f"Thread de session_state validado: {thread_id_session}")
                
                # Verificar si el thread necesita limpieza
                if should_limit_thread(assistants_client, thread_id_session, THREAD_MESSAGE_THRESHOLD):
                    logger.info(f"El thread {thread_id_session} necesita limpieza")
                    limit_thread_history(assistants_client, thread_id_session, MAX_THREAD_MESSAGES // 2)
                
                # Si hay user_id, asegurarse de que el thread está guardado en Firebase
                if user_id:
                    try:
                        firebase_thread_id = get_user_thread(user_id)
                        
                        # Si el thread de session no coincide con el de Firebase, actualizar Firebase
                        if firebase_thread_id != thread_id_session:
                            logger.info(f"Actualizando thread en Firebase de {firebase_thread_id} a {thread_id_session}")
                            save_user_thread(user_id, thread_id_session)
                    except Exception as e:
                        logger.warning(f"Error verificando thread en Firebase: {str(e)}")
                
                # Actualizar información de perfil en el thread
                try:
                    result = assistants_client.update_thread_with_profile(thread_id_session, user_id)
                    if result:
                        logger.info(f"Perfil actualizado en thread {thread_id_session}")
                    else:
                        logger.warning(f"No se pudo actualizar perfil en thread {thread_id_session}")
                except Exception as e:
                    logger.warning(f"Error actualizando perfil en thread: {str(e)}")
                
                return thread_id_session
        
        # Si no hay thread en session_state o no es válido, intentar obtener de Firebase
        firebase_thread_id = get_user_thread(user_id)
        
        # Si encontramos un thread_id en Firebase, verificar que sea válido
        if firebase_thread_id:
            logger.info(f"Thread encontrado en Firebase: {firebase_thread_id}")
            
            # Verificar que el thread existe y es válido
            if assistants_client.verify_thread(firebase_thread_id):
                logger.info(f"Thread de Firebase validado: {firebase_thread_id}")
                
                # Verificar si el thread necesita limpieza
                if should_limit_thread(assistants_client, firebase_thread_id, THREAD_MESSAGE_THRESHOLD):
                    logger.info(f"El thread {firebase_thread_id} necesita limpieza")
                    limit_thread_history(assistants_client, firebase_thread_id, MAX_THREAD_MESSAGES // 2)
                
                # Guardar en session_state para reutilización
                set_session_var("thread_id", firebase_thread_id)
                
                # Actualizar información de perfil en el thread
                try:
                    result = assistants_client.update_thread_with_profile(firebase_thread_id, user_id)
                    if result:
                        logger.info(f"Perfil actualizado en thread {firebase_thread_id}")
                    else:
                        logger.warning(f"No se pudo actualizar perfil en thread {firebase_thread_id}")
                except Exception as e:
                    logger.warning(f"Error actualizando perfil en thread: {str(e)}")
                
                return firebase_thread_id
            else:
                logger.warning(f"Thread existente inválido para usuario {user_id}, se creará uno nuevo")
        
        # Si no hay thread válido, crear uno nuevo
        logger.info(f"Creando nuevo thread para usuario {user_id}")
        
        # Crear nuevo thread con información de perfil del usuario
        thread_response = assistants_client.create_thread(user_id=user_id)
        
        # Extraer thread_id del resultado
        if thread_response and "id" in thread_response:
            thread_id = thread_response["id"]
            
            # Guardar en Firebase
            try:
                save_user_thread(user_id, thread_id)
                logger.info(f"Nuevo thread {thread_id} guardado en Firebase para usuario {user_id}")
            except Exception as e:
                logger.warning(f"Error guardando thread en Firebase: {str(e)}")
            
            # Guardar en session_state para reutilización
            set_session_var("thread_id", thread_id)
            
            logger.info(f"Nuevo thread creado para usuario {user_id}: {thread_id}")
            return thread_id
        else:
            logger.error("No se pudo crear un nuevo thread")
            return None
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error obteniendo/creando thread para usuario {user_id}: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return None

def process_function_calls(assistant_id, thread_id, run_id, client):
    """
    Procesa las llamadas a funciones que el asistente solicita.
    
    Args:
        assistant_id (str): ID del asistente
        thread_id (str): ID del thread
        run_id (str): ID de la ejecución
        client: Cliente de OpenAI Assistants
        
    Returns:
        bool: True si se procesaron correctamente, False en caso contrario
    """
    try:
        # Verificar estado de la ejecución
        run_status = client._api_request("GET", f"/threads/{thread_id}/runs/{run_id}")
        
        if not run_status or "status" not in run_status:
            logger.error("Error obteniendo estado de la ejecución para procesar función")
            return False
        
        # Si la ejecución no requiere acción, salir
        if run_status["status"] != "requires_action":
            logger.info(f"La ejecución no requiere acción (estado: {run_status['status']})")
            return True
        
        # Verificar que el tipo de acción es function_calling
        required_action = run_status.get("required_action", {})
        action_type = required_action.get("type")
        
        if action_type != "submit_tool_outputs":
            logger.warning(f"Tipo de acción no soportado: {action_type}")
            return False
        
        # Obtener las herramientas solicitadas
        tool_calls = required_action.get("submit_tool_outputs", {}).get("tool_calls", [])
        
        if not tool_calls:
            logger.warning("No se encontraron llamadas a herramientas")
            return False
        
        # Procesar cada llamada a función
        tool_outputs = []
        
        for tool_call in tool_calls:
            # Extraer información de la llamada
            call_id = tool_call.get("id")
            function_data = tool_call.get("function", {})
            function_name = function_data.get("name")
            function_args = function_data.get("arguments", "{}")
            
            logger.info(f"Procesando llamada a función: {function_name}")
            
            try:
                # Parsear argumentos
                arguments = json.loads(function_args)
                
                # Ejecutar la función
                result = execute_function(function_name, arguments)
                
                # Añadir resultado a las salidas
                tool_outputs.append({
                    "tool_call_id": call_id,
                    "output": json.dumps(result, ensure_ascii=False)
                })
                
                logger.info(f"Función {function_name} ejecutada correctamente")
            
            except Exception as func_error:
                error_msg = f"Error ejecutando función {function_name}: {str(func_error)}"
                logger.error(error_msg)
                
                # Añadir error a las salidas
                tool_outputs.append({
                    "tool_call_id": call_id,
                    "output": json.dumps({"error": error_msg}, ensure_ascii=False)
                })
        
        # Enviar resultados al asistente
        submit_response = client._api_request(
            "POST", 
            f"/threads/{thread_id}/runs/{run_id}/submit_tool_outputs",
            data={"tool_outputs": tool_outputs}
        )
        
        if not submit_response or "status" not in submit_response:
            logger.error("Error enviando resultados de funciones al asistente")
            return False
        
        logger.info(f"Resultados de funciones enviados correctamente, nuevo estado: {submit_response['status']}")
        return True
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error procesando llamadas a funciones: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return False

def process_with_assistant_with_rate_limiting(system_message, user_message, task_type="default", thread_id=None, user_id=None):
    """
    Versión mejorada de process_with_assistant con rate limiting y backoff exponencial.
    Maneja específicamente errores de límite de tasa (TPM) de OpenAI.
    
    Args:
        system_message (str): Mensaje del sistema (instrucciones)
        user_message (str): Mensaje del usuario (contenido)
        task_type (str): Tipo de tarea ('correccion_texto', 'generacion_ejercicios', etc.)
        thread_id (str, opcional): ID del thread existente
        user_id (str, opcional): ID del usuario
        
    Returns:
        tuple: (respuesta_raw, resultado_json)
    """
    max_retries = 5
    base_delay = 2  # segundos
    
    for attempt in range(max_retries):
        try:
            # Si es el tipo de tarea de corrección de texto y es primer intento, intentar con prompt ultra-conciso
            if task_type == "correccion_texto" and attempt == 0:
                # Obtener número aproximado de palabras
                words_count = len(user_message.split())
                
                # Usar el prompt ultra-conciso
                # Extraer el idioma del mensaje del usuario
                idioma_match = re.search(r'Idioma para explicaciones:\s*(\w+)', user_message)
                idioma = idioma_match.group(1) if idioma_match else "español"
                
                # Obtener prompt optimizado
                optimized_prompt = get_optimized_correction_prompt(words_count, idioma)
                logger.info(f"Usando prompt ultra-conciso para corrección de texto (intento {attempt+1})")
                
                # Procesar con el prompt optimizado
                return process_with_assistant(optimized_prompt, user_message, task_type, thread_id, user_id)
            
            # Para otros intentos o tipos de tarea, usar el prompt normal
            return process_with_assistant(system_message, user_message, task_type, thread_id, user_id)
        
        except Exception as e:
            error_message = str(e)
            
            # Verificar si es un error de límite de tasa
            is_rate_limit = any(pattern in error_message.lower() for pattern in 
                               ["tokens per min (tpm)", "rate limit", "too many requests", "request too large"])
            
            if is_rate_limit:
                logger.warning(f"Rate limit alcanzado (intento {attempt+1}/{max_retries})")
                
                # Si es primer intento y no estábamos usando prompt ultra-conciso, intentar con él
                if attempt == 0 and task_type == "correccion_texto" and "ultra-conciso" not in str(system_message):
                    # Extraer el idioma del mensaje del usuario
                    idioma_match = re.search(r'Idioma para explicaciones:\s*(\w+)', user_message)
                    idioma = idioma_match.group(1) if idioma_match else "español"
                    
                    # Obtener prompt ultra-conciso
                    words_count = len(user_message.split())
                    optimized_prompt = get_optimized_correction_prompt(words_count, idioma)
                    
                    logger.info("Cambiando a prompt ultra-conciso para el siguiente intento")
                    
                    # No esperar, intentar inmediatamente con el prompt ultra-conciso
                    continue
                
                # Cálculo de backoff exponencial
                delay = base_delay * (2 ** attempt)
                logger.info(f"Esperando {delay} segundos antes de reintentar...")
                time.sleep(delay)
                
                if attempt == max_retries - 1:
                    # Si es el último intento, informar al usuario
                    logger.error(f"Se superó el número máximo de reintentos ({max_retries}) para el error de rate limit")
                    return None, {
                        "error": True,
                        "mensaje": "El servicio está procesando demasiadas solicitudes en este momento. Por favor, intenta nuevamente en unos minutos.",
                        "texto_original": user_message
                    }
            else:
                # Si no es un error de tasa, propagar la excepción
                logger.error(f"Error no relacionado con rate limit: {error_message}")
                raise

def process_with_assistant(system_message, user_message, task_type="default", thread_id=None, user_id=None):
    """
    Procesa un mensaje con el asistente de OpenAI usando el cliente limpio.
    Versión mejorada con soporte para Function Calling y limpieza de threads.
    
    Args:
        system_message (str): Mensaje del sistema (instrucciones)
        user_message (str): Mensaje del usuario (contenido)
        task_type (str): Tipo de tarea ('correccion_texto', 'generacion_ejercicios', etc.)
        thread_id (str, opcional): ID del thread existente
        user_id (str, opcional): ID del usuario
        
    Returns:
        tuple: (respuesta_raw, resultado_json)
    """
    # Verificar si hay thread_id
    if not thread_id:
        # Intentar obtener thread_id de session_state
        thread_id = get_session_var("thread_id")
        
        # Si no hay thread_id en session_state y hay user_id, intentar obtener/crear thread
        if not thread_id and user_id:
            thread_id = get_thread_for_user(user_id)
    
    # Obtener cliente de OpenAI Assistants limpio
    assistants_client = get_clean_openai_assistants_client()
    if not assistants_client:
        logger.error("No se pudo obtener cliente de OpenAI Assistants")
        return None, {"error": "No se pudo conectar con el servicio de asistentes"}
    
    # Añadir logging para verificar el system_message
    system_message_info = f"System message - Longitud: {len(system_message)} caracteres"
    if len(system_message) > 0:
        # Mostrar los primeros y últimos 100 caracteres para verificar sin revelar todo el contenido
        inicio = system_message[:100].replace('\n', ' ').strip()
        fin = system_message[-100:].replace('\n', ' ').strip()
        system_message_info += f"\nInicio: {inicio}...\nFin: ...{fin}"
        logger.info(system_message_info)
    else:
        logger.warning("⚠️ ADVERTENCIA: system_message está vacío - el asistente usará sus instrucciones por defecto")
    
    # Obtener funciones disponibles para el asistente
    assistant_functions = get_functions_definitions()
    
    # Registrar información del proceso
    start_time = time.time()
    logger.info(f"Procesando mensaje con asistente - Tipo: {task_type}, Thread existente: {bool(thread_id)}")
    
    try:
        # Verificar si tenemos un thread válido
        thread_id_valid = False
        if thread_id:
            thread_id_valid = assistants_client.verify_thread(thread_id)
            
            # Verificar si el thread necesita limpieza
            if thread_id_valid and should_limit_thread(assistants_client, thread_id, THREAD_MESSAGE_THRESHOLD):
                logger.info(f"Limitando historial del thread {thread_id}")
                limit_thread_history(assistants_client, thread_id, MAX_THREAD_MESSAGES // 2)
        
        # Si no tenemos thread válido, crear uno nuevo
        if not thread_id_valid:
            thread_response = assistants_client.create_thread(user_id=user_id)
            if not thread_response or "id" not in thread_response:
                logger.error("Error creando nuevo thread")
                return None, {"error": "No se pudo crear un nuevo thread"}
            
            thread_id = thread_response["id"]
            logger.info(f"Nuevo thread creado: {thread_id}")
            
            # Guardar en session_state
            set_session_var("thread_id", thread_id)
            
            # Si hay user_id, guardar en Firebase
            if user_id:
                try:
                    from core.firebase_client import save_user_thread
                    save_user_thread(user_id, thread_id)
                    logger.info(f"Thread guardado en Firebase para usuario {user_id}")
                except Exception as e:
                    logger.warning(f"Error guardando thread en Firebase: {str(e)}")
        
        # Añadir mensaje al thread
        message_response = assistants_client.add_message_to_thread(thread_id, user_message)
        if not message_response or "id" not in message_response:
            logger.error("Error añadiendo mensaje al thread")
            return None, {"error": "No se pudo añadir mensaje al thread"}
        
        # Obtener ID de asistente
        try:
            # Usar el system_message proporcionado
            assistant_id = assistants_client.get_assistant_id(task_type, system_message)
            logger.info(f"ID de asistente obtenido: {assistant_id}")
        except Exception as e:
            logger.error(f"Error obteniendo ID de asistente: {str(e)}")
            return None, {"error": f"Error obteniendo ID de asistente: {str(e)}"}
        
        # Ejecutar asistente con el thread
        run_response = assistants_client._api_request(
            "POST", 
            f"/threads/{thread_id}/runs", 
            data={
                "assistant_id": assistant_id,
                "tools": assistant_functions  # Añadir funciones disponibles
            }
        )
        
        if not run_response or "id" not in run_response:
            logger.error("Error iniciando ejecución del asistente")
            return None, {"error": "Error iniciando ejecución del asistente"}
        
        run_id = run_response["id"]
        logger.info(f"Ejecución iniciada: {run_id}")
        
        # Esperar a que la ejecución se complete (con manejo de funciones)
        max_wait_time = 120  # 2 minutos máximo
        start_wait_time = time.time()
        polling_interval = 1
        max_polling_interval = 5
        
        while True:
            # Verificar timeout
            elapsed_time = time.time() - start_wait_time
            if elapsed_time > max_wait_time:
                logger.warning(f"Timeout después de {max_wait_time}s esperando respuesta")
                return None, {"error": f"Timeout después de {max_wait_time}s esperando respuesta"}
            
            # Obtener estado de la ejecución
            run_status_response = assistants_client.get_run(thread_id, run_id)
            
            if not run_status_response or "status" not in run_status_response:
                logger.error("Error obteniendo estado de la ejecución")
                return None, {"error": "Error obteniendo estado de la ejecución"}
            
            status = run_status_response["status"]
            logger.info(f"Estado de ejecución: {status} (tiempo transcurrido: {elapsed_time:.1f}s)")
            
            # Verificar si ha terminado
            if status == "completed":
                logger.info(f"Ejecución completada en {elapsed_time:.1f}s")
                break
            
            # Verificar si ha fallado
            if status in ["failed", "cancelled", "expired"]:
                error_message = run_status_response.get("last_error", {}).get("message", "Unknown error")
                
                # Verificar específicamente si es un error de rate limiting (TPM)
                if "tokens per min (TPM)" in error_message:
                    logger.error(f"Error de rate limit (TPM): {error_message}")
                    
                    # Obtener detalles específicos del error para informar mejor
                    requested_tokens = None
                    limit_tokens = None
                    
                    # Intentar extraer los valores con regex
                    tokens_match = re.search(r'Limit (\d+), Requested (\d+)', error_message)
                    if tokens_match:
                        limit_tokens = int(tokens_match.group(1))
                        requested_tokens = int(tokens_match.group(2))
                        logger.error(f"Límite TPM: {limit_tokens}, Solicitados: {requested_tokens}")
                    
                    # Lanzar excepción con información detallada para que la maneje el rate limiter
                    raise Exception(f"Rate limit excedido: {error_message}")
                else:
                    logger.error(f"Ejecución fallida: {status} - {error_message}")
                    return None, {"error": f"Ejecución fallida: {status} - {error_message}"}
            
            # Verificar si requiere acción (función)
            if status == "requires_action":
                logger.info("La ejecución requiere acción (function calling)")
                
                # Procesar llamadas a funciones
                function_success = process_function_calls(assistant_id, thread_id, run_id, assistants_client)
                
                if not function_success:
                    logger.error("Error procesando llamadas a funciones")
                    return None, {"error": "Error procesando llamadas a funciones"}
                
                # Continuar con el siguiente ciclo (no dormir)
                continue
            
            # Esperar antes de verificar estado de nuevo
            time.sleep(polling_interval)
            
            # Ajustar intervalo de polling
            polling_interval = min(polling_interval * 1.5, max_polling_interval)
        
        # Obtener mensajes
        messages_response = assistants_client.list_messages(thread_id)
        
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
        
        # Añadir thread_id al resultado
        if isinstance(json_data, dict):
            json_data["thread_id"] = thread_id
        
        # Registrar tiempo total
        elapsed_time = time.time() - start_time
        logger.info(f"Procesamiento completado en {elapsed_time:.2f}s")
        
        # Devolver la respuesta y los datos JSON
        return content_text, json_data
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error en process_with_assistant: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        
        # Verificar si es un error de rate limit y propagarlo para que lo maneje la función con rate limiting
        if "tokens per min (TPM)" in str(e) or "rate limit" in str(e).lower():
            raise
        
        return None, {"error": f"Error en process_with_assistant: {str(e)}"}

def get_user_profile_data(user_id):
    """
    Obtiene el perfil completo del usuario.
    Función auxiliar para facilitar el acceso al perfil desde otros módulos.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Perfil completo del usuario o diccionario vacío si hay error
    """
    try:
        from features.functions_definitions import get_user_profile
        return get_user_profile(user_id)
    except Exception as e:
        logger.error(f"Error obteniendo perfil de usuario: {str(e)}")
        return {}
