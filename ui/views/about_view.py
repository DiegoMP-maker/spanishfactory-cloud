#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista de acerca de
-----------------
Este módulo implementa la interfaz de usuario para la página de información
sobre la aplicación, sus características y creadores.
"""

import logging
import streamlit as st
import os
from PIL import Image

from config.settings import APP_VERSION, APP_NAME
from utils.file_utils import get_app_file_path

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista de acerca de.
    
    Returns:
        None
    """
    try:
        # Título de la página
        st.markdown("## ℹ️ Acerca de")
        
        # Cargar y mostrar el logo
        logo_path = get_app_file_path("assets/Spanish_FactorIA_Logo.png")
        
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(logo, width=200)
        
        # Información sobre la aplicación
        st.markdown(f"### {APP_NAME} v{APP_VERSION}")
        st.markdown("""
        **Textocorrector ELE** es una aplicación diseñada para ayudar a estudiantes y profesores 
        de Español como Lengua Extranjera (ELE) a mejorar sus habilidades lingüísticas mediante 
        herramientas de corrección, ejercicios personalizados, simulacros de examen y recursos didácticos.
        """)
        
        # Crear pestañas para organizar la información
        tab1, tab2, tab3, tab4 = st.tabs(["Características", "Tecnología", "Equipo", "Términos y condiciones"])
        
        with tab1:
            mostrar_caracteristicas()
        
        with tab2:
            mostrar_tecnologia()
        
        with tab3:
            mostrar_equipo()
        
        with tab4:
            mostrar_terminos()
    except Exception as e:
        logger.error(f"Error renderizando vista de acerca de: {str(e)}")
        st.error(f"Error al cargar la información: {str(e)}")

def mostrar_caracteristicas():
    """
    Muestra las características principales de la aplicación.
    
    Returns:
        None
    """
    try:
        st.markdown("### Características principales")
        
        # Corrección de textos
        st.markdown("#### 🖊️ Corrección de textos")
        st.markdown("""
        - Corrección inteligente adaptada al nivel del estudiante
        - Detección y clasificación de errores gramaticales, ortográficos, de vocabulario y cohesión
        - Explicaciones detalladas y sugerencias de mejora
        - Posibilidad de exportar las correcciones en diferentes formatos
        """)
        
        # Ejercicios personalizados
        st.markdown("#### 📝 Ejercicios personalizados")
        st.markdown("""
        - Generación de ejercicios adaptados al nivel y necesidades específicas
        - Múltiples tipos de ejercicios: gramática, vocabulario, comprensión, etc.
        - Corrección automática y retroalimentación personalizada
        - Seguimiento del progreso y áreas de mejora
        """)
        
        # Simulacro de examen
        st.markdown("#### 🏆 Simulacro de examen DELE")
        st.markdown("""
        - Simulacros de exámenes DELE para todos los niveles (A1-C2)
        - Estructura y formato similar a los exámenes oficiales
        - Evaluación detallada de cada destreza
        - Retroalimentación específica para mejorar en cada sección
        """)
        
        # Herramientas ELE
        st.markdown("#### 🛠️ Herramientas complementarias")
        st.markdown("""
        - Transcripción de textos manuscritos
        - Generador de consignas para actividades
        - Generador de imágenes para descripción
        - Recursos didácticos adaptados a cada nivel
        """)
        
        # Perfil y progreso
        st.markdown("#### 👤 Perfil y progreso")
        st.markdown("""
        - Seguimiento detallado del progreso individual
        - Estadísticas y gráficos de evolución
        - Análisis de errores recurrentes
        - Recomendaciones personalizadas basadas en el rendimiento
        """)
        
        # Plan de estudio
        st.markdown("#### 📚 Plan de estudio")
        st.markdown("""
        - Planes de estudio personalizados según nivel y objetivos
        - Actividades secuenciadas para una progresión óptima
        - Recursos recomendados para cada fase
        - Seguimiento del avance en el plan
        """)
    except Exception as e:
        logger.error(f"Error mostrando características: {str(e)}")
        st.error(f"Error al mostrar las características: {str(e)}")

