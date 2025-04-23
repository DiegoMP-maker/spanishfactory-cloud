#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cliente para la API directa de OpenAI (no Assistants)
----------------------------------------------------
Este módulo proporciona funciones para interactuar con la API directa de OpenAI,
usado para transcripción, consignas, imágenes DALL-E y otras funciones que no utilizan Assistants.
"""

import time
import json
import logging
import requests
import traceback
from typing import Optional, Dict, Any, Tuple, List

import streamlit as st
from openai import OpenAI

from core.circuit_breaker import circuit_breaker, retry_with_backoff
from config.settings import (
    DEFAULT_OPENAI_MODEL, DEFAULT_TIMEOUT, MAX_RETRIES, 
    OPENAI_MODELS_PREFERIDOS_ECONOMICOS, OPENAI_MODELS_PREFERIDOS_CAPACIDAD
)

logger = logging.getLogger(__name__)

def get_api_key() -> Optional[str]:
    """
    Obtiene la API key de OpenAI desde los secrets de Streamlit.

    Returns:
        str: API key o None si no está configurada
    """
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception as e:
        logger.warning(f"Error al obtener API Key de OpenAI: {e}")
        return None

def list_available_openai_models() -> List[str]:
    """
    Lista todos los modelos disponibles de OpenAI.

    Returns:
        list: Lista de nombres de modelos disponibles o lista por defecto
    """
    api_key = get_api_key()
    if api_key is None:
        logger.warning("API key de OpenAI no configurada")
        return []

    if not circuit_breaker.can_execute("openai"):
        logger.warning("Circuit breaker abierto para OpenAI")
        return []

    try:
        # Configurar la API key para OpenAI
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Función para ejecutar la solicitud con reintentos
        def fetch_models():
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=10  # Timeout reducido para esta solicitud informativa
            )
            response.raise_for_status()
            return response.json()

        # Ejecutar con reintentos
        models_data = retry_with_backoff(fetch_models, max_retries=2)

        # Filtrar modelos GPT
        gpt_models = [model["id"] for model in models_data.get("data", [])
                      if "gpt" in model["id"].lower()]

        logger.info(f"Modelos OpenAI disponibles: {gpt_models}")

        # Registrar éxito
        circuit_breaker.record_success("openai")

        return gpt_models
    except Exception as e:
        logger.error(f"Error al listar modelos OpenAI: {e}")
        circuit_breaker.record_failure("openai", error_type="list_models")
        # Devolver lista por defecto en caso de error
        return ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]

def get_best_openai_model(priorizar_costo=True) -> str:
    """
    Determina el mejor modelo OpenAI disponible basado en prioridades.
    Puede priorizar costo o capacidad según necesidades.

    Args:
        priorizar_costo: Si es True, prioriza modelos más económicos.

    Returns:
        str: Nombre del mejor modelo disponible o un modelo predeterminado
    """
    if priorizar_costo:
        # Lista de modelos preferidos en orden de prioridad (primero los más económicos)
        preferred_models = OPENAI_MODELS_PREFERIDOS_ECONOMICOS
    else:
        # Lista de modelos preferidos en orden de capacidad (primero los más potentes)
        preferred_models = OPENAI_MODELS_PREFERIDOS_CAPACIDAD

    # Obtener modelos disponibles
    available_models = list_available_openai_models()

    # Si no hay modelos disponibles, usar un modelo predeterminado
    if not available_models:
        logger.warning("No se encontraron modelos OpenAI disponibles, usando valor predeterminado")
        return DEFAULT_OPENAI_MODEL

    # Buscar el primer modelo preferido que esté disponible
    for model in preferred_models:
        if any(model in available_model for available_model in available_models):
            return model

    # Si ninguno de los preferidos está disponible, usar el primero de la lista
    return available_models[0]

def configure_openai() -> Tuple[Optional[str], bool]:
    """
    Configura el cliente de OpenAI con la API key y verifica la conexión.

    Returns:
        tuple: (modelo_seleccionado, éxito_configuración)
    """
    api_key = get_api_key()
    if api_key is None:
        logger.warning("API key de OpenAI no configurada")
        return None, False

    if not circuit_breaker.can_execute("openai"):
        logger.warning("Circuit breaker abierto para OpenAI")
        return None, False

    try:
        # Obtener preferencia de priorización de costos
        priorizar_costo = st.session_state.get("priorizar_costo", True)

        # Seleccionar mejor modelo según preferencia
        best_model_name = get_best_openai_model(priorizar_costo)
        logger.info(f"Usando modelo OpenAI: {best_model_name}")

        # Verificar que la configuración funcione haciendo una llamada simple
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": best_model_name,
            "messages": [{"role": "user", "content": "Hello, testing OpenAI connection."}],
            "max_tokens": 10
        }

        # Función para verificar la conexión con reintentos
        def test_connection():
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=15  # Timeout para conexión de prueba
            )
            response.raise_for_status()
            return response.json()

        # Probar conexión con reintentos
        response_data = retry_with_backoff(test_connection, max_retries=2)

        # Si llegamos aquí, la configuración fue exitosa
        circuit_breaker.record_success("openai")
        st.session_state.servicios_disponibles = {
            **st.session_state.get("servicios_disponibles", {}),
            "openai": True
        }

        # Registrar información del modelo seleccionado
        logger.info(f"Conexión a OpenAI exitosa con modelo {best_model_name}")

        return best_model_name, True
    except requests.Timeout as e:
        logger.error(f"Timeout al configurar OpenAI: {e}")
        circuit_breaker.record_failure("openai", error_type="timeout")
        return None, False
    except requests.HTTPError as e:
        status_code = e.response.status_code if hasattr(e, 'response') else 0
        logger.error(f"Error HTTP {status_code} al configurar OpenAI: {e}")
        circuit_breaker.record_failure("openai", error_type=f"http_{status_code}")
        return None, False
    except Exception as e:
        logger.error(f"Error al configurar OpenAI: {e}")
        circuit_breaker.record_failure("openai", error_type="generic")
        return None, False

def get_completion_direct(system_msg: str, user_msg: str, model: str = None, max_retries: int = MAX_RETRIES) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Obtiene una respuesta directamente de la API de OpenAI (sin usar Assistants).
    
    Args:
        system_msg: Mensaje del sistema
        user_msg: Mensaje del usuario
        model: Modelo a utilizar (si es None, se utilizará el mejor disponible)
        max_retries: Número máximo de reintentos
    
    Returns:
        tuple: (respuesta_texto, datos_json_si_disponibles)
    """
    api_key = get_api_key()
    if api_key is None:
        return None, {"error": "API de OpenAI no configurada"}

    if not circuit_breaker.can_execute("openai"):
        return None, {"error": "Servicio OpenAI temporalmente no disponible"}

    # Si no se especifica modelo, usar el mejor disponible
    if model is None:
        model, success = configure_openai()
        if not success:
            return None, {"error": "No se pudo configurar OpenAI"}

    # Intentar detectar si se espera respuesta en JSON
    expect_json = "json" in system_msg.lower() or "json" in user_msg.lower()

    # Registrar tiempo de inicio para métricas
    tiempo_inicio = time.time()
    longitud_estimada = len(user_msg.split())

    for attempt in range(max_retries):
        try:
            # Configurar cliente OpenAI
            client = OpenAI(api_key=api_key)
            
            # Llamada a la API de OpenAI
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7,
                max_tokens=1500,
                response_format={"type": "json_object"} if expect_json else None
            )
            
            # Extraer contenido de la respuesta
            content = response.choices[0].message.content
            
            # Intentar extraer JSON si se espera
            data_json = {}
            if expect_json:
                try:
                    data_json = json.loads(content)
                except json.JSONDecodeError:
                    # Si falla el parseo JSON, intentar extraer con regex
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            data_json = json.loads(json_match.group(0))
                        except json.JSONDecodeError:
                            data_json = {"error": "Error al parsear JSON", "text": content}
                    else:
                        data_json = {"error": "No se encontró JSON en la respuesta", "text": content}
            
            # Registrar métricas
            tiempo_total = time.time() - tiempo_inicio
            from core.firebase_client import save_model_metrics
            save_model_metrics(
                modelo=model,
                tiempo_respuesta=tiempo_total,
                longitud_texto=longitud_estimada,
                resultado_exitoso=True
            )
            
            # Registrar éxito
            circuit_breaker.record_success("openai")
            
            return content, data_json
            
        except Exception as e:
            logger.error(f"Error en intento {attempt+1}/{max_retries}: {str(e)}")
            
            # Si es el último intento, registrar fallo
            if attempt == max_retries - 1:
                circuit_breaker.record_failure("openai", error_type="completion")
                tiempo_total = time.time() - tiempo_inicio
                from core.firebase_client import save_model_metrics
                save_model_metrics(
                    modelo=model if model else DEFAULT_OPENAI_MODEL,
                    tiempo_respuesta=tiempo_total,
                    longitud_texto=longitud_estimada,
                    resultado_exitoso=False
                )
                return None, {"error": f"Error en API de OpenAI: {str(e)}"}
            
            # Calcular tiempo de espera para backoff exponencial
            wait_time = min(60, 2 ** attempt)
            logger.info(f"Esperando {wait_time}s antes de reintentar")
            time.sleep(wait_time)
    
    # Este punto no debería alcanzarse nunca, pero por si acaso
    return None, {"error": "Error inesperado en get_completion_direct"}

