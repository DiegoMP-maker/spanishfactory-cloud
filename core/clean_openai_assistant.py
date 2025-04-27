#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cliente limpio para OpenAI Assistants API
-----------------------------------------
Una implementación minimalista y robusta que usa directamente las APIs REST 
para evitar problemas con la biblioteca oficial de Python.
Incluye soporte para perfiles de estudiante y contexto personalizado.
"""

import json
import time
import hashlib
import logging
import traceback
import streamlit as st
import os
import requests

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
            longitud_texto=longitud_texto,  # Corregido
            resultado_exitoso=resultado_exitoso
        )
    except Exception as e:
        logger.error(f"Error guardando métricas del modelo: {str(e)}")

def get_student_profile(user_id):
    """
    Obtiene el perfil completo del estudiante desde Firebase.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Perfil del estudiante o diccionario vacío si no está disponible
    """
    if not user_id:
        return {}
    
    try:
        # Intentar importar dinámicamente para evitar dependencias circulares
        from core.firebase_client import get_user_data
        
        # Obtener datos del usuario
        user_data = get_user_data(user_id)
        
        # Extraer información relevante para el perfil
        profile = {
            "nivel_mcer": user_data.get("nivel", "B1"),
            "idioma_nativo": user_data.get("idioma_nativo", ""),
            "objetivos_aprendizaje": user_data.get("objetivos_aprendizaje", []),
            "areas_interes": user_data.get("areas_interes", []),
            "numero_correcciones": user_data.get("numero_correcciones", 0)
        }
        
        # Añadir estadísticas de errores si están disponibles
        if "errores_por_tipo" in user_data:
            profile["estadisticas_errores"] = user_data["errores_por_tipo"]
            
        # Añadir preferencias de feedback si están disponibles
        if "preferencias_feedback" in user_data:
            profile["preferencias_feedback"] = user_data["preferencias_feedback"]
            
        return profile
    
    except Exception as e:
        logger.error(f"Error obteniendo perfil del estudiante: {str(e)}")
        return {}

class CleanOpenAIAssistants:
    """
    Clase para interactuar con la API de Asistentes de OpenAI sin usar 
    la biblioteca oficial de Python, para evitar problemas de configuración.
    Incluye soporte para perfiles de estudiante y contexto personalizado.
    """
    
    BASE_URL = "https://api.openai.com/v1"
    
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
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "assistants=v2"  # Actualizado a v2
        }
        
        # Cargar IDs de asistentes desde secrets si están disponibles
        self._load_assistant_ids_from_secrets()
        
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
    
    def _api_request(self, method, endpoint, data=None, params=None, timeout=10):
        """
        Realiza una petición a la API de OpenAI.
        
        Args:
            method: Método HTTP (GET, POST, etc.)
            endpoint: Endpoint de la API (sin el prefijo /v1)
            data: Datos para enviar en el cuerpo (para POST, PUT, etc.)
            params: Parámetros de query string (para GET)
            timeout: Timeout en segundos
            
        Returns:
            dict: Respuesta de la API o None si hay error
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=timeout)
            else:
                logger.error(f"Método HTTP no soportado: {method}")
                return None
                
            # Verificar respuesta
            response.raise_for_status()
            
            # Parsear JSON si la respuesta no está vacía
            if response.status_code != 204 and response.content:  # 204 = No Content
                return response.json()
            return {"success": True}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en petición a {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Detalles del error: {error_detail}")
                except:
                    logger.error(f"Status: {e.response.status_code}, Contenido: {e.response.content}")
            return None
    
    def list_assistants(self, limit=20):
        """
        Lista los asistentes disponibles.
        
        Args:
            limit: Límite de asistentes a obtener
            
        Returns:
            list: Lista de asistentes o None si hay error
        """
        params = {"limit": limit}
        return self._api_request("GET", "/assistants", params=params)
    
    def get_assistant(self, assistant_id):
        """
        Obtiene un asistente por su ID.
        
        Args:
            assistant_id: ID del asistente
            
        Returns:
            dict: Datos del asistente o None si hay error
        """
        return self._api_request("GET", f"/assistants/{assistant_id}")
    
    def create_assistant(self, name, instructions, model="gpt-4-turbo", json_mode=False):
        """
        Crea un nuevo asistente.
        
        Args:
            name: Nombre del asistente
            instructions: Instrucciones del asistente
            model: Modelo a utilizar
            json_mode: Si se debe forzar respuestas en formato JSON
            
        Returns:
            dict: Datos del asistente creado o None si hay error
        """
        data = {
            "name": name,
            "instructions": instructions,
            "model": model
        }
        
        if json_mode:
            data["response_format"] = {"type": "json_object"}
            
        return self._api_request("POST", "/assistants", data=data)
    
    def create_thread(self, initial_message=None, user_id=None, metadata=None):
        """
        Crea un nuevo thread con opciones mejoradas para incluir perfil de usuario.
        
        Args:
            initial_message (str, opcional): Mensaje inicial para el thread
            user_id (str, opcional): ID del usuario para incluir información de perfil
            metadata (dict, opcional): Metadatos adicionales para el thread
            
        Returns:
            dict: Datos del thread creado o None si hay error
        """
        # Crear datos básicos del thread
        thread_data = {}
        
        # Añadir metadatos si existen
        if metadata and isinstance(metadata, dict):
            thread_data["metadata"] = metadata
        
        # Crear el thread
        thread_response = self._api_request("POST", "/threads", data=thread_data)
        
        # Si no hay thread_id, salir
        if not thread_response or "id" not in thread_response:
            logger.error("No se pudo crear el thread")
            return None
        
        thread_id = thread_response["id"]
        
        # Añadir mensaje inicial con información de perfil si tenemos user_id
        if user_id:
            try:
                # Obtener perfil del estudiante
                profile_data = get_student_profile(user_id)
                
                if profile_data:
                    # Crear mensaje con la información del perfil
                    profile_message = f"""
PERFIL DEL ESTUDIANTE:
```json
{json.dumps(profile_data, indent=2, ensure_ascii=False)}
```

Por favor, adapta tus respuestas según este perfil. Ten en cuenta especialmente:
- Nivel MCER: {profile_data.get('nivel_mcer', 'B1')}
- Idioma nativo: {profile_data.get('idioma_nativo', 'No especificado')}
- Objetivos de aprendizaje: {', '.join(profile_data.get('objetivos_aprendizaje', ['No especificados']))}
- Áreas de mejora: {str(profile_data.get('estadisticas_errores', {}))}

Ten en cuenta estos datos para personalizar el feedback y la dificultad del contenido.
"""
                    # Añadir mensaje de perfil al thread
                    self.add_message_to_thread(thread_id, profile_message)
                    logger.info(f"Perfil de estudiante añadido al nuevo thread {thread_id}")
            except Exception as profile_error:
                logger.warning(f"No se pudo añadir perfil al thread: {str(profile_error)}")
        
        # Añadir mensaje inicial personalizado si existe
        if initial_message:
            self.add_message_to_thread(thread_id, initial_message)
            logger.info(f"Mensaje inicial añadido al thread {thread_id}")
        
        return thread_response
    
    def get_thread(self, thread_id):
        """
        Obtiene un thread por su ID.
        
        Args:
            thread_id: ID del thread
            
        Returns:
            dict: Datos del thread o None si hay error
        """
        return self._api_request("GET", f"/threads/{thread_id}")
    
    def add_message_to_thread(self, thread_id, message, role="user"):
        """
        Añade un mensaje a un thread.
        
        Args:
            thread_id: ID del thread
            message: Contenido del mensaje
            role: Rol del mensaje (user o assistant)
            
        Returns:
            dict: Datos del mensaje creado o None si hay error
        """
        data = {
            "role": role,
            "content": message
        }
        return self._api_request("POST", f"/threads/{thread_id}/messages", data=data)
    
    def update_thread_with_profile(self, thread_id, user_id):
        """
        Actualiza un thread existente con la información de perfil del estudiante.
        
        Args:
            thread_id: ID del thread
            user_id: ID del usuario
            
        Returns:
            bool: True si se actualizó correctamente, False en caso contrario
        """
        try:
            if not thread_id or not user_id:
                logger.warning("thread_id o user_id vacío en update_thread_with_profile")
                return False
            
            # Verificar que el thread existe
            if not self.verify_thread(thread_id):
                logger.warning(f"Thread inválido: {thread_id}")
                return False
            
            # Obtener perfil del estudiante
            profile_data = get_student_profile(user_id)
            
            if not profile_data:
                logger.warning(f"No se pudo obtener perfil para usuario {user_id}")
                return False
            
            # Crear mensaje con la información de perfil actualizada
            profile_message = f"""
ACTUALIZACIÓN DE PERFIL DEL ESTUDIANTE:
```json
{json.dumps(profile_data, indent=2, ensure_ascii=False)}
```

Por favor, adapta tus respuestas según este perfil actualizado.
"""
            # Añadir mensaje al thread
            message_response = self.add_message_to_thread(thread_id, profile_message)
            
            if message_response and "id" in message_response:
                logger.info(f"Perfil actualizado en thread {thread_id}")
                return True
            else:
                logger.error(f"Error al añadir mensaje de perfil al thread {thread_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error en update_thread_with_profile: {str(e)}")
            return False
    
    def run_assistant(self, thread_id, assistant_id):
        """
        Ejecuta un asistente en un thread.
        
        Args:
            thread_id: ID del thread
            assistant_id: ID del asistente
            
        Returns:
            dict: Datos de la ejecución creada o None si hay error
        """
        data = {"assistant_id": assistant_id}
        return self._api_request("POST", f"/threads/{thread_id}/runs", data=data)
    
    def get_run(self, thread_id, run_id):
        """
        Obtiene el estado de una ejecución.
        
        Args:
            thread_id: ID del thread
            run_id: ID de la ejecución
            
        Returns:
            dict: Estado de la ejecución o None si hay error
        """
        return self._api_request("GET", f"/threads/{thread_id}/runs/{run_id}")
    
    def list_messages(self, thread_id, limit=20):
        """
        Lista los mensajes de un thread.
        
        Args:
            thread_id: ID del thread
            limit: Límite de mensajes a obtener
            
        Returns:
            list: Lista de mensajes o None si hay error
        """
        params = {"limit": limit}
        return self._api_request("GET", f"/threads/{thread_id}/messages", params=params)
    
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
        
        result = self.get_thread(thread_id)
        if result and "id" in result and result["id"] == thread_id:
            logger.info(f"Thread existente verificado: {thread_id}")
            return True
        
        logger.warning(f"Thread inválido: {thread_id}")
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
            # Verificar que el asistente existe
            if self.get_assistant(self.ASSISTANT_IDS[task_type]):
                return self.ASSISTANT_IDS[task_type]
            else:
                logger.warning(f"El asistente configurado para {task_type} no existe o es inaccesible")
        
        # 2. Verificar si tenemos un ID por defecto
        if self.ASSISTANT_IDS["default"] and self.get_assistant(self.ASSISTANT_IDS["default"]):
            return self.ASSISTANT_IDS["default"]
        
        # 3. Buscar en caché basado en el hash del mensaje
        instruccion_hash = hashlib.md5(f"{system_message}_{self.current_model}".encode()).hexdigest()
        if instruccion_hash in self.assistant_cache:
            # Verificar que el asistente de caché existe
            if self.get_assistant(self.assistant_cache[instruccion_hash]):
                return self.assistant_cache[instruccion_hash]
        
        # 4. Crear un nuevo asistente
        has_json_keyword = "json" in system_message.lower()
        
        if not has_json_keyword:
            logger.warning("El mensaje del sistema no contiene la palabra 'json', usando formato de respuesta abierto")
        
        new_assistant = self.create_assistant(
            name=f"TextoCorrector ELE - {task_type}",
            instructions=system_message,
            model=self.current_model,
            json_mode=has_json_keyword
        )
        
        if new_assistant and "id" in new_assistant:
            assistant_id = new_assistant["id"]
            self.assistant_cache[instruccion_hash] = assistant_id
            logger.info(f"Creado nuevo asistente para {task_type} con ID: {assistant_id}")
            return assistant_id
        
        raise Exception("No se pudo crear o encontrar un asistente válido")
    
    def get_completion(self, system_message, user_message, 
                     max_retries=MAX_RETRIES, task_type="default", 
                     thread_id=None, user_id=None):
        """
        Obtiene una respuesta usando OpenAI Assistants con soporte para thread persistente.
        
        Args:
            system_message: Mensaje del sistema (instrucciones)
            user_message: Mensaje del usuario (contenido)
            max_retries: Número máximo de reintentos
            task_type: Tipo de tarea para seleccionar el asistente adecuado
            thread_id: ID de un thread existente para continuar la conversación
            user_id: ID del usuario para incluir información de perfil (opcional)
        
        Returns:
            tuple: (respuesta_raw, resultado_json)
        """
        # Verificar precondiciones
        if not self.api_key:
            return None, {"error": "API de OpenAI no configurada"}
            
        if not circuit_breaker.can_execute("openai"):
            return None, {"error": "Servicio OpenAI temporalmente no disponible"}
        
        # Solo modificar user_message con la referencia a JSON si system_message está vacío 
        # y no hay referencia a JSON en el mensaje del usuario
        # CAMBIO AQUÍ: No sobrescribir el system_prompt del asistente cuando system_message está vacío
        has_json_keyword = False
        
        # Si system_message está presente, verificamos si contiene "json"
        if system_message:
            has_json_keyword = "json" in system_message.lower()
        
        # También verificamos si user_message contiene "json"
        has_json_keyword = has_json_keyword or "json" in user_message.lower()
        
        if not has_json_keyword:
            logger.warning("Ni el mensaje del sistema ni el mensaje del usuario contienen la palabra 'json'")
            # Añadir una referencia a JSON en el mensaje del usuario si es necesario
            if task_type in ["correccion_texto", "generacion_ejercicios", "plan_estudio"]:
                user_message += "\n\nPor favor, proporciona tu respuesta en formato json."
                logger.info("Añadida referencia a JSON en el mensaje del usuario")
        
        # Iniciar métricas
        tiempo_inicio = time.time()
        longitud_estimada = len(user_message.split())
        
        # Verificar thread existente
        thread_id_is_valid = False
        if thread_id:
            thread_id_is_valid = self.verify_thread(thread_id)
        
        try:
            # Obtener ID del asistente apropiado
            try:
                # CAMBIO AQUÍ: Si system_message está vacío, pasamos un string vacío para no modificar 
                # el prompt configurado en el asistente
                assistant_instruction = system_message if system_message else ""
                assistant_id = self.get_assistant_id(task_type, assistant_instruction)
            except Exception as e:
                logger.error(f"Error al obtener ID de asistente: {e}")
                return None, {"error": f"Error al obtener ID de asistente: {str(e)}"}
            
            # Crear o usar thread existente
            if not thread_id_is_valid:
                # Crear nuevo thread con perfil de usuario si está disponible
                thread_response = self.create_thread(user_id=user_id)
                if not thread_response or "id" not in thread_response:
                    return None, {"error": "No se pudo crear thread"}
                thread_id = thread_response["id"]
                logger.info(f"Creado nuevo thread: {thread_id}")
            else:
                logger.info(f"Usando thread existente: {thread_id}")
                
                # Si tenemos user_id y thread existente, verificar si necesitamos actualizar el perfil
                # Esta lógica podría optimizarse con un control de "última actualización de perfil"
                if user_id:
                    # Cada 10 interacciones o según necesidad, actualizar el perfil
                    thread_messages = self.list_messages(thread_id)
                    if thread_messages and "data" in thread_messages:
                        message_count = len(thread_messages["data"])
                        if message_count % 10 == 0:  # Actualizar cada 10 mensajes
                            try:
                                self.update_thread_with_profile(thread_id, user_id)
                            except Exception as profile_error:
                                logger.warning(f"Error actualizando perfil en thread: {str(profile_error)}")
            
            # Añadir mensaje al thread
            message_response = self.add_message_to_thread(thread_id, user_message)
            if not message_response:
                return None, {"error": "Error al añadir mensaje al thread"}
            
            # Ejecutar asistente con reintentos
            for attempt in range(max_retries):
                try:
                    # Iniciar ejecución
                    run_response = self.run_assistant(thread_id, assistant_id)
                    if not run_response or "id" not in run_response:
                        raise Exception("Error al iniciar ejecución del asistente")
                    
                    run_id = run_response["id"]
                    
                    # Esperar a que la ejecución se complete (con timeout)
                    max_wait_time = DEFAULT_TIMEOUT
                    start_time = time.time()
                    polling_interval = 1
                    max_polling_interval = 5
                    polling_count = 0
                    
                    # Bucle de polling para esperar que termine la ejecución
                    while True:
                        # Verificar timeout
                        if time.time() - start_time > max_wait_time:
                            raise TimeoutError(f"Timeout esperando respuesta después de {max_wait_time}s")
                        
                        # Consultar estado de la ejecución
                        run_status_response = self.get_run(thread_id, run_id)
                        if not run_status_response or "status" not in run_status_response:
                            raise Exception("Error al obtener estado de la ejecución")
                        
                        status = run_status_response["status"]
                        polling_count += 1
                        logger.info(f"Estado de ejecución ({polling_count}): {status}")
                        
                        # Verificar si ha terminado
                        if status == "completed":
                            logger.info(f"Ejecución completada después de {polling_count} consultas")
                            break
                            
                        # Verificar si ha fallado
                        if status in ["failed", "cancelled", "expired"]:
                            error_detail = run_status_response.get("last_error", {})
                            error_message = error_detail.get("message", "Unknown error")
                            raise Exception(f"Ejecución fallida con estado {status}: {error_message}")
                        
                        # Verificar si requiere acción
                        if status == "requires_action":
                            raise Exception("El asistente requiere una acción que esta implementación no soporta")
                        
                        # Ajustar intervalo de polling
                        if polling_count > 30:
                            logger.warning(f"Demasiadas consultas de estado ({polling_count})")
                            polling_interval = max_polling_interval
                        else:
                            polling_interval = min(polling_interval * 1.5, max_polling_interval)
                            
                        logger.info(f"Esperando {polling_interval:.1f}s antes de verificar estado nuevamente")
                        time.sleep(polling_interval)
                    
                    # Obtener mensajes
                    messages_response = self.list_messages(thread_id)
                    if not messages_response or "data" not in messages_response:
                        raise Exception("Error al obtener mensajes del thread")
                    
                    # Buscar la respuesta del asistente (primer mensaje en la lista)
                    for message in messages_response["data"]:
                        if message["role"] == "assistant":
                            # Extraer contenido
                            content_text = ""
                            for content_item in message.get("content", []):
                                if content_item["type"] == "text":
                                    content_text += content_item["text"]["value"]
                            
                            # Extraer JSON
                            data_json = extract_json_safely(content_text)
                            
                            # Añadir thread_id
                            if isinstance(data_json, dict):
                                data_json["thread_id"] = thread_id
                            
                            # Guardar métricas
                            tiempo_total = time.time() - tiempo_inicio
                            guardar_metricas_modelo(
                                modelo=self.current_model,
                                tiempo_respuesta=tiempo_total,
                                longitud_texto=longitud_estimada,
                                resultado_exitoso="error" not in data_json
                            )
                            
                            # Registrar éxito
                            circuit_breaker.record_success("openai")
                            
                            logger.info(f"Solicitud completada en {tiempo_total:.2f}s")
                            return content_text, data_json
                    
                    # Si no se encontró respuesta
                    raise Exception("No se encontró respuesta del asistente")
                    
                except TimeoutError as e:
                    logger.warning(f"Timeout en intento {attempt+1}/{max_retries}: {e}")
                    
                    if attempt == max_retries - 1:
                        # Si es el último intento, registrar fallo
                        circuit_breaker.record_failure("openai", error_type="timeout")
                        tiempo_total = time.time() - tiempo_inicio
                        guardar_metricas_modelo(
                            modelo=self.current_model,
                            tiempo_respuesta=tiempo_total,
                            longitud_texto=longitud_estimada,
                            resultado_exitoso=False
                        )
                        return None, {"error": f"Timeout después de {max_retries} intentos"}
                    
                    # Esperar antes de reintentar
                    wait_time = min(60, 4 ** attempt)
                    logger.info(f"Esperando {wait_time}s antes de reintentar")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    logger.warning(f"Error en intento {attempt+1}/{max_retries}: {e}")
                    
                    if attempt == max_retries - 1:
                        # Si es el último intento, registrar fallo
                        circuit_breaker.record_failure("openai", error_type="general")
                        tiempo_total = time.time() - tiempo_inicio
                        guardar_metricas_modelo(
                            modelo=self.current_model,
                            tiempo_respuesta=tiempo_total,
                            longitud_texto=longitud_estimada,
                            resultado_exitoso=False
                        )
                        return None, {"error": f"Error: {str(e)}"}
                    
                    # Esperar antes de reintentar
                    wait_time = min(60, 2 ** attempt)
                    logger.info(f"Esperando {wait_time}s antes de reintentar")
                    time.sleep(wait_time)
        
        except Exception as e:
            # Error general
            logger.error(f"Error general: {e}")
            circuit_breaker.record_failure("openai", error_type="general")
            tiempo_total = time.time() - tiempo_inicio
            guardar_metricas_modelo(
                modelo=self.current_model if hasattr(self, 'current_model') else "desconocido",
                tiempo_respuesta=tiempo_total,
                longitud_texto=longitud_estimada,
                resultado_exitoso=False
            )
            return None, {"error": f"Error general: {str(e)}"}

def get_clean_openai_assistants_client():
    """
    Obtiene una instancia del cliente limpio de OpenAI Assistants.
    No usa la biblioteca oficial para evitar problemas de configuración.

    Returns:
        CleanOpenAIAssistants o None: Cliente de OpenAI Assistants o None si no está disponible
    """
    # Limpiar variables de entorno de proxies
    if "HTTP_PROXY" in os.environ:
        del os.environ["HTTP_PROXY"]
    if "HTTPS_PROXY" in os.environ:
        del os.environ["HTTPS_PROXY"]
    
    # Obtener API key
    from core.openai_utils import get_openai_api_key
    api_key = get_openai_api_key()
    
    if not api_key:
        logger.error("API key de OpenAI no configurada")
        return None

    # Verificar circuit breaker
    if not circuit_breaker.can_execute("openai"):
        logger.warning("Circuit breaker abierto para OpenAI")
        return None
    
    # Crear cliente
    try:
        client = CleanOpenAIAssistants(api_key=api_key)
        
        # Guardar en session_state
        st.session_state["clean_openai_assistants_client"] = client
        
        return client
    except Exception as e:
        logger.error(f"Error inicializando CleanOpenAIAssistants: {e}")
        return None
