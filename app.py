#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Textocorrector ELE - Punto de entrada principal
------------------------------------------------
Este archivo es el punto de entrada principal de la aplicación Textocorrector ELE.
Configura la interfaz de usuario y gestiona la navegación entre las diferentes vistas.
"""

import logging
import streamlit as st
import os
import sys
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Limpiar clientes OpenAI de session_state al iniciar
from core.openai_utils import clean_openai_clients_from_session

# Verifica si ya se ha limpiado en esta sesión
if 'clients_cleaned' not in st.session_state:
    clean_openai_clients_from_session()
    st.session_state.clients_cleaned = True

# Importar componentes principales
from ui.main_layout import crear_layout_principal, mostrar_pie_pagina
from ui.sidebar import configurar_sidebar
from ui.login import mostrar_login

# Importar vistas
from ui.views.correccion_view import render_view as render_correccion

# Configurar Circuit Breaker para controlar llamadas a APIs externas
def configurar_circuit_breaker():
    """
    Configura el Circuit Breaker para controlar llamadas a APIs externas.
    
    Returns:
        None
    """
    try:
        # Importar CircuitBreaker
        from core.circuit_breaker import CircuitBreaker
        
        # Inicializar si no existe
        if 'circuit_breaker' not in st.session_state:
            st.session_state.circuit_breaker = CircuitBreaker(
                name="app_circuit_breaker"  # El parámetro correcto es 'name', no 'max_failures'
            )
            logger.info("Circuit Breaker inicializado")
    except Exception as e:
        logger.error(f"Error configurando Circuit Breaker: {str(e)}")

# Configurar API keys para servicios externos
def configurar_api_keys():
    """
    Configura las claves de API para servicios externos.
    
    Returns:
        None
    """
    try:
        # Inicializar api_keys si no existe
        if 'api_keys' not in st.session_state:
            st.session_state.api_keys = {
                "elevenlabs": {
                    "api_key": st.secrets.get("ELEVENLABS_API_KEY", ""),
                    "voice_id": st.secrets.get("ELEVENLABS_VOICE_ID", "")
                }
                # Otras APIs se pueden añadir aquí
            }
            logger.info("API keys configuradas")
    except Exception as e:
        logger.error(f"Error configurando API keys: {str(e)}")

# Temporalmente, vamos a definir funciones placeholder para las otras vistas
# hasta que se implementen correctamente
def render_ejercicios():
    st.markdown("## 📝 Ejercicios personalizados")
    st.info("La vista de ejercicios personalizados está en desarrollo. Estará disponible pronto.")

def render_simulacro():
    st.markdown("## 🏆 Simulacro de examen")
    st.info("La vista de simulacro de examen está en desarrollo. Estará disponible pronto.")
    
def render_herramientas():
    st.markdown("## 🛠️ Herramientas ELE")
    st.info("La vista de herramientas está en desarrollo. Estará disponible pronto.")

def render_perfil():
    st.markdown("## 👤 Mi perfil y progreso")
    st.info("La vista de perfil y progreso está en desarrollo. Estará disponible pronto.")

def render_plan():
    st.markdown("## 📚 Plan de estudio")
    st.info("La vista de plan de estudio está en desarrollo. Estará disponible pronto.")

def render_about():
    st.markdown("## ℹ️ Acerca de")
    st.info("La vista de información está en desarrollo. Estará disponible pronto.")

def main():
    """
    Función principal que inicia la aplicación.
    
    Returns:
        None
    """
    try:
        # Crear layout principal
        crear_layout_principal()
        
        # Configurar Circuit Breaker y API keys para nuevas funcionalidades
        configurar_circuit_breaker()
        configurar_api_keys()
        
        # Mostrar pantalla de login si no hay usuario logueado
        usuario_logueado = mostrar_login()
        
        if usuario_logueado:
            # Configurar sidebar y obtener página seleccionada
            pagina_actual = configurar_sidebar()
            
            # Renderizar la vista correspondiente
            if pagina_actual == "correccion":
                render_correccion()
            elif pagina_actual == "ejercicios":
                render_ejercicios()
            elif pagina_actual == "simulacro":
                render_simulacro()
            elif pagina_actual == "herramientas":
                render_herramientas()
            elif pagina_actual == "perfil":
                render_perfil()
            elif pagina_actual == "plan":
                render_plan()
            elif pagina_actual == "about":
                render_about()
            
            # Mostrar pie de página
            mostrar_pie_pagina()
    except Exception as e:
        logger.error(f"Error en la función principal: {str(e)}")
        st.error(f"Ha ocurrido un error inesperado: {str(e)}")
        
        # Botón para reiniciar la aplicación
        if st.button("Reiniciar aplicación"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_rerun()

if __name__ == "__main__":
    main()