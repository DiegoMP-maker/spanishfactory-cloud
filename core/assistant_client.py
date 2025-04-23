#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cliente para OpenAI Assistants API
---------------------------------
Este módulo proporciona una interfaz para interactuar con OpenAI Assistants API,
gestionar threads, mensajes y ejecuciones de forma robusta con soporte para reintentos.
"""

# Primero todas las importaciones de futuros
from __future__ import annotations

# Luego importaciones estándar
import logging
import traceback
import time
import json
import re

# Después importaciones de terceros
import streamlit as st
from typing import Tuple, Dict, Any, List, Optional, Union

# Finalmente importaciones del proyecto
from config.settings import MAX_RETRIES, DEFAULT_TIMEOUT, OPENAI_MODELS_PREFERIDOS_CAPACIDAD
from core.circuit_breaker import circuit_breaker, retry_with_backoff

# Configurar logger
logger = logging.getLogger(__name__)

def extract_json_from_content(content):
    """
    Extrae JSON válido de una cadena de texto que puede contener otros elementos.
    Maneja diversos casos incluyendo JSON con y sin anotación, múltiples bloques JSON,
    y formatos irregulares.
    
    Args:
        content (str): Contenido que puede incluir JSON
        
    Returns:
        dict/None: Diccionario con el JSON extraído o None si no se encuentra
    """
    if not content:
        return None
    
    # Eliminar marcas de código y texto que no forme parte del JSON
    try:
        # Patrón para extraer JSON entre comillas triples
        triple_quotes_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        json_matches = re.findall(triple_quotes_pattern, content)
        
        # Patrón alternativo para JSON entre llaves (más agresivo, puede capturar texto no válido)
        if not json_matches:
            brace_pattern = r'(\{[\s\S]*\})'
            json_matches = re.findall(brace_pattern, content)
        
        # Probar cada coincidencia hasta encontrar JSON válido
        for match in json_matches:
            try:
                # Limpiar la cadena
                clean_json = match.strip()
                data = json.loads(clean_json)
                return data
            except json.JSONDecodeError:
                continue
        
        # Si no se encontró JSON válido hasta ahora, intentar con el texto completo
        try:
            # Algunos modelos pueden devolver JSON sin marcadores
            data = json.loads(content.strip())
            return data
        except json.JSONDecodeError:
            pass
        
        # Intentar una extracción más agresiva buscando el primer { y último }
        try:
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                potential_json = content[start_idx:end_idx+1]
                data = json.loads(potential_json)
                return data
        except json.JSONDecodeError:
            pass
        
        # Último recurso: estrategia de búsqueda incremental
        try:
            start_idx = content.find('{')
            if start_idx != -1:
                # Buscar el cierre de llave correspondiente
                open_count = 0
                for i in range(start_idx, len(content)):
                    if content[i] == '{':
                        open_count += 1
                    elif content[i] == '}':
                        open_count -= 1
                        if open_count == 0:
                            # Encontramos un bloque JSON potencialmente válido
                            potential_json = content[start_idx:i+1]
                            try:
                                data = json.loads(potential_json)
                                return data
                            except json.JSONDecodeError:
                                # Continuar buscando otro bloque JSON
                                pass
        except Exception:
            pass
        
        # Si llegamos aquí, no se encontró JSON válido
        logger.warning("No se pudo extraer JSON válido del contenido")
        return {}
        
    except Exception as e:
        logger.error(f"Error extrayendo JSON del contenido: {str(e)}")
        return {}

class AssistantClient:
    """
    Cliente para interactuar con la API de Assistants de OpenAI.
    Proporciona métodos para gestionar threads, mensajes y ejecuciones de asistentes.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el cliente de Assistants.
        
        Args:
            api_key: API key de OpenAI
        """
        self.api_key = api_key
        self.current_model = OPENAI_MODELS_PREFERIDOS_CAPACIDAD[0] if OPENAI_MODELS_PREFERIDOS_CAPACIDAD else "gpt-4-turbo-preview"
        self.client = None
        
        # Inicializar el cliente de OpenAI
        try:
            if self.api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info("Cliente OpenAI inicializado correctamente")
            else:
                logger.warning("No se proporcionó API key para OpenAI")
        except Exception as e:
            logger.error(f"Error inicializando cliente OpenAI: {str(e)}")
            self.client = None

    def get_or_create_thread_for_user(self, uid: str, email: str = None) -> Optional[str]:
        """
        Obtiene un thread existente para el usuario o crea uno nuevo.
        Actualiza Firestore con el thread_id.

        Args:
            uid: UID del usuario
            email: Email del usuario (opcional)

        Returns:
            str: ID del thread para el usuario o None si hay error
        """
        from core.firebase_client import get_user_thread, save_user_thread
        
        if not uid:
            logger.warning("No se proporcionó UID para el thread")
            return None
            
        # Intentar obtener thread_id existente
        thread_id = get_user_thread(uid)
        
        if thread_id:
            # Verificar que el thread existe y es válido
            try:
                # Obtener mensajes para verificar que el thread existe
                messages = self.get_thread_messages(thread_id, limit=1)
                if messages is not None:
                    logger.info(f"Thread existente recuperado para usuario {uid}: {thread_id}")
                    return thread_id
            except Exception as e:
                logger.warning(f"Thread existente inválido para usuario {uid}: {e}")
                # Continuar para crear uno nuevo
        
        # Crear un nuevo thread
        thread_id = self.create_thread()
        
        # Si se creó correctamente, guardar en Firebase
        if thread_id:
            save_user_thread(uid, thread_id, email)
            logger.info(f"Nuevo thread creado para usuario {uid}: {thread_id}")
        
        return thread_id

    def process_with_assistant(self, system_message: str, user_message: str, 
                              task_type: str = "default", thread_id: str = None,
                              user_uid: str = None, max_retries: int = MAX_RETRIES) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Procesa un mensaje con el asistente de OpenAI con soporte para timeout y reintentos.
        Este método combina varias operaciones: obtener/crear thread, obtener assistant_id,
        añadir mensaje y ejecutar el asistente.

        Args:
            system_message: Mensaje del sistema (instrucciones)
            user_message: Mensaje del usuario (contenido)
            task_type: Tipo de tarea ('correccion_texto', 'generacion_ejercicios', etc.)
            thread_id: ID del thread existente (opcional)
            user_uid: UID del usuario para asociar thread (opcional)
            max_retries: Número máximo de reintentos

        Returns:
            tuple: (respuesta_raw, resultado_json)
        """
        # Verificar que OpenAI esté configurado
        if self.api_key is None or self.client is None:
            return None, {"error": "API de OpenAI no configurada o inicializada"}

        # Verificar circuit breaker
        if not circuit_breaker.can_execute("openai"):
            return None, {"error": "Servicio OpenAI temporalmente no disponible"}
            
        # Si no hay thread_id pero hay user_uid, intentar obtener o crear thread para el usuario
        if not thread_id and user_uid:
            thread_id = self.get_or_create_thread_for_user(user_uid)
            # Guardar thread_id en session_state para uso futuro
            if thread_id:
                set_session_var("thread_id", thread_id)
            
        # Si no hay thread_id (y no se pudo obtener/crear), crear uno temporal
        if not thread_id:
            thread_id = self.create_thread()
            if not thread_id:
                return None, {"error": "No se pudo crear thread para la conversación"}
            # Guardar thread_id temporal en session_state
            set_session_var("thread_id", thread_id)

        # Registrar tiempo para métricas
        tiempo_inicio = time.time()
        longitud_estimada = len(user_message.split())

        # Ejecutar con reintentos
        for attempt in range(max_retries):
            try:
                # Determinar qué asistente usar
                try:
                    assistant_id = self.get_assistant_id(task_type, system_message)
                except Exception as e:
                    return None, {"error": f"Error al obtener ID de asistente: {str(e)}"}

                # Añadir mensaje al thread
                if not self.add_message_to_thread(thread_id, user_message):
                    return None, {"error": "Error al añadir mensaje al thread"}

                # Ejecutar el asistente con timeout extendido
                result = self.run_assistant(thread_id, assistant_id, timeout=DEFAULT_TIMEOUT)
                
                if not result:
                    if attempt == max_retries - 1:
                        tiempo_total = time.time() - tiempo_inicio
                        from core.firebase_client import save_model_metrics
                        save_model_metrics(
                            modelo=self.current_model,
                            tiempo_respuesta=tiempo_total,
                            longitud_texto=longitud_estimada,
                            resultado_exitoso=False
                        )
                        return None, {"error": "Error al ejecutar asistente"}
                    else:
                        wait_time = min(60, 2 ** attempt)
                        logger.info(f"Esperando {wait_time}s antes de reintentar")
                        time.sleep(wait_time)
                        continue
                
                # Obtener contenido y datos JSON
                content = result.get("content", "")
                data_json = result.get("data", {})
                
                # Asegurar que tiene marcador via_assistant
                if isinstance(data_json, dict) and "via_assistant" not in data_json:
                    data_json["via_assistant"] = True
                
                # Registrar métricas
                tiempo_total = time.time() - tiempo_inicio
                from core.firebase_client import save_model_metrics
                save_model_metrics(
                    modelo=self.current_model,
                    tiempo_respuesta=tiempo_total,
                    longitud_texto=longitud_estimada,
                    resultado_exitoso="error" not in data_json
                )
                
                # Registrar éxito
                circuit_breaker.record_success("openai")
                
                return content, data_json
                
            except Exception as e:
                logger.error(f"Error en intento {attempt+1}/{max_retries}: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Si es el último intento, registrar fallo
                if attempt == max_retries - 1:
                    circuit_breaker.record_failure("openai", error_type="general")
                    tiempo_total = time.time() - tiempo_inicio
                    from core.firebase_client import save_model_metrics
                    save_model_metrics(
                        modelo=self.current_model,
                        tiempo_respuesta=tiempo_total,
                        longitud_texto=longitud_estimada,
                        resultado_exitoso=False
                    )
                    return None, {"error": f"Error en OpenAI Assistants API: {str(e)}"}
                
                # Esperar antes de reintentar
                wait_time = min(60, 2 ** attempt)
                logger.info(f"Esperando {wait_time}s antes de reintentar")
                time.sleep(wait_time)
        
        # Este punto no debería alcanzarse nunca, pero por si acaso
        return None, {"error": "Error inesperado en process_with_assistant"}
    
    # Métodos auxiliares usados en los métodos anteriores
    def get_thread_messages(self, thread_id: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene los mensajes de un thread.
        
        Args:
            thread_id: ID del thread
            limit: Número máximo de mensajes a obtener
            
        Returns:
            list: Lista de mensajes o None si hay error
        """
        try:
            if not self.client:
                return None
                
            # Obtener mensajes del thread
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                limit=limit
            )
            
            # Convertir a formato más sencillo
            result = []
            for message in messages.data:
                message_data = {
                    "id": message.id,
                    "role": message.role,
                    "created_at": message.created_at,
                    "content": []
                }
                
                # Extraer contenido
                for content_item in message.content:
                    if hasattr(content_item, 'text'):
                        message_data["content"].append({
                            "type": "text",
                            "text": content_item.text.value
                        })
                
                result.append(message_data)
            
            return result
        except Exception as e:
            logger.error(f"Error obteniendo mensajes del thread: {str(e)}")
            return None
    
    def create_thread(self) -> Optional[str]:
        """
        Crea un nuevo thread en OpenAI.
        
        Returns:
            str: ID del thread creado o None si hay error
        """
        try:
            if not self.client:
                return None
                
            # Crear thread
            thread = self.client.beta.threads.create()
            
            # Devolver ID
            return thread.id
        except Exception as e:
            logger.error(f"Error creando thread: {str(e)}")
            return None
    
    def get_assistant_id(self, task_type: str, system_message: str) -> str:
        """
        Obtiene el ID del asistente adecuado para la tarea.
        Si no hay un asistente específico, crea uno temporal.
        
        Args:
            task_type: Tipo de tarea
            system_message: Instrucciones para el asistente
            
        Returns:
            str: ID del asistente
        """
        try:
            # Importar configuración
            from config.settings import (
                OPENAI_ASSISTANT_CORRECCION,
                OPENAI_ASSISTANT_EJERCICIOS,
                OPENAI_ASSISTANT_SIMULACRO
            )
            
            # Mapeo de tipos de tarea a IDs de asistentes
            assistant_ids = {
                "correccion_texto": OPENAI_ASSISTANT_CORRECCION,
                "generacion_ejercicios": OPENAI_ASSISTANT_EJERCICIOS,
                "simulacro_examen": OPENAI_ASSISTANT_SIMULACRO
            }
            
            # Verificar si hay un asistente específico para la tarea
            assistant_id = assistant_ids.get(task_type, None)
            
            if assistant_id:
                return assistant_id
            
            # Si no hay asistente específico, crear uno temporal
            if not self.client:
                raise ValueError("Cliente OpenAI no inicializado")
                
            # Crear asistente temporal
            assistant = self.client.beta.assistants.create(
                name=f"Asistente temporal para {task_type}",
                instructions=system_message,
                model=self.current_model
            )
            
            return assistant.id
        except Exception as e:
            logger.error(f"Error obteniendo/creando asistente para {task_type}: {str(e)}")
            raise
    
    def add_message_to_thread(self, thread_id: str, message: str) -> bool:
        """
        Añade un mensaje al thread.
        
        Args:
            thread_id: ID del thread
            message: Mensaje a añadir
            
        Returns:
            bool: True si se añadió correctamente, False en caso contrario
        """
        try:
            if not self.client:
                return False
                
            # Añadir mensaje
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            return True
        except Exception as e:
            logger.error(f"Error añadiendo mensaje al thread: {str(e)}")
            return False
    
    def run_assistant(self, thread_id: str, assistant_id: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
        """
        Ejecuta un asistente en un hilo y espera la respuesta.
        
        Args:
            thread_id: ID del hilo
            assistant_id: ID del asistente
            timeout: Tiempo máximo de espera en segundos
            
        Returns:
            dict: Resultado de la ejecución o None si hay error
        """
        try:
            if not self.client:
                return None
                
            # Crear ejecución
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id
            )
            
            # Esperar a que termine la ejecución con manejo de estados adecuado
            run_result = self.wait_for_run_completion(thread_id, run.id, timeout)
            
            # Verificar resultado
            if "error" in run_result:
                logger.error(f"Error en ejecución del asistente: {run_result['error']}")
                return None
                
            # Obtener mensajes solo si la ejecución fue exitosa
            if run_result.get("status") == "completed":
                # Obtener mensajes
                messages = self.client.beta.threads.messages.list(
                    thread_id=thread_id
                )
                
                # Obtener el último mensaje del asistente
                for message in messages.data:
                    if message.role == "assistant":
                        # Extraer contenido
                        content = message.content[0].text.value
                        data = extract_json_from_content(content)
                        return {"content": content, "data": data}
                
                # Si no se encontró respuesta
                logger.warning("Ejecución completada pero no se encontró respuesta del asistente")
                return {"content": "No se encontró respuesta", "data": {}}
            
            # Si no se completó pero tampoco hubo error explícito
            logger.warning(f"Estado final inesperado de la ejecución: {run_result.get('status', 'desconocido')}")
            return None
            
        except Exception as e:
            logger.error(f"Error ejecutando asistente: {str(e)}")
            return None
            
    def wait_for_run_completion(self, thread_id: str, run_id: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """
        Espera a que una ejecución (run) se complete, con timeout y manejo robusto.
        
        Args:
            thread_id: ID del thread
            run_id: ID de la ejecución
            timeout: Timeout en segundos
            
        Returns:
            dict: Resultado de la ejecución
        """
        try:
            if not self.client:
                raise ValueError("Cliente no inicializado")
            
            # Parámetros de control
            start_time = time.time()
            status = None
            
            # Esperar hasta que la ejecución complete o falle
            while True:
                # Verificar timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"Timeout esperando respuesta de OpenAI ({timeout}s)")
                    return {"error": f"La operación excedió el tiempo máximo de espera ({timeout}s)"}
                
                # Consultar estado de la ejecución
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run_id
                )
                
                status = run.status
                
                # Verificar estado
                if status == "completed":
                    # Éxito - ejecución completada
                    logger.info(f"Ejecución completada en {elapsed:.2f}s")
                    return {"status": "completed"}
                elif status in ["failed", "cancelled", "expired"]:
                    # Error - ejecución falló
                    error_msg = run.last_error.message if hasattr(run, 'last_error') and hasattr(run.last_error, 'message') else f"Estado: {status}"
                    logger.error(f"Ejecución falló: {error_msg}")
                    return {"error": f"La ejecución falló: {error_msg}"}
                elif status == "requires_action":
                    # Requiere acción (función definida en el asistente)
                    logger.info(f"La ejecución requiere acción: {run.required_action}")
                    # Aquí iría la lógica para manejar llamadas a funciones, si se configuran
                    return {"status": "requires_action", "action": run.required_action}
                
                # Si aún está en proceso, esperar y verificar nuevamente
                logger.debug(f"Esperando respuesta... Estado: {status}, tiempo: {elapsed:.2f}s")
                time.sleep(2)  # Esperar 2 segundos antes de verificar de nuevo
        
        except Exception as e:
            logger.error(f"Error mientras se esperaba respuesta: {str(e)}")
            return {"error": f"Error mientras se esperaba respuesta: {str(e)}"}


# Función para obtener una instancia del cliente desde el estado de sesión o crear una nueva
def get_assistant_client() -> Optional[AssistantClient]:
    """
    Obtiene una instancia del cliente de OpenAI Assistants.
    Comprueba que la API key esté configurada y el circuit breaker permita ejecución.

    Returns:
        AssistantClient o None: Cliente de OpenAI Assistants o None si no está disponible
    """
    # Verificar si ya existe un cliente en la sesión
    if "assistant_client" in st.session_state and st.session_state["assistant_client"]:
        return st.session_state["assistant_client"]
    
    # Obtener API key de OpenAI (primero intentar desde secrets)
    api_key = None
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception as e:
        logger.warning(f"No se pudo obtener OPENAI_API_KEY de secrets: {str(e)}")
    
    if not api_key:
        logger.error("API key de OpenAI no configurada")
        return None

    # Verificar circuit breaker
    if not circuit_breaker.can_execute("openai"):
        logger.warning("Circuit breaker abierto para OpenAI")
        return None

    # Crear y validar cliente
    client = AssistantClient(api_key)
    if client.client is None:
        logger.error("No se pudo inicializar el cliente de OpenAI Assistants")
        return None
    
    # Guardar en session_state para reutilización
    st.session_state["assistant_client"] = client
    
    return client

# Función de utilidad para el estado de sesión
def set_session_var(key, value):
    """Establece una variable en el estado de sesión de Streamlit"""
    st.session_state[key] = value
    