def mostrar_tecnologia():
    """
    Muestra información sobre la tecnología utilizada en la aplicación.
    
    Returns:
        None
    """
    try:
        st.markdown("### Tecnología")
        st.markdown("""
        Textocorrector ELE utiliza tecnología avanzada de inteligencia artificial y procesamiento
        de lenguaje natural para ofrecer una experiencia personalizada y efectiva en el aprendizaje
        del español como lengua extranjera.
        """)
        
        # Componentes principales
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Frontend")
            st.markdown("""
            - **Streamlit**: Framework para aplicaciones web en Python
            - **Plotly**: Visualizaciones interactivas de datos
            - **Pandas**: Análisis y manipulación de datos
            - **HTML/CSS**: Estilizado y personalización de la interfaz
            """)
        
        with col2:
            st.markdown("#### Backend")
            st.markdown("""
            - **Python**: Lenguaje principal de desarrollo
            - **OpenAI API**: Modelos de lenguaje avanzados
            - **Firebase**: Almacenamiento y autenticación
            - **Circuit Breaker**: Patrón para gestión de fallos
            """)
        
        # Inteligencia Artificial
        st.markdown("#### Inteligencia Artificial")
        st.markdown("""
        La aplicación utiliza modelos avanzados de OpenAI, específicamente:
        
        - **GPT-4 Turbo**: para corrección de textos, generación de ejercicios y simulacros
        - **GPT-4 Vision**: para transcripción de textos manuscritos
        - **DALL-E 3**: para generación de imágenes para actividades de descripción
        
        Estos modelos han sido finamente ajustados con prompts especializados para el contexto
        de enseñanza y aprendizaje del español, con especial atención a las particularidades
        de cada nivel según el Marco Común Europeo de Referencia (MCER).
        """)
        
        # Arquitectura
        st.markdown("#### Arquitectura")
        st.markdown("""
        La aplicación sigue una arquitectura modular que permite:
        
        - **Escalabilidad**: Fácil adición de nuevas funcionalidades
        - **Mantenibilidad**: Organización clara del código y responsabilidades
        - **Resiliencia**: Gestión robusta de errores y fallos en servicios externos
        - **Seguridad**: Protección de datos de usuario y contenido generado
        """)
    except Exception as e:
        logger.error(f"Error mostrando tecnología: {str(e)}")
        st.error(f"Error al mostrar la información tecnológica: {str(e)}")

