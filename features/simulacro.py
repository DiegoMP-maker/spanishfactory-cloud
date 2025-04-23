#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de simulacro de examen DELE
----------------------------------
Este módulo contiene las funciones para generar y evaluar simulacros de examen DELE,
utilizando el Asistente de OpenAI para crear tareas realistas de expresión escrita.
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

import streamlit as st

from core.session_manager import get_session_var, set_session_var
from core.assistant_client import get_assistant_client
from config.prompts import get_simulacro_prompt

logger = logging.getLogger(__name__)

def generar_tarea_examen(nivel_examen: str) -> Dict[str, Any]:
    """
    Genera una tarea de expresión escrita para simulacro de examen DELE.
    
    Args:
        nivel_examen: Nivel del examen (A1, A2, B1, B2, C1, C2)
        
    Returns:
        dict: Tarea generada con instrucciones, extensión requerida y criterios
    """
    try:
        # Obtener solo el código de nivel (A1, B2, etc.) si viene con descripción
        nivel_corto = nivel_examen.split()[0] if " " in nivel_examen else nivel_examen
        
        # Obtener el prompt para el simulacro
        system_prompt = get_simulacro_prompt(nivel_corto)
        
        # Crear mensaje del usuario
        user_prompt = f"""
        Genera una tarea de expresión escrita para el examen DELE {nivel_corto}.
        Debe ser una tarea realista y completa que evalúe el nivel de expresión escrita del candidato.
        """
        
        # Obtener el UID del usuario para asociar thread
        uid = get_session_var("uid_usuario", "")
        
        # Obtener el thread_id si existe para el usuario
        thread_id = get_session_var("thread_id", "")
        
        # Obtener el cliente de asistentes
        assistant_client = get_assistant_client()
        if not assistant_client:
            return {
                "error": "No se pudo establecer conexión con OpenAI Assistants",
                "tarea": "No se pudo generar la tarea de examen. Por favor, intenta más tarde."
            }
            
        # Procesar con el asistente
        raw_output, data_json = assistant_client.process_with_assistant(
            system_prompt,
            user_prompt,
            task_type="simulacro_examen",
            thread_id=thread_id,
            user_uid=uid
        )
        
        # Verificar si hay error en la respuesta
        if raw_output is None or "error" in data_json:
            error_msg = data_json.get("error", "Error desconocido en el procesamiento")
            logger.error(f"Error al generar tarea de examen: {error_msg}")
            return {
                "error": error_msg,
                "tarea": f"Error al generar tarea de examen: {error_msg}",
                "nivel": nivel_corto
            }
        
        # Verificar si la respuesta tiene la estructura esperada
        if not isinstance(data_json, dict) or "tarea" not in data_json:
            # Si no está estructurado como JSON esperado, intentar extraer la tarea del texto crudo
            if raw_output:
                # Si no viene como JSON estructurado pero tenemos texto,
                # construir un objeto de tarea básico
                return {
                    "titulo": f"Prueba de expresión escrita DELE {nivel_corto}",
                    "nivel": nivel_corto,
                    "tarea": raw_output,
                    "extension_requerida": "Entre 150 y 200 palabras",
                    "tiempo_recomendado": "30 minutos"
                }
            else:
                # Si no hay datos utilizables, devolver error
                return {
                    "error": "Formato de respuesta inesperado",
                    "tarea": "No se pudo generar la tarea en el formato esperado.",
                    "nivel": nivel_corto
                }
        
        # Si se generó un nuevo thread_id, guardarlo en session_state
        if not thread_id and assistant_client.client:
            thread_id_nuevo = get_session_var("thread_id", "")
            if thread_id_nuevo:
                set_session_var("thread_id", thread_id_nuevo)
                
        # Asegurar que tiene todos los campos necesarios
        tarea_completa = {
            "titulo": data_json.get("titulo", f"Prueba de expresión escrita DELE {nivel_corto}"),
            "nivel": data_json.get("nivel", nivel_corto),
            "tarea": data_json.get("tarea", ""),
            "extension_requerida": data_json.get("extension_requerida", ""),
            "tiempo_recomendado": data_json.get("tiempo_recomendado", "30 minutos"),
            "criterios_evaluacion": data_json.get("criterios_evaluacion", [])
        }
        
        return tarea_completa
        
    except Exception as e:
        logger.error(f"Error en generar_tarea_examen: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "error": str(e),
            "tarea": f"Error al generar tarea: {str(e)}",
            "nivel": nivel_examen
        }

