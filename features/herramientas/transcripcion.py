#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de transcripción de textos manuscritos
--------------------------------------------
Este módulo contiene funciones para transcribir textos manuscritos usando
la API directa de OpenAI (Vision).
"""

import logging
from typing import Optional, Tuple

from core.openai_client import transcribir_imagen_texto
from core.session_manager import get_session_var, set_session_var
from config.settings import IDIOMA_MAP

logger = logging.getLogger(__name__)

def procesar_transcripcion(imagen_bytes, idioma="Español") -> Tuple[str, bool]:
    """
    Procesa una imagen para transcribir texto manuscrito y almacena el resultado.
    
    Args:
        imagen_bytes: Bytes de la imagen a transcribir
        idioma: Idioma del texto manuscrito
        
    Returns:
        tuple: (texto_transcrito, éxito)
    """
    try:
        # Obtener código de idioma
        codigo_idioma = IDIOMA_MAP.get(idioma, "es")
        
        # Transcribir texto usando OpenAI Vision
        texto_transcrito = transcribir_imagen_texto(imagen_bytes, codigo_idioma)
        
        # Verificar si hubo error
        if texto_transcrito and texto_transcrito.startswith("Error:"):
            logger.error(f"Error en la transcripción: {texto_transcrito}")
            return texto_transcrito, False
        
        # Guardar en session state
        set_session_var("ultimo_texto_transcrito", texto_transcrito)
        
        return texto_transcrito, True
        
    except Exception as e:
        logger.error(f"Error al procesar transcripción: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Error al procesar la transcripción: {str(e)}", False

def preparar_para_correccion(texto_transcrito: str) -> bool:
    """
    Prepara el texto transcrito para ser corregido en la sección de corrección.
    
    Args:
        texto_transcrito: Texto transcrito
        
    Returns:
        bool: True si se preparó correctamente, False en caso contrario
    """
    try:
        if not texto_transcrito or texto_transcrito.startswith("Error:"):
            return False
            
        # Guardar texto para corrección
        set_session_var("texto_correccion_corregir", texto_transcrito)
        set_session_var("info_adicional_corregir", "Texto transcrito de imagen manuscrita")
        
        # Marcar para mostrar corrección
        set_session_var("mostrar_correccion_transcripcion", True)
        
        # Cambiar a pestaña de corrección (se hará en la vista)
        # set_session_var("active_tab", 0)
        
        return True
        
    except Exception as e:
        logger.error(f"Error al preparar para corrección: {str(e)}")
        return False

def get_ultimas_transcripciones(max_items=5) -> list:
    """
    Obtiene las últimas transcripciones realizadas por el usuario.
    
    Args:
        max_items: Número máximo de transcripciones a devolver
        
    Returns:
        list: Lista de transcripciones
    """
    try:
        # Intentar obtener historial de transcripciones
        transcripciones = get_session_var("historial_transcripciones", [])
        
        # Devolver las últimas max_items
        return transcripciones[-max_items:]
        
    except Exception as e:
        logger.error(f"Error al obtener últimas transcripciones: {str(e)}")
        return []

def guardar_transcripcion(texto_transcrito: str, texto_editado: str = None, idioma: str = "Español") -> bool:
    """
    Guarda una transcripción en el historial del usuario.
    
    Args:
        texto_transcrito: Texto transcrito original
        texto_editado: Texto editado por el usuario (opcional)
        idioma: Idioma del texto
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener historial de transcripciones
        transcripciones = get_session_var("historial_transcripciones", [])
        
        # Crear nueva entrada
        from datetime import datetime
        nueva_transcripcion = {
            "fecha": datetime.now().isoformat(),
            "texto_original": texto_transcrito,
            "texto_editado": texto_editado if texto_editado else texto_transcrito,
            "idioma": idioma
        }
        
        # Añadir al historial
        transcripciones.append(nueva_transcripcion)
        
        # Limitar a 20 transcripciones como máximo para no sobrecargar session_state
        if len(transcripciones) > 20:
            transcripciones = transcripciones[-20:]
            
        # Guardar en session_state
        set_session_var("historial_transcripciones", transcripciones)
        
        # También guardar en Firebase si está disponible
        try:
            from core.firebase_client import initialize_firebase
            db, success = initialize_firebase()
            
            if success and db:
                uid = get_session_var("uid_usuario", "")
                if uid:
                    # Guardar en colección de transcripciones del usuario
                    import uuid
                    transcripcion_id = str(uuid.uuid4())
                    db.collection("usuarios").document(uid).collection("transcripciones").document(transcripcion_id).set(nueva_transcripcion)
                    logger.info(f"Transcripción guardada en Firebase para usuario {uid}")
        except Exception as firebase_error:
            logger.error(f"Error al guardar transcripción en Firebase: {str(firebase_error)}")
            # Continuar sin guardar en Firebase
            
        return True
        
    except Exception as e:
        logger.error(f"Error al guardar transcripción: {str(e)}")
        return False
    