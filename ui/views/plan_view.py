#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista del plan de estudio
------------------------
Este módulo implementa la interfaz de usuario para la visualización y seguimiento
del plan de estudio personalizado.
"""

import logging
import streamlit as st
from datetime import datetime, timedelta

from features.plan_estudio import (
    generar_plan_estudio,
    guardar_plan_estudio,
    obtener_plan_estudio,
    actualizar_progreso_actividad
)
from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.main_layout import mostrar_mensaje_error

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista del plan de estudio.
    
    Returns:
        None
    """
    try:
        # Título de la página
        st.markdown("## 📚 Plan de estudio")
        st.markdown("""
        Un plan de estudio personalizado para mejorar tu español de manera estructurada.
        El plan se adapta a tu nivel y objetivos, ofreciendo actividades y recursos específicos.
        """)
        
        # Verificar si hay un usuario logueado
        user_info = get_user_info()
        if not user_info:
            st.info("Debes iniciar sesión para acceder a tu plan de estudio personalizado.")
            return
        
        # Si es usuario anónimo, mostrar mensaje especial
        if user_info.get('es_anonimo', False):
            st.warning("""
            Estás usando la aplicación como usuario anónimo. 
            Para guardar tu plan de estudio y seguir tu progreso, necesitas crear una cuenta.
            """)
        
        # Verificar si ya hay un plan de estudio
        plan_existente = None
        if not user_info.get('es_anonimo', False):
            with st.spinner("Cargando plan de estudio..."):
                plan_existente = obtener_plan_estudio(user_info.get('uid'))
        
        # Si hay un plan existente, mostrarlo
        if plan_existente:
            mostrar_plan_estudio(plan_existente, user_info)
        else:
            # Si no hay plan, mostrar formulario para crear uno
            tab1, tab2 = st.tabs(["Crear plan de estudio", "Plan de ejemplo"])
            
            with tab1:
                mostrar_formulario_plan_estudio(user_info)
            
            with tab2:
                mostrar_plan_ejemplo()
    except Exception as e:
        logger.error(f"Error renderizando vista de plan de estudio: {str(e)}")
        st.error(f"Error al cargar la vista de plan de estudio: {str(e)}")