def iniciar_simulacro(nivel_examen: str, duracion_minutos: int) -> Tuple[Dict[str, Any], bool]:
    """
    Inicia un simulacro de examen DELE configurando la tarea y el temporizador.
    
    Args:
        nivel_examen: Nivel del examen (A1, A2, B1, B2, C1, C2)
        duracion_minutos: Duración del simulacro en minutos
        
    Returns:
        tuple: (tarea_generada, éxito_inicialización)
    """
    try:
        # Generar tarea de examen
        tarea = generar_tarea_examen(nivel_examen)
        
        # Verificar si hubo error en la generación
        if "error" in tarea:
            return tarea, False
        
        # Almacenar datos del simulacro en session_state
        set_session_var("inicio_simulacro", time.time())  # Usar timestamp
        set_session_var("duracion_simulacro", duracion_minutos)
        set_session_var("tarea_simulacro", tarea.get("tarea", ""))
        set_session_var("simulacro_respuesta_texto", "")
        set_session_var("examen_result", None)
        
        # Guardar información adicional sobre el simulacro
        set_session_var("simulacro_info", {
            "nivel": nivel_examen,
            "duracion": duracion_minutos,
            "titulo": tarea.get("titulo", ""),
            "extension_requerida": tarea.get("extension_requerida", ""),
            "criterios_evaluacion": tarea.get("criterios_evaluacion", []),
            "fecha_inicio": datetime.now().isoformat()
        })
        
        return tarea, True
        
    except Exception as e:
        logger.error(f"Error al iniciar simulacro: {str(e)}")
        return {"error": str(e), "tarea": "Error al iniciar el simulacro"}, False

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
        
        # Crear un contenedor único para el temporizador para evitar recrear toda la UI
        timer_placeholder = st.empty()
        
        # Mostrar temporizador en el contenedor
        timer_placeholder.markdown(f"""
        <div class="timer-box">
            <p>Tiempo restante:</p>
            <div class="timer">{horas:02d}:{minutos:02d}:{segundos:02d}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Programar la siguiente actualización para evitar recargas constantes
        # Solo actualizamos la UI completa cada 10 segundos para reducir la carga
        if segundos % 10 == 0 and not st.session_state.get("rerun_scheduled", False):
            st.session_state.rerun_scheduled = True
            
            # Usamos un callback para recargar después de cierto tiempo
            def schedule_rerun():
                time.sleep(10)  # Esperar 10 segundos
                st.session_state.rerun_scheduled = False
                st.rerun()
            
            # Iniciar el callback en un hilo
            import threading
            threading.Thread(target=schedule_rerun, daemon=True).start()
            
    except Exception as e:
        logger.error(f"Error mostrando temporizador: {str(e)}")
        st.error(f"Error en el temporizador: {str(e)}")

def finalizar_simulacro(respuesta: str, tarea: str, nivel: str) -> Dict[str, Any]:
    """
    Finaliza el simulacro evaluando la respuesta del estudiante utilizando el Asistente de OpenAI.
    
    Args:
        respuesta: Texto de respuesta del estudiante
        tarea: Texto de la tarea asignada
        nivel: Nivel del examen
        
    Returns:
        dict: Resultado de la evaluación
    """
    try:
        if not respuesta.strip():
            return {
                "error": "No has proporcionado una respuesta para evaluar",
                "evaluacion": "No se puede evaluar una respuesta vacía"
            }
        
        # Crear prompt para evaluación
        system_prompt = f"""
        Eres un examinador oficial de exámenes DELE (Diploma de Español como Lengua Extranjera).
        Tu tarea es evaluar la respuesta escrita de un candidato a una prueba de expresión escrita
        del nivel {nivel}. Debes proporcionar una evaluación detallada y una calificación.
        
        Tu evaluación debe incluir:
        1. Una valoración general de la respuesta
        2. Análisis de aspectos formales (gramática, vocabulario, ortografía)
        3. Análisis de aspectos comunicativos (coherencia, cohesión, adecuación)
        4. Puntos fuertes y aspectos a mejorar
        5. Calificación final (del 0 al 10)
        
        Formatea tu respuesta como un JSON con la siguiente estructura:
        {{
            "evaluacion_general": "Valoración general de la respuesta",
            "aspectos_formales": {{
                "gramatica": "Análisis de la gramática",
                "vocabulario": "Análisis del vocabulario",
                "ortografia": "Análisis de la ortografía"
            }},
            "aspectos_comunicativos": {{
                "coherencia": "Análisis de la coherencia",
                "cohesion": "Análisis de la cohesión",
                "adecuacion": "Análisis de la adecuación"
            }},
            "puntos_fuertes": ["punto 1", "punto 2", "..."],
            "aspectos_mejorar": ["aspecto 1", "aspecto 2", "..."],
            "calificacion": 8.5,
            "apto": true
        }}
        
        El candidato se considera APTO si la calificación es igual o superior a 6.0.
        """
        
        # Crear mensaje del usuario
        user_prompt = f"""
        Tarea de la prueba:
        
        {tarea}
        
        Respuesta del candidato:
        
        {respuesta}
        
        Por favor, evalúa esta respuesta como examinador oficial de DELE nivel {nivel}.
        """
        
        # Obtener el UID del usuario para asociar thread
        uid = get_session_var("uid_usuario", "")
        
        # Obtener el thread_id si existe para el usuario
        thread_id = get_session_var("thread_id", "")
        
        # Obtener el cliente de asistentes
        assistant_client = get_assistant_client()
        if not assistant_client:
            return {
                "error": "No se pudo establecer conexión con OpenAI Assistants",
                "evaluacion": "No se pudo evaluar la respuesta debido a un problema de conexión"
            }
            
        # Procesar con el asistente
        raw_output, data_json = assistant_client.process_with_assistant(
            system_prompt,
            user_prompt,
            task_type="simulacro_examen",
            thread_id=thread_id,
            user_uid=uid
        )
        
        # Verificar si hay error en la respuesta
        if raw_output is None or "error" in data_json:
            error_msg = data_json.get("error", "Error desconocido en el procesamiento")
            logger.error(f"Error al evaluar simulacro: {error_msg}")
            return {
                "error": error_msg,
                "evaluacion": f"Error al evaluar la respuesta: {error_msg}"
            }
        
        # Guardar el resultado en session_state
        set_session_var("examen_result", data_json)
        
        # Si hay historial de simulacros, añadir este resultado
        historial_simulacros = get_session_var("historial_simulacros", [])
        
        nuevo_registro = {
            "fecha": datetime.now().isoformat(),
            "nivel": nivel,
            "tarea": tarea,
            "respuesta": respuesta,
            "resultado": data_json,
            "calificacion": data_json.get("calificacion", 0),
            "apto": data_json.get("apto", False)
        }
        
        historial_simulacros.append(nuevo_registro)
        set_session_var("historial_simulacros", historial_simulacros)
        
        # Si se generó un nuevo thread_id, guardarlo en session_state
        if not thread_id and assistant_client.client:
            thread_id_nuevo = get_session_var("thread_id", "")
            if thread_id_nuevo:
                set_session_var("thread_id", thread_id_nuevo)
        
        # También guardar en Firebase si está disponible
        try:
            from core.firebase_client import guardar_resultado_simulacro
            uid = get_session_var("uid_usuario", "")
            if uid:
                # Preparar datos para guardar
                datos_guardar = {
                    "uid": uid,
                    "nivel": nivel,
                    "fecha": datetime.now().isoformat(),
                    "tarea": tarea,
                    "respuesta": respuesta,
                    "resultado": data_json,
                    "calificacion": data_json.get("calificacion", 0),
                    "apto": data_json.get("apto", False)
                }
                guardar_resultado_simulacro(datos_guardar)
                logger.info(f"Simulacro guardado en Firebase para usuario {uid}")
        except Exception as firebase_error:
            logger.error(f"Error al guardar simulacro en Firebase: {str(firebase_error)}")
            # Continuar sin guardar en Firebase
        
        # Reiniciar estados del simulacro
        set_session_var("inicio_simulacro", None)
        set_session_var("duracion_simulacro", None)
        set_session_var("tarea_simulacro", None)
        
        return data_json
        
    except Exception as e:
        logger.error(f"Error en finalizar_simulacro: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "error": str(e),
            "evaluacion": f"Error al evaluar la respuesta: {str(e)}"
        }