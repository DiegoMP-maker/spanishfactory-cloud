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
                
                # Resetear la pestaña seleccionada
                st.session_state.tab_index = 0
                
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
        
        # Definir pestañas para la navegación
        tab_names = ["Corrección", "Análisis contextual", "Consejo final", "Exportar informe"]
        
        # Función de callback para cuando cambia la pestaña seleccionada
        def on_tab_change():
            st.session_state.tab_index = tab_names.index(st.session_state.selected_tab)
        
        # Mostrar pestañas con la seleccionada por session_state
        selected_tab = st.radio(
            "Secciones",
            tab_names,
            index=st.session_state.tab_index,
            key="selected_tab",
            on_change=on_tab_change,
            horizontal=True
        )
        
        try:
            # Tab 1: Corrección (texto corregido y errores)
            if selected_tab == "Corrección":
                # Sólo mostramos la parte de corrección
                try:
                    from features.correccion_utils import display_correction_section
                    display_correction_section(st.session_state.correction_result)
                except ImportError:
                    # Fallback por si no existe la función específica
                    st.subheader("Texto corregido")
                    st.write(st.session_state.correction_result.get("texto_corregido", ""))
                    
                    # Mostrar errores por categoría
                    st.subheader("Errores encontrados")
                    errores = st.session_state.correction_result.get("errores", {})
                    if errores:
                        for categoria, lista_errores in errores.items():
                            if lista_errores:
                                with st.expander(f"{categoria} ({len(lista_errores)})"):
                                    for error in lista_errores:
                                        st.markdown(f"❌ **Error:** {error.get('fragmento_erroneo', '')}")
                                        st.markdown(f"✅ **Corrección:** {error.get('correccion', '')}")
                                        st.markdown(f"💡 **Explicación:** {error.get('explicacion', '')}")
                                        st.markdown("---")
                    else:
                        st.success("¡No se encontraron errores en el texto!")
            
            # Tab 2: Análisis contextual
            elif selected_tab == "Análisis contextual":
                try:
                    from features.correccion_utils import display_analysis_section
                    display_analysis_section(st.session_state.correction_result)
                except ImportError:
                    # Fallback
                    st.subheader("Análisis contextual")
                    analisis = st.session_state.correction_result.get("analisis_contextual", {})
                    if analisis:
                        for categoria, info in analisis.items():
                            with st.expander(f"{categoria.replace('_', ' ').title()} ({info.get('puntuacion', 0)}/10)"):
                                st.write(info.get("comentario", ""))
                                
                                # Mostrar sugerencias si existen
                                if "sugerencias" in info and info["sugerencias"]:
                                    st.subheader("Sugerencias:")
                                    for sugerencia in info["sugerencias"]:
                                        st.markdown(f"• {sugerencia}")
                    else:
                        st.info("No hay análisis contextual disponible para este texto.")
            
            # Tab 3: Consejo final
            elif selected_tab == "Consejo final":
                st.subheader("Consejo final")
                consejo = st.session_state.correction_result.get("consejo_final", "")
                
                # Mostrar en un contenedor con estilo
                st.success(consejo)
                
                # Mostrar puntuación general si existe
                if "puntuacion" in st.session_state.correction_result:
                    puntuacion = st.session_state.correction_result.get("puntuacion", 0)
                    st.metric("Puntuación global", f"{puntuacion}/10")
            
            # Tab 4: Exportar informe
            elif selected_tab == "Exportar informe":
                st.subheader("Exportar")
                
                # Cargar funciones de exportación dinámicamente
                try:
                    from features.exportacion import exportar_correccion_word, exportar_correccion_pdf
                    
                    # Crear dos columnas para los botones
                    col1, col2 = st.columns(2)
                    
                    # Generar timestamp único para este render
                    import time
                    timestamp = int(time.time())
                    
                    with col1:
                        # Botón para Word con clave única temporal
                        if st.button("📄 Exportar a Word", key=f"export_word_btn_{timestamp}", use_container_width=True):
                            with st.spinner("Generando documento Word..."):
                                result = exportar_correccion_word(st.session_state.correction_result)
                                if result:
                                    st.success("Exportación completada. El documento se descargará automáticamente.")
                                else:
                                    st.error("Error al generar el documento Word.")
                    
                    with col2:
                        # Botón para PDF con clave única temporal
                        if st.button("📑 Exportar a PDF", key=f"export_pdf_btn_{timestamp}", use_container_width=True):
                            with st.spinner("Generando documento PDF..."):
                                result = exportar_correccion_pdf(st.session_state.correction_result)
                                if result:
                                    st.success("Exportación completada. El documento se descargará automáticamente.")
                                else:
                                    st.error("Error al generar el PDF. Asegúrate de tener wkhtmltopdf instalado.")
                
                except ImportError as e:
                    st.error(f"No se pudieron cargar las funciones de exportación: {str(e)}")
                    st.info("Contacta con el administrador del sistema para resolver este problema.")
            
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
