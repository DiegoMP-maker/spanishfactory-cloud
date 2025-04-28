#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gestor de Threads para OpenAI Assistants
----------------------------------------
Implementa estrategias para reducir el consumo de tokens controlando
el tamaño y vida útil de los threads.
"""

import logging
import streamlit as st
import time

from core.clean_openai_assistant import get_clean_openai_assistants_client, reset_thread
from core.session_manager import get_session_var, set_session_var
from core.firebase_client import get_user_thread, save_user_thread, get_thread_message_count

logger = logging.getLogger(__name__)

# Umbrales de gestión de threads
MAX_MESSAGES_PER_THREAD = 15    # Número máximo de mensajes antes de rotar
MAX_THREAD_AGE_HOURS = 24       # Edad máxima del thread en horas
MAX_THREAD_SIZE_KB = 50         # Tamaño aproximado máximo en KB

def get_optimized_thread(user_id=None, force_new=False):
    """
    Obtiene un thread optimizado para el usuario, rotando automáticamente
    cuando se alcanzan ciertos umbrales de tamaño o antigüedad.
    
    Args:
        user_id (str, opcional): ID del usuario
        force_new (bool): Forzar creación de un nuevo thread
        
    Returns:
        str: ID del thread optimizado o None si hay error
    """
    try:
        # Si se solicita forzar nuevo thread, reiniciar directamente
        if force_new:
            logger.info("Forzando creación de nuevo thread")
            return reset_thread(user_id)
        
        # Obtener thread actual
        current_thread_id = get_session_var("thread_id")
        
        # Si no hay thread en session, intentar obtener de Firebase
        if not current_thread_id and user_id:
            current_thread_id = get_user_thread(user_id)
            
            if current_thread_id:
                # Guardar en session para facilitar acceso
                set_session_var("thread_id", current_thread_id)
                logger.info(f"Thread recuperado de Firebase: {current_thread_id}")
        
        # Si no hay thread, crear uno nuevo
        if not current_thread_id:
            logger.info("No se encontró thread existente, creando uno nuevo")
            return reset_thread(user_id)
        
        # Comprobar criterios de rotación
        should_rotate = False
        rotation_reason = ""
        
        # 1. Comprobar número de mensajes
        message_count = get_thread_message_count(current_thread_id)
        if message_count and message_count > MAX_MESSAGES_PER_THREAD:
            should_rotate = True
            rotation_reason = f"thread alcanzó {message_count} mensajes (máximo: {MAX_MESSAGES_PER_THREAD})"
        
        # 2. Comprobar antigüedad del thread
        thread_creation_time = get_session_var(f"thread_{current_thread_id}_created_at")
        if not thread_creation_time:
            # Si no tenemos tiempo de creación, asumir ahora
            thread_creation_time = time.time()
            set_session_var(f"thread_{current_thread_id}_created_at", thread_creation_time)
        
        thread_age_hours = (time.time() - thread_creation_time) / 3600
        if thread_age_hours > MAX_THREAD_AGE_HOURS:
            should_rotate = True
            rotation_reason = f"thread tiene {int(thread_age_hours)} horas (máximo: {MAX_THREAD_AGE_HOURS})"
        
        # 3. Intento de estimación de tamaño basado en mensajes
        if message_count:
            # Estimación simple: asumimos 3KB por mensaje en promedio
            estimated_size_kb = message_count * 3
            if estimated_size_kb > MAX_THREAD_SIZE_KB:
                should_rotate = True
                rotation_reason = f"thread alcanzó tamaño estimado de {estimated_size_kb}KB (máximo: {MAX_THREAD_SIZE_KB}KB)"
        
        # Si se cumplen criterios de rotación, crear nuevo thread
        if should_rotate:
            logger.info(f"Rotando thread porque {rotation_reason}")
            return reset_thread(user_id)
        
        # Si no hay necesidad de rotar, verificar validez del thread
        client = get_clean_openai_assistants_client()
        if client and client.verify_thread(current_thread_id):
            logger.info(f"Usando thread existente optimizado: {current_thread_id}")
            return current_thread_id
        else:
            logger.warning(f"Thread existente {current_thread_id} no es válido, creando uno nuevo")
            return reset_thread(user_id)
            
    except Exception as e:
        logger.error(f"Error en get_optimized_thread: {e}")
        # En caso de error, intentar crear un nuevo thread como fallback
        return reset_thread(user_id)

def summarize_thread_context(thread_id, user_id=None):
    """
    Crea un resumen del contexto actual del thread para reducir tokens
    mientras mantiene información importante.
    
    Args:
        thread_id (str): ID del thread a resumir
        user_id (str, opcional): ID del usuario
        
    Returns:
        bool: True si el resumen se realizó correctamente
    """
    try:
        client = get_clean_openai_assistants_client()
        if not client:
            logger.error("No se pudo obtener cliente para resumir thread")
            return False
        
        # Obtener mensajes del thread
        messages_response = client.list_messages(thread_id, limit=50)
        
        if not messages_response or "data" not in messages_response:
            logger.error("No se pudieron obtener mensajes para resumir")
            return False
        
        messages = messages_response.get("data", [])
        
        # Si hay pocos mensajes, no es necesario resumir
        if len(messages) < 10:
            logger.info(f"Thread {thread_id} tiene solo {len(messages)} mensajes, no es necesario resumir")
            return True
        
        # Crear mensaje de resumen para el asistente
        summary_prompt = """
        Por favor, crea un resumen conciso del contexto de nuestra conversación hasta ahora.
        Incluye solo la información esencial que necesitarías para continuar asistiendo al usuario.
        Este resumen reemplazará parte del historial para optimizar el uso de tokens.
        """
        
        # Añadir mensaje de solicitud de resumen
        client.add_message_to_thread(thread_id, summary_prompt)
        
        # Ejecutar asistente para generar resumen
        assistant_id = client.get_assistant_id("resumen_contexto", "Crea un resumen conciso del contexto")
        run_response = client.run_assistant(thread_id, assistant_id)
        
        if not run_response or "id" not in run_response:
            logger.error("No se pudo iniciar ejecución para resumir thread")
            return False
        
        run_id = run_response["id"]
        
        # Esperar a que se complete (timeout más corto ya que es una tarea simple)
        max_wait = 30  # 30 segundos máximo
        start_time = time.time()
        
        while True:
            if time.time() - start_time > max_wait:
                logger.warning("Timeout esperando resumen de thread")
                return False
                
            run_status = client.get_run(thread_id, run_id)
            
            if not run_status or "status" not in run_status:
                logger.error("Error obteniendo estado de ejecución de resumen")
                return False
                
            status = run_status["status"]
            
            if status == "completed":
                logger.info("Resumen de thread completado")
                break
                
            if status in ["failed", "cancelled", "expired"]:
                logger.error(f"Ejecución de resumen fallida: {status}")
                return False
                
            time.sleep(1)
        
        # Crear nuevo thread con el resumen como primer mensaje
        new_thread = client.create_thread(user_id=user_id)
        
        if not new_thread or "id" not in new_thread:
            logger.error("No se pudo crear nuevo thread para resumen")
            return False
            
        new_thread_id = new_thread["id"]
        
        # Obtener el resumen generado
        messages_after = client.list_messages(thread_id, limit=1)
        if not messages_after or "data" not in messages_after or not messages_after["data"]:
            logger.error("No se pudo obtener el resumen generado")
            return False
            
        summary_message = None
        for msg in messages_after["data"]:
            if msg["role"] == "assistant":
                summary_message = msg
                break
                
        if not summary_message:
            logger.error("No se encontró mensaje de resumen del asistente")
            return False
            
        # Extraer contenido del resumen
        summary_content = ""
        for content_item in summary_message.get("content", []):
            if content_item["type"] == "text":
                summary_content += content_item["text"]["value"]
        
        # Añadir resumen como primer mensaje en el nuevo thread
        context_message = f"""
        RESUMEN DEL CONTEXTO PREVIO:
        
        {summary_content}
        
        (Este es un resumen automático de la conversación previa para optimizar el uso de tokens)
        """
        
        client.add_message_to_thread(new_thread_id, context_message)
        
        # Actualizar referencias al thread
        set_session_var("thread_id", new_thread_id)
        if user_id:
            save_user_thread(user_id, new_thread_id)
            
        # Registrar tiempo de creación
        set_session_var(f"thread_{new_thread_id}_created_at", time.time())
        
        logger.info(f"Thread resumido correctamente. Nuevo thread_id: {new_thread_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error en summarize_thread_context: {e}")
        return False
        
def clear_thread_history(user_id=None):
    """
    Limpia completamente el historial creando un nuevo thread vacío.
    Útil cuando el usuario quiere empezar de cero.
    
    Args:
        user_id (str, opcional): ID del usuario
        
    Returns:
        str: ID del nuevo thread o None si hay error
    """
    logger.info(f"Limpiando historial para usuario: {user_id}")
    return reset_thread(user_id)
