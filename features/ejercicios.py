#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de generación de ejercicios personalizados
------------------------------------------------
Este módulo contiene las funciones para generar ejercicios personalizados
para estudiantes de español, adaptados al nivel y área de mejora.
"""

import logging
import json
import re
from typing import Dict, Any, Optional

import streamlit as st

from core.session_manager import get_session_var, set_session_var
from core.assistant_client import get_assistant_client
from config.prompts import get_ejercicios_prompt

logger = logging.getLogger(__name__)

def generar_ejercicio_personalizado(tipo_ejercicio: str, nivel: str, area_mejora: str) -> Dict[str, Any]:
    """
    Genera un ejercicio personalizado según el tipo, nivel y área de mejora utilizando
    el Asistente de OpenAI.

    Args:
        tipo_ejercicio: Tipo de ejercicio a generar
        nivel: Nivel del estudiante
        area_mejora: Área específica en la que enfocarse

    Returns:
        dict: Ejercicio generado con instrucciones, contenido y solución
    """
    try:
        # Obtener el sistema de prompts para generación de ejercicios
        system_prompt = get_ejercicios_prompt(tipo_ejercicio, nivel, area_mejora)
        
        # Crear mensaje del usuario para el asistente
        user_prompt = f"""
        Crea un ejercicio personalizado de {tipo_ejercicio} para nivel {nivel} enfocado en mejorar {area_mejora}.
        El ejercicio debe ser práctico, específico y con solución detallada.
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
                "titulo": f"Ejercicio de {tipo_ejercicio} (nivel {nivel})",
                "tipo": tipo_ejercicio,
                "nivel": nivel,
                "area_mejora": area_mejora,
                "instrucciones": "No disponible",
                "contenido": "No disponible",
                "solucion": "No disponible"
            }
            
        # Procesar con el asistente
        raw_output, data_json = assistant_client.process_with_assistant(
            system_prompt,
            user_prompt,
            task_type="generacion_ejercicios",
            thread_id=thread_id,
            user_uid=uid
        )
        
        # Verificar si hay error en la respuesta
        if raw_output is None or "error" in data_json:
            error_msg = data_json.get("error", "Error desconocido en el procesamiento")
            logger.error(f"Error al generar ejercicio: {error_msg}")
            return {
                "error": error_msg,
                "titulo": f"Ejercicio de {tipo_ejercicio} (nivel {nivel})",
                "tipo": tipo_ejercicio,
                "nivel": nivel,
                "area_mejora": area_mejora,
                "instrucciones": "No disponible",
                "contenido": "No disponible",
                "solucion": "No disponible"
            }
        
        # Procesar el resultado: limpiar HTML o markdown potencialmente problemático
        # y asegurar que la solución esté completamente separada
        if isinstance(data_json, dict):
            # Sanitizar contenido HTML
            for campo in ['instrucciones', 'contenido', 'solucion', 'titulo']:
                if campo in data_json and isinstance(data_json[campo], str):
                    # Mantener el formato HTML pero eliminar posibles scripts maliciosos
                    texto = data_json[campo]
                    # Eliminar etiquetas script
                    texto = re.sub(r'<script.*?>.*?</script>', '', texto, flags=re.DOTALL)
                    # Asegurar que etiquetas como <div> estén correctamente cerradas
                    data_json[campo] = texto
                else:
                    # Si el campo no existe o no es string, asignar valor por defecto
                    data_json[campo] = data_json.get(campo, "No disponible")

            # Verificar que la solución no esté en el contenido
            if "solucion" in data_json and "contenido" in data_json:
                contenido = data_json["contenido"].lower()
                # Buscar palabras clave que podrían indicar que la solución está en el contenido
                palabras_clave = ["solución", "solution", "respuesta", "answer", "clave"]

                if any(palabra in contenido for palabra in palabras_clave):
                    # Si se detecta una posible solución en el contenido, intentar separar
                    partes = re.split(r'(solución|solution|respuesta|answer|clave)',
                                      data_json["contenido"],
                                      flags=re.IGNORECASE)
                    if len(partes) > 1:
                        # Mantener solo la primera parte como contenido
                        data_json["contenido"] = partes[0].strip()
                        # Si no hay solución definida, usar el resto como solución
                        if not data_json["solucion"] or data_json["solucion"] == "No disponible":
                            data_json["solucion"] = " ".join(partes[1:]).strip()
            
            # Si se generó un nuevo thread_id, guardarlo en session_state
            if not thread_id and assistant_client.client:
                thread_id_nuevo = get_session_var("thread_id", "")
                if thread_id_nuevo:
                    set_session_var("thread_id", thread_id_nuevo)
        
        return data_json

    except Exception as e:
        logger.error(f"Error en generar_ejercicio_personalizado: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "error": str(e),
            "titulo": f"Ejercicio de {tipo_ejercicio} (nivel {nivel})",
            "tipo": tipo_ejercicio,
            "nivel": nivel,
            "area_mejora": area_mejora,
            "instrucciones": "No disponible",
            "contenido": "No disponible",
            "solucion": "No disponible"
        }

