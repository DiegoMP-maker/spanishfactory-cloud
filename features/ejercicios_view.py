#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista de ejercicios personalizados
--------------------------------
Este módulo implementa la interfaz de usuario para la funcionalidad de ejercicios personalizados.
"""

import logging
import streamlit as st
import time
from datetime import datetime

from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.main_layout import mostrar_mensaje_error
from utils.text_processing import parse_ejercicio_structure

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista de ejercicios personalizados.
    
    Returns:
        None
    """
    try:
        # Título de la página
        st.markdown("## 📝 Ejercicios personalizados")
        st.markdown("""
        Genera ejercicios personalizados según tu nivel y necesidades específicas.
        Practica gramática, vocabulario, comprensión lectora y más.
        """)
        
        # Verificar si hay un ejercicio recomendado
        ejercicio_recomendado = get_session_var("ejercicio_recomendado", None)
        if ejercicio_recomendado:
            st.info(f"Ejercicio recomendado: {ejercicio_recomendado.get('tipo', 'gramática')} para nivel {ejercicio_recomendado.get('nivel', 'B1')}")
            # Limpiar la recomendación para no mostrarla de nuevo
            set_session_var("ejercicio_recomendado", None)
        
        # Verificar si hay una consigna para usar en ejercicios
        consigna_para_ejercicio = get_session_var("consigna_para_ejercicio", None)
        if consigna_para_ejercicio:
            st.info("Se utilizará la consigna generada anteriormente para crear el ejercicio.")
            # Limpiamos después de mostrarla
            set_session_var("consigna_para_ejercicio", None)
        
        # Verificar si hay una imagen para usar en ejercicios
        imagen_para_ejercicio = get_session_var("imagen_para_ejercicio", None)
        if imagen_para_ejercicio:
            st.image(imagen_para_ejercicio, caption="Imagen para el ejercicio", use_column_width=True)
            # Limpiamos después de mostrarla
            set_session_var("imagen_para_ejercicio", None)
        
        # Obtener información del usuario
        user_info = get_user_info()
        nivel_usuario = user_info.get('nivel', 'B1') if user_info else 'B1'
        
        # Crear pestañas
        tab1, tab2 = st.tabs(["Generar ejercicio", "Historial de ejercicios"])
        
        with tab1:
            # Formulario para generar ejercicio
            mostrar_formulario_ejercicio(nivel_usuario)
        
        with tab2:
            # Historial de ejercicios
            mostrar_historial_ejercicios()
    except Exception as e:
        logger.error(f"Error renderizando vista de ejercicios: {str(e)}")
        st.error(f"Error al cargar la vista de ejercicios: {str(e)}")

