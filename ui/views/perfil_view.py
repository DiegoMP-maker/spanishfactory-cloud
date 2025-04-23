#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista de perfil y progreso
-------------------------
Este módulo implementa la interfaz de usuario para la visualización y edición del perfil
del usuario, así como el seguimiento de su progreso en el aprendizaje.
"""

import logging
import streamlit as st
from datetime import datetime

from features.perfil import (
    mostrar_perfil_usuario,
    mostrar_resumen_progreso,
    cargar_perfil_usuario
)
from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.main_layout import mostrar_mensaje_error

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista de perfil y progreso.
    
    Returns:
        None
    """
    try:
        # Título de la página
        st.markdown("## 👤 Mi perfil y progreso")
        
        # Verificar si hay un usuario logueado
        user_info = get_user_info()
        if not user_info:
            st.info("Debes iniciar sesión para ver tu perfil y progreso.")
            return
        
        # Si es usuario anónimo, mostrar mensaje especial
        if user_info.get('es_anonimo', False):
            st.warning("""
            Estás usando la aplicación como usuario anónimo. 
            Para guardar tu perfil y seguir tu progreso, necesitas crear una cuenta.
            """)
        
        # Cargar datos del perfil
        uid = user_info.get('uid')
        if uid and not user_info.get('es_anonimo', False):
            cargar_perfil_usuario(uid)
        
        # Crear pestañas
        tab1, tab2 = st.tabs(["Mi perfil", "Mi progreso"])
        
        with tab1:
            # Mostrar información del perfil
            mostrar_seccion_perfil()
        
        with tab2:
            # Mostrar información de progreso
            mostrar_seccion_progreso()
    except Exception as e:
        logger.error(f"Error renderizando vista de perfil: {str(e)}")
        st.error(f"Error al cargar la vista de perfil: {str(e)}")

def mostrar_seccion_perfil():
    """
    Muestra la sección del perfil del usuario.
    
    Returns:
        None
    """
    try:
        st.markdown("### Mi perfil")
        
        # Verificar si hay un usuario logueado
        user_info = get_user_info()
        if not user_info:
            st.info("Debes iniciar sesión para ver tu perfil.")
            return
        
        # Si es usuario anónimo, mostrar formulario de registro
        if user_info.get('es_anonimo', False):
            st.warning("""
            Estás usando la aplicación como usuario anónimo.
            Para guardar tu perfil, crea una cuenta:
            """)
            mostrar_formulario_registro_desde_anonimo(user_info)
            return
        
        # Mostrar perfil
        mostrar_perfil_usuario()
    except Exception as e:
        logger.error(f"Error mostrando sección de perfil: {str(e)}")
        st.error(f"Error al cargar el perfil: {str(e)}")

def mostrar_seccion_progreso():
    """
    Muestra la sección de progreso del usuario.
    
    Returns:
        None
    """
    try:
        st.markdown("### Mi progreso")
        
        # Verificar si hay un usuario logueado
        user_info = get_user_info()
        if not user_info:
            st.info("Debes iniciar sesión para ver tu progreso.")
            return
        
        # Si es usuario anónimo, mostrar mensaje
        if user_info.get('es_anonimo', False):
            st.info("""
            Como usuario anónimo, no se guarda tu progreso.
            Crea una cuenta para empezar a registrar tu progreso.
            """)
            return
        
        # Obtener periodo seleccionado (por defecto "semana")
        periodo = get_session_var("periodo_progreso", "semana")
        
        # Mostrar resumen de progreso
        nuevo_periodo = mostrar_resumen_progreso(user_info.get('uid'), periodo)
        
        # Actualizar periodo si cambió
        if nuevo_periodo != periodo:
            set_session_var("periodo_progreso", nuevo_periodo)
    except Exception as e:
        logger.error(f"Error mostrando sección de progreso: {str(e)}")
        st.error(f"Error al cargar el progreso: {str(e)}")

def mostrar_formulario_registro_desde_anonimo(user_info):
    """
    Muestra un formulario de registro para convertir un usuario anónimo en registrado.
    
    Args:
        user_info (dict): Información del usuario anónimo
        
    Returns:
        None
    """
    try:
        with st.form("form_registro_desde_anonimo"):
            st.subheader("Crear cuenta")
            
            # Campos del formulario
            nombre = st.text_input("Nombre", value=user_info.get('nombre', '').replace('Usuario', ''))
            apellido = st.text_input("Apellido", value=user_info.get('apellido', '').replace('Anónimo', ''))
            email = st.text_input("Email")
            password = st.text_input("Contraseña", type="password")
            confirm_password = st.text_input("Confirmar contraseña", type="password")
            
            # Nivel de español
            niveles = ["A1", "A2", "B1", "B2", "C1", "C2"]
            nivel = st.selectbox("Nivel de español", niveles, index=niveles.index(user_info.get('nivel', 'B1')))
            
            # Objetivo de aprendizaje
            objetivos = [
                "Mejorar en general", 
                "Preparar examen DELE", 
                "Uso profesional", 
                "Uso académico", 
                "Viajes", 
                "Otro"
            ]
            objetivo = st.selectbox("Objetivo principal", objetivos)
            
            # Lengua materna
            lengua_materna = st.text_input("Lengua materna")
            
            # Botón de envío
            submitted = st.form_submit_button("Crear cuenta")
            
            if submitted:
                # Validaciones
                if not nombre or not email or not password or not confirm_password:
                    mostrar_mensaje_error("Por favor, completa todos los campos obligatorios.", "warning")
                elif password != confirm_password:
                    mostrar_mensaje_error("Las contraseñas no coinciden.", "warning")
                elif len(password) < 6:
                    mostrar_mensaje_error("La contraseña debe tener al menos 6 caracteres.", "warning")
                else:
                    with st.spinner("Creando cuenta..."):
                        # Importar función de creación de usuario
                        from core.firebase_client import create_user
                        
                        # Preparar datos de usuario
                        user_data = {
                            'nombre': nombre,
                            'apellido': apellido,
                            'nivel': nivel,
                            'objetivo': objetivo,
                            'lengua_materna': lengua_materna,
                            'fecha_registro': datetime.now().isoformat(),
                            'ultimo_login': datetime.now().isoformat()
                        }
                        
                        # Intentar convertir el usuario anónimo en registrado
                        result = create_user(email, password, user_data)
                        
                        if result and 'error' not in result:
                            # Registro exitoso
                            st.success("¡Cuenta creada exitosamente!")
                            
                            # Actualizar información en sesión
                            new_user_info = {
                                'uid': result['uid'],
                                'email': email,
                                **user_data
                            }
                            
                            set_session_var('user_info', new_user_info)
                            
                            # Recargar la página
                            st.experimental_rerun()
                        else:
                            # Registro fallido
                            error_msg = result.get('error', 'Error al crear la cuenta. Inténtalo de nuevo.')
                            mostrar_mensaje_error(error_msg)
    except Exception as e:
        logger.error(f"Error mostrando formulario de registro desde anónimo: {str(e)}")
        st.error(f"Error al procesar el registro: {str(e)}")
