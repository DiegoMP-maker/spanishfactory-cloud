#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Componentes principales de la UI
--------------------------------
Este módulo contiene funciones para configurar el layout principal de la aplicación.
"""

import logging
import streamlit as st
from PIL import Image
import os

from config.settings import APP_VERSION, APP_NAME
from core.session_manager import init_session_state, get_user_info
from utils.file_utils import get_app_file_path

logger = logging.getLogger(__name__)

def setup_page_config():
    """
    Configura los parámetros generales de la página de Streamlit.
    
    Returns:
        None
    """
    try:
        # Configurar página
        st.set_page_config(
            page_title=APP_NAME,
            page_icon="📝",
            layout="wide",
            initial_sidebar_state="expanded",
            menu_items={
                'About': f"{APP_NAME} v{APP_VERSION} - Una herramienta para la corrección y mejora de textos en español."
            }
        )
        
        # Agregar estilos personalizados
        aplicar_estilos_css()
    except Exception as e:
        logger.error(f"Error configurando página: {str(e)}")

def aplicar_estilos_css():
    """
    Aplica estilos CSS personalizados a la aplicación.
    
    Returns:
        None
    """
    try:
        # Definir estilos CSS personalizados
        st.markdown("""
        <style>
        /* Estilos generales */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* Estilos para tarjetas */
        .stCard {
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        /* Estilos para texto corregido */
        .texto-corregido {
            border-left: 4px solid #1f77b4;
            padding-left: 1rem;
            background-color: #f0f2f6;
            border-radius: 0.3rem;
        }
        
        /* Estilos para los tipos de errores */
        .error-ortografia {
            background-color: #ffccd5;
            padding: 0 2px;
            border-radius: 3px;
            border-bottom: 2px dashed #ff6b6b;
            cursor: help;
        }
        
        .error-gramatica {
            background-color: #ffe8cc;
            padding: 0 2px;
            border-radius: 3px;
            border-bottom: 2px dashed #ff9f1c;
            cursor: help;
        }
        
        .error-vocabulario {
            background-color: #e2f0cb;
            padding: 0 2px;
            border-radius: 3px;
            border-bottom: 2px dashed #70e000;
            cursor: help;
        }
        
        .error-cohesion {
            background-color: #cce5ff;
            padding: 0 2px;
            border-radius: 3px;
            border-bottom: 2px dashed #0077b6;
            cursor: help;
        }
        
        .error-coherencia {
            background-color: #d0d1ff;
            padding: 0 2px;
            border-radius: 3px;
            border-bottom: 2px dashed #6a0dad;
            cursor: help;
        }
        
        .error-puntuacion {
            background-color: #fff2cc;
            padding: 0 2px;
            border-radius: 3px;
            border-bottom: 2px dashed #ffcb47;
            cursor: help;
        }
        
        .error-otro {
            background-color: #f0f0f0;
            padding: 0 2px;
            border-radius: 3px;
            border-bottom: 2px dashed #6c757d;
            cursor: help;
        }
        
        /* Estilos para leyenda de errores */
        .leyenda-errores {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 10px 0;
            font-size: 0.8rem;
        }
        
        .leyenda-item {
            display: flex;
            align-items: center;
            margin-right: 10px;
        }
        
        .leyenda-color {
            display: inline-block;
            width: 12px;
            height: 12px;
            margin-right: 5px;
            border-radius: 2px;
        }
        
        /* Estilos para los botones */
        .stButton button {
            border-radius: 0.3rem;
        }
        
        /* Estilos para las pestañas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #f0f2f6;
            border-radius: 5px 5px 0 0;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: #1f77b4;
            color: white;
        }
        
        /* Estilos para el simulacro de examen */
        .timer-box {
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            margin-bottom: 15px;
        }
        
        .timer {
            font-size: 1.8rem;
            font-weight: bold;
        }
        
        /* Estilos para el perfil */
        .perfil-card {
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        /* Estilos para tooltips */
        .tooltip {
            position: relative;
            display: inline-block;
            border-bottom: 1px dotted #ccc;
        }
        
        .tooltip .tooltiptext {
            visibility: hidden;
            width: 200px;
            background-color: #555;
            color: #fff;
            text-align: center;
            border-radius: 6px;
            padding: 5px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -100px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        
        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
        
        /* Estilo para loadings */
        .loading-spinner {
            display: flex;
            justify-content: center;
            margin: 20px 0;
        }
        
        /* Anular estilo de fondo para los inputs de texto */
        div[data-baseweb="base-input"] {
            background-color: white !important;
        }
        </style>
        """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error aplicando estilos CSS: {str(e)}")

def mostrar_encabezado():
    """
    Muestra el encabezado de la aplicación con logo y título.
    
    Returns:
        None
    """
    try:
        # Crear dos columnas para el logo y el título
        col1, col2 = st.columns([1, 5])
        
        with col1:
            # Cargar y mostrar el logo
            logo_path = get_app_file_path("assets/Spanish_FactorIA_Logo.png")
            
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                st.image(logo, width=130)
            else:
                st.warning("Logo no encontrado. Verifique la ruta de los assets.")
        
        with col2:
            # Mostrar título y subtítulo
            st.title(APP_NAME)
            st.markdown(f"<h4 style='margin-top: -15px; color: #666;'>Versión {APP_VERSION}</h4>", 
                        unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error mostrando encabezado: {str(e)}")
        # Mostrar título simple en caso de error
        st.title(APP_NAME)

def mostrar_pie_pagina():
    """
    Muestra el pie de página de la aplicación.
    
    Returns:
        None
    """
    try:
        st.markdown("""
        <div style="text-align: center; margin-top: 30px; padding: 10px; border-top: 1px solid #eee;">
            <p style="color: #666; font-size: 0.8rem;">
                © 2023 - Textocorrector ELE v{} - Desarrollado con ❤️ para estudiantes y profesores de español
            </p>
        </div>
        """.format(APP_VERSION), unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error mostrando pie de página: {str(e)}")

def mostrar_bienvenida():
    """
    Muestra un mensaje de bienvenida personalizado al usuario.
    
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        
        if user_info and 'nombre' in user_info:
            nombre = user_info['nombre']
            nivel = user_info.get('nivel', 'estudiante')
            
            st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <h3>¡Bienvenido/a, {nombre}!</h3>
                <p>
                    Estás utilizando Textocorrector ELE, tu asistente para mejorar tu español como lengua extranjera.
                    Actualmente estás en el nivel <b>{nivel}</b>.
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                <h3>¡Bienvenido/a a Textocorrector ELE!</h3>
                <p>
                    Esta aplicación te ayudará a mejorar tu español como lengua extranjera.
                    Utiliza las diferentes herramientas para practicar y recibir retroalimentación personalizada.
                </p>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error mostrando bienvenida: {str(e)}")

def crear_layout_principal():
    """
    Crea y configura el layout principal de la aplicación.
    
    Returns:
        None
    """
    try:
        # Inicializar estado de sesión
        init_session_state()
        
        # Configurar página
        setup_page_config()
        
        # Mostrar encabezado
        mostrar_encabezado()
    except Exception as e:
        logger.error(f"Error creando layout principal: {str(e)}")
        st.error(f"Error al cargar la interfaz: {str(e)}")

def mostrar_mensaje_error(mensaje, tipo="error"):
    """
    Muestra un mensaje de error o advertencia con formato mejorado.
    
    Args:
        mensaje (str): Mensaje a mostrar
        tipo (str): Tipo de mensaje (error, warning, info)
        
    Returns:
        None
    """
    try:
        if tipo == "error":
            st.markdown(f"""
            <div style="background-color: #ffebee; color: #c62828; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <strong>Error:</strong> {mensaje}
            </div>
            """, unsafe_allow_html=True)
        elif tipo == "warning":
            st.markdown(f"""
            <div style="background-color: #fff8e1; color: #ff8f00; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <strong>Advertencia:</strong> {mensaje}
            </div>
            """, unsafe_allow_html=True)
        elif tipo == "info":
            st.markdown(f"""
            <div style="background-color: #e3f2fd; color: #0277bd; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <strong>Información:</strong> {mensaje}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0;">
                {mensaje}
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error mostrando mensaje de error: {str(e)}")
        # Mostrar mensaje de error estándar si falla
        if tipo == "error":
            st.error(mensaje)
        elif tipo == "warning":
            st.warning(mensaje)
        elif tipo == "info":
            st.info(mensaje)
        else:
            st.markdown(mensaje)

def mostrar_spinner_personalizado(mensaje="Procesando..."):
    """
    Muestra un spinner personalizado con mensaje.
    
    Args:
        mensaje (str): Mensaje a mostrar junto al spinner
        
    Returns:
        st.spinner: Objeto spinner de Streamlit
    """
    return st.spinner(mensaje)

def mostrar_leyenda_errores():
    """
    Muestra una leyenda explicando los colores de los diferentes tipos de errores.
    
    Returns:
        None
    """
    try:
        st.markdown("""
        <div class="leyenda-errores">
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #ffccd5;"></span>
                <span>Ortografía</span>
            </div>
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #ffe8cc;"></span>
                <span>Gramática</span>
            </div>
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #e2f0cb;"></span>
                <span>Vocabulario</span>
            </div>
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #cce5ff;"></span>
                <span>Cohesión</span>
            </div>
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #d0d1ff;"></span>
                <span>Coherencia</span>
            </div>
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #fff2cc;"></span>
                <span>Puntuación</span>
            </div>
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #f9d9ff;"></span>
                <span>Registro lingüístico</span>
            </div>
            <div class="leyenda-item">
                <span class="leyenda-color" style="background-color: #f0f0f0;"></span>
                <span>Otro</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error mostrando leyenda de errores: {str(e)}")
