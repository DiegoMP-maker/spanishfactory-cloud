#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista de herramientas ELE
-------------------------
Este módulo implementa la interfaz de usuario para las herramientas complementarias
de apoyo al aprendizaje de español.
"""

import logging
import streamlit as st
import io
from PIL import Image

from features.herramientas.transcripcion import transcribir_imagen
from features.herramientas.consignas import generar_consigna, guardar_consigna, obtener_historial_consignas
from features.herramientas.imagenes import generar_imagen_dalle
from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.main_layout import mostrar_mensaje_error
from ui.sidebar import mostrar_filtros_herramientas
from utils.file_utils import mostrar_upload_area, procesar_imagen_subida

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista de herramientas ELE.
    
    Returns:
        None
    """
    try:
        # Título de la página
        st.markdown("## 🛠️ Herramientas ELE")
        st.markdown("""
        Herramientas complementarias para facilitar la enseñanza y el aprendizaje del español.
        Selecciona una herramienta en el menú lateral.
        """)
        
        # Obtener herramienta seleccionada del sidebar
        herramienta = mostrar_filtros_herramientas()
        
        # Renderizar la herramienta seleccionada
        if herramienta == "Transcripción de textos":
            mostrar_herramienta_transcripcion()
        elif herramienta == "Generador de consignas":
            mostrar_herramienta_consignas()
        elif herramienta == "Generador de imágenes":
            mostrar_herramienta_imagenes()
        else:
            st.warning("Selecciona una herramienta en el menú lateral.")
    except Exception as e:
        logger.error(f"Error renderizando vista de herramientas: {str(e)}")
        st.error(f"Error al cargar la vista de herramientas: {str(e)}")

def mostrar_herramienta_transcripcion():
    """
    Muestra la herramienta de transcripción de textos manuscritos.
    
    Returns:
        None
    """
    try:
        # Título y descripción
        st.markdown("### 🔤 Transcripción de textos manuscritos")
        st.markdown("""
        Esta herramienta te permite obtener la transcripción de textos manuscritos o impresos en español.
        Sube una imagen que contenga texto y obtén su contenido en formato editable.
        """)
        
        # Formulario para subir imagen
        uploaded_file = mostrar_upload_area(
            tipo="imagen",
            key="upload_transcripcion",
            help_text="Sube una imagen clara del texto. Formatos aceptados: JPG, PNG, GIF, BMP"
        )
        
        if uploaded_file:
            # Procesar imagen subida
            image, _ = procesar_imagen_subida(uploaded_file)
            
            if image:
                # Mostrar imagen
                st.image(image, caption="Imagen subida", use_column_width=True)
                
                # Botón para transcribir
                if st.button("Transcribir texto"):
                    with st.spinner("Transcribiendo texto... Esto puede tardar unos segundos."):
                        # Convertir imagen a bytes
                        img_byte_arr = io.BytesIO()
                        image.save(img_byte_arr, format='PNG')
                        img_byte_arr = img_byte_arr.getvalue()
                        
                        # Llamar a la función de transcripción
                        resultado = transcribir_imagen(img_byte_arr)
                        
                        if resultado and 'error' not in resultado:
                            # Mostrar resultado
                            st.markdown("### Texto transcrito:")
                            st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">{resultado["texto"]}</div>', unsafe_allow_html=True)
                            
                            # Guardar en sesión
                            set_session_var("ultima_transcripcion", resultado["texto"])
                            
                            # Botón para copiar al portapapeles (mediante JS)
                            st.markdown("""
                            <script>
                            function copyToClipboard(text) {
                                navigator.clipboard.writeText(text).then(function() {
                                    alert('Texto copiado al portapapeles');
                                }, function() {
                                    alert('Error al copiar');
                                });
                            }
                            </script>
                            """, unsafe_allow_html=True)
                            
                            # Botón para editar en corrección
                            if st.button("Editar en corrección"):
                                # Guardar en sesión para usar en corrección
                                set_session_var("texto_para_correccion", resultado["texto"])
                                # Cambiar a página de corrección
                                set_session_var("current_page", "correccion")
                                st.experimental_rerun()
                        else:
                            # Mostrar error
                            error_msg = resultado.get('error', 'Error al transcribir la imagen. Por favor, inténtalo con otra imagen.')
                            mostrar_mensaje_error(error_msg)
        
        # Mostrar última transcripción si existe
        ultima_transcripcion = get_session_var("ultima_transcripcion", None)
        if ultima_transcripcion and not uploaded_file:
            with st.expander("Última transcripción", expanded=False):
                st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">{ultima_transcripcion}</div>', unsafe_allow_html=True)
                
                # Botón para editar en corrección
                if st.button("Editar en corrección"):
                    # Guardar en sesión para usar en corrección
                    set_session_var("texto_para_correccion", ultima_transcripcion)
                    # Cambiar a página de corrección
                    set_session_var("current_page", "correccion")
                    st.experimental_rerun()
        
        # Consejos para mejor resultado
        with st.expander("Consejos para mejor resultado"):
            st.markdown("""
            - Asegúrate de que el texto sea claramente visible en la imagen
            - Evita fondos con mucho ruido o patrones
            - La iluminación uniforme mejora la precisión
            - Si el texto está escrito a mano, intenta que sea lo más legible posible
            - Para textos largos, considera dividirlos en múltiples imágenes
            """)
    except Exception as e:
        logger.error(f"Error mostrando herramienta de transcripción: {str(e)}")
        st.error(f"Error al cargar la herramienta de transcripción: {str(e)}")

