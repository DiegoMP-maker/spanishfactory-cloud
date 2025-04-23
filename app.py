#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Textocorrector ELE - Punto de entrada principal
------------------------------------------------
Este archivo es el punto de entrada principal de la aplicación Textocorrector ELE.
Configura la interfaz de usuario y gestiona la navegación entre las diferentes vistas.
"""

import logging
import streamlit as st
import os
import sys
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Importar componentes principales
from ui.main_layout import crear_layout_principal, mostrar_pie_pagina
from ui.sidebar import configurar_sidebar
from ui.login import mostrar_login

# Importar vistas
from ui.views.correccion_view import render_view as render_correccion

# Temporalmente, vamos a definir funciones placeholder para las otras vistas
# hasta que se implementen correctamente
def render_ejercicios():
    st.markdown("## 📝 Ejercicios personalizados")
    st.info("La vista de ejercicios personalizados está en desarrollo. Estará disponible pronto.")

def render_simulacro():
    st.markdown("## 🏆 Simulacro de examen")
    st.info("La vista de simulacro de examen está en desarrollo. Estará disponible pronto.")

def render_herramientas():
    st.markdown("## 🛠️ Herramientas ELE")
    st.info("La vista de herramientas está en desarrollo. Estará disponible pronto.")

def render_perfil():
    st.markdown("## 👤 Mi perfil y progreso")
    st.info("La vista de perfil y progreso está en desarrollo. Estará disponible pronto.")

def render_plan():
    st.markdown("## 📚 Plan de estudio")
    st.info("La vista de plan de estudio está en desarrollo. Estará disponible pronto.")

def render_about():
    st.markdown("## ℹ️ Acerca de")
    st.info("La vista de información está en desarrollo. Estará disponible pronto.")

def main():
    """
    Función principal que inicia la aplicación.
    
    Returns:
        None
    """
    try:
        # Crear layout principal
        crear_layout_principal()
        
        # Mostrar pantalla de login si no hay usuario logueado
        usuario_logueado = mostrar_login()
        
        if usuario_logueado:
            # Configurar sidebar y obtener página seleccionada
            pagina_actual = configurar_sidebar()
            
            # Renderizar la vista correspondiente
            if pagina_actual == "correccion":
                render_correccion()
            elif pagina_actual == "ejercicios":
                render_ejercicios()
            elif pagina_actual == "simulacro":
                render_simulacro()
            elif pagina_actual == "herramientas":
                render_herramientas()
            elif pagina_actual == "perfil":
                render_perfil()
            elif pagina_actual == "plan":
                render_plan()
            elif pagina_actual == "about":
                render_about()
            
            # Mostrar pie de página
            mostrar_pie_pagina()
    except Exception as e:
        logger.error(f"Error en la función principal: {str(e)}")
        st.error(f"Ha ocurrido un error inesperado: {str(e)}")
        
        # Botón para reiniciar la aplicación
        if st.button("Reiniciar aplicación"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_rerun()

if __name__ == "__main__":
    main()