def mostrar_formulario_plan_estudio(user_info):
    """
    Muestra el formulario para crear un plan de estudio personalizado.
    
    Args:
        user_info (dict): Información del usuario
        
    Returns:
        None
    """
    try:
        st.markdown("### Crear plan de estudio personalizado")
        st.markdown("""
        Configura tu plan de estudio según tus necesidades y objetivos.
        El plan generado se adaptará a tu nivel actual y te guiará para mejorar progresivamente.
        """)
        
        with st.form("form_plan_estudio"):
            # Obtener nivel actual del usuario
            nivel_actual = user_info.get('nivel', 'B1')
            
            # Selector de nivel objetivo
            niveles = ["A1", "A2", "B1", "B2", "C1", "C2"]
            nivel_index = niveles.index(nivel_actual)
            
            # Mostrar solo niveles superiores al actual
            niveles_objetivo = niveles[nivel_index:]
            if len(niveles_objetivo) > 1:
                nivel_objetivo = st.selectbox(
                    "Nivel objetivo",
                    niveles_objetivo[1:],  # Excluir nivel actual
                    index=0
                )
            else:
                nivel_objetivo = "C2"
                st.info("Ya estás en el nivel más alto (C2). Tu plan se enfocará en perfeccionar tus habilidades.")
            
            # Duración del plan
            duracion = st.select_slider(
                "Duración del plan",
                options=["1 mes", "2 meses", "3 meses", "6 meses", "1 año"],
                value="3 meses"
            )
            
            # Intensidad
            intensidad = st.select_slider(
                "Intensidad",
                options=["Baja (2-3 horas/semana)", "Media (4-6 horas/semana)", "Alta (7-10 horas/semana)"],
                value="Media (4-6 horas/semana)"
            )
            
            # Objetivos específicos
            objetivos = st.multiselect(
                "Objetivos específicos",
                [
                    "Mejorar gramática",
                    "Ampliar vocabulario",
                    "Perfeccionar pronunciación",
                    "Mejorar expresión escrita",
                    "Mejorar comprensión lectora",
                    "Mejorar comprensión auditiva",
                    "Preparación para examen DELE",
                    "Español para fines profesionales",
                    "Español para viajes"
                ],
                default=["Mejorar gramática", "Ampliar vocabulario"]
            )
            
            # Áreas de interés
            areas_interes = st.multiselect(
                "Áreas de interés",
                [
                    "Literatura y cultura",
                    "Negocios y economía",
                    "Ciencia y tecnología",
                    "Arte y entretenimiento",
                    "Actualidad y política",
                    "Viajes y turismo",
                    "Gastronomía",
                    "Deportes",
                    "Historia",
                    "Naturaleza y medio ambiente"
                ],
                default=["Literatura y cultura", "Viajes y turismo"]
            )
            
            # Disponibilidad
            dias_disponibles = st.multiselect(
                "Días disponibles para estudiar",
                ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
                default=["Lunes", "Miércoles", "Viernes"]
            )
            
            # Observaciones adicionales
            observaciones = st.text_area(
                "Observaciones adicionales (opcional)",
                placeholder="Ej: Necesito enfocarme en el uso de tiempos verbales, prefiero actividades prácticas, etc."
            )
            
            # Botón de envío
            submitted = st.form_submit_button("Generar plan de estudio")
            
            if submitted:
                if not objetivos:
                    st.warning("Por favor, selecciona al menos un objetivo específico.")
                elif not areas_interes:
                    st.warning("Por favor, selecciona al menos un área de interés.")
                elif not dias_disponibles:
                    st.warning("Por favor, selecciona al menos un día disponible para estudiar.")
                else:
                    with st.spinner("Generando plan de estudio personalizado... Esto puede tardar unos segundos."):
                        # Mapear duración a número de semanas
                        duracion_semanas = {
                            "1 mes": 4,
                            "2 meses": 8,
                            "3 meses": 12,
                            "6 meses": 24,
                            "1 año": 52
                        }.get(duracion, 12)
                        
                        # Mapear intensidad a horas por semana
                        horas_semana = {
                            "Baja (2-3 horas/semana)": 3,
                            "Media (4-6 horas/semana)": 5,
                            "Alta (7-10 horas/semana)": 8
                        }.get(intensidad, 5)
                        
                        # Preparar parámetros
                        parametros = {
                            "nivel_actual": nivel_actual,
                            "nivel_objetivo": nivel_objetivo,
                            "duracion_semanas": duracion_semanas,
                            "horas_semana": horas_semana,
                            "objetivos": objetivos,
                            "areas_interes": areas_interes,
                            "dias_disponibles": dias_disponibles,
                            "observaciones": observaciones if observaciones else None
                        }
                        
                        # Obtener UID del usuario
                        uid = user_info.get('uid', None)
                        
                        # Llamar a la función de generación
                        resultado = generar_plan_estudio(parametros, uid)
                        
                        if resultado and 'error' not in resultado:
                            # Guardar plan en Firebase si hay usuario registrado
                            if uid and not user_info.get('es_anonimo', False):
                                # Datos para guardar
                                datos_guardar = {
                                    "uid": uid,
                                    "plan": resultado.get('plan', {}),
                                    "parametros": parametros,
                                    "fecha_creacion": datetime.now().isoformat(),
                                    "progreso": {}
                                }
                                
                                # Guardar en Firebase
                                guardar_plan_estudio(datos_guardar)
                            
                            # Recargar para mostrar el plan
                            st.experimental_rerun()
                        else:
                            # Mostrar error
                            error_msg = resultado.get('error', 'Error al generar el plan de estudio. Por favor, inténtalo de nuevo.')
                            mostrar_mensaje_error(error_msg)
    except Exception as e:
        logger.error(f"Error mostrando formulario de plan de estudio: {str(e)}")
        st.error(f"Error al cargar el formulario: {str(e)}")