def mostrar_herramienta_consignas():
    """
    Muestra la herramienta de generación de consignas para ejercicios.
    
    Returns:
        None
    """
    try:
        # Título y descripción
        st.markdown("### 📋 Generador de consignas")
        st.markdown("""
        Esta herramienta te permite generar consignas (instrucciones) para ejercicios y actividades
        de español como lengua extranjera, adaptadas al nivel y enfoque deseado.
        """)
        
        # Crear dos pestañas
        tab1, tab2 = st.tabs(["Generar consigna", "Historial de consignas"])
        
        with tab1:
            mostrar_generador_consignas()
        
        with tab2:
            mostrar_historial_consignas()
    except Exception as e:
        logger.error(f"Error mostrando herramienta de consignas: {str(e)}")
        st.error(f"Error al cargar la herramienta de consignas: {str(e)}")

def mostrar_generador_consignas():
    """
    Muestra el formulario para generar consignas.
    
    Returns:
        None
    """
    try:
        # Formulario para generar consigna
        with st.form("form_consigna"):
            # Selector de nivel
            nivel = st.selectbox(
                "Nivel de español",
                ["A1", "A2", "B1", "B2", "C1", "C2"]
            )
            
            # Selector de habilidad
            habilidad = st.selectbox(
                "Habilidad lingüística",
                [
                    "Expresión escrita",
                    "Expresión oral",
                    "Comprensión lectora",
                    "Comprensión auditiva",
                    "Interacción oral",
                    "Todas las habilidades"
                ]
            )
            
            # Selector de tipo de actividad
            tipo_actividad = st.selectbox(
                "Tipo de actividad",
                [
                    "Redacción",
                    "Debate/Discusión",
                    "Lectura y preguntas",
                    "Role-play",
                    "Ejercicio gramatical",
                    "Vocabulario",
                    "Pronunciación",
                    "Juego didáctico",
                    "Actividad cultural"
                ]
            )
            
            # Tema
            tema = st.text_input(
                "Tema específico (opcional)",
                placeholder="Ej: Viajes, comida, tecnología, rutina diaria, etc."
            )
            
            # Duración aproximada
            duracion = st.slider(
                "Duración aproximada (minutos)",
                min_value=5,
                max_value=60,
                value=20,
                step=5
            )
            
            # Instrucciones adicionales
            instrucciones = st.text_area(
                "Instrucciones adicionales (opcional)",
                placeholder="Ej: Incluir vocabulario específico, enfocarse en ciertos tiempos verbales, etc."
            )
            
            # Botón de envío
            submitted = st.form_submit_button("Generar consigna")
            
            if submitted:
                with st.spinner("Generando consigna... Esto puede tardar unos segundos."):
                    # Preparar parámetros
                    parametros = {
                        "nivel": nivel,
                        "habilidad": habilidad,
                        "tipo_actividad": tipo_actividad,
                        "tema": tema if tema else None,
                        "duracion": duracion,
                        "instrucciones": instrucciones if instrucciones else None
                    }
                    
                    # Obtener UID del usuario
                    user_info = get_user_info()
                    uid = user_info.get('uid', None) if user_info else None
                    
                    # Llamar a la función de generación
                    resultado = generar_consigna(parametros)
                    
                    if resultado and 'error' not in resultado:
                        # Mostrar resultado
                        st.markdown("### Consigna generada:")
                        st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">{resultado["consigna"]}</div>', unsafe_allow_html=True)
                        
                        # Guardar en sesión
                        set_session_var("ultima_consigna", resultado["consigna"])
                        
                        # Guardar en historial si hay usuario
                        if uid and not user_info.get('es_anonimo', False):
                            # Datos para guardar
                            datos_guardar = {
                                "uid": uid,
                                "consigna": resultado["consigna"],
                                "parametros": parametros,
                                "fecha": resultado.get("fecha", None)
                            }
                            
                            # Guardar en Firebase
                            guardar_consigna(datos_guardar)
                        
                        # Botón para usar en ejercicios
                        if st.button("Crear ejercicio con esta consigna"):
                            # Guardar en sesión para usar en ejercicios
                            set_session_var("consigna_para_ejercicio", resultado["consigna"])
                            # Cambiar a página de ejercicios
                            set_session_var("current_page", "ejercicios")
                            st.experimental_rerun()
                    else:
                        # Mostrar error
                        error_msg = resultado.get('error', 'Error al generar la consigna. Por favor, inténtalo de nuevo.')
                        mostrar_mensaje_error(error_msg)
        
        # Mostrar última consigna si existe
        ultima_consigna = get_session_var("ultima_consigna", None)
        if ultima_consigna and not submitted:
            with st.expander("Última consigna generada", expanded=False):
                st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">{ultima_consigna}</div>', unsafe_allow_html=True)
                
                # Botón para usar en ejercicios
                if st.button("Crear ejercicio con esta consigna"):
                    # Guardar en sesión para usar en ejercicios
                    set_session_var("consigna_para_ejercicio", ultima_consigna)
                    # Cambiar a página de ejercicios
                    set_session_var("current_page", "ejercicios")
                    st.experimental_rerun()
    except Exception as e:
        logger.error(f"Error mostrando generador de consignas: {str(e)}")
        st.error(f"Error al cargar el generador: {str(e)}")

