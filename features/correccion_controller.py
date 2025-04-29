#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Controlador para la vista de corrección de textos
------------------------------------------------
Este módulo centraliza la lógica de controlador para la vista de corrección,
separando claramente las responsabilidades entre el modelo (lógica de negocio)
y la vista (presentación al usuario).
"""

import logging
import streamlit as st
import time
import traceback

# Importaciones del proyecto
from core.session_manager import get_user_info, get_session_var, set_session_var
from features.correccion_service import corregir_texto
from core.json_extractor import ensure_correction_structure

logger = logging.getLogger(__name__)

def handle_correction_request(text, level, detail="Intermedio", language="español"):
    """
    Maneja una solicitud de corrección de texto.
    
    Args:
        text (str): Texto a corregir
        level (str): Nivel de español (A1-C2)
        detail (str): Nivel de detalle de la corrección
        language (str): Idioma para las explicaciones
        
    Returns:
        dict: Resultado de la corrección o información de error
    """
    try:
        # Validar parámetros
        if not text or not text.strip():
            return {
                "error": True,
                "mensaje": "Por favor, introduce un texto para corregir",
                "tipo": "warning"
            }
            
        # Verificar longitud del texto
        if len(text) > 5000:
            return {
                "error": True,
                "mensaje": "El texto es demasiado largo. Por favor, limítalo a 5000 caracteres",
                "tipo": "warning"
            }
            
        # Mostrar mensaje de procesamiento
        with st.status("Procesando texto...", expanded=True) as status:
            st.write("Analizando texto...")
            
            # Obtener información del usuario actual
            user_info = get_user_info()
            user_id = user_info.get("uid") if user_info else None
            
            # Registrar inicio de procesamiento para métricas
            start_time = time.time()
            
            # Guardar texto para historia de correcciones
            set_session_var("ultimo_texto", text)
            
            # Procesar texto usando el servicio de corrección
            st.write("Aplicando correcciones...")
            correction_result = corregir_texto(
                texto_input=text,
                nivel=level,
                detalle=detail,
                user_id=user_id,
                idioma=language
            )
            
            # Registrar tiempo de procesamiento
            elapsed_time = time.time() - start_time
            logger.info(f"Corrección procesada en {elapsed_time:.2f} segundos")
            
            # Verificar si hay error en el resultado
            if correction_result and "error" in correction_result and correction_result["error"]:
                status.update(label="Error en el procesamiento", state="error")
                return {
                    "error": True,
                    "mensaje": correction_result.get("mensaje", "Error procesando la corrección"),
                    "tipo": "error",
                    "texto_original": text,
                    "detalles": correction_result
                }
                
            # Asegurar estructura completa del resultado
            result = ensure_correction_structure(correction_result, text)
            
            # Guardar thread_id para futuras correcciones
            if "thread_id" in correction_result:
                set_session_var("thread_id", correction_result["thread_id"])
                logger.info(f"Thread ID guardado: {correction_result['thread_id']}")
            
            # Incrementar contador de correcciones
            corrections_count = get_session_var("corrections_count", 0)
            set_session_var("corrections_count", corrections_count + 1)
            
            # Guardar historia de correcciones
            correction_history = get_session_var("correction_history", [])
            correction_history.append({
                "texto_original": text,
                "resultado": result,
                "nivel": level,
                "fecha": time.time(),
                "tiempo_procesamiento": elapsed_time
            })
            # Limitar historia a últimas 10 correcciones
            if len(correction_history) > 10:
                correction_history = correction_history[-10:]
            set_session_var("correction_history", correction_history)
            
            # Actualizar estado final
            status.update(label="¡Corrección completada!", state="complete")
            
            return result
            
    except Exception as e:
        # Capturar cualquier error inesperado
        error_details = traceback.format_exc()
        logger.error(f"Error en handle_correction_request: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        
        return {
            "error": True,
            "mensaje": f"Se produjo un error inesperado: {str(e)}",
            "tipo": "error",
            "texto_original": text
        }

def get_correction_metrics():
    """
    Obtiene métricas sobre las correcciones realizadas en la sesión actual.
    
    Returns:
        dict: Métricas de corrección
    """
    try:
        # Obtener historia de correcciones
        correction_history = get_session_var("correction_history", [])
        
        # Si no hay historia, devolver métricas vacías
        if not correction_history:
            return {
                "total_correcciones": 0,
                "tiempo_promedio": 0,
                "nivel_mas_comun": "Ninguno",
                "ultima_correccion": None
            }
        
        # Calcular métricas
        total_correcciones = len(correction_history)
        tiempos = [c.get("tiempo_procesamiento", 0) for c in correction_history if "tiempo_procesamiento" in c]
        tiempo_promedio = sum(tiempos) / len(tiempos) if tiempos else 0
        
        # Contar niveles para encontrar el más común
        niveles = {}
        for c in correction_history:
            nivel = c.get("nivel", "B1")
            niveles[nivel] = niveles.get(nivel, 0) + 1
        
        nivel_mas_comun = max(niveles.items(), key=lambda x: x[1])[0] if niveles else "Ninguno"
        
        # Obtener información de la última corrección
        ultima_correccion = correction_history[-1] if correction_history else None
        
        return {
            "total_correcciones": total_correcciones,
            "tiempo_promedio": tiempo_promedio,
            "nivel_mas_comun": nivel_mas_comun,
            "ultima_correccion": ultima_correccion
        }
        
    except Exception as e:
        logger.error(f"Error en get_correction_metrics: {str(e)}")
        return {
            "total_correcciones": 0,
            "tiempo_promedio": 0,
            "nivel_mas_comun": "Error",
            "ultima_correccion": None
        }

def display_correction_result(correction_result):
    """
    Muestra el resultado de una corrección en la interfaz de Streamlit.
    
    Args:
        correction_result (dict): Resultado de la corrección
        
    Returns:
        None
    """
    try:
        # Importar función de visualización
        from features.correccion_utils import display_correccion_result
        
        # Verificar si hay un error en el resultado
        if not correction_result:
            st.error("No se recibió respuesta del servicio de corrección")
            return
            
        if "error" in correction_result and correction_result["error"]:
            mensaje_error = correction_result.get("mensaje", "Error desconocido durante la corrección")
            tipo_error = correction_result.get("tipo", "error")
            
            if tipo_error == "warning":
                st.warning(mensaje_error)
            else:
                st.error(mensaje_error)
            
            # Si el thread se reinició, mostrar mensaje específico
            if correction_result.get("thread_reiniciado"):
                st.info("La sesión ha sido reiniciada. Por favor, intenta nuevamente tu corrección.")
            
            # Mostrar detalles técnicos si están disponibles
            if "detalles" in correction_result:
                with st.expander("Detalles técnicos (para desarrolladores)"):
                    st.json(correction_result["detalles"])
            
            # Mostrar el texto original si está disponible
            if "texto_original" in correction_result:
                with st.expander("Tu texto original"):
                    st.write(correction_result["texto_original"])
            
            return
        
        # Si no hay error, mostrar el resultado con la función específica
        display_correccion_result(correction_result)
        
    except Exception as e:
        # Capturar cualquier error en la visualización
        error_details = traceback.format_exc()
        logger.error(f"Error mostrando resultado: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        
        # Mostrar mensaje al usuario
        st.error(f"Error mostrando el resultado: {str(e)}")
        
        # Si tenemos el resultado original, intentar mostrar al menos el texto
        if isinstance(correction_result, dict):
            if "texto_corregido" in correction_result:
                st.subheader("Texto corregido")
                st.write(correction_result["texto_corregido"])
            elif "texto_original" in correction_result:
                with st.expander("Tu texto original"):
                    st.write(correction_result["texto_original"])
