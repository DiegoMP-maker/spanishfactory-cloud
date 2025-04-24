#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de análisis contextual para Textocorrector ELE
----------------------------------------------------
Este módulo contiene funciones para visualizar el análisis contextual
de textos en español utilizando gráficos interactivos de Plotly.
"""

import logging
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def create_radar_chart(analisis_contextual):
    """
    Crea un gráfico de radar (spider chart) para visualizar el análisis contextual.
    
    Args:
        analisis_contextual (dict): Diccionario con los componentes del análisis contextual
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico de radar
    """
    try:
        if not analisis_contextual:
            # Crear figura vacía con mensaje
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de análisis contextual disponibles",
                template="plotly_white"
            )
            return fig
        
        # Extraer puntuaciones y preparar datos para el gráfico
        categorias = []
        valores = []
        descripciones = []
        
        # Categorías a incluir (en orden deseado)
        componentes = [
            ('coherencia', 'Coherencia'),
            ('cohesion', 'Cohesión'),
            ('registro_linguistico', 'Registro Lingüístico'),
            ('adecuacion_cultural', 'Adecuación Cultural')
        ]
        
        for key, label in componentes:
            if key in analisis_contextual and isinstance(analisis_contextual[key], dict):
                # Añadir categoría
                categorias.append(label)
                
                # Extraer puntuación (asegurar que está en escala 0-10)
                puntuacion = analisis_contextual[key].get('puntuacion', 0)
                if not isinstance(puntuacion, (int, float)):
                    try:
                        puntuacion = float(puntuacion)
                    except (ValueError, TypeError):
                        puntuacion = 0
                
                valores.append(puntuacion)
                
                # Preparar texto para tooltip
                comentario = analisis_contextual[key].get('comentario', '')
                if not comentario and key == 'registro_linguistico':
                    # Para registro lingüístico, usar campo "adecuacion" si "comentario" no existe
                    comentario = analisis_contextual[key].get('adecuacion', '')
                
                descripciones.append(comentario)
        
        # Cerrar el polígono repitiendo el primer punto
        categorias.append(categorias[0])
        valores.append(valores[0])
        descripciones.append(descripciones[0])
        
        # Crear gráfico de radar
        fig = go.Figure()
        
        # Añadir área rellena
        fig.add_trace(go.Scatterpolar(
            r=valores,
            theta=categorias,
            fill='toself',
            name='Análisis Contextual',
            line=dict(color='rgb(67, 147, 195)', width=2),
            fillcolor='rgba(67, 147, 195, 0.2)',
            hoverinfo='text',
            hovertext=[f"<b>{cat}:</b> {val}/10<br>{desc}" for cat, val, desc in zip(categorias, valores, descripciones)],
        ))
        
        # Configurar diseño
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 10],
                    tickvals=[2, 4, 6, 8, 10],
                    ticktext=['2', '4', '6', '8', '10'],
                    gridcolor='rgba(0, 0, 0, 0.1)',
                    linecolor='rgba(0, 0, 0, 0.3)',
                ),
                angularaxis=dict(
                    gridcolor='rgba(0, 0, 0, 0.1)',
                    linecolor='rgba(0, 0, 0, 0.3)',
                )
            ),
            showlegend=False,
            margin=dict(l=70, r=70, t=50, b=50),
            height=450,
            template="plotly_white",
            hovermode='closest'
        )
        
        return fig
    
    except Exception as e:
        logger.error(f"Error creando gráfico de radar: {str(e)}")
        # Crear figura vacía con mensaje de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def create_bar_chart(analisis_contextual):
    """
    Crea un gráfico de barras para visualizar el análisis contextual.
    
    Args:
        analisis_contextual (dict): Diccionario con los componentes del análisis contextual
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico de barras
    """
    try:
        if not analisis_contextual:
            # Crear figura vacía con mensaje
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de análisis contextual disponibles",
                template="plotly_white"
            )
            return fig
        
        # Extraer puntuaciones y preparar datos para el gráfico
        categorias = []
        valores = []
        descripciones = []
        
        # Categorías a incluir (en orden deseado)
        componentes = [
            ('coherencia', 'Coherencia'),
            ('cohesion', 'Cohesión'),
            ('registro_linguistico', 'Registro Lingüístico'),
            ('adecuacion_cultural', 'Adecuación Cultural')
        ]
        
        for key, label in componentes:
            if key in analisis_contextual and isinstance(analisis_contextual[key], dict):
                # Añadir categoría
                categorias.append(label)
                
                # Extraer puntuación (asegurar que está en escala 0-10)
                puntuacion = analisis_contextual[key].get('puntuacion', 0)
                if not isinstance(puntuacion, (int, float)):
                    try:
                        puntuacion = float(puntuacion)
                    except (ValueError, TypeError):
                        puntuacion = 0
                
                valores.append(puntuacion)
                
                # Preparar texto para tooltip
                comentario = analisis_contextual[key].get('comentario', '')
                if not comentario and key == 'registro_linguistico':
                    # Para registro lingüístico, usar campo "adecuacion" si "comentario" no existe
                    comentario = analisis_contextual[key].get('adecuacion', '')
                
                descripciones.append(comentario)
        
        # Crear DataFrame
        df = pd.DataFrame({
            'Categoría': categorias,
            'Puntuación': valores,
            'Descripción': descripciones
        })
        
        # Crear gráfico de barras
        fig = px.bar(
            df,
            x='Categoría',
            y='Puntuación',
            color='Puntuación',
            color_continuous_scale='Blues',
            range_y=[0, 10],
            hover_data=['Descripción'],
            labels={'Puntuación': 'Valoración (0-10)'}
        )
        
        # Personalizar diseño
        fig.update_layout(
            coloraxis_showscale=False,
            xaxis_title="",
            yaxis_title="Puntuación (0-10)",
            template="plotly_white",
            margin=dict(l=50, r=50, t=30, b=50),
            height=400,
            hovermode='x unified'
        )
        
        # Añadir línea de referencia para puntuación 5 (media)
        fig.add_shape(
            type='line',
            x0=-0.5,
            x1=len(categorias) - 0.5,
            y0=5,
            y1=5,
            line=dict(
                color='rgba(0, 0, 0, 0.3)',
                width=1,
                dash='dash'
            )
        )
        
        return fig
    
    except Exception as e:
        logger.error(f"Error creando gráfico de barras: {str(e)}")
        # Crear figura vacía con mensaje de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def format_contextual_analysis_details(analisis_contextual):
    """
    Formatea los detalles del análisis contextual en un formato legible.
    
    Args:
        analisis_contextual (dict): Diccionario con los componentes del análisis contextual
        
    Returns:
        str: HTML formateado con los detalles del análisis
    """
    try:
        if not analisis_contextual:
            return "<p>No hay análisis contextual disponible.</p>"
        
        # Iniciar HTML
        html_content = '<div class="analisis-contextual-details">'
        
        # Categorías a incluir (en orden deseado)
        componentes = [
            ('coherencia', 'Coherencia'),
            ('cohesion', 'Cohesión'),
            ('registro_linguistico', 'Registro Lingüístico'),
            ('adecuacion_cultural', 'Adecuación Cultural')
        ]
        
        # Procesar cada componente
        for key, label in componentes:
            if key in analisis_contextual and isinstance(analisis_contextual[key], dict):
                html_content += f'<div class="analisis-categoria analisis-{key}">'
                
                # Título con puntuación
                puntuacion = analisis_contextual[key].get('puntuacion', 0)
                html_content += f'<h4>{label} <span class="puntuacion">{puntuacion}/10</span></h4>'
                
                # Comentario principal
                comentario = analisis_contextual[key].get('comentario', '')
                if not comentario and key == 'registro_linguistico':
                    # Para registro lingüístico, usar campo "adecuacion" si "comentario" no existe
                    comentario = analisis_contextual[key].get('adecuacion', '')
                
                if comentario:
                    html_content += f'<p class="comentario">{comentario}</p>'
                
                # Para registro lingüístico, mostrar tipo detectado
                if key == 'registro_linguistico' and 'tipo_detectado' in analisis_contextual[key]:
                    tipo = analisis_contextual[key]['tipo_detectado']
                    html_content += f'<p class="tipo-registro">Tipo de registro: <strong>{tipo}</strong></p>'
                
                # Sugerencias
                if 'sugerencias' in analisis_contextual[key] and analisis_contextual[key]['sugerencias']:
                    sugerencias = analisis_contextual[key]['sugerencias']
                    if sugerencias:
                        html_content += '<div class="sugerencias">'
                        html_content += '<h5>Sugerencias:</h5>'
                        html_content += '<ul>'
                        for sugerencia in sugerencias:
                            html_content += f'<li>{sugerencia}</li>'
                        html_content += '</ul>'
                        html_content += '</div>'
                
                # Elementos destacables (solo para adecuación cultural)
                if key == 'adecuacion_cultural' and 'elementos_destacables' in analisis_contextual[key]:
                    elementos = analisis_contextual[key]['elementos_destacables']
                    if elementos:
                        html_content += '<div class="elementos-destacables">'
                        html_content += '<h5>Elementos destacables:</h5>'
                        html_content += '<ul>'
                        for elemento in elementos:
                            html_content += f'<li>{elemento}</li>'
                        html_content += '</ul>'
                        html_content += '</div>'
                
                html_content += '</div>'
        
        html_content += '</div>'
        
        # Añadir estilos CSS
        html_content = f'''
        <style>
            .analisis-contextual-details {{
                margin-top: 20px;
            }}
            
            .analisis-categoria {{
                margin-bottom: 20px;
                padding: 15px;
                border-radius: 8px;
            }}
            
            .analisis-coherencia {{
                background-color: rgba(33, 150, 243, 0.05);
                border-left: 4px solid #2196F3;
            }}
            
            .analisis-cohesion {{
                background-color: rgba(76, 175, 80, 0.05);
                border-left: 4px solid #4CAF50;
            }}
            
            .analisis-registro_linguistico {{
                background-color: rgba(255, 152, 0, 0.05);
                border-left: 4px solid #FF9800;
            }}
            
            .analisis-adecuacion_cultural {{
                background-color: rgba(156, 39, 176, 0.05);
                border-left: 4px solid #9C27B0;
            }}
            
            .analisis-categoria h4 {{
                margin-top: 0;
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .puntuacion {{
                background-color: #f0f0f0;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.9em;
                font-weight: normal;
            }}
            
            .comentario {{
                margin-bottom: 10px;
            }}
            
            .tipo-registro {{
                margin-bottom: 10px;
                font-style: italic;
            }}
            
            .sugerencias, .elementos-destacables {{
                margin-top: 12px;
            }}
            
            .sugerencias h5, .elementos-destacables h5 {{
                margin-bottom: 8px;
                font-size: 0.95em;
            }}
            
            .sugerencias ul, .elementos-destacables ul {{
                margin-top: 5px;
                padding-left: 20px;
            }}
            
            .sugerencias li, .elementos-destacables li {{
                margin-bottom: 5px;
            }}
        </style>
        {html_content}
        '''
        
        return html_content
    
    except Exception as e:
        logger.error(f"Error formateando detalles del análisis contextual: {str(e)}")
        return f"<p>Error al formatear el análisis contextual: {str(e)}</p>"

def display_contextual_analysis(analisis_contextual, chart_type='radar'):
    """
    Muestra el análisis contextual en Streamlit utilizando gráficos interactivos.
    
    Args:
        analisis_contextual (dict): Diccionario con los componentes del análisis contextual
        chart_type (str): Tipo de gráfico a mostrar ('radar' o 'bar')
        
    Returns:
        None
    """
    try:
        if not analisis_contextual:
            st.info("No hay datos de análisis contextual disponibles.")
            return
        
        # Columnas para gráfico y detalles
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Crear y mostrar gráfico según tipo seleccionado
            if chart_type == 'radar':
                fig = create_radar_chart(analisis_contextual)
            else:  # 'bar' por defecto si no es 'radar'
                fig = create_bar_chart(analisis_contextual)
            
            # Mostrar gráfico
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Mostrar detalles del análisis
            detalles_html = format_contextual_analysis_details(analisis_contextual)
            st.markdown(detalles_html, unsafe_allow_html=True)
    
    except Exception as e:
        logger.error(f"Error mostrando análisis contextual: {str(e)}")
        st.error(f"Error al mostrar el análisis contextual: {str(e)}")

def get_chart_toggle():
    """
    Crea un toggle para alternar entre tipos de gráficos.
    
    Returns:
        str: Tipo de gráfico seleccionado ('radar' o 'bar')
    """
    try:
        # Crear un contenedor para el toggle
        toggle_container = st.container()
        
        # Columnas para alinear el toggle a la derecha
        _, col_toggle = st.columns([4, 1])
        
        with col_toggle:
            # Usar radio buttons horizontales como toggle
            chart_option = st.radio(
                "Tipo de gráfico",
                options=["Radar", "Barras"],
                horizontal=True,
                label_visibility="collapsed",
                key="chart_type_toggle"
            )
            
            # Convertir selección a formato interno
            return 'radar' if chart_option == "Radar" else 'bar'
    
    except Exception as e:
        logger.error(f"Error creando toggle de gráfico: {str(e)}")
        return 'radar'  # Valor por defecto
    