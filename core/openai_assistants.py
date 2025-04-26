#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gestión de OpenAI Assistants API v2
-----------------------------------
Este módulo proporciona una interfaz para interactuar con la API v2 de OpenAI Assistants,
permitiendo la reutilización de threads y manteniendo un sistema robusto de gestión de errores.
"""

import json
import time
import hashlib
import logging
import traceback
import streamlit as st
import os

# Asegurar que la configuración de proxies esté limpia antes de importar openai
if "HTTP_PROXY" in os.environ:
    del os.environ["HTTP_PROXY"]
if "HTTPS_PROXY" in os.environ:
    del os.environ["HTTPS_PROXY"]

# Importación segura de openai
import openai

# Importar dependencias del proyecto
from config.settings import MAX_RETRIES, DEFAULT_TIMEOUT
from core.circuit_breaker import circuit_breaker

# Configurar logger
logger = logging.getLogger(__name__)

def extract_json_safely(content):
    """
    Extrae JSON válido de una cadena de texto con manejo de errores.
    
    Args:
        content (str): Contenido que puede incluir JSON
        
    Returns:
        dict: Diccionario con el JSON extraído o diccionario vacío si no se encuentra
    """
    if not content:
        return {}
    
    try:
        # Primero intentar parsear directamente
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Buscar bloques de código JSON
        import re
        json_code_blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)```', content)
        for block in json_code_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue
        
        # Buscar cualquier estructura JSON en el texto
        json_match = re.search(r'({[\s\S]*})', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Si llegamos aquí, no hay JSON válido
        logger.warning("No se pudo extraer JSON válido del contenido")
        return {}
        
    except Exception as e:
        logger.error(f"Error extrayendo JSON del contenido: {str(e)}")
        return {}

def guardar_metricas_modelo(modelo, tiempo_respuesta, longitud_texto, resultado_exitoso):
    """
    Guarda métricas de uso del modelo en Firebase.
    
    Args:
        modelo (str): Nombre del modelo utilizado
        tiempo_respuesta (float): Tiempo de respuesta en segundos
        longitud_texto (int): Longitud aproximada del texto procesado
        resultado_exitoso (bool): Si la operación fue exitosa
    """
    try:
        from core.firebase_client import save_model_metrics
        save_model_metrics(
            modelo=modelo,
            tiempo_respuesta=tiempo_respuesta,
            longitud_texto=longitud_texto,
            resultado_exitoso=resultado_exitoso
        )
    except Exception as e:
        logger.error(f"Error guardando métricas del modelo: {str(e)}")

class OpenAIAssistants:
    """
    Clase para interactuar con la API de Asistentes de OpenAI.
    """
    
    # Mapeo de tipos de tarea a IDs de asistentes
    ASSISTANT_IDS = {
        "correccion_texto": None,  # ID para corrección de textos
        "generacion_ejercicios": None,  # ID para generación de ejercicios
        "plan_estudio": None,  # ID para planes de estudio
        "simulacro_examen": None,  # ID para simulacros de examen
        "default": None  # ID por defecto para otras tareas
    }
    
    def __init__(self, api_key):
        """
        Inicializa el gestor de Asistentes de OpenAI.
        
        Args:
            api_key: API key de OpenAI
        """
        self.api_key = api_key
        self.current_model = "gpt-4-turbo"  # Modelo predeterminado
        self.assistant_cache = {}  # Caché de asistentes creados
        
        # Cargar IDs de asistentes desde secrets si están disponibles
        self._load_assistant_ids_from_secrets()
        
        # Inicializar cliente (solo configurar API key)
        self._initialize_client()
    
    def _load_assistant_ids_from_secrets(self):
        """
        Carga las IDs de asistentes desde los secrets de Streamlit.
        """
        try:
            # Intentar cargar IDs de los secrets
            if hasattr(st, 'secrets'):
                # Primero intentar cargar desde sección específica OPENAI_ASSISTANTS
                if 'OPENAI_ASSISTANTS' in st.secrets:
                    assistants_config = st.secrets['OPENAI_ASSISTANTS']
                    
                    for task_type, config_key in [
                        ("correccion_texto", "CORRECTION_ASSISTANT_ID"),
                        ("generacion_ejercicios", "EXERCISES_ASSISTANT_ID"),
                        ("plan_estudio", "STUDY_PLAN_ASSISTANT_ID"),
                        ("simulacro_examen", "EXAM_ASSISTANT_ID"),
                        ("default", "DEFAULT_ASSISTANT_ID")
                    ]:
                        if config_key in assistants_config:
                            self.ASSISTANT_IDS[task_type] = assistants_config[config_key]
                            logger.info(f"Cargada ID de asistente para {task_type}: {self.ASSISTANT_IDS[task_type]}")
                
                # Buscar también en el nivel principal de secrets (para compatibilidad)
                elif 'CORRECTION_ASSISTANT_ID' in st.secrets:
                    self.ASSISTANT_IDS["correccion_texto"] = st.secrets['CORRECTION_ASSISTANT_ID']
                    logger.info(f"Cargada ID de asistente de corrección desde nivel principal: {self.ASSISTANT_IDS['correccion_texto']}")
                    
                # Cargar también los IDs configurados en settings.py
                try:
                    from config.settings import (
                        OPENAI_ASSISTANT_CORRECCION,
                        OPENAI_ASSISTANT_EJERCICIOS,
                        OPENAI_ASSISTANT_SIMULACRO
                    )
                    
                    if OPENAI_ASSISTANT_CORRECCION and not self.ASSISTANT_IDS["correccion_texto"]:
                        self.ASSISTANT_IDS["correccion_texto"] = OPENAI_ASSISTANT_CORRECCION
                        logger.info(f"Cargada ID de asistente de corrección desde settings: {self.ASSISTANT_IDS['correccion_texto']}")
                    
                    if OPENAI_ASSISTANT_EJERCICIOS and not self.ASSISTANT_IDS["generacion_ejercicios"]:
                        self.ASSISTANT_IDS["generacion_ejercicios"] = OPENAI_ASSISTANT_EJERCICIOS
                        logger.info(f"Cargada ID de asistente de ejercicios desde settings: {self.ASSISTANT_IDS['generacion_ejercicios']}")
                    
                    if OPENAI_ASSISTANT_SIMULACRO and not self.ASSISTANT_IDS["simulacro_examen"]:
                        self.ASSISTANT_IDS["simulacro_examen"] = OPENAI_ASSISTANT_SIMULACRO
                        logger.info(f"Cargada ID de asistente de simulacro desde settings: {self.ASSISTANT_IDS['simulacro_examen']}")
                except Exception as settings_error:
                    logger.warning(f"Error cargando IDs de settings: {settings_error}")
        except Exception as e:
            logger.warning(f"Error al cargar IDs de asistentes desde secrets: {e}")
    
    def _initialize_client(self):
        """
        Inicializa el cliente de OpenAI configurando solo la API key.
        """
        try:
            # Configurar API key globalmente
            openai.api_key = self.api_key
            
            # Verificar conectividad con una operación simple
            try:
                # Listar asistentes para verificar acceso
                response = openai.beta.assistants.list(limit=1)
                
                # Verificar asistentes configurados
                if any(self.ASSISTANT_IDS.values()):
                    for task_type, assistant_id in self.ASSISTANT_IDS.items():
                        if assistant_id:
                            try:
                                # Verificar que el asistente existe
                                assistant = openai.beta.assistants.retrieve(assistant_id)
                                logger.info(f"Asistente para {task_type} verificado: {assistant_id}")
                            except Exception as e:
                                logger.warning(f"No se pudo verificar el asistente para {task_type} ({assistant_id}): {e}")
                
                # Registrar éxito
                circuit_breaker.record_success("openai")
                logger.info(f"Conexión exitosa a OpenAI Assistants con modelo {self.current_model}")
                
                return True
            except Exception as e:
                logger.error(f"Error al verificar conexión a OpenAI Assistants: {str(e)}")
                circuit_breaker.record_failure("openai", error_type="initialization")
                return False
                
        except Exception as e:
            logger.error(f"Error al inicializar OpenAI Assistants: {str(e)}")
            circuit_breaker.record_failure("openai", error_type="initialization")
            return False
    
    def verify_thread(self, thread_id):
        """
        Verifica que un thread existe y es válido.
        
        Args:
            thread_id: ID del thread a verificar
            
        Returns:
            bool: True si el thread es válido, False en caso contrario
        """
        if not thread_id:
            return False
            
        try:
            # Verificar que el thread existe
            thread = openai.beta.threads.retrieve(thread_id)
            if thread.id == thread_id:
                logger.info(f"Thread existente verificado: {thread_id}")
                return True
        except Exception as e:
            logger.warning(f"Thread inválido ({thread_id}): {e}")
            
        return False
    
    def get_assistant_id(self, task_type, system_message):
        """
        Determina qué ID de asistente usar basado en el tipo de tarea y mensaje.
        
        Args:
            task_type: Tipo de tarea ('correccion_texto', 'generacion_ejercicios', etc.)
            system_message: Mensaje del sistema que describe la tarea
            
        Returns:
            str: ID del asistente a usar
        """
        # 1. Verificar si tenemos un ID configurado para este tipo de tarea
        if task_type in self.ASSISTANT_IDS and self.ASSISTANT_IDS[task_type]:
            return self.ASSISTANT_IDS[task_type]
        
        # 2. Verificar si tenemos un ID por defecto
        if self.ASSISTANT_IDS["default"]:
            return self.ASSISTANT_IDS["default"]
        
        # 3. Buscar en caché basado en el hash del mensaje
        instruccion_hash = hashlib.md5(f"{system_message}_{self.current_model}".encode()).hexdigest()
        if instruccion_hash in self.assistant_cache:
            return self.assistant_cache[instruccion_hash]
        
        # 4. Crear un nuevo asistente con formato JSON si es apropiado
        try:
            # Verificar si el mensaje del sistema contiene la palabra "json"
            has_json_keyword = "json" in system_message.lower()
            
            # Configurar formato de respuesta
            response_format = {"type": "json_object"} if has_json_keyword else None
            
            # Si no tiene la palabra "json", añadir una nota
            if not has_json_keyword:
                logger.warning("El mensaje del sistema no contiene la palabra 'json', usando formato de respuesta abierto")
                
            # Crear el asistente con la configuración adecuada
            assistant = openai.beta.assistants.create(
                name=f"TextoCorrector ELE - {task_type}",
                instructions=system_message,
                model=self.current_model,
                response_format=response_format
            )
            
            assistant_id = assistant.id
            
            # Guardar en caché
            self.assistant_cache[instruccion_hash] = assistant_id
            
            logger.info(f"Creado nuevo asistente para {task_type} con ID: {assistant_id}")
            return assistant_id
        except Exception as e:
            logger.error(f"Error al crear asistente: {e}")
            raise
    
    def get_completion(self, system_message, user_message, 
                      max_retries=MAX_RETRIES, task_type="default", 
                      thread_id=None):
        """
        Obtiene una respuesta usando OpenAI Assistants con soporte para thread persistente.
        
        Args:
            system_message: Mensaje del sistema (instrucciones)
            user_message: Mensaje del usuario (contenido)
            max_retries: Número máximo de reintentos
            task_type: Tipo de tarea para seleccionar el asistente adecuado
            thread_id: ID de un thread existente para continuar la conversación
        
        Returns:
            tuple: (respuesta_raw, resultado_json)
        """
        # Verificar que OpenAI esté configurado
        if not openai.api_key:
            return None, {"error": "API de OpenAI no configurada o inicializada"}
            
        if not circuit_breaker.can_execute("openai"):
            return None, {"error": "Servicio OpenAI temporalmente no disponible"}
        
        # Verificar si system_message o user_message contienen la palabra "json"
        has_json_keyword = "json" in system_message.lower() or "json" in user_message.lower()
        if not has_json_keyword:
            logger.warning("Ni el mensaje del sistema ni el mensaje del usuario contienen la palabra 'json'")
            # Añadir una referencia a JSON en el mensaje del usuario si es necesario
            if task_type in ["correccion_texto", "generacion_ejercicios", "plan_estudio"]:
                user_message += "\n\nPor favor, proporciona tu respuesta en formato JSON."
                logger.info("Añadida referencia a JSON en el mensaje del usuario")
        
        # Registrar tiempo de inicio para métricas
        tiempo_inicio = time.time()
        longitud_estimada = len(user_message.split())
        
        # Verificar si tenemos un thread_id válido
        thread_id_is_valid = False
        if thread_id:
            thread_id_is_valid = self.verify_thread(thread_id)
        
        try:
            # Determinar qué asistente usar
            try:
                assistant_id = self.get_assistant_id(task_type, system_message)
            except Exception as e:
                return None, {"error": f"Error al obtener ID de asistente: {str(e)}"}
            
            # Crear un nuevo thread o usar el existente
            if not thread_id_is_valid:
                thread = openai.beta.threads.create()
                thread_id = thread.id
                logger.info(f"Creado nuevo thread: {thread_id}")
            else:
                logger.info(f"Usando thread existente: {thread_id}")
            
            # Añadir el mensaje del usuario al thread
            openai.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=user_message
            )
            
            # Ejecutar el asistente con reintentos
            for attempt in range(max_retries):
                try:
                    # Ejecutar el asistente con manejo de ejecuciones activas
                    try:
                        # Intentar crear una nueva ejecución
                        run = openai.beta.threads.runs.create(
                            thread_id=thread_id,
                            assistant_id=assistant_id
                        )
                    except Exception as run_error:
                        # Verificar si el error es porque ya hay una ejecución activa
                        if "already has an active run" in str(run_error):
                            logger.warning(f"El hilo {thread_id} ya tiene una ejecución activa. Intentando recuperarla...")
                            
                            # Obtener la lista de ejecuciones para este hilo
                            runs_list = openai.beta.threads.runs.list(thread_id=thread_id)
                            
                            # Buscar la ejecución activa
                            active_run = None
                            for existing_run in runs_list.data:
                                if existing_run.status in ["queued", "in_progress", "requires_action"]:
                                    active_run = existing_run
                                    break
                            
                            if active_run:
                                # Usar la ejecución activa
                                logger.info(f"Recuperada ejecución activa: {active_run.id} con estado: {active_run.status}")
                                run = active_run
                            else:
                                # Si no podemos encontrar la ejecución activa, intentar cancelar todas las ejecuciones
                                logger.warning("No se pudo encontrar la ejecución activa. Intentando cancelar ejecuciones existentes...")
                                
                                for existing_run in runs_list.data:
                                    try:
                                        openai.beta.threads.runs.cancel(
                                            thread_id=thread_id,
                                            run_id=existing_run.id
                                        )
                                        logger.info(f"Cancelada ejecución: {existing_run.id}")
                                    except Exception as cancel_error:
                                        logger.warning(f"No se pudo cancelar ejecución {existing_run.id}: {cancel_error}")
                                
                                # Esperar un momento para que las cancelaciones se procesen
                                time.sleep(2)
                                
                                # Intentar crear una nueva ejecución otra vez
                                run = openai.beta.threads.runs.create(
                                    thread_id=thread_id,
                                    assistant_id=assistant_id
                                )
                        else:
                            # Si es otro tipo de error, propagarlo
                            raise
                    
                    # Esperar a que termine la ejecución con timeout
                    max_wait_time = DEFAULT_TIMEOUT  # Usar el timeout de la configuración
                    start_time = time.time()
                    
                    polling_interval = 1  # Comenzamos con 1 segundo
                    max_polling_interval = 5  # Máximo intervalo de polling: 5 segundos
                    polling_count = 0
                    
                    while True:
                        # Verificar si hemos excedido el tiempo máximo
                        if time.time() - start_time > max_wait_time:
                            raise TimeoutError(f"Timeout esperando respuesta del asistente después de {max_wait_time}s")
                        
                        # Obtener estado de la ejecución
                        run_status = openai.beta.threads.runs.retrieve(
                            thread_id=thread_id,
                            run_id=run.id
                        )
                        
                        polling_count += 1
                        status = run_status.status
                        logger.info(f"Estado de ejecución ({polling_count}): {status}")
                        
                        # Si ha terminado, salir del bucle
                        if status == "completed":
                            logger.info(f"Ejecución completada después de {polling_count} consultas")
                            break
                            
                        # Si ha fallado, levantar excepción
                        if status in ["failed", "cancelled", "expired"]:
                            error_detail = ""
                            if hasattr(run_status, 'last_error'):
                                error_detail = f" - {run_status.last_error}"
                            raise Exception(f"Ejecución fallida con estado: {status}{error_detail}")
                        
                        # Verificar si está en estado de requerir acción (requires_action)
                        if status == "requires_action":
                            logger.warning(f"El asistente requiere una acción que no podemos proporcionar. Abortando.")
                            raise Exception("El asistente requiere una acción que esta implementación no soporta")
                        
                        # Verificar si está en espera (queued) o en proceso (in_progress)
                        # y ajustar el tiempo de espera en consecuencia
                        if polling_count > 30:  # Si llevamos muchas iteraciones, posible problema
                            logger.warning(f"Demasiadas consultas de estado ({polling_count}). Posible problema con el asistente.")
                            # Opción 1: Continuar con intervalos más largos
                            polling_interval = max_polling_interval
                            # Opción 2: Abortar (descomenta la siguiente línea si prefieres abortar)
                            # raise Exception(f"Demasiadas consultas de estado ({polling_count}). Abortando.")
                        
                        # Ajustar intervalo de polling de forma exponencial hasta el máximo
                        polling_interval = min(polling_interval * 1.5, max_polling_interval)
                        logger.info(f"Esperando {polling_interval:.1f}s antes de verificar estado nuevamente")
                        
                        # Esperar antes de verificar de nuevo
                        time.sleep(polling_interval)
                    
                    # Obtener los mensajes del thread
                    messages = openai.beta.threads.messages.list(
                        thread_id=thread_id
                    )
                    
                    # El primer mensaje será la respuesta más reciente del asistente
                    for message in messages.data:
                        if message.role == "assistant":
                            # Extraer el contenido
                            content_parts = [
                                part.text.value for part in message.content
                                if hasattr(part, 'text')
                            ]
                            content = ''.join(content_parts)
                            
                            # Intentar extraer JSON
                            data_json = extract_json_safely(content)
                            
                            # Añadir thread_id al resultado para facilitar su reutilización
                            if isinstance(data_json, dict):
                                data_json["thread_id"] = thread_id
                            
                            # Calcular tiempo total de respuesta
                            tiempo_total = time.time() - tiempo_inicio
                            
                            # Registrar métricas
                            guardar_metricas_modelo(
                                modelo=self.current_model,
                                tiempo_respuesta=tiempo_total,
                                longitud_texto=longitud_estimada,
                                resultado_exitoso="error" not in data_json
                            )
                            
                            # Registrar éxito
                            circuit_breaker.record_success("openai")
                            
                            logger.info(f"Solicitud a OpenAI Assistants completada en {tiempo_total:.2f}s")
                            return content, data_json
                    
                    # Si llegamos aquí, no hay respuesta del asistente
                    raise Exception("No se encontró respuesta del asistente")
                    
                except TimeoutError as e:
                    logger.warning(f"Timeout en solicitud a OpenAI Assistants (intento {attempt+1}/{max_retries}): {e}")
                    
                    if attempt == max_retries - 1:
                        # Registrar fallo si es el último intento
                        circuit_breaker.record_failure("openai", error_type="timeout")
                        tiempo_total = time.time() - tiempo_inicio
                        guardar_metricas_modelo(
                            modelo=self.current_model,
                            tiempo_respuesta=tiempo_total,
                            longitud_texto=longitud_estimada,
                            resultado_exitoso=False
                        )
                        return None, {"error": f"Timeout en solicitud a OpenAI Assistants después de {max_retries} intentos"}
                    
                    # Esperar antes de reintentar
                    wait_time = min(60, 4 ** attempt)
                    logger.info(f"Esperando {wait_time}s antes de reintentar.")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    logger.warning(f"Error en solicitud a OpenAI Assistants (intento {attempt+1}/{max_retries}): {e}")
                    
                    if attempt == max_retries - 1:
                        # Registrar fallo si es el último intento
                        circuit_breaker.record_failure("openai", error_type="general")
                        tiempo_total = time.time() - tiempo_inicio
                        guardar_metricas_modelo(
                            modelo=self.current_model,
                            tiempo_respuesta=tiempo_total,
                            longitud_texto=longitud_estimada,
                            resultado_exitoso=False
                        )
                        return None, {"error": f"Error en solicitud a OpenAI Assistants: {str(e)}"}
                    
                    # Esperar antes de reintentar
                    wait_time = min(60, 2 ** attempt)
                    logger.info(f"Esperando {wait_time}s antes de reintentar.")
                    time.sleep(wait_time)
        
        except Exception as e:
            # Registrar fallo general
            logger.error(f"Error general en OpenAI Assistants: {str(e)}")
            circuit_breaker.record_failure("openai", error_type="general")
            tiempo_total = time.time() - tiempo_inicio
            guardar_metricas_modelo(
                modelo=self.current_model if hasattr(self, 'current_model') else "desconocido",
                tiempo_respuesta=tiempo_total,
                longitud_texto=longitud_estimada,
                resultado_exitoso=False
            )
            return None, {"error": f"Error en API de OpenAI Assistants: {str(e)}"}


def get_openai_assistants_client():
    """
    Obtiene una instancia del cliente de OpenAI Assistants.
    Comprueba que la API key esté configurada y el circuit breaker permita ejecución.

    Returns:
        OpenAIAssistants o None: Cliente de OpenAI Assistants o None si no está disponible
    """
    # Limpiar cualquier configuración de proxies en variables de entorno
    if "HTTP_PROXY" in os.environ:
        del os.environ["HTTP_PROXY"]
    if "HTTPS_PROXY" in os.environ:
        del os.environ["HTTPS_PROXY"]
    
    # Obtener API key de OpenAI
    from core.openai_utils import get_openai_api_key
    api_key = get_openai_api_key()
    
    if not api_key:
        logger.error("API key de OpenAI no configurada")
        return None

    # Verificar circuit breaker
    if not circuit_breaker.can_execute("openai"):
        logger.warning("Circuit breaker abierto para OpenAI")
        return None
    
    # Configurar API key globalmente
    openai.api_key = api_key
    
    # Intentar actualizar openai_init (ya que puede tener monkey patching)
    try:
        from core.openai_init import init_openai
        init_openai()
    except Exception as e:
        logger.warning(f"Error al inicializar OpenAI con openai_init: {e}")
    
    # Crear cliente
    client = OpenAIAssistants(api_key=api_key)
    
    # Guardar en session_state para reutilización
    st.session_state["openai_assistants_client"] = client
    
    return client