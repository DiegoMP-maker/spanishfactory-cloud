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
import importlib

# Importar dependencias del proyecto
from config.settings import MAX_RETRIES, DEFAULT_TIMEOUT
from core.circuit_breaker import circuit_breaker

# Configurar logger
logger = logging.getLogger(__name__)

# Configuración global para timeouts
DEFAULT_API_TIMEOUT = 30       # Timeout para peticiones API básicas
MESSAGES_API_TIMEOUT = 60      # Timeout para obtener mensajes
RUN_API_TIMEOUT = 60           # Timeout para ejecutar asistentes
POLLING_API_TIMEOUT = 30       # Timeout para polling de estado

def extract_json_safely(content):
    """
    Extrae JSON válido de una cadena de texto con manejo de errores mejorado y reparación.
    Versión optimizada y robusta para manejar respuestas del asistente.
    
    Args:
        content (str): Contenido que puede incluir JSON
        
    Returns:
        dict: Diccionario con el JSON extraído o diccionario vacío si no se encuentra
    """
    if not content:
        logger.warning("Contenido vacío, no se puede extraer JSON")
        return {}
    
    # Guardar las primeras 100 caracteres para diagnóstico
    preview = content[:100].replace('\n', ' ') + "..." if len(content) > 100 else content
    logger.info(f"Intentando extraer JSON del contenido. Vista previa: {preview}")
    
    try:
        # 1. Primero intentar parsear directamente todo el contenido
        try:
            result = json.loads(content)
            logger.info("✅ Éxito: JSON extraído directamente del contenido completo")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"No se pudo parsear directamente como JSON: {str(e)}")
            # Mostrar detalles del error para diagnóstico
            error_position = e.pos
            error_line, error_column = 0, 0
            lines = content[:error_position].splitlines()
            if lines:
                error_line = len(lines)
                error_column = len(lines[-1]) + 1
            context_start = max(0, error_position - 20)
            context_end = min(len(content), error_position + 20)
            error_context = content[context_start:context_end]
            logger.debug(f"Error JSON en línea {error_line}, columna {error_column}: '{error_context}'")
        
        # 2. Buscar bloques de código JSON con formato markdown
        import re
        
        # 2.1 Buscar bloques de código con etiqueta json explícita
        json_code_blocks = re.findall(r'```json\s*([\s\S]*?)```', content)
        if json_code_blocks:
            logger.info(f"Encontrados {len(json_code_blocks)} bloques de código JSON explícitos")
            for i, block in enumerate(json_code_blocks):
                try:
                    result = json.loads(block.strip())
                    logger.info(f"✅ Éxito: JSON extraído del bloque de código JSON explícito #{i+1}")
                    return result
                except json.JSONDecodeError as e:
                    logger.debug(f"Bloque JSON explícito #{i+1} no es JSON válido: {str(e)}")
        
        # 2.2 Buscar bloques de código genéricos que podrían contener JSON
        generic_code_blocks = re.findall(r'```\s*([\s\S]*?)```', content)
        if generic_code_blocks:
            logger.info(f"Encontrados {len(generic_code_blocks)} bloques de código genéricos")
            for i, block in enumerate(generic_code_blocks):
                try:
                    # Verificar si el bloque empieza con '{'
                    if block.strip().startswith('{'):
                        result = json.loads(block.strip())
                        logger.info(f"✅ Éxito: JSON extraído del bloque de código genérico #{i+1}")
                        return result
                except json.JSONDecodeError as e:
                    logger.debug(f"Bloque genérico #{i+1} no es JSON válido: {str(e)}")
        
        # 3. Buscar cualquier estructura con forma de JSON en el texto
        # Es importante encontrar el JSON completo, desde el primer { hasta el último }
        # que forme un objeto JSON válido completo
        
        # 3.1 Buscar desde el primer { hasta el último }
        first_brace = content.find('{')
        last_brace = content.rfind('}')
        
        if first_brace >= 0 and last_brace > first_brace:
            potential_json = content[first_brace:last_brace+1]
            logger.debug(f"Encontrada posible estructura JSON desde posición {first_brace} hasta {last_brace}")
            
            try:
                result = json.loads(potential_json)
                logger.info(f"✅ Éxito: JSON extraído desde '{{{' hasta último '}}}'")
                return result
            except json.JSONDecodeError as e:
                logger.debug(f"La estructura encontrada no es JSON válido: {str(e)}")
        
        # 4. Extraer todas las estructuras que parecen JSON y probar cada una
        all_json_like = re.findall(r'({[^{]*})', content)
        if all_json_like:
            logger.info(f"Encontrados {len(all_json_like)} fragmentos potenciales de JSON")
            
            # Ordenar por longitud (preferir fragmentos más largos primero)
            all_json_like.sort(key=len, reverse=True)
            
            for i, json_fragment in enumerate(all_json_like):
                try:
                    result = json.loads(json_fragment)
                    logger.info(f"✅ Éxito: JSON extraído de fragmento potencial #{i+1}")
                    return result
                except json.JSONDecodeError:
                    pass
        
        # 5. Buscar estructuras que tengan las clave esperadas para una corrección
        expected_keys = ["errores", "texto_corregido", "saludo", "tipo_texto", "analisis_contextual", "consejo_final"]
        
        # Contar cuántas claves esperadas aparecen en el contenido
        keys_present = [key for key in expected_keys if f'"{key}"' in content or f"'{key}'" in content]
        
        if len(keys_present) >= 3:  # Si al menos 3 claves están presentes, podría ser una corrección
            logger.info(f"Encontradas {len(keys_present)} claves esperadas en el contenido: {', '.join(keys_present)}")
            
            # 5.1 Intentar una reparación agresiva
            # Extraer el contenido entre el primer { y el último }
            if first_brace >= 0 and last_brace > first_brace:
                potential_json = content[first_brace:last_brace+1]
                
                # Limpiar caracteres problemáticos
                cleaned_json = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', potential_json)
                
                # Normalizar comillas
                # Reemplazar " por " si hay un desequilibrio
                quote_count = cleaned_json.count('"')
                if quote_count % 2 != 0:
                    logger.info("Detectado número impar de comillas, intentando normalizar")
                    cleaned_json = cleaned_json.replace('"', '"')
                
                # Intentar parsear el JSON limpio
                try:
                    result = json.loads(cleaned_json)
                    logger.info("✅ Éxito: JSON extraído después de limpieza extensiva")
                    return result
                except json.JSONDecodeError:
                    logger.debug("La limpieza extensiva no fue suficiente")
            
            # 5.2 Si todo falla, crear manualmente un JSON con estructura mínima
            logger.warning("No se pudo extraer JSON válido. Creando estructura mínima.")
            
            # Intenta extraer el texto corregido
            texto_corregido_match = re.search(r'"texto_corregido"\s*:\s*"([^"]*)"', content)
            texto_corregido = texto_corregido_match.group(1) if texto_corregido_match else ""
            
            # Intenta extraer el consejo final
            consejo_final_match = re.search(r'"consejo_final"\s*:\s*"([^"]*)"', content)
            consejo_final = consejo_final_match.group(1) if consejo_final_match else ""
            
            # Crear estructura mínima
            minimal_json = {
                "texto_corregido": texto_corregido or content,
                "errores": {
                    "Gramática": [],
                    "Léxico": [],
                    "Puntuación": [],
                    "Estructura textual": []
                },
                "consejo_final": consejo_final or "No se pudo extraer el consejo final."
            }
            
            logger.info("✅ Creada estructura JSON mínima como fallback")
            return minimal_json
        
        # Si llegamos aquí, no hay JSON válido
        logger.warning("❌ No se pudo extraer JSON válido del contenido después de múltiples intentos")
        
        # Mostrar fragmentos del contenido para diagnóstico
        if len(content) > 500:
            logger.debug(f"Primeros 250 caracteres del contenido: {content[:250]}")
            logger.debug(f"Últimos 250 caracteres del contenido: {content[-250:]}")
        else:
            logger.debug(f"Contenido completo: {content}")
        
        # Proporcionar un objeto de respuesta mínimo que evite errores posteriores
        return {
            "texto_corregido": "No se pudo procesar la respuesta correctamente.",
            "errores": {
                "Gramática": [],
                "Léxico": [],
                "Puntuación": [],
                "Estructura textual": []
            },
            "consejo_final": "Hubo un problema al procesar la respuesta. Por favor, intenta nuevamente."
        }
        
    except Exception as e:
        logger.error(f"❌ Error inesperado extrayendo JSON del contenido: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Proporcionar un objeto de respuesta mínimo que evite errores posteriores
        return {
            "texto_corregido": "Error interno procesando la respuesta.",
            "errores": {
                "Gramática": [],
                "Léxico": [],
                "Puntuación": [],
                "Estructura textual": []
            },
            "consejo_final": "Ocurrió un error interno. Por favor, intenta nuevamente."
        }

def guardar_metricas_modelo(modelo, tiempo_respuesta, longitud_texto, resultado_exitoso):
    """
    Guarda métricas de uso de modelos.
    
    Args:
        modelo: Nombre del modelo usado
        tiempo_respuesta: Tiempo de respuesta en segundos
        longitud_texto: Longitud del texto procesado
        resultado_exitoso: Si la operación fue exitosa
    """
    try:
        # Importar dinámicamente para evitar dependencias circulares
        from core.firebase_client import save_model_metrics
        
        # Intentar guardar métricas
        save_model_metrics(
            modelo=modelo,
            tiempo_respuesta=tiempo_respuesta,
            longitud_texto=longitud_texto,
            resultado_exitoso=resultado_exitoso
        )
    except Exception as e:
        # No es crítico si falla
        logger.warning(f"No se pudieron guardar métricas del modelo: {e}")

def get_student_profile_helper(user_id):
    """
    Función auxiliar para obtener el perfil del estudiante.
    Usa importación dinámica para evitar dependencias circulares.
    
    Args:
        user_id: ID del usuario
        
    Returns:
        dict: Perfil del estudiante o diccionario vacío si hay error
    """
    try:
        # Importar dinámicamente para evitar dependencias circulares
        correccion_module = importlib.import_module('features.correccion')
        
        # Comprobar si la función existe
        if hasattr(correccion_module, 'get_student_profile'):
            return correccion_module.get_student_profile(user_id)
        else:
            logger.error("No se encontró la función get_student_profile en el módulo correccion")
            return {}
    except Exception as e:
        logger.error(f"Error al obtener perfil de estudiante: {e}")
        return {}

class CleanOpenAIAssistants:
    """
    Cliente limpio para OpenAI Assistants API.
    No usa la biblioteca oficial para evitar problemas de configuración.
    """
    
    BASE_URL = "https://api.openai.com/v1"
    
    # Diccionario para almacenar IDs de asistentes por tipo de tarea
    ASSISTANT_IDS = {
        "correccion_texto": "",
        "generacion_ejercicios": "",
        "simulacro_examen": "",
        "plan_estudio": "",
        "default": ""
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
    
    def _api_request(self, method, endpoint, data=None, params=None, timeout=DEFAULT_API_TIMEOUT):
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
            
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"Timeout en petición a {url}: {e} (timeout={timeout}s)")
            return {"error": f"Timeout después de {timeout}s", "error_type": "timeout"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en petición a {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Detalles del error: {error_detail}")
                except:
                    logger.error(f"Status: {e.response.status_code}, Contenido: {e.response.content}")
            return {"error": str(e), "error_type": "request"}
    
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
            
        return self._api_request("POST", "/assistants", data=data, timeout=RUN_API_TIMEOUT)
    
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
        thread_response = self._api_request("POST", "/threads", data=thread_data, timeout=RUN_API_TIMEOUT)
        
        # Si no hay thread_id, salir
        if not thread_response or "id" not in thread_response:
            logger.error("No se pudo crear el thread")
            return None
        
        thread_id = thread_response["id"]
        
        # Añadir mensaje inicial con información de perfil si tenemos user_id
        if user_id:
            try:
                # Obtener perfil del estudiante usando la función auxiliar
                profile_data = get_student_profile_helper(user_id)
                
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
        return self._api_request("POST", f"/threads/{thread_id}/messages", data=data, timeout=RUN_API_TIMEOUT)
    
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
            
            # Obtener perfil del estudiante mediante la función auxiliar
            profile_data = get_student_profile_helper(user_id)
            
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
                error_msg = message_response.get("error", "Error desconocido") if isinstance(message_response, dict) else "Error desconocido"
                error_type = message_response.get("error_type", "general") if isinstance(message_response, dict) else "general" 
                
                if error_type == "timeout":
                    logger.error(f"Timeout al añadir mensaje de perfil al thread {thread_id}: {error_msg}")
                else:
                    logger.error(f"Error al añadir mensaje de perfil al thread {thread_id}: {error_msg}")
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
        return self._api_request("POST", f"/threads/{thread_id}/runs", data=data, timeout=RUN_API_TIMEOUT)
    
    def get_run(self, thread_id, run_id):
        """
        Obtiene el estado de una ejecución.
        
        Args:
            thread_id: ID del thread
            run_id: ID de la ejecución
            
        Returns:
            dict: Estado de la ejecución o None si hay error
        """
        return self._api_request("GET", f"/threads/{thread_id}/runs/{run_id}", timeout=POLLING_API_TIMEOUT)
    
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
        return self._api_request("GET", f"/threads/{thread_id}/messages", params=params, timeout=MESSAGES_API_TIMEOUT)
    
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
        
        # Para el tipo de tarea de corrección de texto, asegurar que usamos el prompt correcto
        instructions_to_use = system_message
        if task_type == "correccion_texto":
            # Si el system_message está vacío o es muy corto, intentar obtener el prompt completo
            if not system_message or len(system_message) < 500:
                try:
                    # Importar dinámicamente para evitar dependencias circulares
                    import sys
                    import importlib
                    if 'features.correccion' in sys.modules:
                        # Si ya está importado, usarlo directamente
                        correccion_module = sys.modules['features.correccion']
                    else:
                        # Si no está importado, importarlo
                        correccion_module = importlib.import_module('features.correccion')
                    
                    # Acceder a la constante
                    if hasattr(correccion_module, 'SYSTEM_PROMPT_CORRECTION'):
                        instructions_to_use = correccion_module.SYSTEM_PROMPT_CORRECTION
                        logger.info("✅ SYSTEM_PROMPT_CORRECTION cargado correctamente para crear asistente")
                    else:
                        logger.warning("⚠️ No se encontró SYSTEM_PROMPT_CORRECTION en el módulo correccion")
                except Exception as e:
                    logger.warning(f"⚠️ Error cargando SYSTEM_PROMPT_CORRECTION: {str(e)}")
            else:
                logger.info(f"Usando system_message proporcionado (longitud: {len(system_message)} caracteres)")
        
        # 3. Buscar en caché basado en el hash del mensaje
        instruccion_hash = hashlib.md5(f"{instructions_to_use}_{self.current_model}".encode()).hexdigest()
        if instruccion_hash in self.assistant_cache:
            # Verificar que el asistente de caché existe
            cached_assistant_id = self.assistant_cache[instruccion_hash]
            assistant_info = self.get_assistant(cached_assistant_id)
            if assistant_info:
                logger.info(f"Usando asistente existente de caché: {cached_assistant_id}")
                return cached_assistant_id
            else:
                logger.warning(f"Asistente en caché {cached_assistant_id} no existe o es inaccesible")
        
        # 4. Crear un nuevo asistente
        has_json_keyword = "json" in instructions_to_use.lower()
        
        if not has_json_keyword:
            logger.warning("El mensaje del sistema no contiene la palabra 'json', usando formato de respuesta abierto")
        
        # Registrar información sobre las instrucciones utilizadas
        instructions_info = f"Creando asistente con instrucciones - Longitud: {len(instructions_to_use)} caracteres"
        if len(instructions_to_use) > 100:
            instructions_info += f"\nInicio: {instructions_to_use[:50]}...\nFin: ...{instructions_to_use[-50:]}"
        logger.info(instructions_info)
        
        new_assistant = self.create_assistant(
            name=f"TextoCorrector ELE - {task_type}",
            instructions=instructions_to_use,
            model=self.current_model,
            json_mode=has_json_keyword
        )
        
        if new_assistant and "id" in new_assistant:
            assistant_id = new_assistant["id"]
            self.assistant_cache[instruccion_hash] = assistant_id
            logger.info(f"✅ Creado nuevo asistente para {task_type} con ID: {assistant_id}")
            return assistant_id
        
        raise Exception("No se pudo crear o encontrar un asistente válido")
    
    def get_completion(self, system_message, user_message, 
                     max_retries=MAX_RETRIES, task_type="default", 
                     thread_id=None, user_id=None):
        """
        Obtiene una respuesta usando OpenAI Assistants con soporte para thread persistente.
        Versión mejorada para forzar formato JSON en las respuestas.
        
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
        
        # Para task_type "correccion_texto", asegurarse de incluir recordatorio JSON en el mensaje
        if task_type == "correccion_texto":
            # Verificar si ya hay referencia a JSON en los mensajes
            has_json_keyword = "json" in system_message.lower() or "json" in user_message.lower()
            
            if not has_json_keyword:
                logger.warning("⚠️ Ni el system_message ni el user_message contienen la palabra 'json'")
                # Añadir una referencia explícita a JSON y estructura en el mensaje del usuario
                json_reminder = """

RECORDATORIO CRÍTICO:
Debes responder ÚNICAMENTE con un objeto JSON válido, siguiendo exactamente esta estructura:
{
  "saludo": "...",
  "tipo_texto": "...",
  "errores": {
    "Gramática": [...],
    "Léxico": [...],
    "Puntuación": [...],
    "Estructura textual": [...]
  },
  "texto_corregido": "...",
  "analisis_contextual": {
    "coherencia": {...},
    "cohesion": {...},
    "registro_linguistico": {...},
    "adecuacion_cultural": {...}
  },
  "consejo_final": "...",
  "fin": "Fin de texto corregido."
}

Tu respuesta DEBE comenzar con '{' y terminar con '}' sin ningún texto fuera del objeto JSON.
"""
                user_message += json_reminder
                logger.info("✅ Añadido recordatorio detallado de estructura JSON al mensaje del usuario")
        # Para otros tipos de tareas, mantener comportamiento original
        else:
            # Verificar si system_message o user_message contienen la palabra "json"
            has_json_keyword = "json" in system_message.lower() or "json" in user_message.lower()
            if not has_json_keyword:
                logger.warning("Ni el mensaje del sistema ni el mensaje del usuario contienen la palabra 'json'")
                # Añadir una referencia a JSON en el mensaje del usuario si es necesario
                if task_type in ["generacion_ejercicios", "plan_estudio"]:
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
                assistant_instruction = system_message if system_message else ""
                assistant_id = self.get_assistant_id(task_type, assistant_instruction)
            except Exception as e:
                logger.error(f"Error al obtener ID de asistente: {e}")
                return None, {
                    "error": f"Error al obtener ID de asistente: {str(e)}",
                    "texto_corregido": "Error interno al configurar el servicio de corrección.",
                    "errores": {
                        "Gramática": [],
                        "Léxico": [],
                        "Puntuación": [],
                        "Estructura textual": []
                    }
                }
            
            # Crear o usar thread existente
            if not thread_id_is_valid:
                # Crear nuevo thread con perfil de usuario si está disponible
                thread_response = self.create_thread(user_id=user_id)
                if not thread_response or "id" not in thread_response:
                    return None, {
                        "error": "No se pudo crear thread",
                        "texto_corregido": "No se pudo iniciar la sesión de corrección.",
                        "errores": {
                            "Gramática": [],
                            "Léxico": [],
                            "Puntuación": [],
                            "Estructura textual": []
                        }
                    }
                thread_id = thread_response["id"]
                logger.info(f"Creado nuevo thread: {thread_id}")
            else:
                logger.info(f"Usando thread existente: {thread_id}")
                
                # Si tenemos user_id y thread existente, verificar si necesitamos actualizar el perfil
                if user_id:
                    # Cada 10 interacciones o según necesidad, actualizar el perfil
                    thread_messages = self.list_messages(thread_id)
                    
                    # Verificar si la respuesta contiene error de timeout
                    if isinstance(thread_messages, dict) and "error_type" in thread_messages and thread_messages["error_type"] == "timeout":
                        logger.warning(f"Timeout al obtener mensajes del thread: {thread_messages.get('error', 'Timeout')}")
                        return None, {
                            "error": "Timeout al obtener mensajes del thread",
                            "texto_corregido": "El servicio de corrección está tardando demasiado en responder. Por favor, inténtelo de nuevo más tarde.",
                            "errores": {
                                "Gramática": [],
                                "Léxico": [],
                                "Puntuación": [],
                                "Estructura textual": []
                            }
                        }
                    
                    if thread_messages and "data" in thread_messages:
                        message_count = len(thread_messages["data"])
                        if message_count % 10 == 0:  # Actualizar cada 10 mensajes
                            try:
                                self.update_thread_with_profile(thread_id, user_id)
                            except Exception as profile_error:
                                logger.warning(f"Error actualizando perfil en thread: {str(profile_error)}")
            
            # Añadir mensaje al thread
            message_response = self.add_message_to_thread(thread_id, user_message)
            
            # Verificar si la respuesta contiene error de timeout
            if isinstance(message_response, dict) and "error_type" in message_response and message_response["error_type"] == "timeout":
                logger.warning(f"Timeout al añadir mensaje al thread: {message_response.get('error', 'Timeout')}")
                return None, {
                    "error": "Timeout al añadir mensaje al thread",
                    "texto_corregido": "El servicio de corrección está tardando demasiado en responder. Por favor, inténtelo de nuevo más tarde.",
                    "errores": {
                        "Gramática": [],
                        "Léxico": [],
                        "Puntuación": [],
                        "Estructura textual": []
                    }
                }
            
            if not message_response or (isinstance(message_response, dict) and "id" not in message_response):
                return None, {
                    "error": "Error al añadir mensaje al thread",
                    "texto_corregido": "No se pudo enviar el texto para su corrección.",
                    "errores": {
                        "Gramática": [],
                        "Léxico": [],
                        "Puntuación": [],
                        "Estructura textual": []
                    }
                }
            
            # Obtener funciones disponibles para el asistente
            from features.functions_definitions import get_functions_definitions
            assistant_functions = get_functions_definitions()
            
            # Ejecutar asistente con reintentos
            for attempt in range(max_retries):
                try:
                    # Iniciar ejecución con función calling
                    run_response = self._api_request(
                        "POST", 
                        f"/threads/{thread_id}/runs", 
                        data={
                            "assistant_id": assistant_id,
                            "tools": assistant_functions  # Añadir funciones disponibles
                        }
                    )
                    
                    # Verificar si la respuesta contiene error de timeout
                    if isinstance(run_response, dict) and "error_type" in run_response and run_response["error_type"] == "timeout":
                        logger.warning(f"Timeout al iniciar ejecución del asistente: {run_response.get('error', 'Timeout')}")
                        raise TimeoutError(f"Timeout al iniciar ejecución: {run_response.get('error', 'Timeout')}")
                    
                    if not run_response or "id" not in run_response:
                        raise Exception("Error al iniciar ejecución del asistente")
                    
                    run_id = run_response["id"]
                    
                    # Esperar a que la ejecución se complete (con manejo de funciones)
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
                        
                        # Verificar si la respuesta contiene error de timeout
                        if isinstance(run_status_response, dict) and "error_type" in run_status_response and run_status_response["error_type"] == "timeout":
                            logger.warning(f"Timeout al obtener estado de ejecución: {run_status_response.get('error', 'Timeout')}")
                            raise TimeoutError(f"Timeout al obtener estado: {run_status_response.get('error', 'Timeout')}")
                        
                        if not run_status_response or "status" not in run_status_response:
                            raise Exception("Error al obtener estado de la ejecución")
                        
                        status = run_status_response["status"]
                        polling_count += 1
                        logger.info(f"Estado de ejecución ({polling_count}): {status} (tiempo transcurrido: {time.time() - start_time:.1f}s)")
                        
                        # Verificar si ha terminado
                        if status == "completed":
                            logger.info(f"Ejecución completada después de {polling_count} consultas")
                            break
                            
                        # Verificar si ha fallado
                        if status in ["failed", "cancelled", "expired"]:
                            error_detail = run_status_response.get("last_error", {})
                            error_message = error_detail.get("message", "Unknown error")
                            raise Exception(f"Ejecución fallida con estado {status}: {error_message}")
                        
                        # Verificar si requiere acción (función)
                        if status == "requires_action":
                            logger.info("La ejecución requiere acción (function calling)")
                            
                            # Procesar llamadas a funciones
                            # Importar la función mejorada
                            from core.openai_integration import process_function_calls
                            function_success = process_function_calls(assistant_id, thread_id, run_id, self)
                            
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
                    messages_response = self.list_messages(thread_id)
                    
                    # Verificar si la respuesta contiene error de timeout
                    if isinstance(messages_response, dict) and "error_type" in messages_response and messages_response["error_type"] == "timeout":
                        logger.warning(f"Timeout al obtener mensajes del thread: {messages_response.get('error', 'Timeout')}")
                        raise TimeoutError(f"Timeout al obtener mensajes: {messages_response.get('error', 'Timeout')}")
                    
                    if not messages_response or "data" not in messages_response:
                        raise Exception("Error al obtener mensajes del thread")
                    
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
                    
                    # Log para debug
                    if content_text:
                        preview = content_text[:100].replace('\n', ' ') + "..." if len(content_text) > 100 else content_text
                        logger.info(f"Respuesta recibida: {preview}")
                    else:
                        logger.warning("Contenido de respuesta vacío")
                    
                    # Verificar si la respuesta contiene JSON
                    has_json = "{" in content_text and "}" in content_text
                    if not has_json:
                        logger.warning("La respuesta no parece contener JSON, se intentará extraer manualmente")
                    
                    # Extraer JSON del contenido
                    json_data = extract_json_safely(content_text)
                    
                    # Añadir thread_id
                    if isinstance(json_data, dict):
                        json_data["thread_id"] = thread_id
                    
                    # Añadir texto original si no está incluido
                    if isinstance(json_data, dict) and "texto_original" not in json_data:
                        # Extraer texto original del mensaje del usuario
                        for user_msg in messages_response["data"]:
                            if user_msg["role"] == "user":
                                user_text = ""
                                for content_item in user_msg.get("content", []):
                                    if content_item["type"] == "text":
                                        user_text += content_item["text"]["value"]
                                # Buscar el texto original
                                import re
                                texto_match = re.search(r'TEXTO PARA CORREGIR:\s*["\']([^"\']+)["\']', user_text)
                                if texto_match:
                                    json_data["texto_original"] = texto_match.group(1)
                                else:
                                    # Si no encuentra el patrón, usar todo el mensaje
                                    json_data["texto_original"] = user_text
                                break
                    
                    # Asegurar que hay una estructura mínima
                    if isinstance(json_data, dict):
                        if "errores" not in json_data:
                            json_data["errores"] = {
                                "Gramática": [],
                                "Léxico": [],
                                "Puntuación": [],
                                "Estructura textual": []
                            }
                        if "texto_corregido" not in json_data:
                            json_data["texto_corregido"] = content_text
                    
                    # Guardar métricas
                    tiempo_total = time.time() - tiempo_inicio
                    guardar_metricas_modelo(
                        modelo=self.current_model,
                        tiempo_respuesta=tiempo_total,
                        longitud_texto=longitud_estimada,
                        resultado_exitoso="error" not in json_data
                    )
                    
                    # Registrar éxito
                    circuit_breaker.record_success("openai")
                    
                    logger.info(f"Solicitud completada en {tiempo_total:.2f}s")
                    return content_text, json_data
                
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
                        return None, {
                            "error": f"Timeout después de {max_retries} intentos",
                            "texto_corregido": "Lo siento, el servicio de corrección está tardando demasiado en responder. Por favor, intenta nuevamente en unos momentos.",
                            "errores": {
                                "Gramática": [],
                                "Léxico": [],
                                "Puntuación": [],
                                "Estructura textual": []
                            }
                        }
                    
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
                        return None, {
                            "error": f"Error: {str(e)}",
                            "texto_corregido": "Lo siento, ha ocurrido un error al procesar tu texto. Por favor, intenta nuevamente.",
                            "errores": {
                                "Gramática": [],
                                "Léxico": [],
                                "Puntuación": [],
                                "Estructura textual": []
                            }
                        }
                    
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
            return None, {
                "error": f"Error general: {str(e)}",
                "texto_corregido": "Lo siento, ha ocurrido un error inesperado. Por favor, intenta nuevamente más tarde.",
                "errores": {
                    "Gramática": [],
                    "Léxico": [],
                    "Puntuación": [],
                    "Estructura textual": []
                }
            }

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

# Añade esta función en core/clean_openai_assistant.py, al final del archivo pero antes 
# de la función get_clean_openai_assistants_client()

def reset_thread(user_id=None):
    """
    Reinicia el thread para un usuario, creando uno nuevo y limpiando referencias al antiguo.
    Útil cuando hay problemas con threads existentes que generan errores 500.
    
    Args:
        user_id (str, opcional): ID del usuario
        
    Returns:
        str: ID del nuevo thread o None si hay error
    """
    try:
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
        
        # Crear cliente
        client = CleanOpenAIAssistants(api_key=api_key)
        
        # Eliminar thread_id de session_state si existe
        if "thread_id" in st.session_state:
            logger.info(f"Eliminando thread_id {st.session_state['thread_id']} de session_state")
            del st.session_state["thread_id"]
        
        # Si hay user_id, limpiar también en Firebase
        if user_id:
            try:
                from core.firebase_client import save_user_thread
                logger.info(f"Limpiando thread_id para usuario {user_id} en Firebase")
                # Pasar None como thread_id para indicar que no hay thread activo
                save_user_thread(user_id, None)
            except Exception as e:
                logger.warning(f"Error limpiando thread en Firebase: {str(e)}")
        
        # Crear nuevo thread
        logger.info("Creando nuevo thread después de reset")
        thread_response = client.create_thread(user_id=user_id)
        
        if thread_response and "id" in thread_response:
            thread_id = thread_response["id"]
            
            # Guardar en session_state
            st.session_state["thread_id"] = thread_id
            
            # Si hay user_id, guardar en Firebase
            if user_id:
                try:
                    from core.firebase_client import save_user_thread
                    save_user_thread(user_id, thread_id)
                    logger.info(f"Nuevo thread {thread_id} guardado en Firebase para usuario {user_id}")
                except Exception as e:
                    logger.warning(f"Error guardando nuevo thread en Firebase: {str(e)}")
            
            logger.info(f"Thread reiniciado exitosamente. Nuevo thread_id: {thread_id}")
            return thread_id
        else:
            logger.error("No se pudo crear un nuevo thread después de reset")
            return None
    
    except Exception as e:
        logger.error(f"Error en reset_thread: {str(e)}")
        return None


