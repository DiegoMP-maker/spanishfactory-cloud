#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de resaltado de texto para Textocorrector ELE
---------------------------------------------------
Este módulo contiene funciones para resaltar errores en textos con tooltips
explicativos, utilizando HTML y CSS para la visualización en Streamlit.
"""

import logging
import re
import html
import streamlit as st

logger = logging.getLogger(__name__)

def generate_error_highlighting_css():
    """
    Genera el CSS necesario para el resaltado de errores y tooltips.
    
    Returns:
        str: Código CSS para incluir en la página
    """
    return """
    <style>
        /* Estilos base para todos los errores */
        .error-fragment {
            position: relative;
            border-bottom: 2px dotted;
            padding: 2px 0;
            cursor: help;
        }
        
        /* Tooltips personalizados */
        .error-fragment .tooltip-text {
            visibility: hidden;
            position: absolute;
            z-index: 100;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            background-color: rgba(51, 51, 51, 0.95);
            color: white;
            text-align: left;
            border-radius: 6px;
            padding: 8px 12px;
            width: 220px;
            box-shadow: 0 5px 10px rgba(0, 0, 0, 0.2);
            opacity: 0;
            transition: opacity 0.3s, visibility 0.3s;
            pointer-events: none;
            font-size: 14px;
            line-height: 1.4;
        }
        
        .error-fragment:hover .tooltip-text {
            visibility: visible;
            opacity: 1;
        }
        
        /* Flecha del tooltip */
        .error-fragment .tooltip-text::after {
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: rgba(51, 51, 51, 0.95) transparent transparent transparent;
        }
        
        /* Estilos específicos por categoría */
        .error-gramatica {
            background-color: rgba(244, 67, 54, 0.1);
            border-bottom-color: #F44336;
        }
        
        .error-lexico {
            background-color: rgba(255, 193, 7, 0.1);
            border-bottom-color: #FFC107;
        }
        
        .error-puntuacion {
            background-color: rgba(33, 150, 243, 0.1);
            border-bottom-color: #2196F3;
        }
        
        .error-estructura-textual {
            background-color: rgba(76, 175, 80, 0.1);
            border-bottom-color: #4CAF50;
        }
        
        /* Contenedor de texto con errores */
        .texto-original-container {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #2979FF;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 20px;
            overflow-wrap: break-word;
            word-wrap: break-word;
        }
        
        /* Estilos para resumen de errores */
        .error-summary {
            margin-top: 20px;
        }
        
        .error-category {
            margin-bottom: 15px;
            padding: 15px;
            border-radius: 8px;
        }
        
        .error-category-gramatica {
            background-color: rgba(244, 67, 54, 0.05);
            border-left: 4px solid #F44336;
        }
        
        .error-category-lexico {
            background-color: rgba(255, 193, 7, 0.05);
            border-left: 4px solid #FFC107;
        }
        
        .error-category-puntuacion {
            background-color: rgba(33, 150, 243, 0.05);
            border-left: 4px solid #2196F3;
        }
        
        .error-category-estructura-textual {
            background-color: rgba(76, 175, 80, 0.05);
            border-left: 4px solid #4CAF50;
        }
        
        .error-list {
            list-style-type: none;
            padding-left: 0;
        }
        
        .error-item {
            padding: 8px 0;
            border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        }
        
        .error-item:last-child {
            border-bottom: none;
        }
        
        .error-wrong {
            text-decoration: line-through;
            color: #D32F2F;
            margin-right: 5px;
        }
        
        .error-arrow {
            color: #757575;
            margin: 0 5px;
        }
        
        .error-correct {
            color: #388E3C;
            font-weight: 500;
        }
        
        .error-explanation {
            margin-top: 5px;
            color: #616161;
            font-size: 0.9em;
        }
        
        /* Contador de errores */
        .error-counter {
            display: inline-block;
            background-color: #E0E0E0;
            color: #424242;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 8px;
        }
    </style>
    """

def highlight_errors_in_text(texto_original, errores):
    """
    Resalta los errores en el texto original usando HTML con clases CSS 
    y tooltips explicativos.
    
    Args:
        texto_original (str): Texto original sin modificar
        errores (dict): Diccionario con categorías de errores y sus detalles
        
    Returns:
        str: Texto HTML con errores resaltados y tooltips
    """
    try:
        # Si no hay texto o errores, devolver el texto original
        if not texto_original or not errores:
            return f'<div class="texto-original-container">{texto_original}</div>'
        
        # Escapar HTML del texto original, preservando saltos de línea
        texto_html = html.escape(texto_original).replace('\n', '<br>')
        
        # Lista para almacenar todos los errores
        todos_errores = []
        
        # Extraer todos los errores de todas las categorías
        for categoria, lista_errores in errores.items():
            # Normalizar categoría para usarla como clase CSS
            categoria_css = categoria.lower().replace(' ', '-')
            
            for error in lista_errores:
                if 'fragmento_erroneo' in error and error['fragmento_erroneo']:
                    todos_errores.append({
                        'fragmento': error['fragmento_erroneo'],
                        'correccion': error.get('correccion', ''),
                        'explicacion': error.get('explicacion', ''),
                        'categoria': categoria,
                        'categoria_css': categoria_css
                    })
        
        # Ordenar errores por longitud del fragmento (descendente)
        # para evitar problemas con fragmentos que son substrings de otros
        todos_errores.sort(key=lambda x: len(x['fragmento']), reverse=True)
        
        # Reemplazar cada fragmento con error por su versión resaltada
        for error in todos_errores:
            # Escapar para uso en expresión regular
            fragmento_regex = re.escape(error['fragmento'])
            
            # Crear HTML para el fragmento con error y tooltip
            html_reemplazo = f'''
            <span class="error-fragment error-{error['categoria_css']}">
                {error['fragmento']}
                <span class="tooltip-text">
                    <strong>{error['categoria']}</strong><br>
                    Corrección: {html.escape(error['correccion'])}<br>
                    {html.escape(error['explicacion'])}
                </span>
            </span>
            '''
            
            # Reemplazar en el texto HTML
            texto_html = re.sub(
                fragmento_regex,
                lambda m: html_reemplazo,
                texto_html
            )
        
        # Envolver en un contenedor con estilo
        texto_html = f'<div class="texto-original-container">{texto_html}</div>'
        
        return texto_html
    
    except Exception as e:
        logger.error(f"Error resaltando errores en texto: {str(e)}")
        return f'<div class="texto-original-container">{texto_original}</div>'

def create_error_summary(errores):
    """
    Crea un resumen HTML de los errores organizados por categoría.
    
    Args:
        errores (dict): Diccionario con categorías de errores y sus detalles
        
    Returns:
        str: HTML con el resumen de errores por categoría
    """
    try:
        # Si no hay errores, devolver mensaje
        if not errores:
            return '<div class="error-summary">No se encontraron errores en el texto.</div>'
        
        html_summary = '<div class="error-summary">'
        
        # Procesar cada categoría de error
        for categoria, lista_errores in errores.items():
            if not lista_errores:  # Omitir categorías sin errores
                continue
                
            # Normalizar categoría para clases CSS
            categoria_css = categoria.lower().replace(' ', '-')
            
            # Añadir título de categoría con contador
            html_summary += f'''
            <div class="error-category error-category-{categoria_css}">
                <h4>{categoria} <span class="error-counter">{len(lista_errores)}</span></h4>
                <ul class="error-list">
            '''
            
            # Añadir cada error individual
            for error in lista_errores:
                if 'fragmento_erroneo' in error and error['fragmento_erroneo']:
                    html_summary += f'''
                    <li class="error-item">
                        <span class="error-wrong">{html.escape(error['fragmento_erroneo'])}</span>
                        <span class="error-arrow">→</span>
                        <span class="error-correct">{html.escape(error.get('correccion', ''))}</span>
                        <div class="error-explanation">{html.escape(error.get('explicacion', ''))}</div>
                    </li>
                    '''
            
            html_summary += '''
                </ul>
            </div>
            '''
        
        html_summary += '</div>'
        return html_summary
    
    except Exception as e:
        logger.error(f"Error creando resumen de errores: {str(e)}")
        return '<div class="error-summary">Error al procesar el resumen de errores.</div>'

def display_highlighted_text(texto_original, errores):
    """
    Muestra el texto con errores resaltados en Streamlit.
    
    Args:
        texto_original (str): Texto original sin modificar
        errores (dict): Diccionario con categorías de errores y sus detalles
        
    Returns:
        None
    """
    try:
        # Generar CSS para resaltado de errores
        css = generate_error_highlighting_css()
        
        # Generar HTML con texto resaltado
        html_resaltado = highlight_errors_in_text(texto_original, errores)
        
        # Mostrar en Streamlit
        st.markdown(css, unsafe_allow_html=True)
        st.markdown(html_resaltado, unsafe_allow_html=True)
    
    except Exception as e:
        logger.error(f"Error mostrando texto resaltado: {str(e)}")
        st.error(f"Error al mostrar el texto con errores resaltados: {str(e)}")
        st.text(texto_original)  # Mostrar texto plano como fallback

def display_error_summary(errores):
    """
    Muestra un resumen de errores organizado por categorías en Streamlit.
    
    Args:
        errores (dict): Diccionario con categorías de errores y sus detalles
        
    Returns:
        None
    """
    try:
        # Generar HTML del resumen
        html_summary = create_error_summary(errores)
        
        # Mostrar en Streamlit
        st.markdown(html_summary, unsafe_allow_html=True)
    
    except Exception as e:
        logger.error(f"Error mostrando resumen de errores: {str(e)}")
        st.error(f"Error al mostrar el resumen de errores: {str(e)}")

def count_errors_by_category(errores):
    """
    Cuenta el número de errores por categoría.
    
    Args:
        errores (dict): Diccionario con categorías de errores y sus detalles
        
    Returns:
        dict: Conteo de errores por categoría
    """
    try:
        conteo = {}
        
        for categoria, lista_errores in errores.items():
            conteo[categoria] = len(lista_errores)
            
        return conteo
    
    except Exception as e:
        logger.error(f"Error contando errores por categoría: {str(e)}")
        return {}
    