def mostrar_historial_consignas():
    """
    Muestra el historial de consignas generadas.
    
    Returns:
        None
    """
    try:
        # Obtener UID del usuario
        user_info = get_user_info()
        uid = user_info.get('uid', None) if user_info else None
        
        if not uid or user_info.get('es_anonimo', False):
            st.info("Para guardar y ver tu historial de consignas, necesitas iniciar sesión o crear una cuenta.")
            return
        
        # Obtener historial
        with st.spinner("Cargando historial..."):
            consignas = obtener_historial_consignas(uid)
        
        if not consignas:
            st.info("No tienes consignas guardadas. Genera tu primera consigna para verla aquí.")
            return
        
        # Mostrar número total
        st.markdown(f"#### Historial de consignas ({len(consignas)})")
        
        # Mostrar cada consigna en un expander
        for i, consigna_data in enumerate(consignas):
            # Extraer datos
            consigna = consigna_data.get('consigna', '')
            parametros = consigna_data.get('parametros', {})
            fecha = consigna_data.get('fecha', '')
            
            # Formato para el título del expander
            nivel = parametros.get('nivel', 'No especificado')
            tipo = parametros.get('tipo_actividad', 'No especificado')
            tema = parametros.get('tema', 'General')
            
            titulo_expander = f"{tipo} - Nivel {nivel} - Tema: {tema}"
            
            with st.expander(titulo_expander):
                # Mostrar detalles
                st.markdown(f"**Fecha:** {fecha}")
                st.markdown(f"**Nivel:** {nivel}")
                st.markdown(f"**Habilidad:** {parametros.get('habilidad', 'No especificada')}")
                st.markdown(f"**Tipo:** {tipo}")
                
                # Mostrar consigna
                st.markdown("##### Consigna:")
                st.markdown(f'<div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px;">{consigna}</div>', unsafe_allow_html=True)
                
                # Botón para usar en ejercicios
                if st.button("Crear ejercicio con esta consigna", key=f"btn_ejercicio_{i}"):
                    # Guardar en sesión para usar en ejercicios
                    set_session_var("consigna_para_ejercicio", consigna)
                    # Cambiar a página de ejercicios
                    set_session_var("current_page", "ejercicios")
                    st.experimental_rerun()
    except Exception as e:
        logger.error(f"Error mostrando historial de consignas: {str(e)}")
        st.error(f"Error al cargar el historial: {str(e)}")