def generar_imagen_dalle(tema: str, nivel: str) -> Tuple[Optional[str], str]:
    """
    Genera una imagen utilizando DALL-E basada en un tema y adaptada al nivel del estudiante.
    
    Args:
        tema: Tema para la imagen
        nivel: Nivel de español (principiante, intermedio, avanzado)
        
    Returns:
        tuple: (URL de la imagen generada, descripción de la imagen)
    """
    api_key = get_api_key()
    if api_key is None:
        return None, "API de DALL-E no disponible"

    if not circuit_breaker.can_execute("dalle"):
        return None, "Servicio DALL-E temporalmente no disponible"

    # Adaptar la complejidad del prompt según el nivel
    if "principiante" in nivel.lower():
        complejidad = "simple con objetos y personas claramente identificables"
    elif "intermedio" in nivel.lower():
        complejidad = "con detalles moderados y una escena cotidiana con varios elementos"
    else:
        complejidad = "detallada con múltiples elementos, que pueda generar descripciones complejas"

    # Crear el prompt para DALL-E
    prompt = f"Una escena {complejidad} sobre {tema}. La imagen debe ser clara, bien iluminada, y adecuada para describir en español."

    try:
        # Configurar client para OpenAI
        client = OpenAI(api_key=api_key)
        
        # Función para envío de solicitud con timeout adaptativo
        def generate_image():
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="standard"
            )
            return response

        # Usar sistema de reintentos
        response = retry_with_backoff(generate_image, max_retries=2, initial_delay=2)

        # Obtener la URL de la imagen
        imagen_url = response.data[0].url

        # Ahora generamos la descripción con OpenAI
        modelo_seleccionado, exito = configure_openai()
        if not exito:
            # Usar una descripción genérica si OpenAI no está disponible
            descripcion = f"Una imagen sobre {tema}. Práctica describiendo lo que ves en español."
            return imagen_url, descripcion

        from config.prompts import get_imagen_descripcion_prompt
        prompt_descripcion = get_imagen_descripcion_prompt(tema, nivel)

        # Realizar llamada para generar descripción
        descripcion_text, _ = get_completion_direct(
            "Eres un profesor de español que crea descripciones educativas de imágenes.",
            prompt_descripcion,
            model=modelo_seleccionado
        )

        if not descripcion_text:
            descripcion_text = f"Una imagen sobre {tema}. Práctica describiendo lo que ves en español."

        # Registrar éxito
        circuit_breaker.record_success("dalle")
        circuit_breaker.record_success("openai")

        return imagen_url, descripcion_text

    except Exception as e:
        logger.error(f"Error en generar_imagen_dalle: {str(e)}")
        logger.error(traceback.format_exc())
        circuit_breaker.record_failure("dalle", error_type="general")
        return None, f"Error: {str(e)}"

