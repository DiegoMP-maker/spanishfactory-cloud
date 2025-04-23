#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vista del simulador de examen
----------------------------
Este módulo implementa la interfaz de usuario para el simulador de examen DELE.
"""

import logging
import streamlit as st
import time
from datetime import datetime, timedelta
import json

from features.simulacro import (
    generar_simulacro,
    evaluar_respuestas_simulacro,
    guardar_resultado_simulacro,
    obtener_historial_simulacros
)
from core.session_manager import get_session_var, set_session_var, get_user_info
from ui.main_layout import mostrar_mensaje_error
from utils.text_processing import parse_simulacro_structure
from features.exportacion import mostrar_opciones_exportacion

logger = logging.getLogger(__name__)

def render_view():
    """
    Renderiza la vista del simulador de examen DELE.
    
    Returns:
        None
    """
    try:
        # Título de la página
        st.markdown("## 🏆 Simulacro de examen DELE")
        st.markdown("""
        Practica con simulacros de examen DELE adaptados a tu nivel. 
        Estos simulacros te ayudarán a familiarizarte con el formato y 
        tipo de preguntas del examen oficial.
        """)
        
        # Verificar si hay un examen en curso
        examen_en_curso = get_session_var("examen_en_curso", False)
        
        if examen_en_curso:
            # Continuar con el examen en curso
            mostrar_examen_en_curso()
        else:
            # Mostrar pestañas de inicio de simulacro e historial
            tab1, tab2 = st.tabs(["Nuevo simulacro", "Historial de simulacros"])
            
            with tab1:
                # Formulario para iniciar nuevo simulacro
                mostrar_formulario_simulacro()
            
            with tab2:
                # Historial de simulacros
                mostrar_historial_simulacros_ui()
    except Exception as e:
        logger.error(f"Error renderizando vista de simulacro: {str(e)}")
        st.error(f"Error al cargar la vista de simulacro: {str(e)}")

def mostrar_formulario_simulacro():
    """
    Muestra el formulario para iniciar un nuevo simulacro.
    
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        nivel_usuario = user_info.get('nivel', 'B1') if user_info else 'B1'
        
        with st.form("form_simulacro"):
            # Selector de nivel
            nivel = st.selectbox(
                "Nivel del examen",
                ["A1", "A2", "B1", "B2", "C1", "C2"],
                index=["A1", "A2", "B1", "B2", "C1", "C2"].index(nivel_usuario)
            )
            
            # Selector de tipo de examen
            tipo_examen = st.selectbox(
                "Tipo de simulacro",
                [
                    "Completo (todas las pruebas)",
                    "Comprensión de lectura",
                    "Comprensión auditiva",
                    "Expresión e interacción escritas",
                    "Expresión e interacción orales"
                ]
            )
            
            # Duración
            duracion = st.slider(
                "Duración aproximada (minutos)",
                min_value=15,
                max_value=180,
                value=60,
                step=15,
                help="La duración real del examen DELE varía según el nivel y la prueba"
            )
            
            # Opciones avanzadas
            with st.expander("Opciones avanzadas"):
                col1, col2 = st.columns(2)
                
                with col1:
                    dificultad = st.select_slider(
                        "Dificultad",
                        options=["Fácil", "Media", "Difícil"],
                        value="Media"
                    )
                
                with col2:
                    temas = st.multiselect(
                        "Temas preferidos",
                        [
                            "General", 
                            "Vida cotidiana", 
                            "Trabajo y profesiones", 
                            "Educación",
                            "Viajes y turismo", 
                            "Salud y bienestar",
                            "Cultura y arte", 
                            "Tecnología", 
                            "Medio ambiente",
                            "Economía y negocios"
                        ],
                        default=["General"]
                    )
                
                # Instrucciones específicas
                instrucciones = st.text_area(
                    "Instrucciones específicas (opcional)",
                    placeholder="Ej: Enfocarse en ciertos aspectos gramaticales, vocabulario específico, etc.",
                    height=100
                )
            
            # Botón de inicio
            submitted = st.form_submit_button("Iniciar simulacro")
            
            if submitted:
                with st.spinner("Generando simulacro de examen... Esto puede tardar unos segundos."):
                    # Preparar parámetros
                    parametros = {
                        "nivel": nivel,
                        "tipo": tipo_examen.split(" (")[0],  # Obtener solo la primera parte
                        "duracion": duracion,
                        "dificultad": dificultad,
                        "temas": temas,
                        "instrucciones": instrucciones if instrucciones else None
                    }
                    
                    # Obtener UID del usuario
                    uid = user_info.get('uid', None) if user_info else None
                    
                    # Llamar a la función de generación
                    resultado = generar_simulacro(parametros, uid)
                    
                    if resultado and 'error' not in resultado:
                        # Guardar simulacro en sesión
                        set_session_var("simulacro_actual", resultado)
                        
                        # Calcular tiempo de finalización
                        tiempo_inicio = datetime.now()
                        tiempo_fin = tiempo_inicio + timedelta(minutes=duracion)
                        
                        # Guardar en sesión
                        set_session_var("examen_en_curso", True)
                        set_session_var("tiempo_inicio_examen", tiempo_inicio.isoformat())
                        set_session_var("tiempo_fin_examen", tiempo_fin.isoformat())
                        set_session_var("respuestas_usuario", {})
                        
                        # Recargar para mostrar el examen
                        st.experimental_rerun()
                    else:
                        # Mostrar error
                        error_msg = resultado.get('error', 'Error al generar el simulacro. Por favor, inténtalo de nuevo.')
                        mostrar_mensaje_error(error_msg)
    except Exception as e:
        logger.error(f"Error mostrando formulario de simulacro: {str(e)}")
        st.error(f"Error al cargar el formulario: {str(e)}")

