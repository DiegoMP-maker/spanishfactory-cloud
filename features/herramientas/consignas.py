#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de generación de consignas para escritura
-----------------------------------------------
Este módulo contiene funciones para generar consignas de escritura adaptadas
al nivel del estudiante, usando la API directa de OpenAI.
"""

import logging
from typing import Optional, Tuple, Dict, Any

from core.openai_client import get_completion_direct
from core.session_manager import get_session_var, set_session_var
from config.prompts import get_consigna_prompt

logger = logging.getLogger(__name__)

def generar_consigna(nivel: str, tipo_texto: str) -> Tuple[str, bool]:
    """
    Genera una consigna de escritura adaptada al nivel y tipo de texto.
    
    Args:
        nivel: Nivel del estudiante (principiante, intermedio, avanzado)
        tipo_texto: Tipo de texto (general, narrativo, descriptivo, etc.)
        
    Returns:
        tuple: (consigna_generada, éxito)
    """
    try:
        # Obtener el prompt para consignas
        system_prompt = get_consigna_prompt()
        
        # Crear mensaje específico
        user_prompt = f"""
        Genera una consigna de escritura para:
        - Nivel: {nivel}
        - Tipo de texto: {tipo_texto}
        
        La consigna debe incluir:
        1. Un título atractivo
        2. Contexto o situación
        3. Tarea específica
        4. Extensión recomendada (palabras)
        5. Elementos lingüísticos sugeridos para este nivel
        
        Sé creativo pero realista, ofreciendo una actividad que motive al estudiante.
        """
        
        # Realizar llamada a OpenAI
        consigna_text, _ = get_completion_direct(system_prompt, user_prompt)
        
        # Verificar si hay error
        if not consigna_text:
            logger.error("No se pudo generar la consigna")
            return "Error al generar la consigna", False
        
        # Guardar en session state
        set_session_var("consigna_actual", consigna_text)
        
        return consigna_text, True
        
    except Exception as e:
        logger.error(f"Error al generar consigna: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error al generar la consigna: {str(e)}", False

def preparar_para_correccion(consigna: str) -> bool:
    """
    Prepara la sección de corrección para trabajar con la consigna generada.
    
    Args:
        consigna: Texto de la consigna
        
    Returns:
        bool: True si se preparó correctamente, False en caso contrario
    """
    try:
        if not consigna:
            return False
            
        # Guardar info para corrección
        set_session_var("texto_correccion_corregir", "")
        set_session_var("info_adicional_corregir", f"Respuesta a la consigna: {consigna[:100]}...")
        set_session_var("usar_consigna_como_texto", True)
        
        return True
        
    except Exception as e:
        logger.error(f"Error al preparar para corrección: {str(e)}")
        return False

def get_ultimas_consignas(max_items=5) -> list:
    """
    Obtiene las últimas consignas generadas para el usuario.
    
    Args:
        max_items: Número máximo de consignas a devolver
        
    Returns:
        list: Lista de consignas
    """
    try:
        # Intentar obtener historial de consignas
        consignas = get_session_var("historial_consignas", [])
        
        # Devolver las últimas max_items
        return consignas[-max_items:]
        
    except Exception as e:
        logger.error(f"Error al obtener últimas consignas: {str(e)}")
        return []

def guardar_consigna(consigna: str, nivel: str, tipo_texto: str) -> bool:
    """
    Guarda una consigna en el historial del usuario.
    
    Args:
        consigna: Texto de la consigna
        nivel: Nivel del estudiante
        tipo_texto: Tipo de texto
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener historial de consignas
        consignas = get_session_var("historial_consignas", [])
        
        # Crear nueva entrada
        from datetime import datetime
        nueva_consigna = {
            "fecha": datetime.now().isoformat(),
            "consigna": consigna,
            "nivel": nivel,
            "tipo_texto": tipo_texto
        }
        
        # Añadir al historial
        consignas.append(nueva_consigna)
        
        # Limitar a 20 consignas como máximo para no sobrecargar session_state
        if len(consignas) > 20:
            consignas = consignas[-20:]
            
        # Guardar en session_state
        set_session_var("historial_consignas", consignas)
        
        # También guardar en Firebase si está disponible
        try:
            from core.firebase_client import initialize_firebase
            db, success = initialize_firebase()
            
            if success and db:
                uid = get_session_var("uid_usuario", "")
                if uid:
                    # Guardar en colección de consignas del usuario
                    import uuid
                    consigna_id = str(uuid.uuid4())
                    db.collection("usuarios").document(uid).collection("consignas").document(consigna_id).set(nueva_consigna)
                    logger.info(f"Consigna guardada en Firebase para usuario {uid}")
        except Exception as firebase_error:
            logger.error(f"Error al guardar consigna en Firebase: {str(firebase_error)}")
            # Continuar sin guardar en Firebase
            
        return True
        
    except Exception as e:
        logger.error(f"Error al guardar consigna: {str(e)}")
        return False
    