def generar_ejercicio_desde_area_mejora(nivel: str) -> Dict[str, Any]:
    """
    Genera un ejercicio personalizado basado en el área de mejora detectada
    en el perfil del estudiante.

    Args:
        nivel: Nivel del estudiante

    Returns:
        dict: Ejercicio generado
    """
    # Obtener área de mejora del perfil del estudiante
    area_mejora = get_session_var("ultima_area_mejora", None)

    if not area_mejora:
        # Si no hay área detectada, usar una general
        area_mejora = "Gramática"

    # Determinar el tipo de ejercicio más adecuado según el área
    tipo_ejercicio_map = {
        "Gramática": "Corrección de errores",
        "Léxico": "Vocabulario en contexto",
        "Puntuación": "Completar huecos",
        "Estructura textual": "Ordenar palabras/frases",
        "Coherencia": "Transformación de frases",
        "Cohesión": "Ordenar palabras/frases",
        "Registro lingüístico": "Elección múltiple"
    }

    tipo_ejercicio = tipo_ejercicio_map.get(area_mejora, "Completar huecos")

    # Generar el ejercicio
    return generar_ejercicio_personalizado(tipo_ejercicio, nivel, area_mejora)

def guardar_ejercicio_en_historial(ejercicio: Dict[str, Any]) -> bool:
    """
    Guarda un ejercicio en el historial del usuario.
    
    Args:
        ejercicio: Ejercicio generado
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener historial existente o crear uno nuevo
        historial_ejercicios = get_session_var("historial_ejercicios", [])
        
        # Añadir fecha y hora
        from datetime import datetime
        ejercicio_con_fecha = ejercicio.copy()
        ejercicio_con_fecha["fecha_generacion"] = datetime.now().isoformat()
        
        # Añadir al historial
        historial_ejercicios.append(ejercicio_con_fecha)
        
        # Guardar en session_state
        set_session_var("historial_ejercicios", historial_ejercicios)
        
        # También guardar en Firebase si está disponible
        try:
            from core.firebase_client import initialize_firebase
            db, success = initialize_firebase()
            
            if success and db:
                uid = get_session_var("uid_usuario", "")
                if uid:
                    # Guardar en colección de ejercicios del usuario
                    import uuid
                    ejercicio_id = str(uuid.uuid4())
                    db.collection("usuarios").document(uid).collection("ejercicios").document(ejercicio_id).set(ejercicio_con_fecha)
                    logger.info(f"Ejercicio guardado en Firebase para usuario {uid}")
                    return True
        except Exception as firebase_error:
            logger.error(f"Error al guardar ejercicio en Firebase: {str(firebase_error)}")
            # Continuar sin guardar en Firebase
            pass
            
        return True
        
    except Exception as e:
        logger.error(f"Error al guardar ejercicio en historial: {str(e)}")
        return False
    