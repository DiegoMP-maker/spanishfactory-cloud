# Primero todas las importaciones de futuros
from __future__ import annotations

# Luego importaciones estándar
import logging
import traceback
import time

# Después importaciones de terceros
import streamlit as st
from typing import Tuple, Dict, Any, List, Optional, Union

# Finalmente importaciones del proyecto
from config.settings import MAX_RETRIES, EXTENDED_TIMEOUT
from core.circuit_breaker import CircuitBreaker

# Configurar logger
logger = logging.getLogger(__name__)

# Inicializar circuit breaker
circuit_breaker = CircuitBreaker("assistant_api")

class AssistantClient:
    """
    Cliente para interactuar con la API de Assistants de OpenAI.
    Proporciona métodos para gestionar threads, mensajes y ejecuciones de asistentes.
    """
    
    def __init__(self, api_key: str):
        """
        Inicializa el cliente de Assistants.
        
        Args:
            api_key: API key de OpenAI
        """
        self.api_key = api_key
        self.client = None
        self.current_model = "gpt-4"  # Valor por defecto
        
        # Inicializar el cliente de OpenAI aquí
        # [Código de inicialización...]

    def get_or_create_thread_for_user(self, uid: str, email: str = None) -> str:
        """
        Obtiene un thread existente para el usuario o crea uno nuevo.
        Actualiza Firestore con el thread_id.

        Args:
            uid: UID del usuario
            email: Email del usuario (opcional)

        Returns:
            str: ID del thread para el usuario
        """
        from core.firebase_client import get_user_thread, save_user_thread
        
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
                              user_uid: str = None, max_retries: int = MAX_RETRIES) -> Tuple[str, Dict[str, Any]]:
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
            
        # Si no hay thread_id (y no se pudo obtener/crear), crear uno temporal
        if not thread_id:
            thread_id = self.create_thread()
            if not thread_id:
                return None, {"error": "No se pudo crear thread para la conversación"}

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
                result = self.run_assistant(thread_id, assistant_id, timeout=EXTENDED_TIMEOUT)
                
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
    
    # Aquí deberían estar los métodos auxiliares usados en los métodos anteriores:
    # - get_thread_messages
    # - create_thread
    # - get_assistant_id
    # - add_message_to_thread
    # - run_assistant


# Función global para obtener una instancia del cliente
def get_assistant_client() -> Optional[AssistantClient]:
    """
    Obtiene una instancia del cliente de OpenAI Assistants.
    Comprueba que la API key esté configurada y el circuit breaker permita ejecución.

    Returns:
        AssistantClient o None: Cliente de OpenAI Assistants o None si no está disponible
    """
    # Obtener API key de OpenAI (primero intentar desde secrets)
    api_key = None
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except:
        logger.warning("No se pudo obtener OPENAI_API_KEY de secrets")
        pass

    if not api_key:
        logger.error("API key de OpenAI no configurada")
        return None

    # Verificar circuit breaker
    if not circuit_breaker.can_execute("openai"):
        logger.warning("Circuit breaker abierto para OpenAI")
        return None

    # Crear y devolver cliente
    client = AssistantClient(api_key)
    if client.client is None:
        return None
    
    return client
