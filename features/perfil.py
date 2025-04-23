#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de gestión del perfil y progreso del estudiante
-----------------------------------------------------
Este módulo contiene funciones para gestionar el perfil del estudiante,
su progreso y estadísticas de aprendizaje.
"""

import logging
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

from core.firebase_client import (
    get_user_data, 
    update_user_data, 
    get_correcciones_usuario,
    get_simulacros_usuario,
    get_ejercicios_usuario
)
from core.session_manager import get_session_var, set_session_var, get_user_info
from utils.analytics import calcular_metricas_progreso

logger = logging.getLogger(__name__)

def cargar_perfil_usuario(user_id):
    """
    Carga los datos del perfil del usuario desde Firebase.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Datos del perfil del usuario
    """
    try:
        # Obtener datos del usuario
        user_data = get_user_data(user_id)
        
        if not user_data:
            logger.warning(f"No se encontraron datos para el usuario {user_id}")
            return {}
        
        # Guardar en sesión
        set_session_var("perfil_usuario", user_data)
        
        return user_data
    except Exception as e:
        logger.error(f"Error cargando perfil de usuario: {str(e)}")
        return {}

def actualizar_perfil_usuario(user_id, datos_actualizados):
    """
    Actualiza los datos del perfil del usuario en Firebase.
    
    Args:
        user_id (str): ID del usuario
        datos_actualizados (dict): Nuevos datos del perfil
        
    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario
    """
    try:
        # Actualizar en Firebase
        success = update_user_data(user_id, datos_actualizados)
        
        if success:
            # Actualizar también en la sesión
            perfil_actual = get_session_var("perfil_usuario", {})
            perfil_actualizado = {**perfil_actual, **datos_actualizados}
            set_session_var("perfil_usuario", perfil_actualizado)
            
        return success
    except Exception as e:
        logger.error(f"Error actualizando perfil de usuario: {str(e)}")
        return False

def obtener_estadisticas_usuario(user_id, periodo=None):
    """
    Obtiene estadísticas de uso y progreso del usuario.
    
    Args:
        user_id (str): ID del usuario
        periodo (str, opcional): Periodo para filtrar (semana, mes, trimestre)
        
    Returns:
        dict: Estadísticas del usuario
    """
    try:
        # Definir fechas para filtro
        fecha_fin = datetime.now()
        if periodo == "semana":
            fecha_inicio = fecha_fin - timedelta(days=7)
        elif periodo == "mes":
            fecha_inicio = fecha_fin - timedelta(days=30)
        elif periodo == "trimestre":
            fecha_inicio = fecha_fin - timedelta(days=90)
        else:
            fecha_inicio = fecha_fin - timedelta(days=365)  # Por defecto último año
        
        # Obtener datos de actividad
        correcciones = get_correcciones_usuario(user_id)
        simulacros = get_simulacros_usuario(user_id)
        ejercicios = get_ejercicios_usuario(user_id)
        
        # Filtrar por fecha si es necesario
        if periodo:
            # Convertir fechas de string a datetime
            for correccion in correcciones:
                if 'fecha' in correccion and isinstance(correccion['fecha'], str):
                    correccion['fecha'] = datetime.fromisoformat(correccion['fecha'].replace('Z', '+00:00'))
            
            for simulacro in simulacros:
                if 'fecha' in simulacro and isinstance(simulacro['fecha'], str):
                    simulacro['fecha'] = datetime.fromisoformat(simulacro['fecha'].replace('Z', '+00:00'))
            
            for ejercicio in ejercicios:
                if 'fecha' in ejercicio and isinstance(ejercicio['fecha'], str):
                    ejercicio['fecha'] = datetime.fromisoformat(ejercicio['fecha'].replace('Z', '+00:00'))
            
            # Aplicar filtro
            correcciones = [c for c in correcciones if c.get('fecha', fecha_fin) >= fecha_inicio]
            simulacros = [s for s in simulacros if s.get('fecha', fecha_fin) >= fecha_inicio]
            ejercicios = [e for e in ejercicios if e.get('fecha', fecha_fin) >= fecha_inicio]
        
        # Calcular métricas
        metricas = calcular_metricas_progreso(correcciones, simulacros, ejercicios)
        
        return {
            "total_correcciones": len(correcciones),
            "total_simulacros": len(simulacros),
            "total_ejercicios": len(ejercicios),
            "metricas": metricas
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de usuario: {str(e)}")
        return {
            "total_correcciones": 0,
            "total_simulacros": 0,
            "total_ejercicios": 0,
            "metricas": {}
        }

def generar_grafico_progreso(user_id, tipo="errores", periodo=None):
    """
    Genera un gráfico de progreso del usuario.
    
    Args:
        user_id (str): ID del usuario
        tipo (str): Tipo de gráfico (errores, actividad, nivel)
        periodo (str, opcional): Periodo para filtrar (semana, mes, trimestre)
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico
    """
    try:
        # Obtener datos
        correcciones = get_correcciones_usuario(user_id)
        
        if not correcciones:
            # Devolver gráfico vacío
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos suficientes para mostrar el progreso",
                xaxis_title="Fecha",
                yaxis_title="Valor",
                template="plotly_white"
            )
            return fig
        
        # Filtrar por fecha si es necesario
        if periodo:
            fecha_fin = datetime.now()
            if periodo == "semana":
                fecha_inicio = fecha_fin - timedelta(days=7)
            elif periodo == "mes":
                fecha_inicio = fecha_fin - timedelta(days=30)
            elif periodo == "trimestre":
                fecha_inicio = fecha_fin - timedelta(days=90)
            else:
                fecha_inicio = fecha_fin - timedelta(days=365)
            
            # Convertir fechas y filtrar
            for correccion in correcciones:
                if 'fecha' in correccion and isinstance(correccion['fecha'], str):
                    correccion['fecha'] = datetime.fromisoformat(correccion['fecha'].replace('Z', '+00:00'))
            
            correcciones = [c for c in correcciones if c.get('fecha', fecha_fin) >= fecha_inicio]
        
        # Crear DataFrame
        correcciones_procesadas = []
        for correccion in correcciones:
            fecha = correccion.get('fecha')
            if isinstance(fecha, str):
                fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
            
            # Para gráfico de errores
            if tipo == "errores" and 'errores' in correccion:
                for error in correccion.get('errores', []):
                    correcciones_procesadas.append({
                        'fecha': fecha,
                        'categoria': error.get('categoria', 'Desconocido'),
                        'cantidad': error.get('cantidad', 0)
                    })
            
            # Para gráfico de actividad
            elif tipo == "actividad":
                palabras = len(correccion.get('texto_original', '').split())
                correcciones_procesadas.append({
                    'fecha': fecha,
                    'tipo': 'Palabras escritas',
                    'cantidad': palabras
                })
            
            # Para gráfico de nivel
            elif tipo == "nivel" and 'puntuacion' in correccion:
                correcciones_procesadas.append({
                    'fecha': fecha,
                    'nivel': correccion.get('nivel', 'A1'),
                    'puntuacion': correccion.get('puntuacion', 0)
                })
        
        # Si no hay datos procesados, devolver gráfico vacío
        if not correcciones_procesadas:
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos suficientes para mostrar el progreso",
                xaxis_title="Fecha",
                yaxis_title="Valor",
                template="plotly_white"
            )
            return fig
        
        # Crear DataFrame
        df = pd.DataFrame(correcciones_procesadas)
        
        # Generar gráfico según el tipo
        if tipo == "errores":
            # Agrupar por fecha y categoría
            df_grouped = df.groupby(['fecha', 'categoria'])['cantidad'].sum().reset_index()
            
            # Crear gráfico de líneas
            fig = px.line(
                df_grouped, 
                x='fecha', 
                y='cantidad', 
                color='categoria',
                title='Evolución de Errores por Categoría',
                labels={'fecha': 'Fecha', 'cantidad': 'Cantidad de Errores', 'categoria': 'Categoría'}
            )
        
        elif tipo == "actividad":
            # Agrupar por fecha
            df_grouped = df.groupby(['fecha', 'tipo'])['cantidad'].sum().reset_index()
            
            # Crear gráfico de barras
            fig = px.bar(
                df_grouped, 
                x='fecha', 
                y='cantidad', 
                color='tipo',
                title='Actividad de Escritura',
                labels={'fecha': 'Fecha', 'cantidad': 'Palabras Escritas', 'tipo': 'Tipo'}
            )
        
        elif tipo == "nivel":
            # Ordenar por fecha
            df = df.sort_values('fecha')
            
            # Crear gráfico de dispersión con línea de tendencia
            fig = px.scatter(
                df, 
                x='fecha', 
                y='puntuacion',
                color='nivel',
                trendline="lowess",
                title='Evolución de la Puntuación',
                labels={'fecha': 'Fecha', 'puntuacion': 'Puntuación', 'nivel': 'Nivel'}
            )
        
        # Personalizar diseño
        fig.update_layout(
            template="plotly_white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error generando gráfico de progreso: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error generando gráfico: {str(e)}",
            xaxis_title="Fecha",
            yaxis_title="Valor",
            template="plotly_white"
        )
        return fig

def obtener_recomendaciones_usuario(user_id):
    """
    Genera recomendaciones personalizadas basadas en el progreso del usuario.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        list: Lista de recomendaciones
    """
    try:
        # Obtener datos de correcciones
        correcciones = get_correcciones_usuario(user_id)
        
        if not correcciones:
            return [
                {
                    "titulo": "Comienza a practicar",
                    "descripcion": "Realiza tu primera corrección para obtener recomendaciones personalizadas.",
                    "tipo": "info"
                }
            ]
        
        # Análisis de errores más frecuentes
        errores_totales = {}
        for correccion in correcciones:
            for error in correccion.get('errores', []):
                categoria = error.get('categoria', 'Otro')
                cantidad = error.get('cantidad', 0)
                if categoria in errores_totales:
                    errores_totales[categoria] += cantidad
                else:
                    errores_totales[categoria] = cantidad
        
        # Ordenar errores por frecuencia
        errores_ordenados = sorted(errores_totales.items(), key=lambda x: x[1], reverse=True)
        
        # Generar recomendaciones basadas en los errores más frecuentes
        recomendaciones = []
        
        # Obtener perfil completo
        perfil = get_user_info()
        nivel = perfil.get('nivel', 'A1')
        
        # Añadir recomendaciones según los tipos de errores más comunes
        if errores_ordenados:
            # Primera recomendación basada en el error más común
            error_principal = errores_ordenados[0][0]
            
            if error_principal == "Ortografía":
                recomendaciones.append({
                    "titulo": "Mejora tu ortografía",
                    "descripcion": "Practica con ejercicios de dictado y revisión ortográfica.",
                    "tipo": "ejercicio",
                    "parametros": {"tipo": "ortografia", "nivel": nivel}
                })
            
            elif error_principal == "Gramática":
                recomendaciones.append({
                    "titulo": "Refuerza tu gramática",
                    "descripcion": "Realiza ejercicios de gramática enfocados en tus puntos débiles.",
                    "tipo": "ejercicio",
                    "parametros": {"tipo": "gramatica", "nivel": nivel}
                })
            
            elif error_principal == "Vocabulario":
                recomendaciones.append({
                    "titulo": "Amplía tu vocabulario",
                    "descripcion": "Practica con ejercicios de vocabulario contextualizado.",
                    "tipo": "ejercicio",
                    "parametros": {"tipo": "vocabulario", "nivel": nivel}
                })
            
            elif error_principal == "Coherencia" or error_principal == "Cohesión":
                recomendaciones.append({
                    "titulo": "Mejora la estructura de tus textos",
                    "descripcion": "Practica con ejercicios de organización textual y conectores.",
                    "tipo": "ejercicio",
                    "parametros": {"tipo": "estructura", "nivel": nivel}
                })
        
        # Recomendación de simulacro si el usuario ha realizado más de 5 correcciones
        if len(correcciones) >= 5:
            recomendaciones.append({
                "titulo": "¡Pon a prueba tus habilidades!",
                "descripcion": f"Ya has realizado {len(correcciones)} correcciones. Es un buen momento para intentar un simulacro de examen DELE.",
                "tipo": "simulacro",
                "parametros": {"nivel": nivel}
            })
        
        # Si no hay suficientes recomendaciones basadas en análisis, añadir genéricas
        if len(recomendaciones) < 3:
            recomendaciones.extend([
                {
                    "titulo": "Practica la comprensión escrita",
                    "descripcion": "Realiza ejercicios de comprensión de lectura para mejorar tu nivel general.",
                    "tipo": "ejercicio",
                    "parametros": {"tipo": "comprension", "nivel": nivel}
                },
                {
                    "titulo": "Mejora tu expresión escrita",
                    "descripcion": "Escribe textos sobre temas cotidianos para mejorar tu fluidez.",
                    "tipo": "correccion",
                    "parametros": {"tipo": "expresion", "nivel": nivel}
                }
            ])
        
        # Limitar a 4 recomendaciones máximo
        return recomendaciones[:4]
    except Exception as e:
        logger.error(f"Error obteniendo recomendaciones: {str(e)}")
        return [
            {
                "titulo": "Continúa practicando",
                "descripcion": "Sigue realizando ejercicios y correcciones para mejorar tu español.",
                "tipo": "info"
            }
        ]

def mostrar_perfil_usuario():
    """
    Muestra la información del perfil del usuario en la interfaz de Streamlit.
    
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        
        if not user_info:
            st.warning("No se ha podido cargar la información del perfil.")
            return
        
        # Mostrar tarjeta de perfil
        st.write("### Perfil del Estudiante")
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Avatar (placeholder)
            st.image("https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y", width=150)
        
        with col2:
            # Información básica
            st.write(f"**Nombre:** {user_info.get('nombre', '')} {user_info.get('apellido', '')}")
            st.write(f"**Email:** {user_info.get('email', '')}")
            st.write(f"**Nivel actual:** {user_info.get('nivel', 'No especificado')}")
            st.write(f"**Objetivo:** {user_info.get('objetivo', 'No especificado')}")
            
            # Botón para editar perfil
            if st.button("Editar perfil"):
                set_session_var("mostrar_edicion_perfil", True)
        
        # Mostrar formulario de edición si está activado
        if get_session_var("mostrar_edicion_perfil", False):
            mostrar_formulario_edicion_perfil(user_info)
    except Exception as e:
        logger.error(f"Error mostrando perfil de usuario: {str(e)}")
        st.error("Ha ocurrido un error al mostrar el perfil. Por favor, intenta de nuevo más tarde.")

