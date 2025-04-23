#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pantalla de login/bienvenida
----------------------------
Este módulo contiene funciones para gestionar la autenticación y pantalla de bienvenida.
"""

import logging
import streamlit as st
from datetime import datetime
import re

from core.firebase_client import login_user, create_user, get_user_data
from core.session_manager import set_session_var, init_session_state
from ui.main_layout import mostrar_mensaje_error

logger = logging.getLogger(__name__)

def mostrar_login():
    """
    Muestra el formulario de login y registro.
    
    Returns:
        bool: True si el usuario está autenticado, False en caso contrario
    """
    try:
        # Inicializar estado de sesión si es necesario
        init_session_state()
        
        # Verificar si ya hay un usuario logueado
        if 'user_info' in st.session_state and st.session_state['user_info']:
            return True
        
        # Título
        st.markdown("<h2>Iniciar sesión</h2>", unsafe_allow_html=True)
        
        # Tabs para login y registro
        tab1, tab2 = st.tabs(["Iniciar sesión", "Registrarse"])
        
        with tab1:
            # Formulario de login
            with st.form("login_form"):
                st.subheader("Inicia sesión con tu cuenta")
                
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Contraseña", type="password", key="login_password")
                
                submitted = st.form_submit_button("Iniciar sesión")
                
                if submitted:
                    if not email or not password:
                        mostrar_mensaje_error("Por favor, completa todos los campos.", "warning")
                    else:
                        # Intentar login
                        with st.spinner("Iniciando sesión..."):
                            result = login_user(email, password)
                            
                            if result and 'error' not in result:
                                # Login exitoso, obtener datos del usuario
                                user_data = get_user_data(result['uid'])
                                
                                # Guardar info en el estado de sesión
                                user_info = {
                                    'uid': result['uid'],
                                    'email': email,
                                    **user_data
                                }
                                
                                set_session_var('user_info', user_info)
                                
                                # Mostrar mensaje de éxito
                                st.success("¡Login exitoso!")
                                
                                # Recargar para redirigir a la página principal
                                st.experimental_rerun()
                                return True
                            else:
                                # Login fallido
                                error_msg = result.get('error', 'Error al iniciar sesión. Verifica tus credenciales.')
                                mostrar_mensaje_error(error_msg)
        
        with tab2:
            # Formulario de registro
            with st.form("register_form"):
                st.subheader("Crea una nueva cuenta")
                
                nombre = st.text_input("Nombre", key="reg_nombre")
                apellido = st.text_input("Apellido", key="reg_apellido")
                email = st.text_input("Email", key="reg_email")
                password = st.text_input("Contraseña", type="password", key="reg_password")
                confirm_password = st.text_input("Confirmar contraseña", type="password", key="reg_confirm")
                
                # Nivel de español
                nivel = st.selectbox(
                    "Nivel de español", 
                    ["A1", "A2", "B1", "B2", "C1", "C2"],
                    key="reg_nivel"
                )
                
                # Objetivo
                objetivo = st.selectbox(
                    "Objetivo principal", 
                    ["Mejorar en general", "Preparar examen DELE", "Uso profesional", "Uso académico", "Viajes", "Otro"],
                    key="reg_objetivo"
                )
                
                # Lengua materna
                lengua_materna = st.text_input("Lengua materna", key="reg_lengua")
                
                submitted = st.form_submit_button("Registrarse")
                
                if submitted:
                    # Validaciones
                    if not nombre or not email or not password or not confirm_password:
                        mostrar_mensaje_error("Por favor, completa todos los campos obligatorios.", "warning")
                    elif password != confirm_password:
                        mostrar_mensaje_error("Las contraseñas no coinciden.", "warning")
                    elif len(password) < 6:
                        mostrar_mensaje_error("La contraseña debe tener al menos 6 caracteres.", "warning")
                    elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                        mostrar_mensaje_error("Por favor, introduce un email válido.", "warning")
                    else:
                        # Intentar registro
                        with st.spinner("Creando cuenta..."):
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
                            
                            result = create_user(email, password, user_data)
                            
                            if result and 'error' not in result:
                                # Registro exitoso, guardar info en el estado de sesión
                                user_info = {
                                    'uid': result['uid'],
                                    'email': email,
                                    **user_data
                                }
                                
                                set_session_var('user_info', user_info)
                                
                                # Mostrar mensaje de éxito
                                st.success("¡Cuenta creada exitosamente!")
                                
                                # Recargar para redirigir a la página principal
                                st.experimental_rerun()
                                return True
                            else:
                                # Registro fallido
                                error_msg = result.get('error', 'Error al crear la cuenta. Inténtalo de nuevo.')
                                mostrar_mensaje_error(error_msg)
        
        # Opción para continuar sin cuenta
        st.markdown("""
        <div style="text-align: center; margin-top: 20px;">
            <p>o</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Continuar sin cuenta", type="primary"):
            # Crear usuario anónimo
            user_info = {
                'uid': f"anon_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'email': "anonimo@textocorrector.ele",
                'nombre': "Usuario",
                'apellido': "Anónimo",
                'nivel': "B1",
                'es_anonimo': True,
                'fecha_registro': datetime.now().isoformat()
            }
            
            set_session_var('user_info', user_info)
            
            # Recargar para redirigir a la página principal
            st.experimental_rerun()
            return True
        
        # Información adicional
        with st.expander("¿Por qué crear una cuenta?"):
            st.markdown("""
            Crear una cuenta te permite:
            - **Guardar tu historial** de correcciones y ejercicios
            - **Realizar seguimiento** de tu progreso
            - **Personalizar** tu experiencia según tu nivel
            - **Sincronizar** tu información entre dispositivos
            
            Tus datos están seguros y no se comparten con terceros.
            """)
        
        return False
    except Exception as e:
        logger.error(f"Error mostrando login: {str(e)}")
        # Mostrar error y devolver False
        st.error(f"Error en la pantalla de login: {str(e)}")
        return False

def mostrar_logout():
    """
    Muestra el botón de logout y gestiona el cierre de sesión.
    
    Returns:
        bool: True si el usuario ha cerrado sesión, False en caso contrario
    """
    try:
        if st.sidebar.button("Cerrar sesión"):
            # Limpiar información de usuario
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            
            # Recargar para volver a la pantalla de login
            st.experimental_rerun()
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error en logout: {str(e)}")
        return False

def mostrar_info_usuario():
    """
    Muestra la información del usuario en la sidebar.
    
    Returns:
        None
    """
    try:
        if 'user_info' in st.session_state and st.session_state['user_info']:
            user_info = st.session_state['user_info']
            
            # Mostrar información
            st.sidebar.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 20px;">
                <p><strong>{user_info.get('nombre', '')} {user_info.get('apellido', '')}</strong></p>
                <p style="font-size: 0.9rem; color: #666;">{user_info.get('email', '')}</p>
                <p style="font-size: 0.9rem;">Nivel: <strong>{user_info.get('nivel', 'No especificado')}</strong></p>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error mostrando info de usuario: {str(e)}")