def mostrar_examen_en_curso():
    """
    Muestra el examen en curso.
    
    Returns:
        None
    """
    try:
        # Obtener datos del examen
        simulacro = get_session_var("simulacro_actual", None)
        tiempo_inicio = get_session_var("tiempo_inicio_examen", None)
        tiempo_fin = get_session_var("tiempo_fin_examen", None)
        respuestas_usuario = get_session_var("respuestas_usuario", {})
        
        if not simulacro or not tiempo_inicio or not tiempo_fin:
            st.warning("No hay un examen en curso. Por favor, inicia un nuevo simulacro.")
            set_session_var("examen_en_curso", False)
            st.experimental_rerun()
            return
        
        # Parsear estructura del simulacro
        simulacro_data = parse_simulacro_structure(simulacro['simulacro'])
        
        # Mostrar cabecera del examen
        st.markdown(f"### {simulacro_data.get('titulo', 'Simulacro de examen DELE')}")
        st.markdown(f"**Nivel:** {simulacro_data.get('nivel', 'No especificado')}")
        
        # Mostrar temporizador
        mostrar_temporizador(tiempo_fin)
        
        # Mostrar instrucciones generales
        with st.expander("Instrucciones generales", expanded=False):
            st.markdown(simulacro_data.get('instrucciones', ''))
        
        # Mostrar secciones del examen
        secciones = simulacro_data.get('secciones', [])
        
        if not secciones:
            st.warning("Este simulacro no contiene secciones. Por favor, inicia un nuevo simulacro.")
            set_session_var("examen_en_curso", False)
            st.experimental_rerun()
            return
        
        # Crear pestañas para cada sección
        tabs = st.tabs([seccion.get('titulo', f"Sección {i+1}") for i, seccion in enumerate(secciones)])
        
        # Mostrar contenido de cada sección en su pestaña
        for i, (tab, seccion) in enumerate(zip(tabs, secciones)):
            with tab:
                mostrar_seccion_examen(seccion, i, respuestas_usuario)
        
        # Botones de acción
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Cancelar simulacro", type="secondary"):
                if st.session_state.get("confirm_cancel", False):
                    # Cancelar el examen
                    set_session_var("examen_en_curso", False)
                    set_session_var("simulacro_actual", None)
                    set_session_var("tiempo_inicio_examen", None)
                    set_session_var("tiempo_fin_examen", None)
                    set_session_var("respuestas_usuario", {})
                    st.session_state.pop("confirm_cancel", None)
                    st.experimental_rerun()
                else:
                    # Pedir confirmación
                    st.session_state.confirm_cancel = True
                    st.warning("¿Estás seguro de que deseas cancelar el simulacro? Todo el progreso se perderá.")
        
        with col2:
            if st.button("Finalizar y evaluar", type="primary"):
                if st.session_state.get("confirm_finish", False):
                    # Finalizar y evaluar el examen
                    with st.spinner("Evaluando tus respuestas..."):
                        evaluar_y_mostrar_resultados(simulacro, respuestas_usuario)
                else:
                    # Pedir confirmación
                    st.session_state.confirm_finish = True
                    st.warning("¿Estás seguro de que deseas finalizar el simulacro? Ya no podrás modificar tus respuestas.")
    except Exception as e:
        logger.error(f"Error mostrando examen en curso: {str(e)}")
        st.error(f"Error al mostrar el examen: {str(e)}")
        
        # Opción para reiniciar en caso de error grave
        if st.button("Reiniciar simulador"):
            set_session_var("examen_en_curso", False)
            set_session_var("simulacro_actual", None)
            set_session_var("tiempo_inicio_examen", None)
            set_session_var("tiempo_fin_examen", None)
            set_session_var("respuestas_usuario", {})
            st.experimental_rerun()

