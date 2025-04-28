#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista para la corrección de textos
---------------------------------
Este módulo contiene la vista para la corrección de textos,
separando claramente la interfaz de usuario de la lógica de negocio.
"""

import logging
import streamlit as st
import json
import re
from datetime import datetime

# Importaciones para la corrección de textos
from features.correccion_manager import corregir_texto, mostrar_resultado_correccion
from config.settings import NIVELES_ESPANOL

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista de corrección de textos.
    Esta función se encarga de mostrar la interfaz de usuario y manejar
    la interacción con el usuario.
    """
    st.markdown("## ✏️ Corrección de Textos")
    st.markdown("""
    Escribe o pega tu texto en español para recibir una corrección detallada. 
    Se analizarán errores gramaticales, léxicos, de puntuación y estructura textual.
    """)
    
    # Inicializar estado si no existe
    if "correction_result" not in st.session_state:
        st.session_state.correction_result = None
    if "texto_original" not in st.session_state:
        st.session_state.texto_original = ""
    if "mostrar_resultado" not in st.session_state:
        st.session_state.mostrar_resultado = False
    
    # Formulario para configurar la corrección
    with st.form(key="correction_form"):
        # Área de texto para el texto a corregir
        texto_usuario = st.text_area(
            "Escribe o pega tu texto en español",
            height=200,
            value=st.session_state.texto_original,
            help="El texto se analizará según el nivel de español seleccionado",
            placeholder="Escribe o pega aquí tu texto en español..."
        )
        
        # Opciones de configuración
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Selector de nivel
            nivel_seleccionado = st.selectbox(
                "Nivel de español",
                list(NIVELES_ESPANOL.keys()),
                format_func=lambda x: f"{x} - {NIVELES_ESPANOL[x]}",
                help="Selecciona tu nivel actual de español"
            )
        
        with col2:
            # Selector de detalle
            nivel_detalle = st.select_slider(
                "Nivel de detalle",
                options=["Básico", "Intermedio", "Detallado"],
                value="Intermedio",
                help="Selecciona cuánto detalle quieres en las explicaciones"
            )
        
        with col3:
            # Selector de idioma
            idioma_explicaciones = st.selectbox(
                "Idioma explicaciones",
                ["español", "inglés", "francés", "portugués", "alemán", "italiano"],
                index=0,
                help="Idioma en que se mostrarán las explicaciones de errores"
            )
        
        # Botón para enviar
        enviar = st.form_submit_button("Analizar texto")
        
        # Procesar cuando se envía el formulario
        if enviar and texto_usuario:
            with st.spinner("Analizando tu texto..."):
                # Guardar texto original
                st.session_state.texto_original = texto_usuario
                
                # Obtener información del usuario para el ID
                from core.session_manager import get_user_info
                user_info = get_user_info()
                user_id = user_info.get("uid") if user_info else None
                
                try:
                    # Procesar con la función de corrección
                    resultado = corregir_texto(
                        texto_input=texto_usuario,
                        nivel=nivel_seleccionado,
                        detalle=nivel_detalle,
                        user_id=user_id,
                        idioma=idioma_explicaciones
                    )
                    
                    if resultado:
                        # Guardar resultado
                        st.session_state.correction_result = resultado
                        st.session_state.mostrar_resultado = True
                    else:
                        st.error("No se pudo obtener una corrección válida. Por favor, inténtalo de nuevo.")
                except Exception as e:
                    logger.error(f"Error durante el proceso de corrección: {str(e)}")
                    st.error(f"Error durante el proceso de corrección: {str(e)}")
    
    # Mostrar resultados si están disponibles
    if st.session_state.mostrar_resultado and st.session_state.correction_result:
        st.markdown("---")
        st.markdown("## Resultado del análisis")
        
        # Mostrar resultado de la corrección
        mostrar_resultado_correccion(st.session_state.correction_result)
