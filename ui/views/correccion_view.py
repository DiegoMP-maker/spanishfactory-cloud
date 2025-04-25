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

# Importar funciones de corrección
from features.correccion import corregir_texto, mostrar_resultado_correccion
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
                                    # La función corregir_texto ya se encarga de guardar en Firebase
                                    # por lo que ya no es necesario duplicar este código aquí
                                    pass
                                
                                # Configurar API keys y circuit breaker para mostrar resultado con reproductor de audio
                                if 'api_keys' not in st.session_state:
                                    st.session_state.api_keys = {
                                        "elevenlabs": {
                                            "api_key": st.secrets.get("ELEVENLABS_API_KEY", ""),
                                            "voice_id": st.secrets.get("ELEVENLABS_VOICE_ID", "")
                                        }
                                    }
                                
                                if 'circuit_breaker' not in st.session_state:
                                    from core.circuit_breaker import CircuitBreaker
                                    st.session_state.circuit_breaker = CircuitBreaker(
                                        max_failures=3,
                                        reset_timeout=60,
                                        failure_threshold=0.5
                                    )
                                
                                # Mostrar el resultado con la nueva visualización
                                mostrar_resultado_correccion(
                                    resultado_correccion, 
                                    st.session_state.api_keys,
                                    st.session_state.circuit_breaker
                                )
                            else:
                                # Mostrar error
                                error_msg = resultado_correccion.get('error', 'Error al procesar la corrección. Por favor, inténtalo de nuevo.')
                                mostrar_mensaje_error(error_msg)
                        except Exception as e:
                            logger.error(f"Error procesando corrección: {str(e)}")
                            st.error(f"Error procesando la corrección: {str(e)}")
        
        # Si hay una corrección reciente y no se acaba de enviar una nueva, mostrarla
        ultima_correccion = get_session_var("ultima_correccion", None)
        if ultima_correccion and not submitted:
            # Configurar API keys y circuit breaker para mostrar resultado con reproductor de audio
            if 'api_keys' not in st.session_state:
                st.session_state.api_keys = {
                    "elevenlabs": {
                        "api_key": st.secrets.get("ELEVENLABS_API_KEY", ""),
                        "voice_id": st.secrets.get("ELEVENLABS_VOICE_ID", "")
                    }
                }
            
            if 'circuit_breaker' not in st.session_state:
                from core.circuit_breaker import CircuitBreaker
                st.session_state.circuit_breaker = CircuitBreaker(
                    max_failures=3,
                    reset_timeout=60,
                    failure_threshold=0.5
                )
            
            # Mostrar el resultado con la nueva visualización
            mostrar_resultado_correccion(
                ultima_correccion, 
                st.session_state.api_keys,
                st.session_state.circuit_breaker
            )
    except Exception as e:
        logger.error(f"Error mostrando formulario de corrección: {str(e)}")
        st.error(f"Error al cargar el formulario: {str(e)}")

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
        
        # Usar un selectbox para elegir qué corrección mostrar en detalle
        # Esto evita el problema de expanders anidados
        correcciones_list = []
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
            
            # Texto para mostrar en la lista
            texto_corto = correccion.get('texto_original', '')[:50] + '...' if len(correccion.get('texto_original', '')) > 50 else correccion.get('texto_original', '')
            etiqueta = f"{fecha_formateada} - {tipo_texto} (Nivel {nivel}) - Puntuación: {puntuacion}/10"
            
            correcciones_list.append((etiqueta, correccion, i))
        
        # Opción para seleccionar una corrección
        if correcciones_list:
            opciones_correcciones = ["Selecciona una corrección..."] + [item[0] for item in correcciones_list]
            seleccion = st.selectbox(
                "Selecciona una corrección para ver detalles:",
                options=opciones_correcciones,
                index=0
            )
            
            # Si se ha seleccionado una corrección
            if seleccion != "Selecciona una corrección...":
                # Encontrar la corrección seleccionada
                for etiqueta, correccion, idx in correcciones_list:
                    if etiqueta == seleccion:
                        # Configurar API keys y circuit breaker para mostrar resultado con reproductor de audio
                        if 'api_keys' not in st.session_state:
                            st.session_state.api_keys = {
                                "elevenlabs": {
                                    "api_key": st.secrets.get("ELEVENLABS_API_KEY", ""),
                                    "voice_id": st.secrets.get("ELEVENLABS_VOICE_ID", "")
                                }
                            }
                        
                        if 'circuit_breaker' not in st.session_state:
                            from core.circuit_breaker import CircuitBreaker
                            st.session_state.circuit_breaker = CircuitBreaker(
                                max_failures=3,
                                reset_timeout=60,
                                failure_threshold=0.5
                            )
                        
                        # Mostrar detalles de la corrección seleccionada
                        fecha_str = correccion.get('fecha', '')
                        try:
                            fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                            fecha_formateada = fecha_dt.strftime("%d/%m/%Y %H:%M")
                        except:
                            fecha_formateada = fecha_str
                        
                        # Información básica
                        st.markdown("### Detalles de la corrección")
                        st.markdown(f"**Fecha:** {fecha_formateada}")
                        st.markdown(f"**Tipo de texto:** {correccion.get('tipo_texto', 'General')}")
                        st.markdown(f"**Nivel:** {correccion.get('nivel', 'No especificado')}")
                        st.markdown(f"**Puntuación:** {correccion.get('puntuacion', 0)}/10")
                        
                        # Botones para interactuar con la corrección
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Botón para ver detalles
                            if st.button("Ver corrección completa", key=f"detail_btn_{idx}"):
                                # Mostrar resultado con visualización avanzada
                                mostrar_resultado_correccion(
                                    correccion, 
                                    st.session_state.api_keys,
                                    st.session_state.circuit_breaker
                                )
                        
                        with col2:
                            # Botón para cargar en el editor
                            if st.button("Editar esta corrección", key=f"edit_btn_{idx}"):
                                # Guardar como última corrección para mostrarla en la pestaña de edición
                                set_session_var("ultima_correccion", correccion)
                                # Cambiar a la pestaña de nueva corrección
                                st.experimental_rerun()
                        
                        # Usar tabs para mostrar los textos en lugar de expanders anidados
                        tabs = st.tabs(["Texto original", "Texto corregido", "Retroalimentación"])
                        
                        with tabs[0]:
                            st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; font-family: Arial, sans-serif;">{correccion.get("texto_original", "")}</div>', unsafe_allow_html=True)
                        
                        with tabs[1]:
                            st.markdown(f'<div style="background-color: #f5f9ff; padding: 15px; border-radius: 5px; font-family: Georgia, serif;">{correccion.get("texto_corregido", "")}</div>', unsafe_allow_html=True)
                        
                        with tabs[2]:
                            if correccion.get('retroalimentacion'):
                                st.markdown(correccion.get('retroalimentacion', ''))
                            else:
                                st.info("No hay retroalimentación disponible para esta corrección.")
                        
                        # Opciones de exportación
                        st.markdown("### Exportar corrección")
                        if st.button("Exportar", key=f"export_btn_{idx}"):
                            # Preparar datos para exportación
                            datos_exportacion = {
                                "texto_original": correccion.get('texto_original', ''),
                                "texto_corregido": correccion.get('texto_corregido', ''),
                                "retroalimentacion": correccion.get('retroalimentacion', ''),
                                "errores": correccion.get('errores', []),
                                "puntuacion": correccion.get('puntuacion', 0)
                            }
                            
                            # Mostrar opciones de exportación
                            mostrar_opciones_exportacion(datos_exportacion, f"correccion_{idx}")
                        
                        break
            else:
                # Si no se ha seleccionado ninguna corrección, mostrar una lista simple
                st.markdown("### Correcciones recientes")
                
                # Mostrar correcciones en formato de lista
                for i, (etiqueta, correccion, idx) in enumerate(correcciones_list[:5]):  # Limitar a 5 más recientes
                    # Crear un contenedor para cada corrección
                    with st.container():
                        st.markdown(f"""
                        <div style="padding: 10px; border-radius: 5px; background-color: #f8f9fa; margin-bottom: 10px;">
                            <strong>{etiqueta}</strong><br>
                            <small>"{correccion.get('texto_original', '')[:50]}..."</small>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.info("Selecciona una corrección de la lista desplegable para ver sus detalles.")
    except Exception as e:
        logger.error(f"Error mostrando historial de correcciones: {str(e)}")
        st.error(f"Error al cargar el historial: {str(e)}")
        