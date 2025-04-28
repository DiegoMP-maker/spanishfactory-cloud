# Añade esta función en core/clean_openai_assistant.py, al final del archivo pero antes 
# de la función get_clean_openai_assistants_client()

def reset_thread(user_id=None):
    """
    Reinicia el thread para un usuario, creando uno nuevo y limpiando referencias al antiguo.
    Útil cuando hay problemas con threads existentes que generan errores 500.
    
    Args:
        user_id (str, opcional): ID del usuario
        
    Returns:
        str: ID del nuevo thread o None si hay error
    """
    try:
        # Limpiar variables de entorno de proxies
        if "HTTP_PROXY" in os.environ:
            del os.environ["HTTP_PROXY"]
        if "HTTPS_PROXY" in os.environ:
            del os.environ["HTTPS_PROXY"]
        
        # Obtener API key
        from core.openai_utils import get_openai_api_key
        api_key = get_openai_api_key()
        
        if not api_key:
            logger.error("API key de OpenAI no configurada")
            return None
        
        # Crear cliente
        client = CleanOpenAIAssistants(api_key=api_key)
        
        # Eliminar thread_id de session_state si existe
        if "thread_id" in st.session_state:
            logger.info(f"Eliminando thread_id {st.session_state['thread_id']} de session_state")
            del st.session_state["thread_id"]
        
        # Si hay user_id, limpiar también en Firebase
        if user_id:
            try:
                from core.firebase_client import save_user_thread
                logger.info(f"Limpiando thread_id para usuario {user_id} en Firebase")
                # Pasar None como thread_id para indicar que no hay thread activo
                save_user_thread(user_id, None)
            except Exception as e:
                logger.warning(f"Error limpiando thread en Firebase: {str(e)}")
        
        # Crear nuevo thread
        logger.info("Creando nuevo thread después de reset")
        thread_response = client.create_thread(user_id=user_id)
        
        if thread_response and "id" in thread_response:
            thread_id = thread_response["id"]
            
            # Guardar en session_state
            st.session_state["thread_id"] = thread_id
            
            # Si hay user_id, guardar en Firebase
            if user_id:
                try:
                    from core.firebase_client import save_user_thread
                    save_user_thread(user_id, thread_id)
                    logger.info(f"Nuevo thread {thread_id} guardado en Firebase para usuario {user_id}")
                except Exception as e:
                    logger.warning(f"Error guardando nuevo thread en Firebase: {str(e)}")
            
            logger.info(f"Thread reiniciado exitosamente. Nuevo thread_id: {thread_id}")
            return thread_id
        else:
            logger.error("No se pudo crear un nuevo thread después de reset")
            return None
    
    except Exception as e:
        logger.error(f"Error en reset_thread: {str(e)}")
        return None