def mostrar_plan_estudio(plan, user_info):
    """
    Muestra el plan de estudio y permite interactuar con él.
    
    Args:
        plan (dict): Plan de estudio
        user_info (dict): Información del usuario
        
    Returns:
        None
    """
    try:
        # Extraer datos del plan
        parametros = plan.get('parametros', {})
        plan_data = plan.get('plan', {})
        fecha_creacion = plan.get('fecha_creacion', datetime.now().isoformat())
        progreso = plan.get('progreso', {})
        
        # Convertir fecha de creación a datetime
        try:
            fecha_creacion_dt = datetime.fromisoformat(fecha_creacion.replace('Z', '+00:00'))
            fecha_creacion_str = fecha_creacion_dt.strftime("%d/%m/%Y")
        except:
            fecha_creacion_str = fecha_creacion
        
        # Mostrar encabezado
        st.markdown(f"### Tu plan de estudio personalizado")
        
        # Mostrar resumen del plan
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Nivel actual", parametros.get('nivel_actual', 'No especificado'))
        
        with col2:
            st.metric("Nivel objetivo", parametros.get('nivel_objetivo', 'No especificado'))
        
        with col3:
            duracion_semanas = parametros.get('duracion_semanas', 12)
            # Calcular fecha de finalización
            fecha_fin = fecha_creacion_dt + timedelta(weeks=duracion_semanas)
            fecha_fin_str = fecha_fin.strftime("%d/%m/%Y")
            st.metric("Fecha estimada de finalización", fecha_fin_str)
        
        # Mostrar progreso general
        total_actividades = sum(len(semana.get('actividades', [])) for semana in plan_data.get('semanas', []))
        actividades_completadas = sum(1 for actividad_id, estado in progreso.items() if estado.get('completada', False))
        
        if total_actividades > 0:
            porcentaje_completado = (actividades_completadas / total_actividades) * 100
        else:
            porcentaje_completado = 0
        
        st.progress(porcentaje_completado / 100)
        st.write(f"Progreso general: {porcentaje_completado:.1f}% ({actividades_completadas}/{total_actividades} actividades completadas)")
        
        # Crear pestañas para ver el plan por semanas o por temas
        tab1, tab2 = st.tabs(["Ver por semanas", "Ver por temas"])
        
        with tab1:
            mostrar_plan_por_semanas(plan_data, progreso, user_info)
        
        with tab2:
            mostrar_plan_por_temas(plan_data, progreso, user_info)
        
        # Botón para regenerar plan
        with st.expander("Opciones de plan", expanded=False):
            if st.button("Regenerar plan de estudio"):
                if st.session_state.get("confirm_regenerate", False):
                    # Resetear plan
                    if user_info and not user_info.get('es_anonimo', False):
                        # Eliminar plan actual de Firebase
                        # No implementamos la eliminación real, solo recargaremos para mostrar el formulario
                        pass
                    
                    st.session_state.pop("confirm_regenerate", None)
                    st.experimental_rerun()
                else:
                    # Pedir confirmación
                    st.session_state.confirm_regenerate = True
                    st.warning("¿Estás seguro de que deseas regenerar tu plan de estudio? Perderás todo el progreso actual.")
    except Exception as e:
        logger.error(f"Error mostrando plan de estudio: {str(e)}")
        st.error(f"Error al mostrar el plan: {str(e)}")

def mostrar_plan_por_semanas(plan_data, progreso, user_info):
    """
    Muestra el plan de estudio organizado por semanas.
    
    Args:
        plan_data (dict): Datos del plan
        progreso (dict): Progreso del usuario
        user_info (dict): Información del usuario
        
    Returns:
        None
    """
    try:
        # Obtener semanas
        semanas = plan_data.get('semanas', [])
        
        if not semanas:
            st.info("El plan no contiene semanas definidas.")
            return
        
        # Mostrar cada semana en un expander
        for i, semana in enumerate(semanas):
            # Calcular progreso de la semana
            actividades_semana = semana.get('actividades', [])
            total_act_semana = len(actividades_semana)
            completadas_semana = sum(1 for act in actividades_semana if progreso.get(f"actividad_{i}_{j}", {}).get('completada', False) for j, _ in enumerate(actividades_semana))
            
            if total_act_semana > 0:
                progreso_semana = f"{completadas_semana}/{total_act_semana} completadas"
            else:
                progreso_semana = "Sin actividades"
            
            # Título del expander
            titulo_expander = f"Semana {i+1}: {semana.get('titulo', 'Sin título')} ({progreso_semana})"
            
            with st.expander(titulo_expander, expanded=(i == 0)):
                # Mostrar descripción de la semana
                st.markdown(semana.get('descripcion', ''))
                
                # Mostrar objetivos de la semana
                objetivos_semana = semana.get('objetivos', [])
                if objetivos_semana:
                    st.markdown("#### Objetivos de la semana")
                    for objetivo in objetivos_semana:
                        st.markdown(f"- {objetivo}")
                
                # Mostrar actividades
                st.markdown("#### Actividades")
                
                for j, actividad in enumerate(actividades_semana):
                    # ID único para la actividad
                    actividad_id = f"actividad_{i}_{j}"
                    
                    # Obtener estado de la actividad
                    estado_actividad = progreso.get(actividad_id, {})
                    completada = estado_actividad.get('completada', False)
                    
                    # Mostrar actividad con casilla de verificación
                    col1, col2 = st.columns([0.1, 0.9])
                    
                    with col1:
                        # Mostrar checkbox para marcar como completada
                        nuevo_estado = st.checkbox(
                            "",
                            value=completada,
                            key=f"check_{actividad_id}"
                        )
                        
                        # Actualizar estado si cambió
                        if nuevo_estado != completada and user_info and not user_info.get('es_anonimo', False):
                            with st.spinner("Actualizando progreso..."):
                                # Actualizar en Firebase
                                actualizar_progreso_actividad(
                                    user_info.get('uid'),
                                    actividad_id,
                                    {'completada': nuevo_estado, 'fecha': datetime.now().isoformat()}
                                )
                    
                    with col2:
                        # Mostrar título y descripción de la actividad
                        if completada:
                            st.markdown(f"<s>**{actividad.get('titulo', 'Actividad')}**</s>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{actividad.get('titulo', 'Actividad')}**")
                        
                        st.markdown(actividad.get('descripcion', ''))
                        
                        # Mostrar recursos adicionales si hay
                        recursos = actividad.get('recursos', [])
                        if recursos:
                            with st.expander("Recursos", expanded=False):
                                for recurso in recursos:
                                    st.markdown(f"- {recurso}")
                        
                        # Mostrar duración estimada
                        duracion = actividad.get('duracion', '30 minutos')
                        st.markdown(f"*Duración estimada: {duracion}*")
                    
                    # Separador entre actividades
                    st.markdown("---")
    except Exception as e:
        logger.error(f"Error mostrando plan por semanas: {str(e)}")
        st.error(f"Error al mostrar el plan por semanas: {str(e)}")

