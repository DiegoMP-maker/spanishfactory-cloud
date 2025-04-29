#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integración mejorada con OpenAI API
----------------------------------
Este módulo proporciona funciones para integrar la aplicación con la API de OpenAI,
específicamente con el servicio OpenAI Assistants v2, asegurando respuestas JSON.
"""

import logging
import json
import time
import traceback

# Importaciones del proyecto
from core.clean_openai_assistant import get_clean_openai_assistants_client
from core.json_extractor import extract_json_safely
from features.functions_definitions import execute_function

logger = logging.getLogger(__name__)

def process_with_assistant(system_message, user_message, task_type="default", thread_id=None, user_id=None, max_retries=3):
    """
    Procesa una solicitud utilizando OpenAI Assistants API v2 con soporte mejorado de JSON.
    
    Args:
        system_message (str): Mensaje del sistema (instrucciones)
        user_message (str): Mensaje del usuario
        task_type (str): Tipo de tarea ('correccion_texto', 'ejercicios', etc.)
        thread_id (str, opcional): ID de thread existente
        user_id (str, opcional): ID del usuario para personalización
        max_retries (int): Número máximo de reintentos
        
    Returns:
        tuple: (respuesta_texto, respuesta_json)
    """
    try:
        # Verificar parámetros
        if not user_message:
            logger.warning("Mensaje de usuario vacío en process_with_assistant")
            return None, {"error": "Mensaje de usuario vacío"}
        
        # Registrar inicio para métricas
        start_time = time.time()
        
        # Obtener cliente para OpenAI Assistants
        client = get_clean_openai_assistants_client()
        if not client:
            logger.error("No se pudo obtener cliente de OpenAI Assistants")
            return None, {"error": "Error de conexión con OpenAI"}
        
        # Verificar y mejorar system_message para garantizar respuestas JSON
        enhanced_system_message = system_message
        
        # Si no hay system_message, cargar desde el módulo apropiado
        if not enhanced_system_message or enhanced_system_message.strip() == "":
            if task_type == "correccion_texto":
                from features.correccion_service import SYSTEM_PROMPT_CORRECTION
                enhanced_system_message = SYSTEM_PROMPT_CORRECTION
                logger.info("Sistema cargado desde correccion_service.py")
        
        # Verificar que ya incluye instrucciones para formato JSON
        if "JSON" not in enhanced_system_message and "json" not in enhanced_system_message:
            logger.warning("System message no incluye instrucciones JSON, añadiendo")
            enhanced_system_message += "\n\nIMPORTANTE: Tu respuesta debe estar SIEMPRE en formato JSON válido."
        
        # Mejorar user_message añadiendo recordatorio de formato JSON
        enhanced_user_message = user_message
        if "JSON" not in enhanced_user_message and "json" not in enhanced_user_message:
            enhanced_user_message += "\n\nPor favor, responde ÚNICAMENTE con formato JSON válido."
            
        # VERIFICAR thread_id
        thread_exists = False
        if thread_id:
            thread_exists = client.verify_thread(thread_id)
            logger.info(f"Thread verificado: {thread_id}, existe: {thread_exists}")
            
        # Si no existe thread o no es válido, crear uno nuevo
        if not thread_exists:
            thread_response = client.create_thread(user_id=user_id)
            
            if not thread_response or "id" not in thread_response:
                return None, {"error": "No se pudo crear un nuevo thread"}
                
            thread_id = thread_response["id"]
            logger.info(f"Nuevo thread creado: {thread_id}")
        
        # Obtener funciones disponibles para el asistente
        from features.functions_definitions import get_functions_definitions
        assistant_functions = get_functions_definitions()
        
        # Añadir mensaje al thread
        message_response = client.add_message_to_thread(thread_id, enhanced_user_message)
        
        if not message_response or "id" not in message_response:
            return None, {"error": "Error añadiendo mensaje al thread"}
            
        logger.info(f"Mensaje añadido al thread {thread_id}")
        
        # Obtener ID del asistente
        try:
            assistant_id = client.get_assistant_id(task_type, enhanced_system_message)
            logger.info(f"ID del asistente obtenido: {assistant_id}")
        except Exception as e:
            logger.error(f"Error obteniendo ID del asistente: {str(e)}")
            return None, {"error": f"Error obteniendo asistente: {str(e)}"}
        
        # Ejecutar el asistente con reintentos
        response_content = None
        json_data = None
        
        for attempt in range(max_retries):
            try:
                # Ejecutar asistente con herramientas y formato JSON obligatorio
                run_response = client._api_request(
                    "POST", 
                    f"/threads/{thread_id}/runs", 
                    data={
                        "assistant_id": assistant_id,
                        "tools": assistant_functions,
                        # CRUCIAL: Forzar formato JSON en la respuesta
                        "response_format": {"type": "json_object"}
                    },
                    timeout=60
                )
                
                if not run_response or "id" not in run_response:
                    raise Exception("Error iniciando ejecución del asistente")
                
                run_id = run_response["id"]
                logger.info(f"Ejecución iniciada: {run_id}")
                
                # Esperar a que la ejecución se complete
                max_wait_time = 180  # 3 minutos
                start_wait_time = time.time()
                polling_interval = 1
                max_polling_interval = 5
                polling_count = 0
                
                # Bucle de polling para esperar respuesta
                while True:
                    # Verificar timeout
                    elapsed = time.time() - start_wait_time
                    if elapsed > max_wait_time:
                        raise Exception(f"Timeout después de {max_wait_time}s")
                    
                    # Consultar estado
                    run_status_response = client.get_run(thread_id, run_id)
                    
                    if not run_status_response or "status" not in run_status_response:
                        raise Exception("Error obteniendo estado de ejecución")
                    
                    status = run_status_response["status"]
                    polling_count += 1
                    
                    # Mostrar estado solo cada 5 consultas para reducir ruido en logs
                    if polling_count % 5 == 0:
                        logger.info(f"Estado de ejecución ({polling_count}): {status}")
                    
                    # Verificar si ha terminado
                    if status == "completed":
                        logger.info(f"Ejecución completada en {polling_count} consultas")
                        break
                    
                    # Verificar si ha fallado
                    if status in ["failed", "cancelled", "expired"]:
                        error_detail = run_status_response.get("last_error", {})
                        error_message = error_detail.get("message", "Unknown error")
                        raise Exception(f"Ejecución fallida: {error_message}")
                    
                    # Verificar si requiere función
                    if status == "requires_action":
                        logger.info("La ejecución requiere acción (llamada a función)")
                        
                        # Procesamiento de funciones
                        required_action = run_status_response.get("required_action", {})
                        if required_action.get("type") != "submit_tool_outputs":
                            raise Exception(f"Acción requerida no soportada: {required_action.get('type')}")
                        
                        # Obtener herramientas que se deben ejecutar
                        tool_calls = required_action.get("submit_tool_outputs", {}).get("tool_calls", [])
                        if not tool_calls:
                            raise Exception("No hay llamadas a funciones en required_action")
                        
                        # Procesar cada llamada a función
                        tool_outputs = []
                        for tool_call in tool_calls:
                            function_name = tool_call.get("function", {}).get("name")
                            function_args = tool_call.get("function", {}).get("arguments", "{}")
                            
                            logger.info(f"Ejecutando función: {function_name} con args: {function_args}")
                            
                            try:
                                # Parsear argumentos
                                arguments = json.loads(function_args)
                                
                                # Ejecutar función
                                result = execute_function(function_name, arguments)
                                
                                # Añadir salida
                                tool_outputs.append({
                                    "tool_call_id": tool_call.get("id"),
                                    "output": json.dumps(result)
                                })
                                
                                logger.info(f"Función {function_name} ejecutada correctamente")
                            except Exception as func_error:
                                logger.error(f"Error ejecutando función {function_name}: {str(func_error)}")
                                # Proporcionar un resultado vacío para continuar
                                tool_outputs.append({
                                    "tool_call_id": tool_call.get("id"),
                                    "output": json.dumps({"error": str(func_error)})
                                })
                        
                        # Enviar resultados
                        submit_response = client._api_request(
                            "POST",
                            f"/threads/{thread_id}/runs/{run_id}/submit_tool_outputs",
                            data={"tool_outputs": tool_outputs},
                            timeout=60
                        )
                        
                        if not submit_response:
                            raise Exception("Error enviando resultados de funciones")
                        
                        logger.info(f"Resultados de funciones enviados: {len(tool_outputs)} funciones")
                        
                        # Continuar con el bucle de polling
                        continue
                    
                    # Esperar antes de consultar de nuevo
                    time.sleep(polling_interval)
                    
                    # Ajustar intervalo (esperar más tiempo conforme pasa el tiempo)
                    polling_interval = min(polling_interval * 1.5, max_polling_interval)
                
                # Obtener mensajes
                messages_response = client.list_messages(thread_id)
                
                if not messages_response or "data" not in messages_response:
                    raise Exception("Error obteniendo mensajes del thread")
                
                # Buscar último mensaje del asistente
                assistant_message = None
                for message in messages_response["data"]:
                    if message["role"] == "assistant":
                        assistant_message = message
                        break
                
                if not assistant_message:
                    raise Exception("No se encontró respuesta del asistente")
                
                # Extraer contenido
                response_content = ""
                for content_item in assistant_message.get("content", []):
                    if content_item["type"] == "text":
                        response_content += content_item["text"]["value"]
                
                if not response_content:
                    raise Exception("Respuesta vacía del asistente")
                
                # Extraer JSON
                json_data = extract_json_safely(response_content)
                
                # Añadir thread_id al resultado
                if isinstance(json_data, dict):
                    json_data["thread_id"] = thread_id
                
                # Si llegamos aquí, tenemos respuesta exitosa
                total_time = time.time() - start_time
                logger.info(f"Proceso completado en {total_time:.2f}s después de {attempt+1} intentos")
                
                # Añadir métricas a la respuesta
                if isinstance(json_data, dict):
                    json_data["_metrics"] = {
                        "processing_time": total_time,
                        "attempts": attempt + 1
                    }
                
                return response_content, json_data
                
            except Exception as e:
                logger.warning(f"Error en intento {attempt+1}/{max_retries}: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Si no es el último intento, esperar y reintentar
                    wait_time = 2 ** attempt  # Backoff exponencial
                    logger.info(f"Esperando {wait_time}s antes de reintentar")
                    time.sleep(wait_time)
                else:
                    # Si es el último intento, registrar error detallado
                    logger.error(f"Error final después de {max_retries} intentos: {str(e)}")
                    logger.debug(traceback.format_exc())
                    
                    return response_content, {
                        "error": str(e),
                        "thread_id": thread_id
                    }
        
        # Si llegamos aquí, todos los intentos fallaron
        logger.error(f"Todos los intentos fallaron en process_with_assistant")
        return None, {"error": "Todos los intentos de procesar la solicitud fallaron"}
        
    except Exception as e:
        # Error general
        error_details = traceback.format_exc()
        logger.error(f"Error general en process_with_assistant: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        
        return None, {"error": f"Error: {str(e)}"}

def process_function_calls(assistant_id, thread_id, run_id, client):
    """
    Procesa las llamadas a funciones del asistente.
    Esta función es usada cuando el asistente requiere ejecutar una función.
    
    Args:
        assistant_id (str): ID del asistente
        thread_id (str): ID del thread
        run_id (str): ID de la ejecución
        client: Cliente de OpenAI Assistants
        
    Returns:
        bool: True si el procesamiento fue exitoso
    """
    try:
        # Verificar que tenemos un cliente válido
        if not client:
            logger.error("Cliente no válido en process_function_calls")
            return False
        
        # Obtener detalles de la ejecución
        run_details = client.get_run(thread_id, run_id)
        
        if "required_action" not in run_details:
            logger.error("La ejecución no requiere acción")
            return False
        
        required_action = run_details["required_action"]
        if "submit_tool_outputs" not in required_action.get("type", ""):
            logger.error(f"Tipo de acción no soportado: {required_action.get('type')}")
            return False
        
        # Obtener las llamadas a funciones pendientes
        tool_calls = required_action.get("submit_tool_outputs", {}).get("tool_calls", [])
        
        if not tool_calls:
            logger.warning("No hay llamadas a funciones pendientes")
            return False
        
        # Procesar cada llamada a función
        tool_outputs = []
        
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            function_args = tool_call.get("function", {}).get("arguments", "{}")
            
            logger.info(f"Procesando llamada a función: {function_name}")
            
            # Parsear argumentos
            try:
                args = json.loads(function_args)
            except json.JSONDecodeError:
                logger.error(f"Error al parsear argumentos: {function_args}")
                args = {}
            
            # Ejecutar la función correspondiente
            result = execute_function(function_name, args)
            
            # Añadir resultado a los outputs
            tool_outputs.append({
                "tool_call_id": tool_call.get("id"),
                "output": json.dumps(result)
            })
        
        # Enviar los resultados a la API
        submit_response = client._api_request(
            "POST",
            f"/threads/{thread_id}/runs/{run_id}/submit_tool_outputs",
            data={"tool_outputs": tool_outputs},
            timeout=60
        )
        
        if not submit_response:
            logger.error("Error al enviar los resultados de las funciones")
            return False
        
        logger.info(f"Resultados de funciones enviados correctamente: {len(tool_outputs)} funciones")
        return True
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error en process_function_calls: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return False
