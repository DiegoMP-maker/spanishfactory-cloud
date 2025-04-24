#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista de corrección de textos
----------------------------
Este módulo implementa la interfaz de usuario para la funcionalidad de corrección de textos.
"""

import logging
import streamlit as st
import time
from datetime import datetime

# Corregir importaciones - eliminar obtener_historial_correcciones de features.correccion
from features.correccion import corregir_texto
# Importar funciones de Firebase
from core.firebase_client import guardar_correccion_firebase, obtener_historial_correcciones
from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.main_layout import mostrar_mensaje_error, mostrar_leyenda_errores
from utils.text_processing import extract_errores_from_json
from features.exportacion import mostrar_opciones_exportacion

logger = logging.getLogger(__name__)



def render_view():
    """
    Renderiza la vista de corrección de textos.
    
    Returns:
        None
    """
    try:
        # Título de la página
        st.markdown("## 🖊️ Corrección de textos")
        st.markdown("""
        Escribe o pega un texto en español y obtén una corrección detallada con explicaciones
        de los errores y sugerencias para mejorar.
        """)
        
        # Verificar si hay una recomendación de tema
        correccion_recomendada = get_session_var("correccion_recomendada", None)
        if correccion_recomendada:
            st.info(f"Tema recomendado: {correccion_recomendada.get('tipo', 'expresión escrita')} para nivel {correccion_recomendada.get('nivel', 'B1')}")
            # Limpiar la recomendación para no mostrarla de nuevo
            set_session_var("correccion_recomendada", None)
        
        # Obtener información del usuario
        user_info = get_user_info()
        nivel_usuario = user_info.get('nivel', 'B1') if user_info else 'B1'
        
        # Crear pestañas para Nueva Corrección e Historial
        tab1, tab2 = st.tabs(["Nueva corrección", "Historial de correcciones"])
        
        with tab1:
            # Formulario para nueva corrección
            mostrar_formulario_correccion(nivel_usuario)
        
        with tab2:
            # Historial de correcciones
            mostrar_historial_correcciones()
    except Exception as e:
        logger.error(f"Error renderizando vista de corrección: {str(e)}")
        st.error(f"Error al cargar la vista de corrección: {str(e)}")

def mostrar_formulario_correccion(nivel_usuario):
    """
    Muestra el formulario para enviar un texto a corregir.
    
    Args:
        nivel_usuario (str): Nivel de español del usuario
        
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        
        # Formulario de corrección
        with st.form("form_correccion"):
            # Selector de nivel
            nivel = st.selectbox(
                "Nivel de español",
                ["A1", "A2", "B1", "B2", "C1", "C2"],
                index=["A1", "A2", "B1", "B2", "C1", "C2"].index(nivel_usuario)
            )
            
            # Selector de tipo de texto
            tipo_texto = st.selectbox(
                "Tipo de texto",
                [
                    "General",
                    "Email/Carta",
                    "Redacción/Ensayo",
                    "Descripción",
                    "Narración",
                    "Artículo de opinión",
                    "Diálogo",
                    "Resumen"
                ]
            )
            
            # Campo de texto
            texto = st.text_area(
                "Escribe o pega tu texto en español",
                height=250,
                max_chars=2000,
                help="Máximo 2000 caracteres"
            )
            
            # Instrucciones específicas (opcional)
            instrucciones = st.text_input(
                "Instrucciones específicas (opcional)",
                placeholder="Ej: Concentrarse en la conjugación de verbos, revisar uso de preposiciones, etc.",
                help="Instrucciones adicionales para la corrección"
            )
            
            # Opciones avanzadas en un expander
            with st.expander("Opciones avanzadas"):
                col1, col2 = st.columns(2)
                
                with col1:
                    detalle = st.select_slider(
                        "Nivel de detalle",
                        options=["Básico", "Intermedio", "Detallado"],
                        value="Intermedio",
                        help="Define la cantidad de detalles en la corrección"
                    )
                
                with col2:
                    enfoque = st.multiselect(
                        "Enfocar corrección en",
                        [
                            "Gramática", 
                            "Vocabulario", 
                            "Ortografía", 
                            "Cohesión", 
                            "Coherencia", 
                            "Puntuación"
                        ],
                        default=[],
                        help="Deja en blanco para una corrección completa"
                    )
            
            # Botón de envío
            submitted = st.form_submit_button("Corregir texto")
            
            if submitted:
                if not texto:
                    st.warning("Por favor, escribe o pega un texto para corregir.")
                elif len(texto) < 20:
                    st.warning("El texto es demasiado corto. Por favor, escribe al menos 20 caracteres.")
                else:
                    # Mostrar spinner mientras se procesa
                    with st.spinner("Corrigiendo texto... Esto puede tardar unos segundos."):
                        try:
                            # Preparar parámetros
                            parametros = {
                                "nivel": nivel,
                                "tipo_texto": tipo_texto,
                                "detalle": detalle,
                                "enfoque": enfoque if enfoque else None,
                                "instrucciones": instrucciones if instrucciones else None
                            }
                            
                            # Obtener UID del usuario
                            uid = user_info.get('uid', None) if user_info else None
                            
                            # Llamar a la función de corrección
                            resultado_correccion = corregir_texto(texto, parametros, uid)
                            
                            if resultado_correccion and 'error' not in resultado_correccion:
                                # Guardar resultado en el estado de sesión para mostrarlo
                                set_session_var("ultima_correccion", resultado_correccion)
                                
                                # Guardar en Firebase si hay usuario
                                if uid:
                                    # Extraer errores del JSON si están disponibles
                                    errores = extract_errores_from_json(resultado_correccion.get("json_errores", ""))
                                    
                                    # Preparar datos para guardar
                                    datos_guardar = {
                                        "uid": uid,
                                        "texto_original": texto,
                                        "texto_corregido": resultado_correccion.get("texto_corregido", ""),
                                        "retroalimentacion": resultado_correccion.get("retroalimentacion", ""),
                                        "nivel": nivel,
                                        "tipo_texto": tipo_texto,
                                        "errores": errores,
                                        "fecha": datetime.now().isoformat(),
                                        "puntuacion": resultado_correccion.get("puntuacion", 0),
                                        "thread_id": resultado_correccion.get("thread_id", None)
                                    }
                                    
                                    # Guardar en Firebase
                                    guardar_correccion_firebase(datos_guardar)
                                
                                # Mostrar el resultado
                                mostrar_resultado_correccion(resultado_correccion, texto)
                            else:
                                # Mostrar error
                                error_msg = resultado_correccion.get('error', 'Error al procesar la corrección. Por favor, inténtalo de nuevo.')
                                mostrar_mensaje_error(error_msg)
                        except Exception as e:
                            logger.error(f"Error procesando corrección: {str(e)}")
                            st.error(f"Error procesando la corrección: {str(e)}")
        
        # Si hay una corrección reciente, mostrarla
        ultima_correccion = get_session_var("ultima_correccion", None)
        if ultima_correccion and not submitted:
            mostrar_resultado_correccion(ultima_correccion, ultima_correccion.get("texto_original", ""))
    except Exception as e:
        logger.error(f"Error mostrando formulario de corrección: {str(e)}")
        st.error(f"Error al cargar el formulario: {str(e)}")

