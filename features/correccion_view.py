#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de visualización de correcciones para Textocorrector ELE
--------------------------------------------------------------
Este módulo contiene funciones para visualizar los resultados de corrección
de textos en español, incluyendo resaltado de errores, análisis contextual
y visualizaciones gráficas.
"""

import logging
import json
import streamlit as st
from datetime import datetime
import plotly.graph_objects as go

from utils.text_highlighting import (
    display_highlighted_text,
    display_error_summary,
    count_errors_by_category,
    generate_error_highlighting_css
)
from utils.contextual_analysis import (
    display_contextual_analysis,
    get_chart_toggle
)

logger = logging.getLogger(__name__)

def format_resultado_correccion(resultado):
    """
    Formatea el resultado de la corrección para su visualización.
    
    Args:
        resultado (dict): Resultado de la corrección del Assistant
        
    Returns:
        dict: Resultado formateado
    """
    try:
        if not resultado or "error" in resultado:
            error_msg = resultado.get("error", "Error desconocido en la corrección") if resultado else "No hay resultado de corrección"
            logger.error(f"Error en resultado de corrección: {error_msg}")
            return None
        
        # Extraer componentes principales
        try:
            # Si el resultado ya es un diccionario parseado
            if isinstance(resultado, dict) and "json_errores" in resultado:
                # Extraer JSON de errores si existe
                if resultado["json_errores"]:
                    try:
                        json_data = json.loads(resultado["json_errores"])
                    except json.JSONDecodeError:
                        json_data = {}
                else:
                    json_data = {}
                
                # Extraer componentes
                texto_original = resultado.get("texto_original", "")
                texto_corregido = resultado.get("texto_corregido", "")
                errores = resultado.get("errores", [])
                analisis_contextual = json_data.get("analisis_contextual", {})
                consejo_final = json_data.get("consejo_final", resultado.get("retroalimentacion", ""))
                
                # Extraer errores del nuevo formato
                errores_formateados = {}
                
                # Convertir estructura de errores al formato esperado por las funciones de visualización
                if isinstance(errores, list):
                    # Formato: lista de diccionarios con 'categoria', 'cantidad', 'ejemplos'
                    for error_categoria in errores:
                        categoria = error_categoria.get('categoria', 'Otro')
                        ejemplos = error_categoria.get('ejemplos', [])
                        
                        # Convertir ejemplos al formato esperado
                        errores_formateados[categoria] = []
                        for ejemplo in ejemplos:
                            error_formateado = {
                                'fragmento_erroneo': ejemplo.get('texto', ''),
                                'correccion': ejemplo.get('sugerencia', ''),
                                'explicacion': ejemplo.get('explicacion', '')
                            }
                            if error_formateado['fragmento_erroneo']:
                                errores_formateados[categoria].append(error_formateado)
                
            # Si es una respuesta directa del Assistant en formato JSON
            elif isinstance(resultado, dict) and "texto_corregido" in resultado:
                texto_original = resultado.get("texto_original", "")
                texto_corregido = resultado.get("texto_corregido", "")
                errores_formateados = resultado.get("errores", {})
                analisis_contextual = resultado.get("analisis_contextual", {})
                consejo_final = resultado.get("consejo_final", "")
            
            else:
                # Si no podemos identificar el formato, usar campos por defecto
                texto_original = resultado.get("texto_original", "")
                texto_corregido = resultado.get("texto_corregido", "")
                errores_formateados = {}
                analisis_contextual = {}
                consejo_final = resultado.get("consejo_final", resultado.get("retroalimentacion", ""))
                
                # Intentar extraer JSON del resultado
                try:
                    if isinstance(resultado, str):
                        json_data = json.loads(resultado)
                        if "errores" in json_data:
                            errores_formateados = json_data["errores"]
                        if "analisis_contextual" in json_data:
                            analisis_contextual = json_data["analisis_contextual"]
                        if "consejo_final" in json_data:
                            consejo_final = json_data["consejo_final"]
                except (json.JSONDecodeError, TypeError):
                    pass
                    
        except Exception as e:
            logger.error(f"Error procesando resultado de corrección: {str(e)}")
            texto_original = resultado.get("texto_original", "")
            texto_corregido = resultado.get("texto_corregido", "")
            errores_formateados = {}
            analisis_contextual = {}
            consejo_final = resultado.get("consejo_final", resultado.get("retroalimentacion", ""))
        
        # Crear resultado formateado
        return {
            "texto_original": texto_original,
            "texto_corregido": texto_corregido,
            "errores": errores_formateados,
            "analisis_contextual": analisis_contextual,
            "consejo_final": consejo_final
        }
    
    except Exception as e:
        logger.error(f"Error formateando resultado de corrección: {str(e)}")
        return None

def display_correccion_result(resultado, api_keys=None, circuit_breaker=None):
    """
    Muestra el resultado de la corrección en Streamlit con visualizaciones mejoradas.
    
    Args:
        resultado (dict): Resultado de la corrección
        api_keys (dict, opcional): Diccionario con claves de API
        circuit_breaker (object, opcional): Objeto CircuitBreaker para control de errores
        
    Returns:
        None
    """
    try:
        # Verificar si hay resultado
        if not resultado or isinstance(resultado, str) or "error" in resultado:
            error_msg = resultado.get("error", "Error desconocido") if isinstance(resultado, dict) else "No hay resultado disponible"
            st.error(f"Error en la corrección: {error_msg}")
            return
        
        # Formatear resultado para visualización
        formatted_result = format_resultado_correccion(resultado)
        if not formatted_result:
            st.error("No se pudo procesar el resultado de la corrección.")
            return
        
        # Extraer componentes del resultado
        texto_original = formatted_result["texto_original"]
        texto_corregido = formatted_result["texto_corregido"]
        errores = formatted_result["errores"]
        analisis_contextual = formatted_result["analisis_contextual"]
        consejo_final = formatted_result["consejo_final"]
        
        # Usar tabs para evitar expanders anidados
        tabs = st.tabs(["Texto", "Errores", "Análisis", "Consejo Final"])
        
        # Tab de Texto
        with tabs[0]:
            # Subtabs para diferentes vistas del texto
            texto_tabs = st.tabs(["Texto con errores resaltados", "Texto corregido", "Comparación"])
            
            # Tab de texto con errores resaltados
            with texto_tabs[0]:
                st.info("Pasa el cursor sobre los errores resaltados para ver detalles y correcciones.")
                display_highlighted_text(texto_original, errores)
            
            # Tab de texto corregido
            with texto_tabs[1]:
                st.markdown("### Texto corregido")
                st.markdown(texto_corregido)
            
            # Tab de comparación
            with texto_tabs[2]:
                # Columnas para comparación
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Texto original")
                    st.text_area(
                        "Original",
                        value=texto_original,
                        height=300,
                        label_visibility="collapsed",
                        disabled=True
                    )
                
                with col2:
                    st.markdown("#### Texto corregido")
                    st.text_area(
                        "Corregido",
                        value=texto_corregido,
                        height=300,
                        label_visibility="collapsed",
                        disabled=True
                    )
        
        # Tab de Errores
        with tabs[1]:
            st.markdown("### 🔍 Análisis de errores")
            
            # Contar errores por categoría
            conteo_errores = count_errors_by_category(errores)
            
            # Verificar si hay errores
            if not conteo_errores or sum(conteo_errores.values()) == 0:
                st.success("¡Felicidades! No se encontraron errores en tu texto.")
            else:
                # Columnas para mostrar gráfico y desglose
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    # Crear gráfico de errores
                    try:
                        # Preparar datos para el gráfico
                        categorias = list(conteo_errores.keys())
                        valores = list(conteo_errores.values())
                        
                        # Crear gráfico de barras
                        fig = go.Figure(data=[
                            go.Bar(
                                x=categorias,
                                y=valores,
                                marker_color=[
                                    '#F44336',  # Rojo para Gramática
                                    '#FFC107',  # Amarillo para Léxico
                                    '#2196F3',  # Azul para Puntuación
                                    '#4CAF50'   # Verde para Estructura textual
                                ][:len(categorias)],
                                text=valores,
                                textposition='auto',
                                hoverinfo='text',
                                hovertext=[f"{cat}: {val} error{'es' if val != 1 else ''}" for cat, val in zip(categorias, valores)]
                            )
                        ])
                        
                        # Personalizar diseño
                        fig.update_layout(
                            title="Distribución de errores",
                            xaxis_title="",
                            yaxis_title="Cantidad de errores",
                            template="plotly_white",
                            margin=dict(l=50, r=50, t=70, b=50),
                            height=300
                        )
                        
                        # Mostrar gráfico
                        st.plotly_chart(fig, use_container_width=True)
                        
                    except Exception as e:
                        logger.error(f"Error creando gráfico de errores: {str(e)}")
                        st.warning("No se pudo crear el gráfico de errores.")
                
                with col2:
                    # Mostrar desglose de errores
                    display_error_summary(errores)
        
        # Tab de Análisis contextual
        with tabs[2]:
            if analisis_contextual:
                st.markdown("### 📊 Análisis contextual")
                
                # Obtener tipo de gráfico seleccionado (radar o barras)
                chart_type = get_chart_toggle()
                
                # Mostrar análisis contextual
                display_contextual_analysis(analisis_contextual, chart_type)
            else:
                st.info("No hay análisis contextual disponible para este texto.")
        
        # Tab de Consejo final
        with tabs[3]:
            if consejo_final:
                st.markdown("### 💡 Consejo final")
                st.success(consejo_final)
                
                # Generar audio del consejo si ElevenLabs está disponible
                try:
                    audio_bytes = None
                    # Verificar disponibilidad de API
                    if api_keys and "elevenlabs" in api_keys and api_keys["elevenlabs"]["api_key"] and api_keys["elevenlabs"]["voice_id"]:
                        if circuit_breaker and circuit_breaker.can_execute("elevenlabs"):
                            # Importar función para generar audio
                            from core.audio_client import generar_audio_consejo
                            # Generar audio
                            audio_bytes = generar_audio_consejo(consejo_final)
                    
                    # Mostrar reproductor de audio si se generó correctamente
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3")
                        st.download_button(
                            label="⬇️ Descargar audio",
                            data=audio_bytes,
                            file_name=f"consejo_{datetime.now().strftime('%Y%m%d_%H%M')}.mp3",
                            mime="audio/mp3"
                        )
                except Exception as audio_error:
                    logger.error(f"Error al generar audio: {str(audio_error)}")
                    # No mostrar mensaje al usuario para evitar confusión
            else:
                st.info("No hay consejo final disponible para este texto.")
        
        # 6. Botón para exportar resultado (fuera de los tabs)
        st.markdown("### 📥 Exportar resultado")
        if st.button("Exportar resultado completo", key="export_result"):
            try:
                # Importar función para exportar
                from features.exportacion import exportar_correccion_pdf
                
                # Crear exportación
                exportar_correccion_pdf(formatted_result)
                
                st.success("Exportación completada. Revisa la sección de descargas.")
            except Exception as export_error:
                logger.error(f"Error al exportar resultado: {str(export_error)}")
                st.error("No se pudo exportar el resultado. Inténtalo de nuevo más tarde.")
    
    except Exception as e:
        logger.error(f"Error mostrando resultado de corrección: {str(e)}")
        st.error(f"Error al mostrar el resultado de la corrección: {str(e)}")

def create_toggle_component(options, default_index=0, key=None):
    """
    Crea un componente de alternancia personalizado.
    
    Args:
        options (list): Lista de opciones a mostrar
        default_index (int): Índice de la opción seleccionada por defecto
        key (str): Clave única para el componente
        
    Returns:
        str: Opción seleccionada
    """
    try:
        # Crear un ID único si no se proporciona
        if key is None:
            key = f"toggle_{id(options)}"
        
        # Crear columnas para cada opción
        cols = st.columns(len(options))
        
        # Obtener valor actual o usar predeterminado
        current_value = st.session_state.get(key, options[default_index])
        
        # Lista para almacenar estados de botones
        button_states = []
        
        # Crear botones para cada opción
        for i, (col, option) in enumerate(zip(cols, options)):
            with col:
                # Estilo según si está seleccionado o no
                button_style = "primary" if option == current_value else "secondary"
                button_pressed = st.button(
                    option,
                    key=f"{key}_{i}",
                    type=button_style
                )
                button_states.append(button_pressed)
        
        # Actualizar valor si se selecciona una opción
        for i, pressed in enumerate(button_states):
            if pressed:
                st.session_state[key] = options[i]
                return options[i]
        
        # Devolver valor actual
        return current_value
    
    except Exception as e:
        logger.error(f"Error creando componente de alternancia: {str(e)}")
        return options[default_index]

def display_comparison_view(resultado):
    """
    Muestra una vista comparativa entre texto original y corregido.
    
    Args:
        resultado (dict): Resultado de la corrección
        
    Returns:
        None
    """
    try:
        # Formatear resultado
        formatted_result = format_resultado_correccion(resultado)
        if not formatted_result:
            st.error("No se pudo procesar el resultado para comparación.")
            return
        
        # Extraer componentes
        texto_original = formatted_result["texto_original"]
        texto_corregido = formatted_result["texto_corregido"]
        
        # Columnas para comparación
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Texto Original")
            st.text_area(
                "Texto Original",
                value=texto_original,
                height=400,
                label_visibility="collapsed",
                disabled=True
            )
        
        with col2:
            st.markdown("### Texto Corregido")
            st.text_area(
                "Texto Corregido",
                value=texto_corregido,
                height=400,
                label_visibility="collapsed",
                disabled=True
            )
    
    except Exception as e:
        logger.error(f"Error mostrando vista comparativa: {str(e)}")
        st.error(f"Error al mostrar la comparación: {str(e)}")

def display_result_with_mode_toggle(resultado, api_keys=None, circuit_breaker=None):
    """
    Muestra el resultado con un toggle para cambiar entre modos de visualización.
    
    Args:
        resultado (dict): Resultado de la corrección
        api_keys (dict, opcional): Diccionario con claves de API
        circuit_breaker (object, opcional): Objeto CircuitBreaker para control de errores
        
    Returns:
        None
    """
    try:
        # Crear toggle para modo de visualización
        view_mode = create_toggle_component(
            ["Análisis Completo", "Comparación Simple"],
            default_index=0,
            key="view_mode_toggle"
        )
        
        st.markdown("---")
        
        # Mostrar según modo seleccionado
        if view_mode == "Análisis Completo":
            display_correccion_result(resultado, api_keys, circuit_breaker)
        else:
            display_comparison_view(resultado)
    
    except Exception as e:
        logger.error(f"Error mostrando resultado con toggle de modo: {str(e)}")
        # Fallback a vista estándar
        display_correccion_result(resultado, api_keys, circuit_breaker)
        