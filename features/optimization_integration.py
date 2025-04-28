st.write(f"Tiempo: {m.get('processing_time', 0):.2f}s")
                st.write(f"Longitud del mensaje: {m.get('message_length', 0)} caracteres")
                st.write(f"Thread ID: {m.get('thread_id', 'N/A')}")
                st.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m.get('timestamp', 0)))}")
    except Exception as e:
        st.error(f"Error mostrando métricas: {e}")

def optimize_assistant_configuration():
    """
    Optimiza la configuración del asistente para reducir consumo de tokens.
    Se puede llamar al inicio de la aplicación.
    
    Returns:
        bool: True si la optimización fue exitosa
    """
    try:
        # Configurar ajustes globales de optimización
        if "optimization_settings" not in st.session_state:
            st.session_state["optimization_settings"] = {
                "max_messages_per_thread": 15,
                "force_json_response": True,
                "use_optimized_prompts": True,
                "auto_context_optimization": True,
                "timeout_correction": 180,  # 3 minutos para correcciones
                "timeout_other": 120        # 2 minutos para otras tareas
            }
        
        # Obtener cliente para verificar configuración
        from core.clean_openai_assistant import get_clean_openai_assistants_client
        client = get_clean_openai_assistants_client()
        
        if not client:
            logger.error("No se pudo obtener cliente para optimizar configuración")
            return False
        
        # Verificar y preparar threads optimizados
        user_info = get_user_info()
        user_id = user_info.get("uid") if user_info else None
        
        if user_id:
            # Verificar thread actual
            thread_id = get_optimized_thread(user_id)
            if thread_id:
                logger.info(f"Thread optimizado preparado: {thread_id}")
                
                # Registrar tiempo inicial si es nuevo
                if f"thread_{thread_id}_created_at" not in st.session_state:
                    st.session_state[f"thread_{thread_id}_created_at"] = time.time()
        
        logger.info("Configuración del asistente optimizada correctamente")
        return True
    
    except Exception as e:
        logger.error(f"Error optimizando configuración: {e}")
        return False