def mostrar_resultado_correccion(resultado, texto_original):
    """
    Muestra el resultado de la corrección.
    
    Args:
        resultado (dict): Resultado de la corrección
        texto_original (str): Texto original enviado
        
    Returns:
        None
    """
    try:
        # Extraer datos
        texto_corregido = resultado.get("texto_corregido", "")
        retroalimentacion = resultado.get("retroalimentacion", "")
        puntuacion = resultado.get("puntuacion", 0)
        json_errores = resultado.get("json_errores", "")
        
        # Mostrar línea de separación
        st.markdown("---")
        
        # Título y puntuación
        st.markdown("### Resultado de la corrección")
        
        # Mostrar puntuación
        st.metric("Puntuación", f"{puntuacion}/10")
        
        # Extraer errores del JSON
        errores = extract_errores_from_json(json_errores)
        
        # Mostrar leyenda de tipos de errores
        mostrar_leyenda_errores()
        
        # Mostrar texto original y corregido en columnas
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Texto original")
            st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; height: 300px; overflow-y: auto;">{texto_original}</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown("#### Texto corregido")
            st.markdown(f'<div class="texto-corregido" style="height: 300px; overflow-y: auto;">{texto_corregido}</div>', unsafe_allow_html=True)
        
        # Mostrar resumen de errores
        if errores:
            st.markdown("#### Resumen de errores")
            
            # Crear tabla de errores
            data = []
            for error in errores:
                data.append({
                    "Categoría": error.get("categoria", ""),
                    "Cantidad": error.get("cantidad", 0)
                })
            
            # Mostrar tabla
            st.table(data)
            
            # Mostrar ejemplos específicos si están disponibles
            ejemplos_disponibles = any(len(error.get("ejemplos", [])) > 0 for error in errores)
            
            if ejemplos_disponibles:
                with st.expander("Ver ejemplos específicos de errores", expanded=False):
                    for error in errores:
                        ejemplos = error.get("ejemplos", [])
                        if ejemplos:
                            st.markdown(f"##### {error.get('categoria', 'Error')}")
                            for i, ejemplo in enumerate(ejemplos, 1):
                                st.markdown(f"**Ejemplo {i}:**")
                                st.markdown(f"- Original: *{ejemplo.get('texto', '')}*")
                                st.markdown(f"- Sugerencia: *{ejemplo.get('sugerencia', '')}*")
                                if ejemplo.get('explicacion'):
                                    st.markdown(f"- Explicación: {ejemplo.get('explicacion', '')}")
                                st.markdown("---")
        
        # Mostrar retroalimentación general
        st.markdown("#### Retroalimentación general")
        st.markdown(retroalimentacion)
        
        # Opciones de exportación
        with st.expander("Exportar corrección", expanded=False):
            # Preparar datos para exportación
            datos_exportacion = {
                "texto_original": texto_original,
                "texto_corregido": texto_corregido,
                "retroalimentacion": retroalimentacion,
                "errores": errores,
                "puntuacion": puntuacion
            }
            
            # Mostrar opciones de exportación
            mostrar_opciones_exportacion(datos_exportacion, "correccion")
    except Exception as e:
        logger.error(f"Error mostrando resultado de corrección: {str(e)}")
        st.error(f"Error al mostrar el resultado: {str(e)}")