def transcribir_imagen_texto(imagen_bytes, idioma="es") -> str:
    """
    Transcribe texto manuscrito de una imagen utilizando la API de OpenAI.
    
    Args:
        imagen_bytes: Bytes de la imagen a transcribir
        idioma: Código de idioma (es, en, fr)
        
    Returns:
        str: Texto transcrito o mensaje de error
    """
    api_key = get_api_key()
    if api_key is None:
        return "Error: API de OpenAI no disponible"

    if not circuit_breaker.can_execute("openai"):
        return "Error: Servicio OpenAI temporalmente no disponible"

    try:
        # Importar el prompt adecuado
        from config.prompts import get_transcripcion_prompt
        prompt_transcripcion = get_transcripcion_prompt(idioma)
        
        # Codificar la imagen a base64
        import base64
        encoded_image = base64.b64encode(imagen_bytes).decode('utf-8')
        
        # Configurar cliente OpenAI
        client = OpenAI(api_key=api_key)
        
        # Función para enviar solicitud con reintentos
        def send_vision_request():
            response = client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_transcripcion},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            return response
        
        # Usar sistema de reintentos
        response = retry_with_backoff(send_vision_request, max_retries=2, initial_delay=2)
        
        # Extraer respuesta
        transcripcion = response.choices[0].message.content.strip()
        
        # Registrar éxito
        circuit_breaker.record_success("openai")
        
        # Limpiar la respuesta (eliminar comillas si las hay)
        if transcripcion.startswith('"') and transcripcion.endswith('"'):
            transcripcion = transcripcion[1:-1]
            
        return transcripcion
        
    except Exception as e:
        logger.error(f"Error en transcribir_imagen_texto: {str(e)}")
        logger.error(traceback.format_exc())
        circuit_breaker.record_failure("openai", error_type="vision_error")
        
        return f"Error en la transcripción: {str(e)}"

