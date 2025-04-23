#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de generación de imágenes para descripción
------------------------------------------------
Este módulo contiene funciones para generar imágenes para prácticas de
descripción en español, usando DALL-E y la API directa de OpenAI.
"""

import logging
from typing import Optional, Tuple, Dict, Any

from core.openai_client import generar_imagen_dalle
from core.session_manager import get_session_var, set_session_var

logger = logging.getLogger(__name__)

def generar_imagen_descripcion(tema: str, nivel: str) -> Tuple[Optional[str], str, bool]:
    """
    Genera una imagen y su descripción para practicar.
    
    Args:
        tema: Tema para la imagen
        nivel: Nivel del estudiante (principiante, intermedio, avanzado)
        
    Returns:
        tuple: (url_imagen, descripción, éxito)
    """
    try:
        # Generar imagen y descripción con DALL-E
        imagen_url, descripcion = generar_imagen_dalle(tema, nivel)
        
        # Verificar que la generación fue exitosa
        if not imagen_url:
            logger.error(f"No se pudo generar la imagen para tema: {tema}")
            return None, f"Error al generar imagen para tema: {tema}", False
        
        # Guardar en session state
        set_session_var("imagen_url_state", imagen_url)
        set_session_var("descripcion_state", descripcion)
        set_session_var("imagen_generada_state", True)
        
        return imagen_url, descripcion, True
        
    except Exception as e:
        logger.error(f"Error al generar imagen para descripción: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None, f"Error: {str(e)}", False

def preparar_para_correccion(descripcion_estudiante: str, tema_imagen: str) -> bool:
    """
    Prepara la descripción del estudiante para corrección.
    
    Args:
        descripcion_estudiante: Texto escrito por el estudiante
        tema_imagen: Tema de la imagen
        
    Returns:
        bool: True si se preparó correctamente, False en caso contrario
    """
    try:
        if not descripcion_estudiante:
            return False
            
        # Guardar texto para corrección
        set_session_var("texto_correccion_corregir", descripcion_estudiante)
        set_session_var("info_adicional_corregir", f"Descripción de una imagen sobre: {tema_imagen}")
        
        # Marcar para mostrar corrección
        set_session_var("mostrar_correccion_imagen", True)
        
        return True
        
    except Exception as e:
        logger.error(f"Error al preparar para corrección: {str(e)}")
        return False

def get_ultimas_imagenes(max_items=5) -> list:
    """
    Obtiene las últimas imágenes generadas por el usuario.
    
    Args:
        max_items: Número máximo de imágenes a devolver
        
    Returns:
        list: Lista de imágenes con sus datos
    """
    try:
        # Intentar obtener historial de imágenes
        imagenes = get_session_var("historial_imagenes", [])
        
        # Devolver las últimas max_items
        return imagenes[-max_items:]
        
    except Exception as e:
        logger.error(f"Error al obtener últimas imágenes: {str(e)}")
        return []

def guardar_imagen_generada(imagen_url: str, descripcion: str, tema: str, nivel: str) -> bool:
    """
    Guarda una imagen generada en el historial del usuario.
    
    Args:
        imagen_url: URL de la imagen generada
        descripcion: Descripción generada
        tema: Tema de la imagen
        nivel: Nivel del estudiante
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener historial de imágenes
        imagenes = get_session_var("historial_imagenes", [])
        
        # Crear nueva entrada
        from datetime import datetime
        nueva_imagen = {
            "fecha": datetime.now().isoformat(),
            "imagen_url": imagen_url,
            "descripcion": descripcion,
            "tema": tema,
            "nivel": nivel
        }
        
        # Añadir al historial
        imagenes.append(nueva_imagen)
        
        # Limitar a 10 imágenes como máximo para no sobrecargar session_state
        if len(imagenes) > 10:
            imagenes = imagenes[-10:]
            
        # Guardar en session_state
        set_session_var("historial_imagenes", imagenes)
        
        # También guardar en Firebase si está disponible
        try:
            from core.firebase_client import initialize_firebase
            db, success = initialize_firebase()
            
            if success and db:
                uid = get_session_var("uid_usuario", "")
                if uid:
                    # Guardar en colección de imágenes del usuario
                    import uuid
                    imagen_id = str(uuid.uuid4())
                    # Guardar solo referencia a la imagen, no la URL completa
                    nueva_imagen_firebase = nueva_imagen.copy()
                    nueva_imagen_firebase["imagen_ref"] = imagen_id  # Referencia para posible recuperación futura
                    db.collection("usuarios").document(uid).collection("imagenes").document(imagen_id).set(nueva_imagen_firebase)
                    logger.info(f"Imagen guardada en Firebase para usuario {uid}")
        except Exception as firebase_error:
            logger.error(f"Error al guardar imagen en Firebase: {str(firebase_error)}")
            # Continuar sin guardar en Firebase
            
        return True
        
    except Exception as e:
        logger.error(f"Error al guardar imagen: {str(e)}")
        return False

def obtener_ejemplos_temas(nivel: str) -> list:
    """
    Obtiene ejemplos de temas para imágenes según el nivel.
    
    Args:
        nivel: Nivel del estudiante
        
    Returns:
        list: Lista de ejemplos de temas
    """
    # Temas para cada nivel
    tema_ejemplos = {
        "principiante": [
            "una familia en el parque",
            "mi rutina diaria",
            "un mercado local",
            "mi casa y habitación",
            "las cuatro estaciones"
        ],
        "intermedio": [
            "un festival cultural",
            "un viaje en tren",
            "un encuentro entre amigos",
            "un día en la ciudad",
            "un paisaje natural"
        ],
        "avanzado": [
            "una manifestación cultural",
            "un debate sobre medio ambiente",
            "la brecha tecnológica",
            "las diferencias socioeconómicas",
            "la preservación de tradiciones"
        ]
    }
    
    # Simplificar nivel
    nivel_simple = "intermedio"  # Default
    
    if "principiante" in nivel.lower():
        nivel_simple = "principiante"
    elif "intermedio" in nivel.lower():
        nivel_simple = "intermedio"
    elif "avanzado" in nivel.lower():
        nivel_simple = "avanzado"
    
    # Devolver ejemplos para el nivel
    return tema_ejemplos.get(nivel_simple, tema_ejemplos["intermedio"])
