#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilidades para OpenAI
----------------------
Funciones auxiliares para trabajar con la API de OpenAI.
Compatible con la versión moderna de openai >=1.0.0.
"""

import logging
import os
import streamlit as st
import openai  # Import correcto para la nueva versión

logger = logging.getLogger(__name__)

def get_openai_api_key():
    """
    Obtiene la API key de OpenAI desde secrets o variable de entorno.
    
    Returns:
        str: API key de OpenAI o None si no está configurada.
    """
    api_key = None
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception as e:
        logger.debug(f"No se pudo obtener OPENAI_API_KEY de secrets: {str(e)}")
    
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
        
    return api_key

def configure_openai(api_key=None):
    """
    Configura la API key de OpenAI globalmente. No crea ninguna instancia de cliente.
    
    Args:
        api_key: API key de OpenAI o None para usar st.secrets.
        
    Returns:
        bool: True si la API key fue configurada correctamente, False si no hay API key.
    """
    try:
        if not api_key:
            api_key = get_openai_api_key()
            if not api_key:
                logger.warning("No se pudo obtener OPENAI_API_KEY")
                return False

        # Configuración global de la API key
        openai.api_key = api_key
        logger.info("API key de OpenAI configurada correctamente.")
        return True
    except Exception as e:
        logger.error(f"Error configurando API key de OpenAI: {str(e)}")
        return False

# Función deprecated - Mantener para compatibilidad con código existente
def create_openai_client(api_key=None):
    """
    DEPRECATED: No crea un cliente, solo configura la API key globalmente.
    Use configure_openai() en su lugar.
    
    Args:
        api_key: API key de OpenAI o None para usar st.secrets.
        
    Returns:
        bool: True si la API key fue configurada correctamente, False si no hay API key.
    """
    logger.warning("create_openai_client() está obsoleto, use configure_openai() en su lugar")
    return configure_openai(api_key)

def clean_openai_clients_from_session():
    """
    Limpia los posibles objetos de cliente OpenAI de la sesión.
    """
    keys_to_remove = []
    for key in st.session_state:
        if (
            isinstance(key, str) and 
            ('openai' in key.lower() or 'client' in key.lower() or 'assistant' in key.lower())
        ):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
            logger.debug(f"Eliminada clave {key} de la sesión")