def generar_audio_elevenlabs(texto: str) -> Optional[bytes]:
    """
    Genera un archivo de audio a partir del texto usando ElevenLabs.
    
    Args:
        texto: Texto a convertir en audio
        
    Returns:
        bytes: Audio generado o None si ocurre un error
    """
    try:
        # Obtener claves de API
        elevenlabs_api_key = None
        elevenlabs_voice_id = None
        
        try:
            elevenlabs_api_key = st.secrets["ELEVENLABS_API_KEY"]
            elevenlabs_voice_id = st.secrets["ELEVENLABS_VOICE_ID"]
        except:
            return None
            
        if not elevenlabs_api_key or not elevenlabs_voice_id:
            return None
            
        if not circuit_breaker.can_execute("elevenlabs"):
            logger.warning("ElevenLabs temporalmente no disponible")
            return None

        if not texto:
            return None

        # Limpiar el texto
        audio_text = texto.replace("Consejo final:", "").strip()
        if not audio_text:
            return None

        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}"
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        data = {
            "text": audio_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.3,
                "similarity_boost": 0.9
            }
        }

        # Función para envío de solicitud con timeout
        def send_request():
            response = requests.post(
                tts_url, headers=headers, json=data, timeout=20)
            response.raise_for_status()
            return response

        # Usar sistema de reintentos
        response_audio = retry_with_backoff(send_request, max_retries=2)

        if response_audio.ok:
            circuit_breaker.record_success("elevenlabs")
            st.session_state.servicios_disponibles = {
                **st.session_state.get("servicios_disponibles", {}),
                "elevenlabs": True
            }
            return response_audio.content
        else:
            logger.error(f"Error en ElevenLabs API: {response_audio.status_code}")
            circuit_breaker.record_failure("elevenlabs", error_type="api_error")
            return None

    except requests.exceptions.Timeout:
        logger.error("Timeout en solicitud a ElevenLabs")
        circuit_breaker.record_failure("elevenlabs", error_type="timeout")
        return None
    except Exception as e:
        logger.error(f"Error al generar audio: {str(e)}")
        circuit_breaker.record_failure("elevenlabs", error_type="general")
        return None
    