#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuración del sidebar
------------------------
Este módulo contiene funciones para configurar y gestionar el sidebar de la aplicación.
"""

import logging
import streamlit as st
from PIL import Image
import os

from config.settings import APP_VERSION, APP_NAME
from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.login import mostrar_info_usuario, mostrar_logout
from utils.file_utils import get_app_file_path

logger = logging.getLogger(__name__)

def configurar_sidebar():
    """
    Configura y muestra el sidebar con navegación y opciones.
    
    Returns:
        str: Nombre de la página seleccionada
    """
    try:
        with st.sidebar:
            # Logo en el sidebar
            logo_path = get_app_file_path("assets/Spanish_FactorIA_Logo.png")
            
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                st.image(logo, width=100)
            
            st.markdown(f"### {APP_NAME}")
            st.markdown(f"Versión {APP_VERSION}")
            
            # Separador
            st.markdown("---")
            
            # Mostrar información del usuario
            mostrar_info_usuario()
            
            # Navegación
            st.markdown("### Menú")
            
            # Obtener página actual
            current_page = get_session_var("current_page", "correccion")
            
            # Botones de navegación
            if st.sidebar.button("🖊️ Corrección de textos", 
                                type="primary" if current_page == "correccion" else "secondary"):
                set_session_var("current_page", "correccion")
                return "correccion"
            
            if st.sidebar.button("📝 Ejercicios personalizados",
                                type="primary" if current_page == "ejercicios" else "secondary"):
                set_session_var("current_page", "ejercicios")
                return "ejercicios"
            
            if st.sidebar.button("🏆 Simulacro de examen",
                                type="primary" if current_page == "simulacro" else "secondary"):
                set_session_var("current_page", "simulacro")
                return "simulacro"
            
            if st.sidebar.button("🛠️ Herramientas ELE",
                                type="primary" if current_page == "herramientas" else "secondary"):
                set_session_var("current_page", "herramientas")
                return "herramientas"
            
            if st.sidebar.button("👤 Mi perfil y progreso",
                                type="primary" if current_page == "perfil" else "secondary"):
                set_session_var("current_page", "perfil")
                return "perfil"
            
            if st.sidebar.button("📚 Plan de estudio",
                                type="primary" if current_page == "plan" else "secondary"):
                set_session_var("current_page", "plan")
                return "plan"
            
            # Separador
            st.markdown("---")
            
            # Botón Acerca de
            if st.sidebar.button("ℹ️ Acerca de",
                                type="primary" if current_page == "about" else "secondary"):
                set_session_var("current_page", "about")
                return "about"
            
            # Botón cerrar sesión
            st.markdown("---")
            mostrar_logout()
            
            # Mostrar información de contacto
            st.markdown("### Contacto")
            st.markdown("¿Dudas o sugerencias?")
            st.markdown("📧 ayuda@textocorrector.ele")
            
            # Devolver página actual
            return current_page
    except Exception as e:
        logger.error(f"Error configurando sidebar: {str(e)}")
        return "correccion"  # Página por defecto en caso de error

def mostrar_filtros_nivel():
    """
    Muestra filtros para seleccionar el nivel de español en el sidebar.
    
    Returns:
        str: Nivel seleccionado
    """
    try:
        with st.sidebar:
            st.markdown("### Filtros")
            
            # Obtener nivel del usuario
            user_info = get_user_info()
            nivel_usuario = user_info.get('nivel', 'B1') if user_info else 'B1'
            
            # Selector de nivel
            nivel_seleccionado = st.selectbox(
                "Nivel de español",
                ["A1", "A2", "B1", "B2", "C1", "C2"],
                index=["A1", "A2", "B1", "B2", "C1", "C2"].index(nivel_usuario)
            )
            
            return nivel_seleccionado
    except Exception as e:
        logger.error(f"Error mostrando filtros de nivel: {str(e)}")
        return "B1"  # Nivel por defecto en caso de error

def mostrar_filtros_ejercicios():
    """
    Muestra filtros para seleccionar tipo de ejercicios en el sidebar.
    
    Returns:
        dict: Diccionario con los filtros seleccionados
    """
    try:
        with st.sidebar:
            st.markdown("### Filtros de Ejercicios")
            
            # Obtener nivel del usuario
            user_info = get_user_info()
            nivel_usuario = user_info.get('nivel', 'B1') if user_info else 'B1'
            
            # Selector de nivel
            nivel_seleccionado = st.selectbox(
                "Nivel",
                ["A1", "A2", "B1", "B2", "C1", "C2"],
                index=["A1", "A2", "B1", "B2", "C1", "C2"].index(nivel_usuario),
                key="filtro_nivel_ejercicios"
            )
            
            # Selector de tipo de ejercicio
            tipo_ejercicio = st.selectbox(
                "Tipo de ejercicio",
                [
                    "Gramática", 
                    "Vocabulario", 
                    "Comprensión lectora", 
                    "Comprensión auditiva", 
                    "Expresión escrita",
                    "Mixto"
                ],
                key="filtro_tipo_ejercicio"
            )
            
            # Selector de tema
            tema_ejercicio = st.selectbox(
                "Tema",
                [
                    "General",
                    "Vida cotidiana",
                    "Trabajo y profesiones",
                    "Viajes y turismo",
                    "Cultura y arte",
                    "Tecnología",
                    "Medio ambiente",
                    "Salud y bienestar",
                    "Educación"
                ],
                key="filtro_tema_ejercicio"
            )
            
            # Selector de dificultad
            dificultad = st.select_slider(
                "Dificultad",
                options=["Fácil", "Media", "Difícil"],
                value="Media",
                key="filtro_dificultad_ejercicio"
            )
            
            return {
                "nivel": nivel_seleccionado,
                "tipo": tipo_ejercicio,
                "tema": tema_ejercicio,
                "dificultad": dificultad
            }
    except Exception as e:
        logger.error(f"Error mostrando filtros de ejercicios: {str(e)}")
        return {
            "nivel": "B1",
            "tipo": "Gramática",
            "tema": "General",
            "dificultad": "Media"
        }  # Valores por defecto en caso de error

def mostrar_filtros_herramientas():
    """
    Muestra filtros para seleccionar tipo de herramientas en el sidebar.
    
    Returns:
        str: Herramienta seleccionada
    """
    try:
        with st.sidebar:
            st.markdown("### Herramientas ELE")
            
            # Selector de herramienta
            herramienta_seleccionada = st.radio(
                "Selecciona una herramienta",
                [
                    "🔤 Transcripción de textos",
                    "📋 Generador de consignas",
                    "🖼️ Generador de imágenes"
                ],
                key="filtro_herramienta"
            )
            
            # Extraer nombre de la herramienta sin el emoji
            herramienta = herramienta_seleccionada.split(" ", 1)[1]
            
            return herramienta
    except Exception as e:
        logger.error(f"Error mostrando filtros de herramientas: {str(e)}")
        return "Transcripción de textos"  # Valor por defecto en caso de error

def mostrar_contador_tokens():
    """
    Muestra un contador de tokens usados en el sidebar.
    
    Returns:
        None
    """
    try:
        with st.sidebar:
            st.markdown("---")
            
            # Obtener recuento de tokens de la sesión
            tokens_usados = get_session_var("tokens_usados", 0)
            
            # Mostrar contador
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-top: 20px;">
                <p style="font-size: 0.9rem; margin-bottom: 5px;"><strong>Tokens utilizados:</strong></p>
                <p style="font-size: 1.2rem; margin: 0;">{tokens_usados:,}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Añadir explicación en un expander
            with st.expander("¿Qué son los tokens?"):
                st.markdown("""
                Los tokens son unidades de texto que el modelo procesa.
                Aproximadamente, un token equivale a 4 caracteres o 0.75 palabras en español.
                
                El uso de tokens determina el costo del servicio y hay límites diarios
                según tu plan. Usamos un circuito de protección para evitar
                que excedas tu límite.
                """)
    except Exception as e:
        logger.error(f"Error mostrando contador de tokens: {str(e)}")

def mostrar_estado_servicios():
    """
    Muestra el estado de los servicios externos en el sidebar.
    
    Returns:
        None
    """
    try:
        with st.sidebar:
            # Obtener estado de los servicios de la sesión
            openai_status = get_session_var("openai_status", True)
            firebase_status = get_session_var("firebase_status", True)
            
            # Indicadores de estado
            st.markdown("### Estado de servicios")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if openai_status:
                    st.markdown("🟢 **OpenAI**")
                else:
                    st.markdown("🔴 **OpenAI**")
            
            with col2:
                if firebase_status:
                    st.markdown("🟢 **Firebase**")
                else:
                    st.markdown("🔴 **Firebase**")
            
            # Explicación en un expander
            with st.expander("Detalles"):
                st.markdown("""
                Estos indicadores muestran el estado de los servicios externos utilizados por la aplicación.
                
                - 🟢 **Operativo**: El servicio está funcionando correctamente.
                - 🔴 **No disponible**: El servicio presenta problemas. Algunas funciones pueden no estar disponibles.
                
                Si algún servicio está caído, inténtalo de nuevo más tarde o contacta al soporte.
                """)
    except Exception as e:
        logger.error(f"Error mostrando estado de servicios: {str(e)}")
