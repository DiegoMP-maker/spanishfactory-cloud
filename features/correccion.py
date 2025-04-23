#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de corrección de textos
------------------------------
Este módulo contiene la lógica para corregir textos usando el Asistente de OpenAI.
"""

import logging
import json
from datetime import datetime
import time
import streamlit as st

from config.settings import OPENAI_ASSISTANT_CORRECCION
from config.prompts import PROMPT_CORRECCION
from core.assistant_client import get_assistant_client
from core.firebase_client import guardar_correccion_firebase

logger = logging.getLogger(__name__)

def corregir_texto(texto, parametros, uid=None):
    """
    Corrige un texto utilizando el Asistente de OpenAI.
    
    Args:
        texto (str): Texto a corregir
        parametros (dict): Parámetros para la corrección (nivel, tipo_texto, detalle, etc.)
        uid (str, opcional): ID del usuario
        
    Returns:
        dict: Resultado de la corrección o error
    """
    try:
        # Obtener cliente del asistente
        client = get_assistant_client()
        if not client:
            return {"error": "No se pudo obtener el cliente del asistente"}
        
        # Extraer parámetros
        nivel = parametros.get("nivel", "B1")
        tipo_texto = parametros.get("tipo_texto", "General")
        detalle = parametros.get("detalle", "Intermedio")
        enfoque = parametros.get("enfoque", None)
        instrucciones = parametros.get("instrucciones", None)
        
        # Construir prompt para el asistente
        instrucciones_adicionales = ""
        if enfoque:
            instrucciones_adicionales += f"Enfócate especialmente en: {', '.join(enfoque)}. "
        if instrucciones:
            instrucciones_adicionales += f"Instrucciones adicionales: {instrucciones}"
        
        # Formatear el prompt con los parámetros
        prompt = PROMPT_CORRECCION.format(
            nivel=nivel,
            texto=texto,
            detalle=detalle,
            instrucciones_adicionales=instrucciones_adicionales
        )
        
        # Registrar inicio de corrección
        start_time = time.time()
        logger.info(f"Iniciando corrección de texto para nivel {nivel}")
        
        # Procesar con el asistente
        contenido, datos_json = client.process_with_assistant(
            system_message=prompt,
            user_message=texto,
            task_type="correccion_texto",
            user_uid=uid
        )
        
        # Registrar tiempo de procesamiento
        elapsed_time = time.time() - start_time
        logger.info(f"Corrección completada en {elapsed_time:.2f} segundos")
        
        # Verificar si hay error
        if not contenido or 'error' in datos_json:
            error_msg = datos_json.get('error', 'Error desconocido durante la corrección')
            logger.error(f"Error en corrección: {error_msg}")
            return {"error": error_msg}
        
        # Extraer resultado en formato JSON si está disponible
        json_errores = ""
        try:
            # Buscar JSON en el contenido
            start_idx = contenido.find("```json")
            end_idx = contenido.rfind("```")
            
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_str = contenido[start_idx + 7:end_idx].strip()
                # Guardar el JSON para procesar errores después
                json_errores = json_str
            
            # Si no hay JSON en el contenido, verificar en datos_json
            if not json_errores and 'json_response' in datos_json:
                json_errores = datos_json['json_response']
        except Exception as e:
            logger.warning(f"Error procesando JSON de respuesta: {str(e)}")
        
        # Construir resultado
        resultado = {
            "texto_original": texto,
            "texto_corregido": datos_json.get("texto_corregido", contenido),
            "retroalimentacion": datos_json.get("retroalimentacion", ""),
            "puntuacion": datos_json.get("puntuacion", 0),
            "json_errores": json_errores,
            "nivel": nivel,
            "tipo_texto": tipo_texto,
            "thread_id": datos_json.get("thread_id", None)
        }
        
        return resultado
    except Exception as e:
        logger.error(f"Error en corrección de texto: {str(e)}")
        return {"error": f"Error procesando la corrección: {str(e)}"}

def obtener_historial_correcciones(uid):
    """
    Obtiene el historial de correcciones de un usuario.
    
    Args:
        uid (str): ID del usuario
        
    Returns:
        list: Lista de correcciones o lista vacía en caso de error
    """
    try:
        from core.firebase_client import obtener_historial_correcciones as get_corrections
        
        # Obtener correcciones desde Firebase
        correcciones = get_corrections(uid)
        
        return correcciones
    except Exception as e:
        logger.error(f"Error obteniendo historial de correcciones: {str(e)}")
        return []
    