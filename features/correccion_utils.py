#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilidades para la corrección de textos
------------------------------------
Este módulo proporciona funciones auxiliares para la visualización
y procesamiento de correcciones de textos.
"""

import streamlit as st
import logging
import re

# Importaciones del proyecto
from config.settings import COLORES_ERROR

logger = logging.getLogger(__name__)

def display_correccion_result(result_data):
    """
    Muestra el resultado de la corrección en la interfaz de usuario.
    
    Args:
        result_data (dict): Datos de la corrección a mostrar
        
    Returns:
        None
    """
    try:
        if not result_data or not isinstance(result_data, dict):
            st.error("No hay datos de corrección para mostrar")
            return
            
        # Obtener campos principales
        saludo = result_data.get("saludo", "")
        tipo_texto = result_data.get("tipo_texto", "")
        texto_original = result_data.get("texto_original", "")
        texto_corregido = result_data.get("texto_corregido", "")
        analisis_contextual = result_data.get("analisis_contextual", {})
        consejo_final = result_data.get("consejo_final", "")
        errores = result_data.get("errores", {})
        
        # Mostrar encabezado con saludo personalizado
        if saludo:
            st.markdown(f"### {saludo}")
            
        if tipo_texto:
            st.markdown(f"*Tipo de texto detectado: {tipo_texto}*")
        
        # Crear layout con columnas para texto original y corregido
        col_original, col_corregido = st.columns(2)
        
        with col_original:
            st.markdown("#### Texto original")
            st.text_area(
                label="Texto original",
                value=texto_original,
                height=200,
                disabled=True,
                label_visibility="collapsed"
            )
            
        with col_corregido:
            st.markdown("#### Texto corregido")
            st.text_area(
                label="Texto corregido",
                value=texto_corregido,
                height=200,
                disabled=True,
                label_visibility="collapsed"
            )
        
        # Mostrar errores por categoría
        st.markdown("### Correcciones detalladas")
        
        # Contar errores por tipo
        total_errores = sum(len(errores_lista) for errores_lista in errores.values())
        if total_errores == 0:
            st.success("¡No se encontraron errores en tu texto! ¡Excelente trabajo!")
        else:
            # Mostrar número total de errores
            st.info(f"Se encontraron {total_errores} errores en tu texto.")
            
            # Crear tabs para las categorías de errores
            categorias = ["Gramática", "Léxico", "Puntuación", "Estructura textual"]
            tabs = st.tabs(categorias)
            
            # Mostrar errores por categoría en cada tab
            for i, categoria in enumerate(categorias):
                with tabs[i]:
                    errores_categoria = errores.get(categoria, [])
                    
                    if not errores_categoria:
                        st.success(f"No se encontraron errores de {categoria.lower()}.")
                    else:
                        st.info(f"**{len(errores_categoria)} errores de {categoria.lower()}**")
                        
                        # Para cada error, mostrar fragmento, corrección y explicación
                        for idx, error in enumerate(errores_categoria):
                            with st.container():
                                col1, col2 = st.columns([1, 2])
                                
                                with col1:
                                    # Fragmento erróneo
                                    st.markdown("❌ **Error:**")
                                    st.markdown(f"*{error.get('fragmento_erroneo', '')}*")
                                    
                                    # Corrección
                                    st.markdown("✅ **Corrección:**")
                                    st.markdown(f"*{error.get('correccion', '')}*")
                                
                                with col2:
                                    # Explicación
                                    st.markdown("💡 **Explicación:**")
                                    st.markdown(error.get('explicacion', ''))
                            
                            # Separador si no es el último error
                            if idx < len(errores_categoria) - 1:
                                st.divider()
        
        # Mostrar análisis contextual
        if analisis_contextual:
            with st.expander("Análisis contextual", expanded=True):
                # Crear columnas para las cuatro secciones del análisis
                cols = st.columns(2)
                
                # Componentes del análisis contextual
                componentes = [
                    {"nombre": "Coherencia", "key": "coherencia"},
                    {"nombre": "Cohesión", "key": "cohesion"},
                    {"nombre": "Registro lingüístico", "key": "registro_linguistico"},
                    {"nombre": "Adecuación cultural", "key": "adecuacion_cultural"}
                ]
                
                # Mostrar cada componente
                for i, componente in enumerate(componentes):
                    col_idx = i % 2
                    with cols[col_idx]:
                        datos = analisis_contextual.get(componente["key"], {})
                        
                        if datos:
                            st.markdown(f"**{componente['nombre']}**")
                            
                            # Puntuación
                            puntuacion = datos.get("puntuacion", 0)
                            st.progress(puntuacion/10.0, f"Puntuación: {puntuacion}/10")
                            
                            # Comentario
                            if "comentario" in datos:
                                st.markdown(datos["comentario"])
                            
                            # Sugerencias
                            sugerencias = datos.get("sugerencias", [])
                            if sugerencias:
                                st.markdown("**Sugerencias de mejora:**")
                                for sugerencia in sugerencias:
                                    st.markdown(f"* {sugerencia}")
                                    
                            # Elementos destacables (solo para adecuación cultural)
                            if componente["key"] == "adecuacion_cultural":
                                elementos = datos.get("elementos_destacables", [])
                                if elementos:
                                    st.markdown("**Elementos culturales destacables:**")
                                    for elemento in elementos:
                                        st.markdown(f"* {elemento}")
                            
                            # Tipo detectado (solo para registro lingüístico)
                            if componente["key"] == "registro_linguistico" and "tipo_detectado" in datos:
                                st.markdown(f"**Tipo de registro detectado:** {datos['tipo_detectado']}")
                                
                            # Adecuación (solo para registro lingüístico)
                            if componente["key"] == "registro_linguistico" and "adecuacion" in datos:
                                st.markdown(f"**Adecuación:** {datos['adecuacion']}")
        
        # Mostrar consejo final
        if consejo_final:
            st.markdown("### Consejo final")
            st.success(consejo_final)
            
    except Exception as e:
        logger.error(f"Error en display_correccion_result: {str(e)}")
        st.error(f"Error mostrando el resultado: {str(e)}")

def highlight_errors_in_text(texto, errores):
    """
    Resalta los errores en el texto original.
    
    Args:
        texto (str): Texto original
        errores (dict): Diccionario de errores por categoría
        
    Returns:
        str: Texto con errores resaltados en HTML
    """
    try:
        if not texto or not errores:
            return texto
            
        # Crear una copia del texto para modificar
        texto_html = texto
        
        # Obtenemos todos los errores en una lista
        errores_planos = []
        for categoria, lista_errores in errores.items():
            color = COLORES_ERROR.get(categoria, "#f0f0f0")
            for error in lista_errores:
                if "fragmento_erroneo" in error:
                    errores_planos.append({
                        "fragmento": error["fragmento_erroneo"],
                        "color": color,
                        "categoria": categoria
                    })
        
        # Ordenar errores por longitud descendente para evitar problemas de solapamiento
        errores_planos.sort(key=lambda x: len(x["fragmento"]), reverse=True)
        
        # Reemplazar cada error por su versión resaltada
        for error in errores_planos:
            fragmento = error["fragmento"]
            color = error["color"]
            categoria = error["categoria"]
            
            # Escapar caracteres especiales para regex
            fragmento_escaped = re.escape(fragmento)
            
            # Reemplazar en el texto (solo coincidencias exactas)
            # Usando r-string para evitar problemas con secuencias de escape
            pattern = fr'(?<![^\s]){fragmento_escaped}(?![^\s])'
            texto_html = re.sub(
                pattern, 
                etiqueta_html, 
                texto_html
            )
        
        return texto_html
        
    except Exception as e:
        logger.error(f"Error en highlight_errors_in_text: {str(e)}")
        return texto

def generate_correction_report(correction_data):
    """
    Genera un informe de corrección en formato Markdown.
    
    Args:
        correction_data (dict): Datos de la corrección
        
    Returns:
        str: Informe en formato Markdown
    """
    try:
        if not correction_data or not isinstance(correction_data, dict):
            return "Error: No hay datos de corrección disponibles"
        
        # Obtener campos principales
        saludo = correction_data.get("saludo", "")
        tipo_texto = correction_data.get("tipo_texto", "")
        texto_original = correction_data.get("texto_original", "")
        texto_corregido = correction_data.get("texto_corregido", "")
        analisis_contextual = correction_data.get("analisis_contextual", {})
        consejo_final = correction_data.get("consejo_final", "")
        errores = correction_data.get("errores", {})
        
        # Crear informe en formato Markdown
        informe = f"# Informe de Corrección - TextoCorrector ELE\n\n"
        
        # Añadir saludo y tipo de texto
        if saludo:
            informe += f"## {saludo}\n\n"
        
        if tipo_texto:
            informe += f"*Tipo de texto detectado: {tipo_texto}*\n\n"
        
        # Texto original y corregido
        informe += "## Texto Original\n\n"
        informe += f"```\n{texto_original}\n```\n\n"
        
        informe += "## Texto Corregido\n\n"
        informe += f"```\n{texto_corregido}\n```\n\n"
        
        # Errores por categoría
        informe += "## Correcciones Detalladas\n\n"
        
        # Contar errores por tipo
        total_errores = sum(len(errores_lista) for errores_lista in errores.values())
        
        if total_errores == 0:
            informe += "¡No se encontraron errores! ¡Excelente trabajo!\n\n"
        else:
            informe += f"Se encontraron {total_errores} errores en el texto.\n\n"
            
            # Mostrar errores por categoría
            categorias = ["Gramática", "Léxico", "Puntuación", "Estructura textual"]
            
            for categoria in categorias:
                errores_categoria = errores.get(categoria, [])
                
                if errores_categoria:
                    informe += f"### {categoria} ({len(errores_categoria)} errores)\n\n"
                    
                    # Para cada error, mostrar fragmento, corrección y explicación
                    for idx, error in enumerate(errores_categoria):
                        informe += f"**❌ Error:** _{error.get('fragmento_erroneo', '')}_\n\n"
                        informe += f"**✅ Corrección:** _{error.get('correccion', '')}_\n\n"
                        informe += f"**💡 Explicación:** {error.get('explicacion', '')}\n\n"
                        
                        # Separador si no es el último error
                        if idx < len(errores_categoria) - 1:
                            informe += "---\n\n"
        
        # Análisis contextual
        if analisis_contextual:
            informe += "## Análisis Contextual\n\n"
            
            # Componentes del análisis contextual
            componentes = [
                {"nombre": "Coherencia", "key": "coherencia"},
                {"nombre": "Cohesión", "key": "cohesion"},
                {"nombre": "Registro Lingüístico", "key": "registro_linguistico"},
                {"nombre": "Adecuación Cultural", "key": "adecuacion_cultural"}
            ]
            
            # Mostrar cada componente
            for componente in componentes:
                datos = analisis_contextual.get(componente["key"], {})
                
                if datos:
                    informe += f"### {componente['nombre']}\n\n"
                    
                    # Puntuación
                    puntuacion = datos.get("puntuacion", 0)
                    informe += f"**Puntuación:** {puntuacion}/10\n\n"
                    
                    # Comentario
                    if "comentario" in datos:
                        informe += f"{datos['comentario']}\n\n"
                    
                    # Sugerencias
                    sugerencias = datos.get("sugerencias", [])
                    if sugerencias:
                        informe += "**Sugerencias de mejora:**\n\n"
                        for sugerencia in sugerencias:
                            informe += f"* {sugerencia}\n"
                        informe += "\n"
                        
                    # Elementos destacables (solo para adecuación cultural)
                    if componente["key"] == "adecuacion_cultural":
                        elementos = datos.get("elementos_destacables", [])
                        if elementos:
                            informe += "**Elementos culturales destacables:**\n\n"
                            for elemento in elementos:
                                informe += f"* {elemento}\n"
                            informe += "\n"
                    
                    # Tipo detectado (solo para registro lingüístico)
                    if componente["key"] == "registro_linguistico" and "tipo_detectado" in datos:
                        informe += f"**Tipo de registro detectado:** {datos['tipo_detectado']}\n\n"
                        
                    # Adecuación (solo para registro lingüístico)
                    if componente["key"] == "registro_linguistico" and "adecuacion" in datos:
                        informe += f"**Adecuación:** {datos['adecuacion']}\n\n"
        
        # Consejo final
        if consejo_final:
            informe += "## Consejo Final\n\n"
            informe += f"{consejo_final}\n\n"
            
        # Añadir pie de página
        informe += "---\n\n"
        informe += "*Generado por TextoCorrector ELE*\n"
        
        return informe
        
    except Exception as e:
        logger.error(f"Error en generate_correction_report: {str(e)}")
        return f"Error generando informe: {str(e)}"
