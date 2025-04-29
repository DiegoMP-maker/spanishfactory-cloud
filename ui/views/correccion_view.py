#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista para la corrección de textos
---------------------------------
Este módulo contiene la vista principal para la corrección de textos en español.
Integra la solución mejorada que garantiza respuestas JSON y correcto manejo
de functions con OpenAI Assistants v2.
"""

import logging
import streamlit as st
import time
from datetime import datetime

# Importaciones del proyecto
from config.settings import NIVELES_ESPANOL
from features.correccion_controller import handle_correction_request, display_correction_result, get_correction_metrics
from core.session_manager import get_user_info, get_session_var, set_session_var

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista de corrección de textos.
    
    Returns:
        None
    """
    try:
        # Título y descripción
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
        
        # Crear columnas para la interfaz
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Recuperar el último texto si existe
            default_text = get_session_var("texto_original", "")
            
            # Campo de texto para la corrección
            texto_input = st.text_area(
                "Escribe o pega tu texto en español:",
                value=default_text,
                height=200,
                max_chars=5000,
                placeholder="Escribe aquí tu texto en español...",
                help="Máximo 5000 caracteres"
            )
            
            # Guardar texto para referencia
            set_session_var("texto_original", texto_input)
        
        with col2:
            # Opciones de configuración
            st.markdown("### Configuración")
            
            # Selector de nivel
            nivel_options = list(NIVELES_ESPANOL.keys())
            
            # Recordar el último nivel usado
            default_nivel_index = 2  # B1 por defecto
            last_nivel = get_session_var("ultimo_nivel")
            if last_nivel in nivel_options:
                default_nivel_index = nivel_options.index(last_nivel)
            
            nivel = st.selectbox(
                "Tu nivel de español:",
                nivel_options,
                index=default_nivel_index,
                format_func=lambda x: f"{x} - {NIVELES_ESPANOL[x]}"
            )
            
            # Guardar nivel seleccionado
            set_session_var("ultimo_nivel", nivel)
            
            # Selector de detalle de corrección
            detalle_options = ["Básico", "Intermedio", "Detallado"]
            detalle_default = get_session_var("ultimo_detalle", "Intermedio")
            detalle_index = detalle_options.index(detalle_default) if detalle_default in detalle_options else 1
            
            detalle = st.select_slider(
                "Nivel de detalle:",
                options=detalle_options,
                value=detalle_options[detalle_index],
                help="Básico: Solo errores principales. Detallado: Corrección exhaustiva con explicaciones detalladas."
            )
            
            # Guardar detalle seleccionado
            set_session_var("ultimo_detalle", detalle)
            
            # Selector de idioma para las explicaciones
            idioma_options = ["español", "inglés", "francés", "portugués", "alemán", "italiano", "chino"]
            idioma_default = get_session_var("ultimo_idioma", "español")
            idioma_index = 0
            if idioma_default in idioma_options:
                idioma_index = idioma_options.index(idioma_default)
                
            idioma = st.selectbox(
                "Idioma de las explicaciones:",
                idioma_options,
                index=idioma_index
            )
            
            # Guardar idioma seleccionado
            set_session_var("ultimo_idioma", idioma)
            
            # Botón para corregir
            corregir_button = st.button(
                "Corregir texto",
                type="primary",
                disabled=not texto_input.strip(),
                help="Haz clic para enviar tu texto y recibir la corrección"
            )
            
            # Mostrar métricas de corrección
            metrics = get_correction_metrics()
            st.markdown("### Estadísticas")
            st.markdown(f"**Total correcciones:** {metrics['total_correcciones']}")
            if metrics['tiempo_promedio'] > 0:
                st.markdown(f"**Tiempo promedio:** {metrics['tiempo_promedio']:.1f}s")
            st.markdown(f"**Nivel más usado:** {metrics['nivel_mas_comun']}")
        
        # Separador visual
        st.divider()
        
        # Sección de resultados
        if corregir_button and texto_input:
            # Guardar hora de inicio para métricas
            start_time = time.time()
            
            # Procesar la corrección con el nuevo controlador unificado
            correction_result = handle_correction_request(
                text=texto_input,
                level=nivel,
                detail=detalle,
                language=idioma
            )
            
            # Guardar resultado para futuras referencias
            st.session_state.correction_result = correction_result
            st.session_state.mostrar_resultado = True
            
            # Calcular tiempo de procesamiento
            elapsed_time = time.time() - start_time
            logger.info(f"Corrección procesada en {elapsed_time:.2f} segundos")
            
            # Mostrar resultado de la corrección
            display_correction_result(correction_result)
            
        # Si no hay interacción del botón pero hay un resultado guardado, mostrarlo
        elif not corregir_button and st.session_state.mostrar_resultado:
            last_correction = st.session_state.get("correction_result")
            if last_correction:
                st.markdown("### Última corrección")
                display_correction_result(last_correction)
                
                # Opciones adicionales para la última corrección
                with st.expander("Opciones adicionales"):
                    # Botón para exportar
                    if st.button("Exportar corrección"):
                        try:
                            from features.exportacion import exportar_correccion
                            exportar_correccion(last_correction)
                        except Exception as export_error:
                            st.error(f"Error al exportar: {str(export_error)}")
                            logger.error(f"Error en exportación: {str(export_error)}")
                    
                    # Botón para limpiar resultado
                    if st.button("Limpiar resultado"):
                        st.session_state.correction_result = None
                        st.session_state.mostrar_resultado = False
                        st.experimental_rerun()
        
    except Exception as e:
        logger.error(f"Error en render_view: {str(e)}")
        st.error("Ocurrió un error al cargar la vista de corrección. Por favor, intenta recargar la página.")
        
        # Botón para recargar la vista
        if st.button("Recargar vista"):
            st.experimental_rerun()