def mostrar_formulario_edicion_perfil(user_info):
    """
    Muestra un formulario para editar el perfil del usuario.
    
    Args:
        user_info (dict): Información actual del usuario
        
    Returns:
        None
    """
    try:
        st.write("### Editar Perfil")
        
        with st.form("form_editar_perfil"):
            # Campos del formulario
            nombre = st.text_input("Nombre", value=user_info.get('nombre', ''))
            apellido = st.text_input("Apellido", value=user_info.get('apellido', ''))
            
            # Nivel de español
            niveles = ["A1", "A2", "B1", "B2", "C1", "C2"]
            nivel = st.selectbox("Nivel de español", niveles, index=niveles.index(user_info.get('nivel', 'A1')) if user_info.get('nivel') in niveles else 0)
            
            # Objetivo de aprendizaje
            objetivos = [
                "Mejorar en general", 
                "Preparar examen DELE", 
                "Uso profesional", 
                "Uso académico", 
                "Viajes", 
                "Otro"
            ]
            objetivo_seleccionado = st.selectbox(
                "Objetivo principal", 
                objetivos, 
                index=objetivos.index(user_info.get('objetivo', 'Mejorar en general')) if user_info.get('objetivo') in objetivos else 0
            )
            
            # Si selecciona "Otro", mostrar campo para especificar
            if objetivo_seleccionado == "Otro":
                objetivo_otro = st.text_input("Especifica tu objetivo")
                objetivo = objetivo_otro if objetivo_otro else "Otro"
            else:
                objetivo = objetivo_seleccionado
            
            # Información adicional
            areas_interes = st.multiselect(
                "Áreas de interés", 
                ["Literatura", "Negocios", "Tecnología", "Viajes", "Cultura", "Ciencia", "Deporte", "Arte"],
                default=user_info.get('areas_interes', [])
            )
            
            lengua_materna = st.text_input("Lengua materna", value=user_info.get('lengua_materna', ''))
            
            # Opciones de notificación
            recibir_notificaciones = st.checkbox("Recibir notificaciones por email", value=user_info.get('recibir_notificaciones', True))
            
            # Botones de acción
            submitted = st.form_submit_button("Guardar cambios")
            cancel = st.form_submit_button("Cancelar")
            
            if submitted:
                # Preparar datos actualizados
                datos_actualizados = {
                    "nombre": nombre,
                    "apellido": apellido,
                    "nivel": nivel,
                    "objetivo": objetivo,
                    "areas_interes": areas_interes,
                    "lengua_materna": lengua_materna,
                    "recibir_notificaciones": recibir_notificaciones,
                    "ultima_actualizacion": datetime.now().isoformat()
                }
                
                # Actualizar en Firebase
                user_id = user_info.get('uid')
                if user_id:
                    success = actualizar_perfil_usuario(user_id, datos_actualizados)
                    
                    if success:
                        st.success("Perfil actualizado correctamente")
                        set_session_var("mostrar_edicion_perfil", False)
                        # Recargar para ver los cambios
                        st.experimental_rerun()
                    else:
                        st.error("Error al actualizar el perfil. Por favor, intenta de nuevo.")
                else:
                    st.error("No se pudo identificar al usuario. Por favor, cierra sesión y vuelve a iniciar.")
            
            if cancel:
                set_session_var("mostrar_edicion_perfil", False)
                st.experimental_rerun()
    except Exception as e:
        logger.error(f"Error en formulario de edición de perfil: {str(e)}")
        st.error("Ha ocurrido un error en el formulario. Por favor, intenta de nuevo más tarde.")

