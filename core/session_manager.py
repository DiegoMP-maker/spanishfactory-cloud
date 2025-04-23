#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gestión del estado de sesión de Streamlit
-----------------------------------------
Este módulo proporciona funciones para inicializar, gestionar y acceder de forma segura
al estado de sesión de Streamlit en la aplicación.
"""

import logging
import streamlit as st
from typing import Any, Optional

logger = logging.getLogger(__name__)

def init_session_state():
    """
    Inicializa el estado de sesión con valores por defecto si es necesario.
    
    Returns:
        None
    """
    try:
        # Inicializar variables de estado si no existen
        if 'user_info' not in st.session_state:
            st.session_state.user_info = None
        
        if 'current_page' not in st.session_state:
            st.session_state.current_page = "correccion"
        
        if 'tokens_usados' not in st.session_state:
            st.session_state.tokens_usados = 0
        
        if 'openai_status' not in st.session_state:
            st.session_state.openai_status = True
        
        if 'firebase_status' not in st.session_state:
            st.session_state.firebase_status = True
            
        # Otras variables de estado que puedan ser necesarias
    except Exception as e:
        logger.error(f"Error inicializando estado de sesión: {str(e)}")

def get_session_var(key: str, default: Any = None) -> Any:
    """
    Obtiene una variable del estado de sesión de forma segura.
    
    Args:
        key: Clave de la variable en el estado de sesión
        default: Valor por defecto si la clave no existe
        
    Returns:
        Any: Valor de la variable o valor por defecto
    """
    try:
        if key in st.session_state:
            return st.session_state[key]
        return default
    except Exception as e:
        logger.error(f"Error obteniendo variable de sesión '{key}': {str(e)}")
        return default

def set_session_var(key: str, value: Any) -> None:
    """
    Establece una variable en el estado de sesión de forma segura.
    
    Args:
        key: Clave de la variable en el estado de sesión
        value: Valor a establecer
        
    Returns:
        None
    """
    try:
        st.session_state[key] = value
    except Exception as e:
        logger.error(f"Error estableciendo variable de sesión '{key}': {str(e)}")

def get_user_info() -> Optional[dict]:
    """
    Obtiene la información del usuario actual.
    
    Returns:
        dict: Información del usuario o None si no hay sesión
    """
    try:
        return get_session_var('user_info')
    except Exception as e:
        logger.error(f"Error obteniendo información de usuario: {str(e)}")
        return None

def update_tokens_count(tokens: int) -> None:
    """
    Actualiza el contador de tokens utilizados.
    
    Args:
        tokens: Número de tokens a añadir al contador
        
    Returns:
        None
    """
    try:
        current_count = get_session_var('tokens_usados', 0)
        set_session_var('tokens_usados', current_count + tokens)
    except Exception as e:
        logger.error(f"Error actualizando contador de tokens: {str(e)}")

def clear_session() -> None:
    """
    Limpia todas las variables de estado de la sesión.
    
    Returns:
        None
    """
    try:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        init_session_state()
    except Exception as e:
        logger.error(f"Error limpiando estado de sesión: {str(e)}")
        