def mostrar_equipo():
    """
    Muestra información sobre el equipo de desarrollo.
    
    Returns:
        None
    """
    try:
        st.markdown("### Equipo")
        st.markdown("""
        Textocorrector ELE ha sido desarrollado por un equipo multidisciplinar de profesionales
        en lingüística, educación, ingeniería de software e inteligencia artificial.
        """)
        
        # Equipo ficticio para el ejemplo
        st.markdown("#### Dirección del proyecto")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **Dra. María Rodríguez**  
            *Directora académica*  
            Doctora en Lingüística Aplicada  
            Especialista en ELE
            """)
        
        with col2:
            st.markdown("""
            **Dr. Javier Martínez**  
            *Director técnico*  
            Doctor en Inteligencia Artificial  
            Especialista en PLN
            """)
        
        with col3:
            st.markdown("""
            **Dra. Ana López**  
            *Directora pedagógica*  
            Doctora en Educación  
            Especialista en Tecnología Educativa
            """)
        
        st.markdown("#### Equipo de desarrollo")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            **Carlos Sánchez**  
            *Ingeniero de Software*  
            Desarrollo backend
            """)
        
        with col2:
            st.markdown("""
            **Elena Torres**  
            *Ingeniera de Software*  
            Desarrollo frontend
            """)
        
        with col3:
            st.markdown("""
            **David García**  
            *Científico de datos*  
            Modelos de IA y análisis
            """)
        
        with col4:
            st.markdown("""
            **Lucía Fernández**  
            *Diseñadora UX/UI*  
            Experiencia de usuario
            """)
        
        st.markdown("#### Equipo académico")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **Miguel González**  
            *Profesor ELE*  
            Niveles A1-B1
            """)
        
        with col2:
            st.markdown("""
            **Patricia Díaz**  
            *Profesora ELE*  
            Niveles B2-C2
            """)
        
        with col3:
            st.markdown("""
            **Roberto Álvarez**  
            *Examinador DELE*  
            Evaluación y certificación
            """)
        
        # Agradecimientos
        st.markdown("#### Agradecimientos")
        st.markdown("""
        Queremos agradecer especialmente a:
        
        - **Instituto Cervantes** por su labor en la difusión del español y sus recursos didácticos
        - **Comunidad ELE** por sus valiosas aportaciones y retroalimentación
        - **Estudiantes beta** que participaron en las pruebas iniciales
        - **OpenAI** por el desarrollo de modelos avanzados de IA que hacen posible esta aplicación
        """)
        
        # Contacto
        st.markdown("#### Contacto")
        st.markdown("""
        Para consultas, sugerencias o reportar problemas:
        
        📧 **Email**: contacto@textocorrector.ele  
        🌐 **Web**: www.textocorrectorele.com  
        🐦 **Twitter**: @TextocorrectorELE
        """)
    except Exception as e:
        logger.error(f"Error mostrando equipo: {str(e)}")
        st.error(f"Error al mostrar la información del equipo: {str(e)}")

def mostrar_terminos():
    """
    Muestra los términos y condiciones de uso de la aplicación.
    
    Returns:
        None
    """
    try:
        st.markdown("### Términos y condiciones")
        
        # Términos de uso
        with st.expander("Términos de uso", expanded=True):
            st.markdown("""
            #### 1. Aceptación de los términos
            
            Al utilizar Textocorrector ELE, aceptas estos términos y condiciones en su totalidad.
            Si no estás de acuerdo con alguna parte de estos términos, no debes utilizar la aplicación.
            
            #### 2. Descripción del servicio
            
            Textocorrector ELE es una herramienta educativa diseñada para ayudar en el aprendizaje
            y la enseñanza del español como lengua extranjera. La aplicación ofrece corrección de textos,
            ejercicios personalizados, simulacros de examen y otras herramientas complementarias.
            
            #### 3. Cuenta de usuario
            
            Para acceder a todas las funcionalidades, es necesario crear una cuenta. Eres responsable
            de mantener la confidencialidad de tu contraseña y de todas las actividades realizadas con tu cuenta.
            
            #### 4. Uso adecuado
            
            Te comprometes a utilizar la aplicación únicamente con fines educativos y de acuerdo con
            las leyes aplicables. Queda prohibido:
            
            - Utilizar la aplicación para actividades ilegales o fraudulentas
            - Intentar acceder a áreas restringidas de la aplicación
            - Introducir virus o código malicioso
            - Utilizar la aplicación para generar contenido ofensivo o inapropiado
            
            #### 5. Propiedad intelectual
            
            Todo el contenido de Textocorrector ELE, incluyendo texto, gráficos, logotipos, iconos,
            imágenes y software, es propiedad de los creadores de la aplicación y está protegido por
            las leyes de propiedad intelectual.
            """)
        
        # Política de privacidad
        with st.expander("Política de privacidad"):
            st.markdown("""
            #### 1. Información recopilada
            
            Recopilamos la siguiente información:
            
            - Información de registro (nombre, email, nivel de español)
            - Contenido generado (textos, respuestas a ejercicios)
            - Datos de uso y progreso
            - Información técnica (tipo de dispositivo, navegador)
            
            #### 2. Uso de la información
            
            Utilizamos esta información para:
            
            - Proporcionar y mejorar nuestros servicios
            - Personalizar la experiencia del usuario
            - Analizar tendencias y patrones de uso
            - Comunicarnos con los usuarios sobre actualizaciones o cambios
            
            #### 3. Protección de datos
            
            Implementamos medidas de seguridad para proteger la información contra acceso,
            alteración, divulgación o destrucción no autorizados.
            
            #### 4. Compartir información
            
            No vendemos ni compartimos información personal con terceros, excepto:
            
            - Con proveedores de servicios que nos ayudan a operar la aplicación
            - Cuando sea requerido por ley
            - Con el consentimiento explícito del usuario
            """)
        
        # Limitación de responsabilidad
        with st.expander("Limitación de responsabilidad"):
            st.markdown("""
            #### 1. Precisión del contenido
            
            Aunque nos esforzamos por proporcionar información precisa y útil, no garantizamos
            la exactitud, integridad o actualidad del contenido. La aplicación se proporciona
            "tal cual" y "según disponibilidad".
            
            #### 2. Correcciones y sugerencias
            
            Las correcciones, ejercicios y simulacros generados por la aplicación son orientativos
            y pueden contener errores. Recomendamos contrastar siempre con fuentes adicionales,
            especialmente para contenido académico oficial.
            
            #### 3. Disponibilidad del servicio
            
            No garantizamos que la aplicación esté disponible de forma ininterrumpida o libre de errores.
            Nos reservamos el derecho de modificar, suspender o interrumpir cualquier aspecto del servicio
            en cualquier momento.
            
            #### 4. Limitación de daños
            
            En ningún caso seremos responsables por daños directos, indirectos, incidentales,
            especiales o consecuentes que resulten del uso o la imposibilidad de usar la aplicación.
            """)
        
        # Aviso legal
        st.markdown("""
        **Nota**: Esta aplicación se proporciona con fines educativos y la información
        contenida en estos términos es meramente ilustrativa. Para un proyecto real,
        sería necesario contar con términos y condiciones revisados por profesionales legales.
        """)
        
        # Versión y fecha
        st.markdown(f"""
        *Última actualización: Abril 2023*  
        *Versión de los términos: 1.0*  
        *Versión de la aplicación: {APP_VERSION}*
        """)
    except Exception as e:
        logger.error(f"Error mostrando términos: {str(e)}")
        st.error(f"Error al mostrar los términos y condiciones: {str(e)}")
