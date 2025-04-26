#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilidades para la corrección de textos
---------------------------------------
Este módulo contiene funciones compartidas para procesar los resultados de corrección
de textos y mostrarlos en la interfaz.
"""

import logging
import json
import re
import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
import pandas as pd

from utils.contextual_analysis import (
    display_contextual_analysis,
    get_chart_toggle
)

logger = logging.getLogger(__name__)

def count_errors_by_category(errores):
    """
    Cuenta el número de errores por categoría.
    
    Args:
        errores (dict): Diccionario con categorías de errores y sus listas
        
    Returns:
        dict: Conteo de errores por categoría
    """
    try:
        conteo = {}
        
        # Validar que tengamos un diccionario
        if not isinstance(errores, dict):
            logger.warning(f"errores no es un diccionario: {type(errores)}")
            return {}
            
        if not errores:
            return {}
            
        for categoria, lista_errores in errores.items():
            if isinstance(lista_errores, list):
                conteo[categoria] = len(lista_errores)
            else:
                logger.warning(f"lista_errores para {categoria} no es una lista: {type(lista_errores)}")
                conteo[categoria] = 0
            
        return conteo
    
    except Exception as e:
        logger.error(f"Error contando errores por categoría: {str(e)}")
        return {}

def display_error_table(errores_categoria, categoria):
    """
    Muestra los errores en formato de tabla con iconos.
    
    Args:
        errores_categoria (list): Lista de errores de una categoría
        categoria (str): Nombre de la categoría
        
    Returns:
        None
    """
    try:
        # Validación de entrada
        if not isinstance(errores_categoria, list):
            st.warning(f"Formato inesperado de errores para categoría {categoria}")
            return
            
        if not errores_categoria:
            st.info(f"No se encontraron errores de {categoria}.")
            return
        
        # Encabezado
        st.markdown(f"#### {categoria} ({len(errores_categoria)})")
        
        # Mostrar cada error con iconos
        for error in errores_categoria:
            # Validar que sea un diccionario
            if not isinstance(error, dict):
                st.warning(f"Formato inesperado para error en {categoria}")
                continue
                
            col1, col2, col3 = st.columns([3, 3, 6])
            
            with col1:
                # Buscar el fragmento erróneo con diferentes posibles claves
                fragmento = error.get('fragmento_erroneo', 
                                     error.get('texto', 
                                              error.get('original', '')))
                st.markdown(f"❌ **Erróneo:** {fragmento}")
            
            with col2:
                # Buscar la corrección con diferentes posibles claves
                correccion = error.get('correccion', 
                                      error.get('sugerencia', 
                                               error.get('correcto', '')))
                st.markdown(f"✅ **Corrección:** {correccion}")
                
            with col3:
                # Buscar la explicación con diferentes posibles claves
                explicacion = error.get('explicacion', 
                                       error.get('explicación', 
                                                error.get('razon', '')))
                st.markdown(f"💡 **Explicación:** {explicacion}")
            
            st.markdown("---")
    except Exception as e:
        logger.error(f"Error mostrando tabla de errores: {str(e)}")
        st.error(f"Error mostrando detalles de los errores. Por favor, intenta de nuevo.")

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
        if not resultado:
            st.error("No hay resultado disponible para mostrar.")
            return
            
        # Verificar si hay un error explícito en el resultado
        if "error" in resultado and resultado["error"]:
            mensaje_error = resultado.get("mensaje", "Error desconocido durante la corrección")
            st.error(mensaje_error)
            
            # Mostrar el texto original si está disponible
            if "texto_original" in resultado:
                with st.expander("Tu texto original"):
                    st.write(resultado["texto_original"])
            
            return
        
        # Extraer componentes del resultado (adaptado a la estructura JSON específica)
        texto_original = resultado.get("texto_original", "")
        texto_corregido = resultado.get("texto_corregido", "")
        errores = resultado.get("errores", {})
        analisis_contextual = resultado.get("analisis_contextual", {})
        consejo_final = resultado.get("consejo_final", "")
        saludo = resultado.get("saludo", "")
        tipo_texto = resultado.get("tipo_texto", "")
        
        # Usar tabs simplificadas según los requisitos
        tabs = st.tabs(["Corrección", "Análisis contextual", "Consejo final", "Exportar informe"])
        
        # Tab de Corrección
        with tabs[0]:
            # Mostrar saludo si existe
            if saludo:
                st.markdown(f"### 👋 {saludo}")
                
            # Mostrar tipo de texto si existe
            if tipo_texto:
                st.markdown(f"**Tipo de texto:** {tipo_texto}")
                
            st.markdown("### 📝 Texto corregido")
            
            # Verificar que hay texto corregido
            if not texto_corregido:
                st.warning("No se generó texto corregido en la respuesta.")
                if texto_original:
                    st.text_area("Texto original", texto_original, height=200, disabled=True, label_visibility="collapsed")
            else:
                st.text_area("Texto corregido", texto_corregido, height=200, disabled=True, label_visibility="collapsed")
            
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
                        
                        if not categorias or not valores:
                            st.info("No hay suficientes datos para crear el gráfico.")
                        else:
                            # Crear paleta de colores dinámica según el número de categorías
                            default_colors = [
                                '#F44336',  # Rojo
                                '#FFC107',  # Amarillo
                                '#2196F3',  # Azul
                                '#4CAF50',  # Verde
                                '#9C27B0'   # Púrpura
                            ]
                            
                            # Asegurarse de tener suficientes colores
                            colors = default_colors[:len(categorias)]
                            while len(colors) < len(categorias):
                                colors.append(default_colors[len(colors) % len(default_colors)])
                            
                            # Crear gráfico de barras
                            fig = go.Figure(data=[
                                go.Bar(
                                    x=categorias,
                                    y=valores,
                                    marker_color=colors,
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
                    # Mostrar estadísticas de errores
                    st.markdown("#### Resumen de errores")
                    
                    try:
                        # Verificar que tengamos datos para el DataFrame
                        if not conteo_errores:
                            st.info("No hay estadísticas de errores disponibles.")
                        else:
                            # Crear DataFrame para estadísticas
                            df_errores = pd.DataFrame({
                                "Categoría": list(conteo_errores.keys()),
                                "Cantidad": list(conteo_errores.values())
                            })
                            
                            # Calcular porcentaje
                            total_errores = df_errores["Cantidad"].sum()
                            if total_errores > 0:  # Evitar división por cero
                                df_errores["Porcentaje"] = df_errores["Cantidad"].apply(
                                    lambda x: f"{(x/total_errores)*100:.1f}%"
                                )
                            else:
                                df_errores["Porcentaje"] = "0%"
                            
                            # Mostrar estadísticas
                            st.dataframe(
                                df_errores, 
                                hide_index=True,
                                use_container_width=True
                            )
                    except Exception as df_error:
                        logger.error(f"Error creando dataframe de errores: {str(df_error)}")
                        st.warning("Error mostrando estadísticas de errores.")
            
            # Mostrar detalles de errores por categoría
            st.markdown("### Detalles de errores")
            
            # Verificar que errores sea un diccionario
            if not isinstance(errores, dict):
                st.warning("Formato de errores inesperado. No se pueden mostrar detalles.")
                logger.warning(f"errores no es un diccionario: {type(errores)}")
                
            else:
                # Determinar categorías disponibles
                categorias_disponibles = list(errores.keys())
                
                if not categorias_disponibles:
                    st.info("No hay detalles de errores disponibles.")
                else:
                    try:
                        # Crear tabs para cada categoría
                        error_tabs = st.tabs(categorias_disponibles)
                        
                        for i, categoria in enumerate(categorias_disponibles):
                            with error_tabs[i]:
                                display_error_table(errores[categoria], categoria)
                    except Exception as tabs_error:
                        logger.error(f"Error mostrando tabs de errores: {str(tabs_error)}")
                        st.error("Error mostrando los detalles de errores.")
        
        # Tab de Análisis contextual
        with tabs[1]:
            try:
                if not analisis_contextual:
                    st.info("No hay análisis contextual disponible para este texto.")
                else:
                    st.markdown("### 📊 Análisis contextual")
                    
                    # Obtener tipo de gráfico seleccionado (radar o barras)
                    chart_type = get_chart_toggle()
                    
                    # Mostrar análisis contextual
                    display_contextual_analysis(analisis_contextual, chart_type)
            except Exception as context_error:
                logger.error(f"Error mostrando análisis contextual: {str(context_error)}")
                st.error("Error mostrando el análisis contextual.")
        
        # Tab de Consejo final
        with tabs[2]:
            try:
                if not consejo_final:
                    st.info("No hay consejo final disponible para este texto.")
                else:
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
            except Exception as consejo_error:
                logger.error(f"Error mostrando consejo final: {str(consejo_error)}")
                st.error("Error mostrando el consejo final.")
        
        # Tab de Exportación
        with tabs[3]:
            try:
                st.markdown("### 📤 Exportar informe")
                
                # Importar función para mostrar opciones de exportación
                from features.exportacion import mostrar_opciones_exportacion
                
                # Mostrar opciones
                mostrar_opciones_exportacion(resultado)
            except Exception as export_error:
                logger.error(f"Error mostrando opciones de exportación: {str(export_error)}")
                st.error("Error al cargar las opciones de exportación.")
    
    except Exception as e:
        logger.error(f"Error mostrando resultado de corrección: {str(e)}")
        st.error(f"Error al mostrar el resultado de la corrección. Por favor, inténtalo de nuevo más tarde.")
        
        # Mostrar texto original si está disponible
        if isinstance(resultado, dict) and "texto_original" in resultado:
            with st.expander("Tu texto original"):
                st.write(resultado["texto_original"])