def mostrar_herramienta_imagenes():
    """
    Muestra la herramienta de generación de imágenes para descripción.
    
    Returns:
        None
    """
    try:
        # Título y descripción
        st.markdown("### 🖼️ Generador de imágenes para descripción")
        st.markdown("""
        Esta herramienta te permite generar imágenes para utilizar en ejercicios de descripción en español.
        Las imágenes pueden servir como estímulo visual para practicar vocabulario, tiempos verbales y expresiones.
        """)
        
        # Formulario para generar imagen
        with st.form("form_imagen"):
            # Selector de nivel
            nivel = st.selectbox(
                "Nivel de español",
                ["A1", "A2", "B1", "B2", "C1", "C2"]
            )
            
            # Tema o categoría
            categoria = st.selectbox(
                "Categoría",
                [
                    "Paisaje urbano",
                    "Paisaje natural",
                    "Situaciones cotidianas",
                    "Profesiones y trabajos",
                    "Comida y gastronomía",
                    "Viajes y transportes",
                    "Tecnología",
                    "Arte y cultura",
                    "Deportes",
                    "Festividades y celebraciones"
                ]
            )
            
            # Descripción de la imagen
            descripcion = st.text_area(
                "Descripción de la imagen",
                placeholder="Describe la imagen que quieres generar. Sé específico para obtener mejores resultados.",
                height=100
            )
            
            # Estilo artístico
            estilo = st.selectbox(
                "Estilo artístico",
                [
                    "Realista",
                    "Dibujo animado",
                    "Ilustración digital",
                    "Acuarela",
                    "Boceto",
                    "Minimalista",
                    "Fotorrealista"
                ]
            )
            
            # Opciones avanzadas
            with st.expander("Opciones avanzadas"):
                col1, col2 = st.columns(2)
                
                with col1:
                    resolucion = st.select_slider(
                        "Resolución",
                        options=["Baja", "Media", "Alta"],
                        value="Media"
                    )
                
                with col2:
                    elementos = st.text_input(
                        "Elementos adicionales (opcional)",
                        placeholder="Ej: personas, animales, objetos específicos..."
                    )
            
            # Botón de envío
            submitted = st.form_submit_button("Generar imagen")
            
            if submitted:
                if not descripcion:
                    st.warning("Por favor, proporciona una descripción para la imagen.")
                else:
                    with st.spinner("Generando imagen... Esto puede tardar hasta 30 segundos."):
                        # Preparar prompt completo
                        prompt = f"{descripcion}"
                        
                        if elementos:
                            prompt += f". Incluir los siguientes elementos: {elementos}"
                        
                        # Ajustar prompt según nivel y estilo
                        prompt += f". Estilo: {estilo}"
                        
                        # Convertir resolución a tamaño
                        if resolucion == "Baja":
                            size = "256x256"
                        elif resolucion == "Media":
                            size = "512x512"
                        else:
                            size = "1024x1024"
                        
                        # Llamar a la función de generación
                        resultado = generar_imagen_dalle(prompt, size)
                        
                        if resultado and 'error' not in resultado:
                            # Mostrar imagen generada
                            st.markdown("### Imagen generada:")
                            
                            # Mostrar imagen desde URL
                            st.image(resultado["url"], caption="Imagen generada con DALL-E", use_column_width=True)
                            
                            # Guardar en sesión
                            set_session_var("ultima_imagen_url", resultado["url"])
                            set_session_var("ultima_imagen_prompt", prompt)
                            
                            # Botón para crear ejercicio de descripción
                            if st.button("Crear ejercicio de descripción con esta imagen"):
                                # Preparar consigna automática
                                consigna_auto = f"""
                                ## Ejercicio de descripción - Nivel {nivel}
                                
                                ### Instrucciones:
                                1. Observa detenidamente la imagen.
                                2. Escribe una descripción detallada en español de lo que ves.
                                3. Utiliza el vocabulario y estructuras gramaticales apropiadas para tu nivel.
                                
                                **Tiempo recomendado:** 15-20 minutos
                                
                                **Sugerencias:**
                                - Describe los elementos principales de la imagen
                                - Menciona colores, formas y posiciones
                                - Si hay personas, describe su apariencia y posibles acciones
                                - Utiliza conectores para organizar tu descripción
                                - Revisa tu texto al finalizar
                                """
                                
                                # Guardar en sesión para usar en ejercicios
                                set_session_var("consigna_para_ejercicio", consigna_auto)
                                set_session_var("imagen_para_ejercicio", resultado["url"])
                                # Cambiar a página de ejercicios
                                set_session_var("current_page", "ejercicios")
                                st.experimental_rerun()
                            
                            # Botón para regenerar con prompt similar
                            if st.button("Regenerar con prompt similar"):
                                # Mostrar formulario con el mismo prompt
                                set_session_var("regenerar_imagen_prompt", prompt)
                                st.experimental_rerun()
                        else:
                            # Mostrar error
                            error_msg = resultado.get('error', 'Error al generar la imagen. Por favor, intenta con otra descripción.')
                            mostrar_mensaje_error(error_msg)
        
        # Verificar si hay un prompt para regenerar
        regenerar_prompt = get_session_var("regenerar_imagen_prompt", None)
        if regenerar_prompt:
            # Limpiar para no regenerar automáticamente
            set_session_var("regenerar_imagen_prompt", None)
            # Llenar el formulario con el prompt anterior
            st.info(f"Prompt anterior: {regenerar_prompt}")
        
        # Mostrar última imagen si existe
        ultima_imagen_url = get_session_var("ultima_imagen_url", None)
        ultima_imagen_prompt = get_session_var("ultima_imagen_prompt", None)
        
        if ultima_imagen_url and ultima_imagen_prompt and not submitted:
            with st.expander("Última imagen generada", expanded=False):
                st.image(ultima_imagen_url, caption="Última imagen generada", use_column_width=True)
                st.markdown(f"**Prompt:** {ultima_imagen_prompt}")
                
                # Botón para crear ejercicio de descripción
                if st.button("Crear ejercicio con esta imagen"):
                    # Preparar consigna automática para nivel B1 (por defecto)
                    consigna_auto = f"""
                    ## Ejercicio de descripción - Nivel B1
                    
                    ### Instrucciones:
                    1. Observa detenidamente la imagen.
                    2. Escribe una descripción detallada en español de lo que ves.
                    3. Utiliza el vocabulario y estructuras gramaticales apropiadas para tu nivel.
                    
                    **Tiempo recomendado:** 15-20 minutos
                    
                    **Sugerencias:**
                    - Describe los elementos principales de la imagen
                    - Menciona colores, formas y posiciones
                    - Si hay personas, describe su apariencia y posibles acciones
                    - Utiliza conectores para organizar tu descripción
                    - Revisa tu texto al finalizar
                    """
                    
                    # Guardar en sesión para usar en ejercicios
                    set_session_var("consigna_para_ejercicio", consigna_auto)
                    set_session_var("imagen_para_ejercicio", ultima_imagen_url)
                    # Cambiar a página de ejercicios
                    set_session_var("current_page", "ejercicios")
                    st.experimental_rerun()
        
        # Consejos para mejores resultados
        with st.expander("Consejos para mejores resultados"):
            st.markdown("""
            - **Sé específico** en tu descripción. "Un paisaje de montaña" dará resultados menos precisos que "Un paisaje de montañas nevadas con un lago azul y árboles verdes al atardecer".
            - **Menciona elementos clave** que quieres que aparezcan en la imagen.
            - **Especifica el estilo artístico** deseado para obtener resultados más coherentes.
            - **Adapta la complejidad** de la imagen al nivel de los estudiantes.
            - **Evita descripciones contradictorias** o demasiado abstractas.
            - Si no obtienes el resultado deseado, intenta **regenerar** con una descripción ligeramente modificada.
            """)
    except Exception as e:
        logger.error(f"Error mostrando herramienta de imágenes: {str(e)}")
        st.error(f"Error al cargar la herramienta de generación de imágenes: {str(e)}")