def mostrar_temporizador(tiempo_fin):
    """
    Muestra un temporizador con el tiempo restante.
    
    Args:
        tiempo_fin (str): Tiempo de finalización en formato ISO
        
    Returns:
        None
    """
    try:
        # Convertir tiempo de finalización a datetime
        tiempo_fin_dt = datetime.fromisoformat(tiempo_fin.replace('Z', '+00:00'))
        
        # Calcular tiempo restante
        tiempo_actual = datetime.now()
        tiempo_restante = tiempo_fin_dt - tiempo_actual
        
        # Formatear tiempo restante
        if tiempo_restante.total_seconds() <= 0:
            # Tiempo agotado
            st.error("¡Tiempo agotado! Por favor, finaliza y envía tu examen.")
            return
        
        # Calcular horas, minutos y segundos
        horas = int(tiempo_restante.total_seconds() // 3600)
        minutos = int((tiempo_restante.total_seconds() % 3600) // 60)
        segundos = int(tiempo_restante.total_seconds() % 60)
        
        # Mostrar temporizador
        st.markdown(f"""
        <div class="timer-box">
            <p>Tiempo restante:</p>
            <div class="timer">{horas:02d}:{minutos:02d}:{segundos:02d}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Recargar automáticamente para actualizar temporizador
        if not st.session_state.get("rerun_scheduled", False):
            st.session_state.rerun_scheduled = True
            time.sleep(1)  # Esperar 1 segundo
            st.session_state.rerun_scheduled = False
            st.experimental_rerun()
    except Exception as e:
        logger.error(f"Error mostrando temporizador: {str(e)}")
        st.error(f"Error en el temporizador: {str(e)}")

def mostrar_seccion_examen(seccion, indice_seccion, respuestas_usuario):
    """
    Muestra una sección del examen.
    
    Args:
        seccion (dict): Datos de la sección
        indice_seccion (int): Índice de la sección
        respuestas_usuario (dict): Respuestas actuales del usuario
        
    Returns:
        None
    """
    try:
        # Mostrar título e instrucciones de la sección
        st.markdown(f"### {seccion.get('titulo', f'Sección {indice_seccion+1}')}")
        st.markdown(seccion.get('instrucciones', ''))
        
        # Mostrar tareas/preguntas
        tareas = seccion.get('tareas', [])
        
        if not tareas:
            st.info("Esta sección no contiene tareas.")
            return
        
        # Recorrer cada tarea
        for i, tarea in enumerate(tareas):
            st.markdown(f"#### Tarea {i+1}: {tarea.get('titulo', '')}")
            st.markdown(tarea.get('instrucciones', ''))
            
            # Mostrar contenido de la tarea (texto, imagen, audio, etc.)
            if 'contenido' in tarea:
                st.markdown(tarea['contenido'])
            
            # Mostrar preguntas
            preguntas = tarea.get('preguntas', [])
            
            for j, pregunta in enumerate(preguntas):
                # Identificador único para esta pregunta
                id_pregunta = f"seccion_{indice_seccion}_tarea_{i}_pregunta_{j}"
                
                # Mostrar enunciado de la pregunta
                st.markdown(f"**{j+1}. {pregunta.get('enunciado', '')}**")
                
                # Manejar diferentes tipos de pregunta
                tipo_pregunta = pregunta.get('tipo', 'opcion_multiple')
                
                if tipo_pregunta == 'opcion_multiple':
                    # Pregunta de opción múltiple
                    opciones = pregunta.get('opciones', [])
                    
                    # Valor actual (si existe)
                    valor_actual = respuestas_usuario.get(id_pregunta, None)
                    
                    # Mostrar opciones como radio buttons
                    respuesta = st.radio(
                        f"Selecciona una opción para la pregunta {j+1}:",
                        opciones,
                        index=opciones.index(valor_actual) if valor_actual in opciones else 0,
                        key=f"radio_{id_pregunta}"
                    )
                    
                    # Guardar respuesta
                    respuestas_usuario[id_pregunta] = respuesta
                
                elif tipo_pregunta == 'completar':
                    # Pregunta de completar texto
                    st.markdown(pregunta.get('contexto', ''))
                    
                    # Valor actual (si existe)
                    valor_actual = respuestas_usuario.get(id_pregunta, "")
                    
                    # Mostrar campo de texto
                    respuesta = st.text_input(
                        f"Respuesta {j+1}:",
                        value=valor_actual,
                        key=f"text_{id_pregunta}"
                    )
                    
                    # Guardar respuesta
                    respuestas_usuario[id_pregunta] = respuesta
                
                elif tipo_pregunta == 'desarrollo':
                    # Pregunta de desarrollo/redacción
                    st.markdown(pregunta.get('contexto', ''))
                    
                    # Valor actual (si existe)
                    valor_actual = respuestas_usuario.get(id_pregunta, "")
                    
                    # Mostrar área de texto
                    respuesta = st.text_area(
                        f"Respuesta {j+1}:",
                        value=valor_actual,
                        height=200,
                        key=f"textarea_{id_pregunta}"
                    )
                    
                    # Guardar respuesta
                    respuestas_usuario[id_pregunta] = respuesta
                
                elif tipo_pregunta == 'verdadero_falso':
                    # Pregunta de verdadero/falso
                    st.markdown(pregunta.get('contexto', ''))
                    
                    # Valor actual (si existe)
                    valor_actual = respuestas_usuario.get(id_pregunta, None)
                    
                    # Mostrar opciones como radio buttons
                    respuesta = st.radio(
                        f"Respuesta {j+1}:",
                        ["Verdadero", "Falso"],
                        index=["Verdadero", "Falso"].index(valor_actual) if valor_actual in ["Verdadero", "Falso"] else 0,
                        key=f"vf_{id_pregunta}"
                    )
                    
                    # Guardar respuesta
                    respuestas_usuario[id_pregunta] = respuesta
                
                elif tipo_pregunta == 'emparejar':
                    # Pregunta de emparejar elementos
                    st.markdown(pregunta.get('contexto', ''))
                    
                    # Elementos a emparejar
                    elementos_a = pregunta.get('elementos_a', [])
                    elementos_b = pregunta.get('elementos_b', [])
                    
                    # Crear una fila para cada elemento A
                    for k, elemento_a in enumerate(elementos_a):
                        # ID único para este emparejamiento
                        id_emparejamiento = f"{id_pregunta}_empareja_{k}"
                        
                        # Valor actual (si existe)
                        valor_actual = respuestas_usuario.get(id_emparejamiento, elementos_b[0] if elementos_b else "")
                        
                        # Mostrar selector
                        col1, col2 = st.columns([2, 3])
                        
                        with col1:
                            st.markdown(f"{elemento_a}")
                        
                        with col2:
                            respuesta = st.selectbox(
                                f"Empareja con:",
                                elementos_b,
                                index=elementos_b.index(valor_actual) if valor_actual in elementos_b else 0,
                                key=f"empareja_{id_emparejamiento}"
                            )
                        
                        # Guardar respuesta
                        respuestas_usuario[id_emparejamiento] = respuesta
                
                elif tipo_pregunta == 'ordenar':
                    # Pregunta de ordenar elementos
                    st.markdown(pregunta.get('contexto', ''))
                    
                    # Elementos a ordenar
                    elementos = pregunta.get('elementos', [])
                    
                    # Valor actual (si existe)
                    valores_actuales = respuestas_usuario.get(id_pregunta, elementos.copy())
                    
                    # Mostrar elementos con números para ordenar
                    st.markdown("Ordena los siguientes elementos arrastrando los números:")
                    
                    orden = []
                    for k in range(len(elementos)):
                        # Encontrar el índice actual en valores_actuales
                        indice_actual = valores_actuales.index(elementos[k]) if elementos[k] in valores_actuales else k
                        
                        # Mostrar selector de posición
                        orden.append(st.number_input(
                            elementos[k],
                            min_value=1,
                            max_value=len(elementos),
                            value=indice_actual + 1,
                            key=f"orden_{id_pregunta}_{k}"
                        ))
                    
                    # Reordenar elementos según el orden seleccionado
                    elementos_ordenados = [x for _, x in sorted(zip(orden, elementos))]
                    
                    # Guardar respuesta
                    respuestas_usuario[id_pregunta] = elementos_ordenados
                
                else:
                    # Tipo de pregunta no reconocido
                    st.warning(f"Tipo de pregunta no soportado: {tipo_pregunta}")
                
                # Separador entre preguntas
                st.markdown("---")
        
        # Actualizar respuestas en sesión
        set_session_var("respuestas_usuario", respuestas_usuario)
    except Exception as e:
        logger.error(f"Error mostrando sección de examen: {str(e)}")
        st.error(f"Error al mostrar la sección: {str(e)}")

def evaluar_y_mostrar_resultados(simulacro, respuestas_usuario):
    """
    Evalúa las respuestas del usuario y muestra los resultados.
    
    Args:
        simulacro (dict): Datos del simulacro
        respuestas_usuario (dict): Respuestas del usuario
        
    Returns:
        None
    """
    try:
        # Obtener UID del usuario
        user_info = get_user_info()
        uid = user_info.get('uid', None) if user_info else None
        
        # Llamar a la función de evaluación
        resultado = evaluar_respuestas_simulacro(simulacro, respuestas_usuario, uid)
        
        if resultado and 'error' not in resultado:
            # Guardar resultado en sesión
            set_session_var("examen_en_curso", False)
            set_session_var("ultimo_resultado_simulacro", resultado)
            
            # Guardar en Firebase si hay usuario
            if uid and not user_info.get('es_anonimo', False):
                # Datos para guardar
                datos_guardar = {
                    "uid": uid,
                    "nivel": simulacro.get('nivel', 'No especificado'),
                    "tipo": simulacro.get('tipo', 'No especificado'),
                    "fecha": datetime.now().isoformat(),
                    "puntuacion": resultado.get('puntuacion_total', 0),
                    "puntuaciones_secciones": resultado.get('puntuaciones_secciones', {}),
                    "tiempo_empleado": resultado.get('tiempo_empleado', 0),
                    "respuestas": respuestas_usuario,
                    "thread_id": simulacro.get('thread_id', None)
                }
                
                # Guardar en Firebase
                guardar_resultado_simulacro(datos_guardar)
            
            # Recargar para mostrar resultados
            st.experimental_rerun()
        else:
            # Mostrar error
            error_msg = resultado.get('error', 'Error al evaluar las respuestas. Por favor, inténtalo de nuevo.')
            mostrar_mensaje_error(error_msg)
    except Exception as e:
        logger.error(f"Error evaluando respuestas: {str(e)}")
        st.error(f"Error al evaluar las respuestas: {str(e)}")

def mostrar_resultado_simulacro():
    """
    Muestra el resultado del último simulacro.
    
    Returns:
        None
    """
    try:
        # Obtener resultado
        resultado = get_session_var("ultimo_resultado_simulacro", None)
        
        if not resultado:
            st.warning("No hay resultados disponibles. Por favor, realiza un simulacro.")
            return
        
        # Mostrar encabezado
        st.markdown("### Resultado del simulacro")
        
        # Mostrar puntuación total
        puntuacion_total = resultado.get('puntuacion_total', 0)
        
        # Determinar si está aprobado (según criterio DELE: 60% global y 50% por prueba)
        aprobado = puntuacion_total >= 60
        
        if aprobado:
            st.success(f"¡Felicidades! Has aprobado con una puntuación de {puntuacion_total}/100")
        else:
            st.error(f"No has alcanzado la puntuación mínima. Tu puntuación es {puntuacion_total}/100")
        
        # Mostrar puntuaciones por sección
        st.markdown("#### Puntuaciones por sección")
        
        puntuaciones_secciones = resultado.get('puntuaciones_secciones', {})
        
        if puntuaciones_secciones:
            # Crear tabla de puntuaciones
            data = []
            for seccion, puntuacion in puntuaciones_secciones.items():
                # Determinar si está aprobada la sección (criterio: 50%)
                aprobada = puntuacion >= 50
                estado = "✅ Aprobada" if aprobada else "❌ No aprobada"
                
                data.append({
                    "Sección": seccion,
                    "Puntuación": f"{puntuacion}/100",
                    "Estado": estado
                })
            
            # Mostrar tabla
            st.table(data)
        
        # Mostrar retroalimentación general
        st.markdown("#### Retroalimentación general")
        st.markdown(resultado.get('retroalimentacion_general', ''))
        
        # Mostrar retroalimentación por sección
        st.markdown("#### Retroalimentación detallada")
        
        retroalimentacion_secciones = resultado.get('retroalimentacion_secciones', {})
        
        if retroalimentacion_secciones:
            for seccion, retroalimentacion in retroalimentacion_secciones.items():
                with st.expander(f"Sección: {seccion}"):
                    st.markdown(retroalimentacion)
        
        # Mostrar tiempo empleado
        tiempo_empleado = resultado.get('tiempo_empleado', 0)
        st.markdown(f"**Tiempo empleado:** {tiempo_empleado} minutos")
        
        # Opciones de exportación
        with st.expander("Exportar resultado", expanded=False):
            # Preparar datos para exportación
            datos_exportacion = {
                "titulo": "Resultado de Simulacro DELE",
                "puntuacion_total": puntuacion_total,
                "puntuaciones_secciones": puntuaciones_secciones,
                "retroalimentacion_general": resultado.get('retroalimentacion_general', ''),
                "retroalimentacion_secciones": retroalimentacion_secciones,
                "tiempo_empleado": tiempo_empleado,
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            
            # Mostrar opciones de exportación
            mostrar_opciones_exportacion(datos_exportacion, "simulacro_resultado")
        
        # Botón para volver a la pantalla inicial
        if st.button("Volver a la pantalla inicial"):
            set_session_var("ultimo_resultado_simulacro", None)
            st.experimental_rerun()
    except Exception as e:
        logger.error(f"Error mostrando resultado de simulacro: {str(e)}")
        st.error(f"Error al mostrar el resultado: {str(e)}")

def mostrar_historial_simulacros_ui():
    """
    Muestra el historial de simulacros del usuario.
    
    Returns:
        None
    """
    try:
        # Obtener información del usuario
        user_info = get_user_info()
        uid = user_info.get('uid', None) if user_info else None
        
        if not uid or user_info.get('es_anonimo', False):
            st.info("Para guardar y ver tu historial de simulacros, necesitas iniciar sesión o crear una cuenta.")
            return
        
        # Obtener historial de simulacros
        with st.spinner("Cargando historial..."):
            simulacros = obtener_historial_simulacros(uid)
        
        if not simulacros:
            st.info("No tienes simulacros guardados. Realiza tu primer simulacro para verlo aquí.")
            return
        
        # Mostrar número total de simulacros
        st.markdown(f"#### Historial de simulacros ({len(simulacros)})")
        
        # Ordenar por fecha (más reciente primero)
        simulacros_ordenados = sorted(
            simulacros, 
            key=lambda x: x.get('fecha', ''), 
            reverse=True
        )
        
        # Mostrar cada simulacro en un expander
        for i, simulacro in enumerate(simulacros_ordenados):
            # Extraer datos
            fecha_str = simulacro.get('fecha', '')
            try:
                # Intentar formatear la fecha
                fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
                fecha_formateada = fecha_dt.strftime("%d/%m/%Y %H:%M")
            except:
                fecha_formateada = fecha_str
            
            nivel = simulacro.get('nivel', 'No especificado')
            tipo = simulacro.get('tipo', 'Completo')
            puntuacion = simulacro.get('puntuacion', 0)
            
            # Determinar si está aprobado
            aprobado = puntuacion >= 60
            estado = "✅ Aprobado" if aprobado else "❌ No aprobado"
            
            # Texto para el expander
            titulo_expander = f"{fecha_formateada} - DELE {nivel} ({tipo}) - Puntuación: {puntuacion}/100 - {estado}"
            
            with st.expander(titulo_expander):
                # Mostrar detalles del simulacro
                st.markdown(f"**Fecha:** {fecha_formateada}")
                st.markdown(f"**Nivel:** {nivel}")
                st.markdown(f"**Tipo de simulacro:** {tipo}")
                st.markdown(f"**Puntuación:** {puntuacion}/100")
                
                # Mostrar puntuaciones por sección si están disponibles
                puntuaciones_secciones = simulacro.get('puntuaciones_secciones', {})
                
                if puntuaciones_secciones:
                    st.markdown("##### Puntuaciones por sección")
                    
                    # Crear tabla de puntuaciones
                    data = []
                    for seccion, punt in puntuaciones_secciones.items():
                        # Determinar si está aprobada la sección
                        aprobada = punt >= 50
                        estado_seccion = "✅ Aprobada" if aprobada else "❌ No aprobada"
                        
                        data.append({
                            "Sección": seccion,
                            "Puntuación": f"{punt}/100",
                            "Estado": estado_seccion
                        })
                    
                    # Mostrar tabla
                    st.table(data)
                
                # Tiempo empleado
                tiempo_empleado = simulacro.get('tiempo_empleado', 0)
                st.markdown(f"**Tiempo empleado:** {tiempo_empleado} minutos")
                
                # Opciones de exportación
                if st.button("Exportar resultado", key=f"export_btn_{i}"):
                    # Preparar datos para exportación
                    datos_exportacion = {
                        "titulo": f"Resultado de Simulacro DELE {nivel}",
                        "puntuacion_total": puntuacion,
                        "puntuaciones_secciones": puntuaciones_secciones,
                        "fecha": fecha_formateada,
                        "nivel": nivel,
                        "tipo": tipo,
                        "tiempo_empleado": tiempo_empleado
                    }
                    
                    # Mostrar opciones de exportación
                    mostrar_opciones_exportacion(datos_exportacion, f"simulacro_{i}")
    except Exception as e:
        logger.error(f"Error mostrando historial de simulacros: {str(e)}")
        st.error(f"Error al cargar el historial: {str(e)}")