def mostrar_formulario_ejercicio(nivel_usuario):
    """
    Muestra el formulario para generar un ejercicio.
    
    Args:
        nivel_usuario (str): Nivel de español del usuario
        
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        
        # Formulario de ejercicio
        with st.form("form_ejercicio"):
            # Selector de nivel
            nivel = st.selectbox(
                "Nivel de español",
                ["A1", "A2", "B1", "B2", "C1", "C2"],
                index=["A1", "A2", "B1", "B2", "C1", "C2"].index(nivel_usuario)
            )
            
            # Selector de tipo de ejercicio
            tipo_ejercicio = st.selectbox(
                "Tipo de ejercicio",
                [
                    "Gramática", 
                    "Vocabulario", 
                    "Comprensión lectora", 
                    "Comprensión auditiva", 
                    "Expresión escrita",
                    "Mixto"
                ]
            )
            
            # Tema del ejercicio
            tema = st.text_input(
                "Tema específico (opcional)",
                placeholder="Ej: Viajes, Verbos irregulares, Preposiciones, etc."
            )
            
            # Selector de dificultad
            dificultad = st.select_slider(
                "Dificultad",
                options=["Fácil", "Media", "Difícil"],
                value="Media"
            )
            
            # Instrucciones específicas (opcional)
            instrucciones = st.text_area(
                "Instrucciones específicas (opcional)",
                placeholder="Ej: Incluir ejercicios de selección múltiple y completar frases, enfocarse en el uso del subjuntivo, etc.",
                height=100
            )
            
            # Botón de envío
            submitted = st.form_submit_button("Generar ejercicio")
            
            if submitted:
                # Placeholder para implementación futura
                with st.spinner("Generando ejercicio personalizado... Esto puede tardar unos segundos."):
                    time.sleep(2)  # Simular carga
                    
                    # Mostrar mensaje de función no implementada
                    st.info("La funcionalidad de generación de ejercicios está en desarrollo. Estará disponible pronto.")
                    
                    # NOTA: Aquí se implementaría la llamada a la función de generación de ejercicios
        
        # Mostrar ejemplo de ejercicio para propósitos de demostración
        with st.expander("Ver ejemplo de ejercicio", expanded=False):
            mostrar_ejemplo_ejercicio()
    except Exception as e:
        logger.error(f"Error mostrando formulario de ejercicio: {str(e)}")
        st.error(f"Error al cargar el formulario: {str(e)}")

def mostrar_ejemplo_ejercicio():
    """
    Muestra un ejemplo de ejercicio para fines de demostración.
    
    Returns:
        None
    """
    try:
        st.markdown("### Ejercicio de ejemplo: El pretérito indefinido vs. imperfecto")
        
        st.markdown("""
        **Instrucciones**: Lee el siguiente texto y completa los espacios en blanco con la forma correcta 
        del verbo en pretérito indefinido o pretérito imperfecto.
        """)
        
        st.markdown("""
        Cuando yo **era** (ser) pequeño, **vivía** (vivir) en una casa cerca del mar. 
        Un día, mientras yo **jugaba** (jugar) en la playa, **vi** (ver) algo brillante en la arena. 
        **Era** (ser) una pequeña botella de vidrio con un mensaje dentro. 
        Inmediatamente **corrí** (correr) hacia ella y la **recogí** (recoger). 
        Mis padres no me **creían** (creer) cuando les **conté** (contar) lo que **había encontrado** (encontrar).
        """)
        
        with st.form("form_ejemplo"):
            respuesta1 = st.selectbox(
                "1. Cuando yo _____ pequeño, vivía en una casa cerca del mar.",
                ["fui", "era", "seré", "estuve"]
            )
            
            respuesta2 = st.selectbox(
                "2. Un día, mientras yo _____ en la playa, vi algo brillante en la arena.",
                ["jugué", "jugaré", "jugaba", "juego"]
            )
            
            respuesta3 = st.selectbox(
                "3. Inmediatamente _____ hacia ella y la recogí.",
                ["corría", "corro", "corrí", "correré"]
            )
            
            st.form_submit_button("Verificar respuestas")
        
        # Mostrar retroalimentación simulada
        st.markdown("#### Retroalimentación:")
        st.markdown("Has contestado correctamente 2 de 3 preguntas. ¡Buen trabajo!")
        
        st.markdown("""
        **Explicación**: 
        - Pregunta 1: "era" es correcto porque describe una situación continuada en el pasado.
        - Pregunta 2: "jugaba" es correcto porque describe una acción en progreso interrumpida por otra.
        - Pregunta 3: "corrí" es correcto porque describe una acción puntual y completa en el pasado.
        """)
    except Exception as e:
        logger.error(f"Error mostrando ejemplo de ejercicio: {str(e)}")
        st.error(f"Error al mostrar el ejemplo: {str(e)}")

def mostrar_historial_ejercicios():
    """
    Muestra el historial de ejercicios realizados por el usuario.
    
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        uid = user_info.get('uid', None) if user_info else None
        
        if not uid or user_info.get('es_anonimo', False):
            st.info("Para guardar y ver tu historial de ejercicios, necesitas iniciar sesión o crear una cuenta.")
            return
        
        # Placeholder para implementación futura
        st.info("La función de historial de ejercicios está en desarrollo. Estará disponible pronto.")
        
        # Ejemplo de historial para demostración
        st.markdown("#### Ejemplo de historial")
        
        # Crear tabla de ejemplo
        data = [
            {"Fecha": "20/04/2023", "Tipo": "Gramática", "Tema": "Pretérito/Imperfecto", "Puntuación": "8/10"},
            {"Fecha": "18/04/2023", "Tipo": "Vocabulario", "Tema": "Comida", "Puntuación": "9/10"},
            {"Fecha": "15/04/2023", "Tipo": "Comprensión", "Tema": "Texto narrativo", "Puntuación": "7/10"}
        ]
        
        st.table(data)
    except Exception as e:
        logger.error(f"Error mostrando historial de ejercicios: {str(e)}")
        st.error(f"Error al cargar el historial: {str(e)}")
