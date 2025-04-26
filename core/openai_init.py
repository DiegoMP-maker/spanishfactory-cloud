#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Inicialización segura para OpenAI
--------------------------------
Este módulo se debe importar al inicio de la aplicación para garantizar
una correcta configuración global de OpenAI sin parámetros incompatibles.
"""

import logging
import os
import streamlit as st
import openai

logger = logging.getLogger(__name__)

def init_openai():
    """
    Configura OpenAI de forma segura, evitando parámetros incompatibles.
    Esta función debe llamarse al inicio de la aplicación.
    """
    logger.info("Configurando OpenAI globalmente...")
    
    # Obtener API key
    api_key = None
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception as e:
        logger.debug(f"No se pudo obtener OPENAI_API_KEY de secrets: {str(e)}")
    
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        logger.error("No se encontró API key para OpenAI, la aplicación no funcionará correctamente")
        return False
    
    # Configurar API key globalmente
    openai.api_key = api_key
    
    logger.info("OpenAI configurado correctamente")
    return True