#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gestor de threads para OpenAI Assistants
----------------------------------------
Este módulo proporciona funciones para gestionar el historial de threads,
incluyendo limitación de mensajes para optimizar el uso de tokens.
"""

import logging
import traceback

logger = logging.getLogger(__name__)

def limit_thread_history(client, thread_id, max_messages=2):
    """
    Limita el historial de un thread manteniendo solo un número específico de mensajes.
    Conserva el mensaje más reciente del usuario y las respuestas más recientes del asistente.
    
    Args:
        client: Cliente de OpenAI Assistants
        thread_id (str): ID del thread a limitar
        max_messages (int, opcional): Número máximo de intercambios a mantener
        
    Returns:
        bool: True si se limitó correctamente, False en caso contrario
    """
    try:
        if not thread_id or not client:
            logger.warning("thread_id o client inválido en limit_thread_history")
            return False
        
        # Verificar que el thread existe
        if not client.verify_thread(thread_id):
            logger.warning(f"Thread inválido: {thread_id}")
            return False
        
        # Obtener todos los mensajes del thread
        messages_response = client.list_messages(thread_id, limit=50)  # Obtener suficientes mensajes
        
        if not messages_response or "data" not in messages_response:
            logger.error("Error obteniendo mensajes del thread")
            return False
        
        all_messages = messages_response.get("data", [])
        
        # Si hay menos mensajes que el límite, no hay necesidad de limpiar
        if len(all_messages) <= max_messages * 2:  # * 2 porque contamos pares (usuario + asistente)
            logger.info(f"El thread {thread_id} tiene {len(all_messages)} mensajes, no necesita limpieza")
            return True
        
        # Agrupar mensajes por intercambios (usuario + asistente)
        exchanges = []
        current_exchange = []
        
        for message in all_messages:
            if not current_exchange:
                # Nuevo intercambio
                current_exchange.append(message)
            elif message["role"] != current_exchange[-1]["role"]:
                # Si es un rol diferente al último mensaje, añadir al intercambio actual
                current_exchange.append(message)
                
                # Si tenemos un par completo (usuario + asistente), guardar y reiniciar
                if len(current_exchange) >= 2:
                    exchanges.append(current_exchange)
                    current_exchange = []
            else:
                # Si es el mismo rol, iniciar un nuevo intercambio
                exchanges.append(current_exchange)
                current_exchange = [message]
        
        # Añadir el último intercambio incompleto si existe
        if current_exchange:
            exchanges.append(current_exchange)
        
        # Conservar solo los intercambios más recientes según el límite
        exchanges_to_keep = exchanges[:max_messages]
        exchanges_to_remove = exchanges[max_messages:]
        
        # Extraer los IDs de mensajes a mantener
        message_ids_to_keep = []
        for exchange in exchanges_to_keep:
            for message in exchange:
                message_ids_to_keep.append(message["id"])
                
        # Identificar mensajes a eliminar
        messages_to_delete = []
        for exchange in exchanges_to_remove:
            for message in exchange:
                if message["id"] not in message_ids_to_keep:
                    messages_to_delete.append(message["id"])
        
        # Eliminar los mensajes antiguos
        for message_id in messages_to_delete:
            # La API de OpenAI Assistants v2 no permite eliminar mensajes individuales
            # pero podemos mantener esta lógica para futuras implementaciones
            logger.info(f"Se eliminaría el mensaje {message_id} si la API lo permitiera")
        
        # Crear un nuevo thread con los mensajes que queremos conservar
        # (Esta es una solución temporal hasta que OpenAI permita eliminar mensajes)
        try:
            # Crear nuevo thread
            new_thread = client.create_thread()
            if not new_thread or "id" not in new_thread:
                logger.error("Error creando nuevo thread para limpieza")
                return False
            
            new_thread_id = new_thread["id"]
            logger.info(f"Nuevo thread creado para limpieza: {new_thread_id}")
            
            # Añadir los mensajes conservados al nuevo thread (en orden inverso para mantener cronología)
            messages_to_keep = []
            for exchange in reversed(exchanges_to_keep):
                for message in exchange:
                    messages_to_keep.append(message)
                    
            # Ordenar mensajes por creación (de más antiguos a más recientes)
            messages_to_keep.sort(key=lambda x: x.get("created_at", 0))
            
            # Añadir los mensajes al nuevo thread
            for message in messages_to_keep:
                # Extraer contenido del mensaje
                content_text = ""
                for content_item in message.get("content", []):
                    if content_item["type"] == "text":
                        content_text += content_item["text"]["value"]
                
                # Añadir al nuevo thread
                client.add_message_to_thread(new_thread_id, content_text, role=message["role"])
            
            # Actualizar el thread_id en la sesión y Firebase
            from core.session_manager import set_session_var, get_user_info
            set_session_var("thread_id", new_thread_id)
            
            # Actualizar en Firebase si hay usuario
            user_info = get_user_info()
            if user_info and "uid" in user_info:
                user_id = user_info["uid"]
                try:
                    from core.firebase_client import save_user_thread
                    save_user_thread(user_id, new_thread_id)
                    logger.info(f"Thread actualizado en Firebase para usuario {user_id}")
                except Exception as e:
                    logger.warning(f"Error guardando nuevo thread en Firebase: {str(e)}")
            
            logger.info(f"Historial de thread limitado exitosamente. Nuevo thread: {new_thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error en la limpieza del thread: {str(e)}")
            return False
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error en limit_thread_history: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return False

def should_limit_thread(client, thread_id, message_threshold=10):
    """
    Determina si un thread debe ser limitado basado en el número de mensajes.
    
    Args:
        client: Cliente de OpenAI Assistants
        thread_id (str): ID del thread a verificar
        message_threshold (int, opcional): Umbral de mensajes para limitar
        
    Returns:
        bool: True si el thread debe ser limitado, False en caso contrario
    """
    try:
        if not thread_id or not client:
            return False
        
        # Verificar que el thread existe
        if not client.verify_thread(thread_id):
            return False
        
        # Obtener mensajes del thread
        messages_response = client.list_messages(thread_id, limit=message_threshold+1)
        
        if not messages_response or "data" not in messages_response:
            return False
        
        # Verificar si el número de mensajes supera el umbral
        message_count = len(messages_response.get("data", []))
        should_limit = message_count > message_threshold
        
        if should_limit:
            logger.info(f"Thread {thread_id} tiene {message_count} mensajes, superando el umbral de {message_threshold}")
        
        return should_limit
        
    except Exception as e:
        logger.error(f"Error en should_limit_thread: {str(e)}")
        return False
