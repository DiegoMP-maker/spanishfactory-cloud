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
import uuid
from datetime import datetime

# Importaciones para la corrección de textos
from features.correccion import corregir_texto, mostrar_resultado_correccion
from features.exportacion import mostrar_opciones_exportacion
from features.correccion_utils import display_correccion_result
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
    if "tab_index" not in st.session_state:
        st.session_state.tab_index = 0
    if "exportacion_mostrada" not in st.session_state:
        st.session_state.exportacion_mostrada = False
    
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
        col1, col2 = st.columns(2)
        
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
        
        # Botón para enviar
        enviar = st.form_submit_button("Analizar texto")
        
        # Procesar cuando se envía el formulario
        if enviar and texto_usuario:
            with st.spinner("Analizando tu texto..."):
                # Guardar texto original
                st.session_state.texto_original = texto_usuario
                
                # Resetear estados de visualización
                st.session_state.tab_index = 0
                st.session_state.exportacion_mostrada = False
                
                # Obtener información del usuario para el ID
                from core.session_manager import get_user_info
                user_info = get_user_info()
                user_id = user_info.get("uid") if user_info else None
                
                # Procesar con la función de corrección
                resultado = corregir_texto(
                    texto_input=texto_usuario,  # Corregido: 'texto' -> 'texto_input'
                    nivel=nivel_seleccionado,
                    detalle=nivel_detalle,
                    user_id=user_id
                )
                
                if resultado:
                    # Guardar resultado
                    st.session_state.correction_result = resultado
                    st.session_state.mostrar_resultado = True
                else:
                    st.error("No se pudo obtener una corrección válida. Por favor, inténtalo de nuevo.")
    
    # Mostrar resultados si están disponibles
    if st.session_state.mostrar_resultado and st.session_state.correction_result:
        st.markdown("---")
        st.markdown("## Resultado del análisis")
        
        # Definir pestañas para la navegación
        tab_names = ["Corrección", "Análisis contextual", "Consejo final", "Exportar informe"]
        
        # Función para manejar el cambio de pestaña
        def on_tab_change():
            st.session_state.tab_index = tab_names.index(st.session_state.selected_tab)
            # Resetear exportación mostrada cuando se cambia de pestaña
            if st.session_state.selected_tab == "Exportar informe":
                st.session_state.exportacion_mostrada = False
        
        # Mostrar pestañas con la seleccionada por session_state
        selected_tab = st.radio(
            "Secciones",
            tab_names,
            index=st.session_state.tab_index,
            key="selected_tab",
            on_change=on_tab_change,
            horizontal=True
        )
        
        # Crear un ID único para esta sesión
        session_id = str(uuid.uuid4())[:8]
        
        # Mostrar el contenido de la pestaña seleccionada
        if selected_tab == "Corrección":
            # Mostrar la corrección utilizando la función existente
            display_correccion_result(st.session_state.correction_result)
        
        elif selected_tab == "Análisis contextual":
            # Mostrar el análisis contextual
            analisis = st.session_state.correction_result.get("analisis_contextual", {})
            if analisis:
                for categoria, info in analisis.items():
                    with st.expander(f"{categoria.replace('_', ' ').title()} ({info.get('puntuacion', 0)}/10)", expanded=True):
                        st.write(info.get("comentario", ""))
                        
                        # Mostrar sugerencias si existen
                        if "sugerencias" in info and info["sugerencias"]:
                            st.subheader("Sugerencias:")
                            for sugerencia in info["sugerencias"]:
                                st.markdown(f"• {sugerencia}")
            else:
                st.info("No hay análisis contextual disponible para este texto.")
        
        elif selected_tab == "Consejo final":
            # Mostrar el consejo final
            consejo = st.session_state.correction_result.get("consejo_final", "")
            st.success(consejo)
            
            # Mostrar puntuación general si existe
            if "puntuacion" in st.session_state.correction_result:
                puntuacion = st.session_state.correction_result.get("puntuacion", 0)
                st.metric("Puntuación global", f"{puntuacion}/10")
        
        elif selected_tab == "Exportar informe":
            # Solo mostrar opciones de exportación una vez por pestaña
            if not st.session_state.exportacion_mostrada:
                # Generar un ID único para cada sesión de exportación
                export_id = f"{session_id}_{int(datetime.now().timestamp())}"
                
                # Mostrar opciones de exportación
                mostrar_opciones_exportacion(st.session_state.correction_result, export_id)
                
                # Marcar como mostrado
                st.session_state.exportacion_mostrada = True
