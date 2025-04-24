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
import plotly.graph_objects as go

# Importar función del módulo de corrección
from features.correccion import corregir_texto
# Importar funciones de Firebase
from core.firebase_client import guardar_correccion_firebase, obtener_historial_correcciones
from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.main_layout import mostrar_mensaje_error, mostrar_leyenda_errores
from utils.text_processing import extract_errores_from_json
from features.exportacion import mostrar_opciones_exportacion

# Importar nuevos módulos para visualizaciones mejoradas
from utils.text_highlighting import display_highlighted_text
from utils.contextual_analysis import display_contextual_analysis, get_chart_toggle

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
                                
                                # Mostrar el resultado con visualización mejorada
                                mostrar_resultado_correccion_mejorado(resultado_correccion, texto)
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
            # Usar la nueva visualización para mostrar el resultado más reciente
            mostrar_resultado_correccion_mejorado(ultima_correccion, ultima_correccion.get("texto_original", ""))
    except Exception as e:
        logger.error(f"Error mostrando formulario de corrección: {str(e)}")
        st.error(f"Error al cargar el formulario: {str(e)}")

def mostrar_resultado_correccion_mejorado(resultado, texto_original):
    """
    Muestra el resultado de la corrección con visualizaciones mejoradas.
    
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
        consejo_final = resultado.get("consejo_final", "")
        
        # Extraer errores del JSON
        errores_json = extract_errores_from_json(json_errores)
        
        # Extraer errores en formato para resaltado
        errores_formato = {}
        for error in errores_json:
            categoria = error.get("categoria", "")
            ejemplos = error.get("ejemplos", [])
            if categoria and ejemplos:
                errores_formato[categoria] = []
                for ejemplo in ejemplos:
                    if "texto" in ejemplo and ejemplo["texto"]:
                        error_item = {
                            "fragmento_erroneo": ejemplo.get("texto", ""),
                            "correccion": ejemplo.get("sugerencia", ""),
                            "explicacion": ejemplo.get("explicacion", "")
                        }
                        errores_formato[categoria].append(error_item)
        
        # Obtener análisis contextual
        analisis_contextual = resultado.get("analisis_contextual", {})
        
        # Mostrar línea de separación
        st.markdown("---")
        
        # Título y puntuación
        st.markdown("### Resultado de la corrección")
        
        # Mostrar puntuación
        st.metric("Puntuación", f"{puntuacion}/10")
        
        # Crear pestañas para las diferentes vistas
        tab_texto, tab_analisis, tab_detalles = st.tabs(["Texto con errores", "Análisis contextual", "Detalles y Exportación"])
        
        with tab_texto:
            st.info("Pasa el cursor sobre los errores resaltados para ver detalles y correcciones.")
            
            # Mostrar texto con errores resaltados usando la nueva función
            try:
                display_highlighted_text(texto_original, errores_formato)
            except Exception as e:
                logger.error(f"Error mostrando texto con errores resaltados: {str(e)}")
                # Mostrar versión de fallback
                st.markdown("#### Texto original")
                st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; overflow-y: auto;">{texto_original}</div>', unsafe_allow_html=True)
            
            # Mostrar texto corregido
            with st.expander("Ver texto corregido", expanded=True):
                st.markdown(f'<div class="texto-corregido">{texto_corregido}</div>', unsafe_allow_html=True)
        
        with tab_analisis:
            # Visualizar análisis contextual si está disponible
            if analisis_contextual:
                try:
                    # Obtener tipo de gráfico preferido
                    chart_type = get_chart_toggle()
                    
                    # Mostrar visualización del análisis contextual
                    display_contextual_analysis(analisis_contextual, chart_type)
                except Exception as e:
                    logger.error(f"Error mostrando análisis contextual: {str(e)}")
                    st.warning("No se pudo mostrar el análisis contextual avanzado. Mostrando versión simplificada.")
                    
                    # Mostrar versión simplificada como fallback
                    if isinstance(analisis_contextual, dict):
                        for categoria, datos in analisis_contextual.items():
                            if isinstance(datos, dict) and "puntuacion" in datos:
                                st.markdown(f"**{categoria.title()}:** {datos.get('puntuacion', 0)}/10")
                                st.markdown(datos.get('comentario', ''))
            else:
                st.info("No hay análisis contextual disponible para este texto.")
        
        with tab_detalles:
            # Mostrar resumen de errores
            if errores_json:
                st.markdown("#### Resumen de errores")
                
                # Crear tabla de errores
                data = []
                for error in errores_json:
                    data.append({
                        "Categoría": error.get("categoria", ""),
                        "Cantidad": error.get("cantidad", 0)
                    })
                
                # Mostrar tabla
                st.table(data)
                
                # Crear y mostrar gráfico de errores
                try:
                    # Preparar datos para el gráfico
                    categorias = [error.get("categoria", "") for error in errores_json]
                    valores = [error.get("cantidad", 0) for error in errores_json]
                    
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
                
                # Mostrar ejemplos específicos si están disponibles
                ejemplos_disponibles = any(len(error.get("ejemplos", [])) > 0 for error in errores_json)
                
                if ejemplos_disponibles:
                    with st.expander("Ver ejemplos específicos de errores", expanded=False):
                        for error in errores_json:
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
            
            # Mostrar consejo final con opción de audio
            if consejo_final:
                st.markdown("### 💡 Consejo final")
                st.success(consejo_final)
                
                # Generar audio del consejo final si ElevenLabs está disponible
                try:
                    audio_bytes = None
                    # Verificar si tenemos las claves configuradas
                    if "api_keys" in st.session_state and "elevenlabs" in st.session_state["api_keys"]:
                        api_keys = st.session_state["api_keys"]
                        if api_keys["elevenlabs"]["api_key"] and api_keys["elevenlabs"]["voice_id"]:
                            # Comprobar si podemos usar ElevenLabs (circuit breaker)
                            can_use_elevenlabs = True
                            if "circuit_breaker" in st.session_state:
                                can_use_elevenlabs = st.session_state.circuit_breaker.can_execute("elevenlabs")
                            
                            if can_use_elevenlabs:
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
            
            # Opciones de exportación
            with st.expander("Exportar corrección", expanded=False):
                # Preparar datos para exportación
                datos_exportacion = {
                    "texto_original": texto_original,
                    "texto_corregido": texto_corregido,
                    "retroalimentacion": retroalimentacion,
                    "errores": errores_json,
                    "puntuacion": puntuacion,
                    "consejo_final": consejo_final
                }
                
                # Mostrar opciones de exportación
                mostrar_opciones_exportacion(datos_exportacion, "correccion")
    
    except Exception as e:
        logger.error(f"Error mostrando resultado mejorado: {str(e)}")
        # En caso de error, mostrar la versión original
        mostrar_resultado_correccion(resultado, texto_original)

def mostrar_resultado_correccion(resultado, texto_original):
    """
    Muestra el resultado de la corrección en el formato tradicional (versión de respaldo).
    
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
        
        # Mostrar consejo final si está disponible
        if "consejo_final" in resultado and resultado["consejo_final"]:
            st.markdown("### 💡 Consejo final")
            st.success(resultado.get("consejo_final", ""))
        
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
                
                # Botones para interactuar con la corrección histórica
                col1, col2 = st.columns(2)
                
                with col1:
                    # Botón para ver detalles completos
                    if st.button("Ver detalles completos", key=f"detail_btn_{i}"):
                        # Mostrar resultado con visualización mejorada
                        mostrar_resultado_correccion_mejorado(correccion, correccion.get("texto_original", ""))
                
                with col2:
                    # Botón para cargar en el editor
                    if st.button("Editar esta corrección", key=f"edit_btn_{i}"):
                        # Guardar como última corrección para mostrarla en la pestaña de edición
                        set_session_var("ultima_correccion", correccion)
                        # Cambiar a la pestaña de nueva corrección
                        st.experimental_rerun()
                
                # Mostrar textos original y corregido
                with st.expander("Ver texto original y corregido", expanded=False):
                    st.markdown("##### Texto original")
                    st.markdown(f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px;">{correccion.get("texto_original", "")}</div>', unsafe_allow_html=True)
                    
                    st.markdown("##### Texto corregido")
                    st.markdown(f'<div class="texto-corregido">{correccion.get("texto_corregido", "")}</div>', unsafe_allow_html=True)
                
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