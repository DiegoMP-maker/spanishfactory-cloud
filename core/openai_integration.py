#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de integración con OpenAI Assistants
------------------------------------------
Este módulo proporciona funciones para integrar el cliente limpio OpenAI Assistants
con el resto de la aplicación.
"""

import logging
import streamlit as st

# Importaciones de módulos del proyecto
from core.clean_openai_assistant import get_clean_openai_assistants_client
from core.session_manager import get_user_info, set_session_var, get_session_var

logger = logging.getLogger(__name__)

def get_thread_for_user(user_id=None):
    """
    Obtiene un hilo (thread) existente para el usuario o crea uno nuevo.
    
    Args:
        user_id (str, opcional): ID del usuario
        
    Returns:
        str: ID del thread para el usuario o None si hay error
    """
    if not user_id:
        user_info = get_user_info()
        user_id = user_info.get("uid") if user_info else None
    
    if not user_id:
        logger.warning("No hay ID de usuario para obtener thread")
        return None
    
    try:
        # Intentar obtener thread_id de Firebase
        from core.firebase_client import get_user_thread, save_user_thread
        
        # Intentar obtener thread_id existente
        thread_id = get_user_thread(user_id)
        
        # Si encontramos un thread_id, verificar que sea válido
        if thread_id:
            # Obtener cliente de OpenAI Assistants
            assistants_client = get_clean_openai_assistants_client()
            if not assistants_client:
                logger.error("No se pudo obtener cliente de OpenAI Assistants")
                return None
            
            # Verificar que el thread existe y es válido
            if assistants_client.verify_thread(thread_id):
                # Guardar en session_state para reutilización
                set_session_var("thread_id", thread_id)
                logger.info(f"Thread existente recuperado para usuario {user_id}: {thread_id}")
                
                # Actualizar información de perfil en el thread existente
                try:
                    # Utilizar la nueva función de actualización de perfil
                    result = assistants_client.update_thread_with_profile(thread_id, user_id)
                    if result:
                        logger.info(f"Perfil de estudiante actualizado en thread existente {thread_id}")
                    else:
                        logger.warning(f"No se pudo actualizar perfil en thread existente: {thread_id}")
                except Exception as profile_error:
                    logger.warning(f"Error actualizando perfil en thread: {str(profile_error)}")
                
                return thread_id
            else:
                logger.warning(f"Thread existente inválido para usuario {user_id}, se creará uno nuevo")
        
        # Si no hay thread_id o no es válido, crear uno nuevo con perfil incorporado
        # Obtener cliente de OpenAI Assistants
        assistants_client = get_clean_openai_assistants_client()
        if not assistants_client:
            logger.error("No se pudo obtener cliente de OpenAI Assistants")
            return None
        
        # Crear un nuevo thread con información de perfil del usuario
        thread_response = assistants_client.create_thread(user_id=user_id)
        
        # Extraer thread_id del resultado
        if thread_response and "id" in thread_response:
            thread_id = thread_response["id"]
            
            # Guardar en Firebase
            save_user_thread(user_id, thread_id)
            
            # Guardar en session_state para reutilización
            set_session_var("thread_id", thread_id)
            
            logger.info(f"Nuevo thread creado para usuario {user_id}: {thread_id}")
            return thread_id
        else:
            logger.error("No se pudo crear un nuevo thread")
            return None
        
    except Exception as e:
        logger.error(f"Error obteniendo/creando thread para usuario {user_id}: {str(e)}")
        return None

def process_with_assistant(system_message, user_message, task_type="default", thread_id=None, user_id=None):
    """
    Procesa un mensaje con el asistente de OpenAI usando el cliente limpio.
    
    Args:
        system_message (str): Mensaje del sistema (instrucciones)
        user_message (str): Mensaje del usuario (contenido)
        task_type (str): Tipo de tarea ('correccion_texto', 'generacion_ejercicios', etc.)
        thread_id (str, opcional): ID del thread existente
        user_id (str, opcional): ID del usuario
        
    Returns:
        tuple: (respuesta_raw, resultado_json)
    """
    # Verificar si hay thread_id
    if not thread_id:
        # Intentar obtener thread_id de session_state
        thread_id = get_session_var("thread_id")
        
        # Si no hay thread_id en session_state y hay user_id, intentar obtener/crear thread
        if not thread_id and user_id:
            thread_id = get_thread_for_user(user_id)
    
    # Obtener cliente de OpenAI Assistants limpio
    assistants_client = get_clean_openai_assistants_client()
    if not assistants_client:
        logger.error("No se pudo obtener cliente de OpenAI Assistants")
        return None, {"error": "No se pudo conectar con el servicio de asistentes"}
    
    # Procesar con el asistente, pasando el user_id para permitir la integración del perfil
    content, data = assistants_client.get_completion(
        system_message=system_message,
        user_message=user_message,
        task_type=task_type,
        thread_id=thread_id,
        user_id=user_id
    )
    
    # Si obtenemos un nuevo thread_id, guardarlo
    if isinstance(data, dict) and "thread_id" in data:
        new_thread_id = data["thread_id"]
        
        # Guardar en session_state
        set_session_var("thread_id", new_thread_id)
        
        # Si hay user_id, guardar en Firebase
        if user_id and new_thread_id != thread_id:
            try:
                from core.firebase_client import save_user_thread
                save_user_thread(user_id, new_thread_id)
                logger.info(f"Thread actualizado para usuario {user_id}: {new_thread_id}")
            except Exception as e:
                logger.error(f"Error guardando thread en Firebase: {str(e)}")
    
    return content, data