def mostrar_plan_por_temas(plan_data, progreso, user_info):
    """
    Muestra el plan de estudio organizado por temas.
    
    Args:
        plan_data (dict): Datos del plan
        progreso (dict): Progreso del usuario
        user_info (dict): Información del usuario
        
    Returns:
        None
    """
    try:
        # Extraer temas del plan
        temas = {}
        
        # Recorrer semanas y actividades para agrupar por tema
        semanas = plan_data.get('semanas', [])
        
        for i, semana in enumerate(semanas):
            actividades = semana.get('actividades', [])
            
            for j, actividad in enumerate(actividades):
                # Obtener tema de la actividad
                tema = actividad.get('tema', 'General')
                
                # Crear entrada para el tema si no existe
                if tema not in temas:
                    temas[tema] = []
                
                # Añadir actividad con su identificador
                temas[tema].append({
                    'id': f"actividad_{i}_{j}",
                    'semana': i+1,
                    'actividad': actividad
                })
        
        if not temas:
            st.info("El plan no contiene temas definidos.")
            return
        
        # Mostrar cada tema en un expander
        for tema, actividades_tema in temas.items():
            # Calcular progreso del tema
            total_act_tema = len(actividades_tema)
            completadas_tema = sum(1 for act in actividades_tema if progreso.get(act['id'], {}).get('completada', False))
            
            if total_act_tema > 0:
                progreso_tema = f"{completadas_tema}/{total_act_tema} completadas"
            else:
                progreso_tema = "Sin actividades"
            
            # Título del expander
            titulo_expander = f"{tema} ({progreso_tema})"
            
            with st.expander(titulo_expander):
                # Mostrar actividades agrupadas por tema
                for actividad_info in actividades_tema:
                    # Extraer datos
                    actividad_id = actividad_info['id']
                    semana_num = actividad_info['semana']
                    actividad = actividad_info['actividad']
                    
                    # Obtener estado de la actividad
                    estado_actividad = progreso.get(actividad_id, {})
                    completada = estado_actividad.get('completada', False)
                    
                    # Mostrar actividad con casilla de verificación
                    col1, col2 = st.columns([0.1, 0.9])
                    
                    with col1:
                        # Mostrar checkbox para marcar como completada
                        nuevo_estado = st.checkbox(
                            "",
                            value=completada,
                            key=f"check_tema_{actividad_id}"
                        )
                        
                        # Actualizar estado si cambió
                        if nuevo_estado != completada and user_info and not user_info.get('es_anonimo', False):
                            with st.spinner("Actualizando progreso..."):
                                # Actualizar en Firebase
                                actualizar_progreso_actividad(
                                    user_info.get('uid'),
                                    actividad_id,
                                    {'completada': nuevo_estado, 'fecha': datetime.now().isoformat()}
                                )
                    
                    with col2:
                        # Mostrar título y descripción de la actividad
                        if completada:
                            st.markdown(f"<s>**{actividad.get('titulo', 'Actividad')}** (Semana {semana_num})</s>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{actividad.get('titulo', 'Actividad')}** (Semana {semana_num})")
                        
                        st.markdown(actividad.get('descripcion', ''))
                        
                        # Mostrar recursos adicionales si hay
                        recursos = actividad.get('recursos', [])
                        if recursos:
                            with st.expander("Recursos", expanded=False):
                                for recurso in recursos:
                                    st.markdown(f"- {recurso}")
                        
                        # Mostrar duración estimada
                        duracion = actividad.get('duracion', '30 minutos')
                        st.markdown(f"*Duración estimada: {duracion}*")
                    
                    # Separador entre actividades
                    st.markdown("---")
    except Exception as e:
        logger.error(f"Error mostrando plan por temas: {str(e)}")
        st.error(f"Error al mostrar el plan por temas: {str(e)}")

