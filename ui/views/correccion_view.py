#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista para la corrección de textos
---------------------------------
Este módulo contiene la vista principal para la corrección de textos en español.
"""

import logging
import streamlit as st
import json
import re
from datetime import datetime

# Importaciones para la corrección de textos
from features.correccion import corregir_texto, mostrar_resultado_correccion
from features.exportacion import mostrar_opciones_exportacion
from config.settings import NIVELES_ESPANOL

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista de corrección de textos.
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
        col1, col2, col3 = st.columns([1, 1, 1])
        
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
                "Nivel de detalle en las correcciones",
                options=["Básico", "Intermedio", "Detallado"],
                value="Intermedio",
                help="Selecciona cuánto detalle quieres en las explicaciones"
            )
            
        with col3:
            # Selector de idioma para las explicaciones
            idioma_explicaciones = st.selectbox(
                "Idioma de las explicaciones",
                ["español", "inglés", "francés", "alemán", "italiano", "portugués"],
                index=0,
                help="Selecciona el idioma en el que quieres recibir las explicaciones"
            )
        
        # Botón para enviar
        enviar = st.form_submit_button("Analizar texto")
        
        # Procesar cuando se envía el formulario
        if enviar:
            # Validar que el texto no esté vacío
            if not texto_usuario or not texto_usuario.strip():
                st.error("Por favor, introduce un texto para analizar.")
                return
                
            with st.spinner("Analizando tu texto..."):
                # Guardar texto original
                st.session_state.texto_original = texto_usuario
                
                # Obtener información del usuario para el ID
                from core.session_manager import get_user_info
                user_info = get_user_info()
                user_id = user_info.get("uid") if user_info else None
                
                # Mostrar mensaje de espera
                st.info("Analizando el texto. Por favor, espera unos momentos...")
                
                # Procesar con la función de corrección
                try:
                    # Pasar el texto como texto_input (nombre correcto del parámetro)
                    resultado = corregir_texto(
                        texto_input=texto_usuario,
                        nivel=nivel_seleccionado,
                        detalle=nivel_detalle,
                        user_id=user_id,
                        idioma=idioma_explicaciones
                    )
                    
                    # Verificar el resultado
                    if resultado is None:
                        st.error("No se pudo obtener una corrección. El servidor puede estar ocupado. Por favor, inténtalo de nuevo en unos momentos.")
                        logger.error("corregir_texto() devolvió None")
                        return
                        
                    # Guardar resultado (incluso si tiene error, para mostrar el mensaje apropiado)
                    st.session_state.correction_result = resultado
                    st.session_state.mostrar_resultado = True
                    
                except Exception as e:
                    st.error(f"Ocurrió un error durante el procesamiento: {str(e)}")
                    logger.error(f"Error procesando corrección: {str(e)}")
                    # Asegurar que el usuario no pierda su texto
                    st.session_state.texto_original = texto_usuario
    
    # Mostrar resultados si están disponibles
    if st.session_state.mostrar_resultado and st.session_state.correction_result:
        st.markdown("---")
        st.markdown("## Resultado del análisis")
        
        try:
            # Mostrar resultado de la corrección
            mostrar_resultado_correccion(st.session_state.correction_result)
        except Exception as e:
            st.error(f"Error mostrando el resultado: {str(e)}")
            logger.error(f"Error en mostrar_resultado_correccion: {str(e)}")
            
            # Fallback básico para mostrar algo al usuario
            if isinstance(st.session_state.correction_result, dict):
                if "texto_original" in st.session_state.correction_result:
                    with st.expander("Tu texto original"):
                        st.write(st.session_state.correction_result.get("texto_original", ""))
                
                if "texto_corregido" in st.session_state.correction_result:
                    st.subheader("Texto corregido")
                    st.write(st.session_state.correction_result.get("texto_corregido", ""))