def mostrar_historial_correcciones():
    """
    Muestra el historial de correcciones del usuario.
    
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        uid = user_info.get('uid', None) if user_info else None
        
        if not uid or user_info.get('es_anonimo', False):
            st.info("Para guardar y ver tu historial de correcciones, necesitas iniciar sesión o crear una cuenta.")
            return
        
        # Obtener historial de correcciones
        with st.spinner("Cargando historial..."):
            correcciones = obtener_historial_correcciones(uid)
        
        if not correcciones:
            st.info("No tienes correcciones guardadas. Realiza tu primera corrección para verla aquí.")
            return
        
        # Mostrar número total de correcciones
        st.markdown(f"#### Historial de correcciones ({len(correcciones)})")
        
        # Ordenar por fecha (más reciente primero)
        correcciones_ordenadas = sorted(
            correcciones, 
            key=lambda x: x.get('fecha', ''), 
            reverse=True
        )
        
        # Mostrar cada corrección en un expander
        for i, correccion in enumerate(correcciones_ordenadas):
            # Extraer datos
            fecha_str = correccion.get('fecha', '')
            try:
                # Intentar formatear la fecha
                fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                fecha_formateada = fecha_dt.strftime("%d/%m/%Y %H:%M")
            except:
                fecha_formateada = fecha_str
            
            tipo_texto = correccion.get('tipo_texto', 'General')
            nivel = correccion.get('nivel', 'No especificado')
            puntuacion = correccion.get('puntuacion', 0)
            
            # Texto para el expander
            texto_corto = correccion.get('texto_original', '')[:50] + '...' if len(correccion.get('texto_original', '')) > 50 else correccion.get('texto_original', '')
            titulo_expander = f"{fecha_formateada} - {tipo_texto} (Nivel {nivel}) - Puntuación: {puntuacion}/10"
            
            with st.expander(titulo_expander):
                # Mostrar detalles de la corrección
                st.markdown(f"**Fecha:** {fecha_formateada}")
                st.markdown(f"**Tipo de texto:** {tipo_texto}")
                st.markdown(f"**Nivel:** {nivel}")
                st.markdown(f"**Puntuación:** {puntuacion}/10")
                
                # Mostrar texto original y corregido
                st.markdown("##### Texto original")
                st.markdown(f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px;">{correccion.get("texto_original", "")}</div>', unsafe_allow_html=True)
                
                st.markdown("##### Texto corregido")
                st.markdown(f'<div class="texto-corregido">{correccion.get("texto_corregido", "")}</div>', unsafe_allow_html=True)
                
                # Botón para cargar en el editor
                if st.button("Editar esta corrección", key=f"edit_btn_{i}"):
                    # Guardar como última corrección para mostrarla en la pestaña de edición
                    set_session_var("ultima_correccion", correccion)
                    # Cambiar a la pestaña de nueva corrección
                    st.experimental_rerun()
                
                # Mostrar retroalimentación si está disponible
                if correccion.get('retroalimentacion'):
                    with st.expander("Ver retroalimentación"):
                        st.markdown(correccion.get('retroalimentacion', ''))
                
                # Opciones de exportación
                if st.button("Exportar", key=f"export_btn_{i}"):
                    # Preparar datos para exportación
                    datos_exportacion = {
                        "texto_original": correccion.get('texto_original', ''),
                        "texto_corregido": correccion.get('texto_corregido', ''),
                        "retroalimentacion": correccion.get('retroalimentacion', ''),
                        "errores": correccion.get('errores', []),
                        "puntuacion": correccion.get('puntuacion', 0)
                    }
                    
                    # Mostrar opciones de exportación
                    mostrar_opciones_exportacion(datos_exportacion, f"correccion_{i}")
    except Exception as e:
        logger.error(f"Error mostrando historial de correcciones: {str(e)}")
        st.error(f"Error al cargar el historial: {str(e)}")
        