def mostrar_plan_ejemplo():
    """
    Muestra un ejemplo de plan de estudio.
    
    Returns:
        None
    """
    try:
        st.markdown("### Ejemplo de plan de estudio")
        st.markdown("""
        Este es un ejemplo de cómo se vería un plan de estudio personalizado.
        Para crear tu propio plan adaptado a tus necesidades, inicia sesión y utiliza la pestaña "Crear plan de estudio".
        """)
        
        # Mostrar resumen del plan de ejemplo
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Nivel actual", "B1")
        
        with col2:
            st.metric("Nivel objetivo", "B2")
        
        with col3:
            st.metric("Duración", "12 semanas")
        
        # Mostrar progreso general de ejemplo
        st.progress(0.35)
        st.write("Progreso general: 35% (14/40 actividades completadas)")
        
        # Mostrar ejemplo de semana
        with st.expander("Semana 1: Introducción y diagnóstico (2/5 completadas)", expanded=True):
            st.markdown("""
            Esta semana te servirá para establecer las bases del curso y evaluar tu nivel actual.
            Realizarás un diagnóstico detallado para identificar tus fortalezas y áreas de mejora.
            """)
            
            st.markdown("#### Objetivos de la semana")
            st.markdown("- Evaluar tu nivel actual de español")
            st.markdown("- Identificar áreas específicas para mejorar")
            st.markdown("- Familiarizarte con los recursos y metodología")
            
            st.markdown("#### Actividades")
            
            # Actividad 1 (completada)
            col1, col2 = st.columns([0.1, 0.9])
            with col1:
                st.checkbox("", value=True, disabled=True)
            with col2:
                st.markdown("<s>**Prueba de nivel completa**</s>", unsafe_allow_html=True)
                st.markdown("Realiza una prueba completa para evaluar tu nivel en todas las destrezas: comprensión y expresión oral, comprensión y expresión escrita.")
                st.markdown("*Duración estimada: 60 minutos*")
            
            st.markdown("---")
            
            # Actividad 2 (completada)
            col1, col2 = st.columns([0.1, 0.9])
            with col1:
                st.checkbox("", value=True, disabled=True)
            with col2:
                st.markdown("<s>**Escribir texto de presentación**</s>", unsafe_allow_html=True)
                st.markdown("Escribe un texto de presentación personal (200-250 palabras) que incluya: información personal, rutina diaria, aficiones, y planes para el futuro.")
                st.markdown("*Duración estimada: 30 minutos*")
            
            st.markdown("---")
            
            # Actividad 3 (no completada)
            col1, col2 = st.columns([0.1, 0.9])
            with col1:
                st.checkbox("", value=False, disabled=True)
            with col2:
                st.markdown("**Estudio de tiempos verbales**")
                st.markdown("Repasa los tiempos de indicativo (presente, pretérito perfecto, pretérito indefinido, pretérito imperfecto y futuro) y completa los ejercicios.")
                st.markdown("*Duración estimada: 45 minutos*")
            
            st.markdown("---")
        
        st.info("Este es solo un ejemplo. Tu plan personalizado incluirá actividades adaptadas a tu nivel y objetivos específicos.")
    except Exception as e:
        logger.error(f"Error mostrando plan de ejemplo: {str(e)}")
        st.error(f"Error al mostrar el ejemplo: {str(e)}")
