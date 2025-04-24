#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilidades centralizadas para creación de clientes OpenAI
---------------------------------------------------------
Este módulo proporciona funciones para crear clientes OpenAI de manera consistente
en toda la aplicación, evitando problemas con parámetros incompatibles.
"""

import logging
import streamlit as st

logger = logging.getLogger(__name__)

def create_openai_client(api_key=None, **kwargs):
    """
    Crea un cliente OpenAI de manera consistente en toda la aplicación.
    
    Args:
        api_key: API key para OpenAI (opcional)
        **kwargs: Argumentos adicionales (serán ignorados para evitar problemas)
        
    Returns:
        OpenAI client o None en caso de error
    """
    try:
        # Importación dentro de la función para evitar problemas de importación circular
        from openai import OpenAI
        
        # Log detallado para diagnóstico
        logger.debug(f"Creando cliente OpenAI con api_key{'=' + api_key[:5] + '...' if api_key else ' from environment'}")
        
        # Crear cliente SOLO con api_key, ignorando otros parámetros
        client = OpenAI(api_key=api_key)
        
        logger.info("Cliente OpenAI creado correctamente")
        return client
    except Exception as e:
        logger.error(f"Error creando cliente OpenAI: {str(e)}")
        return None

def get_openai_api_key():
    """
    Obtiene la API key de OpenAI de manera segura desde los secrets de Streamlit.
    
    Returns:
        str o None: API key si está disponible, None en caso contrario
    """
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception as e:
        logger.warning(f"Error al obtener API Key de OpenAI: {e}")
        return None

def clean_openai_clients_from_session():
    """
    Limpia cualquier cliente OpenAI almacenado en session_state.
    Útil para forzar la recreación de clientes después de errores.
    """
    try:
        # Limpiar cliente de asistentes
        if "assistant_client" in st.session_state:
            logger.info("Limpiando assistant_client de session_state")
            del st.session_state["assistant_client"]
        
        # Limpiar cualquier otra referencia a clientes OpenAI
        for key in list(st.session_state.keys()):
            if "client" in key.lower() and "openai" in key.lower():
                logger.info(f"Limpiando {key} de session_state")
                del st.session_state[key]
                
    except Exception as e:
        logger.error(f"Error limpiando clientes OpenAI de session_state: {e}")
