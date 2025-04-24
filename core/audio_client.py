#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cliente de audio para ElevenLabs
--------------------------------
Este módulo proporciona funciones para generar audio a partir de texto
utilizando la API de ElevenLabs.
"""

import logging
import requests
import streamlit as st

logger = logging.getLogger(__name__)

def generar_audio_consejo(texto, voice_id=None, api_key=None):
    """
    Genera audio a partir de un texto utilizando ElevenLabs.
    
    Args:
        texto (str): Texto para convertir a audio
        voice_id (str, opcional): ID de la voz a utilizar. Si es None, se usa el de la sesión.
        api_key (str, opcional): Clave de API de ElevenLabs. Si es None, se usa la de la sesión.
        
    Returns:
        bytes: Datos binarios del audio en formato MP3, o None si hay error
    """
    try:
        # Verificar que hay texto para procesar
        if not texto or texto.strip() == "":
            logger.warning("No hay texto para generar audio")
            return None
        
        # Obtener claves de API de la sesión si no se proporcionan
        if not api_key:
            api_key = st.session_state.get("api_keys", {}).get("elevenlabs", {}).get("api_key")
        
        if not voice_id:
            voice_id = st.session_state.get("api_keys", {}).get("elevenlabs", {}).get("voice_id")
        
        # Verificar que tenemos las credenciales necesarias
        if not api_key or not voice_id:
            logger.warning("Faltan credenciales para ElevenLabs (api_key o voice_id)")
            return None
        
        # Verificar el Circuit Breaker
        if "circuit_breaker" in st.session_state:
            circuit_breaker = st.session_state.circuit_breaker
            if not circuit_breaker.can_execute("elevenlabs"):
                logger.warning("Circuit Breaker abierto para ElevenLabs")
                return None
        
        # Preparar URL y headers
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        # Preparar datos
        data = {
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        # Realizar la solicitud a la API
        response = requests.post(url, headers=headers, json=data)
        
        # Verificar respuesta
        if response.status_code == 200:
            # Registrar éxito en el Circuit Breaker si está disponible
            if "circuit_breaker" in st.session_state:
                st.session_state.circuit_breaker.record_success("elevenlabs")
            return response.content
        else:
            logger.error(f"Error en la API de ElevenLabs: {response.status_code}, {response.text}")
            # Registrar fallo en el Circuit Breaker si está disponible
            if "circuit_breaker" in st.session_state:
                st.session_state.circuit_breaker.record_failure("elevenlabs")
            return None
    
    except Exception as e:
        logger.error(f"Error generando audio con ElevenLabs: {str(e)}")
        # Registrar fallo en el Circuit Breaker si está disponible
        if "circuit_breaker" in st.session_state:
            st.session_state.circuit_breaker.record_failure("elevenlabs")
        return None