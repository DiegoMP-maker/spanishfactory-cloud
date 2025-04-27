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
import json

# Importaciones de módulos del proyecto
from core.clean_openai_assistant import get_clean_openai_assistants_client
from core.session_manager import get_user_info, set_session_var, get_session_var

logger = logging.getLogger(__name__)

def get_user_profile_data(user_id):
    """
    Obtiene los datos de perfil del usuario para incluir en el thread.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Datos de perfil del usuario o diccionario vacío si no hay datos
    """
    if not user_id:
        return {}
    
    try:
        # Obtener datos del usuario desde Firebase
        from core.firebase_client import get_user_data
        user_data = get_user_data(user_id)
        
        # Extraer datos relevantes para el perfil del estudiante
        profile = {
            "nivel_mcer": user_data.get("nivel", "B1"),  # Nivel por defecto si no está definido
            "idioma_nativo": user_data.get("idioma_nativo", ""),
            "objetivos_aprendizaje": user_data.get("objetivos", []),
            "areas_interes": user_data.get("areas_interes", [])
        }
        
        # Obtener estadísticas de errores si están disponibles
        if "errores_por_tipo" in user_data:
            profile["estadisticas_errores"] = user_data["errores_por_tipo"]
        
        # Obtener número de correcciones realizadas
        profile["numero_correcciones"] = user_data.get("numero_correcciones", 0)
        
        logger.info(f"Datos de perfil obtenidos para usuario {user_id}: nivel={profile['nivel_mcer']}")
        return profile
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de perfil para usuario {user_id}: {str(e)}")
        return {}

def get_thread_for_user(user_id=None):
    """
    Obtiene un hilo (thread) existente para el usuario o crea uno nuevo.
    Incluye información de perfil del estudiante en el thread.
    
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
                    profile_data = get_user_profile_data(user_id)
                    if profile_data:
                        # Crear mensaje con la información de perfil actualizada
                        profile_message = f"""
ACTUALIZACIÓN DE PERFIL DEL ESTUDIANTE:
```json
{json.dumps(profile_data, indent=2, ensure_ascii=False)}
```

Por favor, adapta tus próximas correcciones según este perfil actualizado.
"""
                        # Añadir mensaje al thread como actualización de perfil
                        assistants_client.add_message_to_thread(thread_id, profile_message)
                        logger.info(f"Perfil de estudiante actualizado en thread existente {thread_id}")
                except Exception as profile_error:
                    logger.warning(f"No se pudo actualizar perfil en thread existente: {str(profile_error)}")
                
                return thread_id
            else:
                logger.warning(f"Thread existente inválido para usuario {user_id}, se creará uno nuevo")
        
        # Si no hay thread_id o no es válido, crear uno nuevo
        # Obtener cliente de OpenAI Assistants
        assistants_client = get_clean_openai_assistants_client()
        if not assistants_client:
            logger.error("No se pudo obtener cliente de OpenAI Assistants")
            return None
        
        # Crear un nuevo thread
        thread_response = assistants_client.create_thread()
        
        # Extraer thread_id del resultado
        if thread_response and "id" in thread_response:
            thread_id = thread_response["id"]
            
            # Guardar en Firebase
            save_user_thread(user_id, thread_id)
            
            # Guardar en session_state para reutilización
            set_session_var("thread_id", thread_id)
            
            # Añadir información de perfil del estudiante en el thread nuevo
            try:
                profile_data = get_user_profile_data(user_id)
                if profile_data:
                    # Crear mensaje con la información de perfil
                    profile_message = f"""
PERFIL DEL ESTUDIANTE:
```json
{json.dumps(profile_data, indent=2, ensure_ascii=False)}
```

Por favor, adapta tus correcciones según este perfil. Considera especialmente:
1. El nivel MCER ({profile_data.get('nivel_mcer', 'B1')}) para calibrar la severidad
2. El idioma nativo para entender posibles interferencias
3. Los objetivos específicos de aprendizaje
4. Las áreas de error frecuentes para dar feedback específico
"""
                    # Añadir mensaje al thread
                    assistants_client.add_message_to_thread(thread_id, profile_message)
                    logger.info(f"Perfil de estudiante añadido al nuevo thread {thread_id}")
            except Exception as profile_error:
                logger.warning(f"No se pudo añadir perfil al nuevo thread: {str(profile_error)}")
            
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
    
    # Procesar con el asistente
    content, data = assistants_client.get_completion(
        system_message=system_message,
        user_message=user_message,
        task_type=task_type,
        thread_id=thread_id
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
                
                # Si tenemos un nuevo thread, añadir perfil del estudiante
                if thread_id != new_thread_id:
                    profile_data = get_user_profile_data(user_id)
                    if profile_data:
                        # Crear mensaje con la información de perfil
                        profile_message = f"""
PERFIL DEL ESTUDIANTE:
```json
{json.dumps(profile_data, indent=2, ensure_ascii=False)}
```

Adapta tus correcciones según este perfil.
"""
                        # Añadir mensaje al thread
                        assistants_client.add_message_to_thread(new_thread_id, profile_message)
                        logger.info(f"Perfil añadido al nuevo thread {new_thread_id}")
            except Exception as e:
                logger.error(f"Error guardando thread en Firebase: {str(e)}")
    
    return content, data