def mostrar_resumen_progreso(user_id, periodo=None):
    """
    Muestra un resumen del progreso del usuario en la interfaz de Streamlit.
    
    Args:
        user_id (str): ID del usuario
        periodo (str, opcional): Periodo para filtrar (semana, mes, trimestre)
        
    Returns:
        None
    """
    try:
        # Obtener estadísticas
        estadisticas = obtener_estadisticas_usuario(user_id, periodo)
        
        st.write("### Resumen de Actividad")
        
        # Selección de periodo
        periodos = {
            "semana": "Última semana",
            "mes": "Último mes",
            "trimestre": "Último trimestre",
            "todo": "Todo el tiempo"
        }
        
        periodo_seleccionado = st.selectbox(
            "Periodo", 
            list(periodos.keys()), 
            format_func=lambda x: periodos[x],
            index=list(periodos.keys()).index(periodo) if periodo in periodos else 0
        )
        
        if periodo_seleccionado != periodo:
            # Recargar con el nuevo periodo
            return periodo_seleccionado
        
        # Mostrar estadísticas básicas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Textos corregidos", estadisticas["total_correcciones"])
        
        with col2:
            st.metric("Simulacros realizados", estadisticas["total_simulacros"])
        
        with col3:
            st.metric("Ejercicios completados", estadisticas["total_ejercicios"])
        
        # Mostrar gráficos de progreso
        st.write("### Evolución de Errores")
        fig_errores = generar_grafico_progreso(user_id, "errores", periodo_seleccionado if periodo_seleccionado != "todo" else None)
        st.plotly_chart(fig_errores, use_container_width=True)
        
        st.write("### Actividad de Escritura")
        fig_actividad = generar_grafico_progreso(user_id, "actividad", periodo_seleccionado if periodo_seleccionado != "todo" else None)
        st.plotly_chart(fig_actividad, use_container_width=True)
        
        if "metricas" in estadisticas and estadisticas["metricas"]:
            st.write("### Métricas de Aprendizaje")
            
            metricas = estadisticas["metricas"]
            col1, col2 = st.columns(2)
            
            with col1:
                if "tasa_mejora" in metricas:
                    st.metric("Tasa de mejora", f"{metricas['tasa_mejora']:.1f}%")
                
                if "palabras_por_sesion" in metricas:
                    st.metric("Palabras por sesión", f"{metricas['palabras_por_sesion']:.0f}")
            
            with col2:
                if "consistencia" in metricas:
                    st.metric("Consistencia", f"{metricas['consistencia']:.1f}/10")
                
                if "diversidad_temas" in metricas:
                    st.metric("Diversidad de temas", f"{metricas['diversidad_temas']:.1f}/10")
        
        # Mostrar recomendaciones
        st.write("### Recomendaciones Personalizadas")
        recomendaciones = obtener_recomendaciones_usuario(user_id)
        
        for i, recomendacion in enumerate(recomendaciones):
            with st.expander(recomendacion["titulo"], expanded=(i == 0)):
                st.write(recomendacion["descripcion"])
                
                # Botón de acción según el tipo de recomendación
                if recomendacion["tipo"] == "ejercicio":
                    if st.button(f"Realizar ejercicio", key=f"btn_ejercicio_{i}"):
                        # Guardar parámetros en sesión para usar en la vista de ejercicios
                        set_session_var("ejercicio_recomendado", recomendacion["parametros"])
                        st.session_state.current_page = "ejercicios"
                        st.experimental_rerun()
                
                elif recomendacion["tipo"] == "simulacro":
                    if st.button(f"Iniciar simulacro", key=f"btn_simulacro_{i}"):
                        # Guardar parámetros en sesión para usar en la vista de simulacro
                        set_session_var("simulacro_recomendado", recomendacion["parametros"])
                        st.session_state.current_page = "simulacro"
                        st.experimental_rerun()
                
                elif recomendacion["tipo"] == "correccion":
                    if st.button(f"Escribir texto", key=f"btn_correccion_{i}"):
                        # Guardar parámetros en sesión para usar en la vista de corrección
                        set_session_var("correccion_recomendada", recomendacion["parametros"])
                        st.session_state.current_page = "correccion"
                        st.experimental_rerun()
        
        return periodo_seleccionado
    except Exception as e:
        logger.error(f"Error mostrando resumen de progreso: {str(e)}")
        st.error("Ha ocurrido un error al mostrar el resumen de progreso. Por favor, intenta de nuevo más tarde.")
        return periodo