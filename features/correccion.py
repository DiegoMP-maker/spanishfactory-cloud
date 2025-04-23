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
import re

from config.settings import OPENAI_ASSISTANT_CORRECCION
from config.prompts import PROMPT_CORRECCION
from core.assistant_client import get_assistant_client
from core.firebase_client import guardar_correccion_firebase
from utils.text_processing import extract_errores_from_json

logger = logging.getLogger(__name__)

def extract_json_from_content(content):
    """
    Extrae JSON válido de una cadena de texto que puede contener otros elementos.
    Maneja diversos casos incluyendo JSON con y sin anotación, múltiples bloques JSON,
    y formatos irregulares.
    
    Args:
        content (str): Contenido que puede incluir JSON
        
    Returns:
        dict/None: Diccionario con el JSON extraído o None si no se encuentra
    """
    if not content:
        return None
    
    # Eliminar marcas de código y texto que no forme parte del JSON
    try:
        # Patrón para extraer JSON entre comillas triples
        triple_quotes_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        json_matches = re.findall(triple_quotes_pattern, content)
        
        # Patrón alternativo para JSON entre llaves (más agresivo, puede capturar texto no válido)
        if not json_matches:
            brace_pattern = r'(\{[\s\S]*\})'
            json_matches = re.findall(brace_pattern, content)
        
        # Probar cada coincidencia hasta encontrar JSON válido
        for match in json_matches:
            try:
                # Limpiar la cadena
                clean_json = match.strip()
                data = json.loads(clean_json)
                return data
            except json.JSONDecodeError:
                continue
        
        # Si no se encontró JSON válido hasta ahora, intentar con el texto completo
        try:
            # Algunos modelos pueden devolver JSON sin marcadores
            data = json.loads(content.strip())
            return data
        except json.JSONDecodeError:
            pass
        
        # Intentar una extracción más agresiva buscando el primer { y último }
        try:
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                potential_json = content[start_idx:end_idx+1]
                data = json.loads(potential_json)
                return data
        except json.JSONDecodeError:
            pass
        
        # Último recurso: estrategia de búsqueda incremental
        try:
            start_idx = content.find('{')
            if start_idx != -1:
                # Buscar el cierre de llave correspondiente
                open_count = 0
                for i in range(start_idx, len(content)):
                    if content[i] == '{':
                        open_count += 1
                    elif content[i] == '}':
                        open_count -= 1
                        if open_count == 0:
                            # Encontramos un bloque JSON potencialmente válido
                            potential_json = content[start_idx:i+1]
                            try:
                                data = json.loads(potential_json)
                                return data
                            except json.JSONDecodeError:
                                # Continuar buscando otro bloque JSON
                                pass
        except Exception:
            pass
        
        # Si llegamos aquí, no se encontró JSON válido
        logger.warning("No se pudo extraer JSON válido del contenido")
        return None
        
    except Exception as e:
        logger.error(f"Error extrayendo JSON del contenido: {str(e)}")
        return None
    
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
            # Extraer datos del contenido o de datos_json
            json_data = extract_json_from_content(contenido)
            
            # Si se encontró JSON en el contenido
            if json_data:
                json_errores = json.dumps(json_data)
                
                # Usar datos estructurados para el resultado
                resultado = {
                    "texto_original": texto,
                    "texto_corregido": json_data.get("texto_corregido", contenido),
                    "retroalimentacion": json_data.get("retroalimentacion", ""),
                    "puntuacion": json_data.get("puntuacion", 0),
                    "json_errores": json_errores,
                    "nivel": nivel,
                    "tipo_texto": tipo_texto,
                    "thread_id": datos_json.get("thread_id", None)
                }
                return resultado
            
            # Si no hay JSON en el contenido, verificar en datos_json
            if 'json_response' in datos_json:
                json_errores = datos_json['json_response']
                json_data = extract_json_from_content(json_errores)
                
                # Usar datos estructurados si están disponibles
                if json_data:
                    resultado = {
                        "texto_original": texto,
                        "texto_corregido": json_data.get("texto_corregido", contenido),
                        "retroalimentacion": json_data.get("retroalimentacion", ""),
                        "puntuacion": json_data.get("puntuacion", 0),
                        "json_errores": json_errores,
                        "nivel": nivel,
                        "tipo_texto": tipo_texto,
                        "thread_id": datos_json.get("thread_id", None)
                    }
                    return resultado
        except Exception as e:
            logger.warning(f"Error procesando JSON de respuesta: {str(e)}")
        
        # Si no se pudo extraer JSON estructurado, devolver respuesta directa
        resultado = {
            "texto_original": texto,
            "texto_corregido": contenido,
            "retroalimentacion": "",
            "puntuacion": 0,
            "json_errores": "",
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