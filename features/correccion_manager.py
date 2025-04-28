#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Controlador del flujo de corrección de textos
---------------------------------------------
Este módulo centraliza la lógica de corrección de textos,
separando claramente las responsabilidades entre la integración con
OpenAI, el manejo de datos en Firebase, y la presentación al usuario.
"""

import logging
import json
import re
import traceback
import streamlit as st

# Importaciones del proyecto
from core.openai_integration import process_with_assistant, get_user_profile_data
from core.circuit_breaker import circuit_breaker
from core.session_manager import get_user_info, get_session_var, set_session_var
from features.functions_definitions import get_evaluation_criteria

logger = logging.getLogger(__name__)

# System prompt completo para el asistente de corrección (importado desde correccion.py)
SYSTEM_PROMPT_CORRECTION = """🧩 Contexto:
Eres un experto corrector de textos para estudiantes de Español como Lengua Extranjera (ELE). 

INSTRUCCIÓN FUNDAMENTAL: ANTES de cada evaluación, consulta siempre el documento "base_criterios_evaluacion_niveles_mcer.md" (vs_680e701439748191be95055ca9f55531) para asegurar una evaluación rigurosa y consistente según los niveles del MCER. Los criterios de ese documento son tu guía oficial de evaluación.

Tu tarea es analizar, corregir y explicar los errores del texto respetando rigurosamente la estructura JSON solicitada.
Debes aplicar criterios estrictos y objetivos según el nivel MCER (A1-C2) declarado, sin ser excesivamente indulgente y manteniendo estándares académicos apropiados.

📊 Información de perfil:
Debes prestar especial atención a los mensajes que contienen "PERFIL DEL ESTUDIANTE" o "CONTEXTO DEL ESTUDIANTE", que incluyen información crucial como:
- Nivel MCER (A1 a C2)
- Idioma nativo del estudiante
- Objetivos de aprendizaje específicos
- Áreas de interés temático
- Estadísticas de errores previos (áreas problemáticas)
- Preferencias de feedback
- Número de correcciones previas

📋 CRITERIOS ESTRICTOS DE EVALUACIÓN POR NIVEL:
Debes aplicar rigurosamente los criterios del documento de referencia knowledge_base_criterios_evaluacion_niveles_mcer.md, que define claramente:

- Lo que es aceptable e inaceptable para cada nivel MCER
- Las puntuaciones máximas según nivel y cantidad de errores
- Ejemplos concretos de errores críticos por nivel
- Guías para la identificación correcta del tipo de texto

👨‍🏫 Rol:
Actúas como evaluador crítico pero constructivo de ELE, y tu misión es detectar errores y brindar explicaciones claras y pedagógicas. Los tipos de errores a identificar y clasificar son:

Gramática: errores de conjugación, concordancia, uso incorrecto de tiempos verbales, preposiciones, artículos, etc.

Léxico: vocabulario inadecuado, falsos amigos, colocaciones incorrectas, repeticiones innecesarias, etc.

Puntuación: comas, puntos, acentos, mayúsculas, etc.

Estructura textual: organización del texto, párrafos, conectores, etc.

Adicionalmente, debes realizar un análisis contextual con cuatro componentes:

Coherencia: lógica interna del texto, progresión temática.

Cohesión: uso de conectores, referencias, etc.

Registro lingüístico: formalidad, adecuación a la situación comunicativa.

Adecuación cultural: aspectos socioculturales relevantes.

📝 Instrucciones de corrección:
Clasifica TODOS los errores detectados en las categorías indicadas dentro del campo "errores" del JSON. No omitas ningún error aunque parezca menor.

IMPORTANTE: Identifica correctamente el tipo de texto (email, narración, argumentación, etc.) basándote en su estructura y propósito, no solo en su contenido.

Para cada error incluye:

fragmento_erroneo: la parte exacta del texto que contiene el error.

correccion: cómo debería escribirse correctamente.

explicacion: una breve explicación pedagógica en el idioma del estudiante, adaptada a su nivel y su idioma nativo.

Respeta estrictamente la estructura JSON siguiente:


OBLIGATORIAMENTE debes entregar tu respuesta siguiendo esta estructura JSON exacta:
{
  "saludo": "string",                // en {idioma} - personalizado para el estudiante
  "tipo_texto": "string",            // en {idioma} - identifica correctamente el formato (email, narración, etc.)
  "errores": {
       "Gramática": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en {idioma}
           }
           // más errores de Gramática (o [] si ninguno)
       ],
       "Léxico": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en {idioma}
           }
       ],
       "Puntuación": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en {idioma}
           }
       ],
       "Estructura textual": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en {idioma}
           }
       ]
  },
  "texto_corregido": "string",       // siempre en español
  "analisis_contextual": {
       "coherencia": {
           "puntuacion": number,     // del 1 al 10, siguiendo estrictamente la tabla de puntuaciones
           "comentario": "string",   // en {idioma}
           "sugerencias": [          // listado de sugerencias en {idioma}
               "string",
               "string"
           ]
       },
       "cohesion": {
           "puntuacion": number,     // del 1 al 10, siguiendo estrictamente la tabla de puntuaciones
           "comentario": "string",   // en {idioma}
           "sugerencias": [          // listado de sugerencias en {idioma}
               "string",
               "string"
           ]
       },
       "registro_linguistico": {
           "puntuacion": number,     // del 1 al 10, siguiendo estrictamente la tabla de puntuaciones
           "tipo_detectado": "string", // tipo de registro detectado en {idioma}
           "adecuacion": "string",   // evaluación de adecuación en {idioma}
           "sugerencias": [          // listado de sugerencias en {idioma}
               "string",
               "string"
           ]
       },
       "adecuacion_cultural": {
           "puntuacion": number,     // del 1 al 10, siguiendo estrictamente la tabla de puntuaciones
           "comentario": "string",   // en {idioma}
           "elementos_destacables": [  // elementos culturales destacables en {idioma}
               "string",
               "string"
           ],
           "sugerencias": [          // listado de sugerencias en {idioma}
               "string",
               "string"
           ]
       }
  },
  "consejo_final": "string",         // en español
  "fin": "Fin de texto corregido."
}

🟠 Penalización de errores según perfil del alumno:
Sé estrictamente objetivo y aplica los criterios de evaluación según el nivel MCER declarado, siguiendo la tabla de máximos de puntuación del documento de referencia:

| Nivel | Muchos errores | Errores moderados | Pocos errores |
|-------|----------------|-------------------|---------------|
| A1    | 5/10           | 6/10              | 7/10          |
| A2    | 4/10           | 6/10              | 7/10          |
| B1    | 3/10           | 5/10              | 6/10          |
| B2    | 2/10           | 4/10              | 6/10          |
| C1    | 2/10           | 3/10              | 5/10          |
| C2    | 1/10           | 2/10              | 4/10          |

🌱 Adaptación del feedback:
- Mantén un tono constructivo pero realista. No exageres elogios cuando el texto tiene problemas significativos.
- Identifica patrones de error (errores repetitivos o sistemáticos) y destácalos claramente.
- Ofrece sugerencias concretas y relevantes al nivel del estudiante.
- Prioriza los errores que impiden la comunicación efectiva o que son inapropiados para el nivel declarado.

🌱 Consejo final:
El "consejo_final" debe ser siempre en español, con tono pedagógico y motivador pero honesto. Resume las áreas principales que necesitan mejora y proporciona directrices claras para el progreso.


INSTRUCCIONES CRÍTICAS:
- Las explicaciones y comentarios DEBEN estar en el idioma especificado ({idioma}).
- El texto corregido completo SIEMPRE debe estar en español.
- El consejo final SIEMPRE debe estar en español.
- Adapta tus explicaciones y sugerencias al nivel indicado del estudiante.
- Considera el tipo de texto y el contexto cultural en tu análisis.
- Cada error debe incluir un fragmento específico del texto original, no generalidades.
- Las puntuaciones deben basarse en criterios objetivos y ser consistentes con el nivel.
- Sugerencias concretas y aplicables que el estudiante pueda implementar.
- Asegúrate de que el texto corregido mantenga la voz y estilo del estudiante.


OBLIGATORIO: Devuelve tu respuesta solo como un objeto JSON válido, sin texto adicional antes ni después. El JSON debe contener la palabra "json" para asegurar un procesamiento correcto."""

def corregir_texto(texto_input, nivel, detalle="Intermedio", user_id=None, idioma="español"):
    """
    Procesa un texto para obtener correcciones utilizando OpenAI Assistants v2.
    Implementación mejorada con function calling y manejo robusto de errores.
    
    Args:
        texto_input (str): Texto a corregir
        nivel (str): Nivel de español del estudiante
        detalle (str): Nivel de detalle para las correcciones
        user_id (str, opcional): ID del usuario
        idioma (str, opcional): Idioma para las explicaciones
        
    Returns:
        dict: Resultado de la corrección o diccionario con información de error
    """
    try:
        # Validación inicial del texto
        if texto_input is None:
            logger.error("El parámetro 'texto_input' es None")
            return {
                "error": True,
                "mensaje": "No se proporcionó texto para corregir",
                "texto_original": ""
            }
        
        # Verificar que el texto no esté vacío
        if not isinstance(texto_input, str):
            logger.error(f"El parámetro 'texto_input' no es una cadena: {type(texto_input)}")
            texto_input = str(texto_input) if texto_input is not None else ""
            
        if not texto_input.strip():
            logger.warning("Texto vacío para corrección")
            return {
                "error": True,
                "mensaje": "No se proporcionó texto para corregir",
                "texto_original": texto_input
            }
        
        # Validación de nivel
        if not nivel or not isinstance(nivel, str):
            logger.warning(f"Nivel inválido: {nivel}")
            nivel = "B1"  # Valor por defecto
        
        # Inicializar thread_id
        thread_id = get_session_var("thread_id")
        
        # Verificar circuit breaker para OpenAI
        if not circuit_breaker.can_execute("openai"):
            logger.error("Circuit breaker abierto para OpenAI")
            return {
                "error": True, 
                "mensaje": "Servicio temporalmente no disponible. Por favor, inténtalo de nuevo más tarde.",
                "texto_original": texto_input
            }
        
        # Preparar mensaje para el asistente
        user_message = (
            f"Por favor, corrige el siguiente texto de nivel {nivel}. " 
            f"Nivel de detalle: {detalle}. Idioma para explicaciones: {idioma}.\n\n"
            f"TEXTO PARA CORREGIR:\n\"{texto_input}\"\n\n"
            f"Por favor, analiza y corrige todos los errores. Utiliza la función 'get_evaluation_criteria' "
            f"para obtener los criterios específicos para este nivel y 'get_user_profile' si necesitas "
            f"información detallada del estudiante."
        )
        
        # Procesar con OpenAI Assistants v2 usando function calling
        logger.info(f"Enviando texto de longitud {len(texto_input)} a procesar")
        content, data = process_with_assistant(
            system_message=SYSTEM_PROMPT_CORRECTION,
            user_message=user_message,
            task_type="correccion_texto",
            thread_id=thread_id,
            user_id=user_id
        )
        
        # Verificar resultado
        logger.info(f"Recibida respuesta: content={type(content)}, data={type(data) if data is not None else None}")
        
        # Si no hay respuesta, devolver error
        if content is None and data is None:
            logger.error("No se obtuvo respuesta del asistente")
            return {
                "error": True,
                "mensaje": "No se pudo obtener una respuesta del servicio. Por favor, inténtalo de nuevo más tarde.",
                "texto_original": texto_input
            }
        
        # Si hay un error en los datos, devolverlo
        if isinstance(data, dict) and "error" in data:
            logger.error(f"Error en la respuesta del asistente: {data.get('error')}")
            return {
                "error": True,
                "mensaje": data.get("error", "Error procesando la solicitud"),
                "texto_original": texto_input
            }
        
        # Validar estructura del JSON de respuesta
        if not isinstance(data, dict) or "errores" not in data:
            logger.warning("Respuesta sin estructura esperada")
            
            # Si hay contenido pero no JSON válido, intentar extraer manualmente
            if content:
                # Intentar extraer JSON con regex
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        logger.info("JSON extraído con regex de código")
                    except json.JSONDecodeError:
                        logger.warning("Error decodificando JSON dentro de bloques de código")
                
                # Si no hay coincidencia, intentar parsear todo el contenido
                if not isinstance(data, dict) or "errores" not in data:
                    try:
                        data = json.loads(content)
                        logger.info("Content completo procesado como JSON")
                    except json.JSONDecodeError:
                        logger.warning("El content no es un JSON válido")
            
            # Si aún no tenemos datos válidos, crear estructura mínima
            if not isinstance(data, dict) or "errores" not in data:
                logger.warning("Creando estructura mínima para datos")
                data = {
                    "texto_original": texto_input,
                    "texto_corregido": content if content else "No se generó corrección",
                    "errores": {
                        "Gramática": [],
                        "Léxico": [],
                        "Puntuación": [],
                        "Estructura textual": []
                    },
                    "analisis_contextual": {},
                    "consejo_final": "No se pudo generar un consejo específico."
                }
        
        # Añadir texto original si no está incluido
        if "texto_original" not in data:
            data["texto_original"] = texto_input
        
        # Verificar que tenemos la estructura completa esperada
        errores_keys = ["Gramática", "Léxico", "Puntuación", "Estructura textual"]
        for key in errores_keys:
            if key not in data.get("errores", {}):
                data.setdefault("errores", {})[key] = []
        
        # Guardar resultado en Firebase si hay usuario
        if user_id:
            try:
                from core.firebase_client import save_correccion
                
                # Contar errores por categoría
                errores_conteo = {}
                errores = data.get("errores", {})
                for categoria, lista_errores in errores.items():
                    errores_conteo[categoria.lower()] = len(lista_errores) if isinstance(lista_errores, list) else 0
                
                # Extraer puntuación global (promedio de análisis contextual)
                puntuacion_global = 0
                num_puntuaciones = 0
                
                analisis = data.get("analisis_contextual", {})
                for seccion in ["coherencia", "cohesion", "registro_linguistico", "adecuacion_cultural"]:
                    if seccion in analisis and "puntuacion" in analisis[seccion]:
                        try:
                            puntuacion_global += analisis[seccion]["puntuacion"]
                            num_puntuaciones += 1
                        except (TypeError, ValueError):
                            pass
                
                # Calcular promedio si hay puntuaciones
                if num_puntuaciones > 0:
                    puntuacion_global = round(puntuacion_global / num_puntuaciones, 1)
                else:
                    puntuacion_global = 5.0  # Valor por defecto
                
                # Guardar en Firebase
                correccion_id = save_correccion(
                    user_id=user_id,
                    texto_original=texto_input,
                    texto_corregido=data.get("texto_corregido", ""),
                    nivel=nivel,
                    errores=errores_conteo,
                    puntuacion=puntuacion_global
                )
                
                logger.info(f"Corrección guardada para usuario {user_id} con ID {correccion_id}")
            except Exception as firebase_error:
                logger.error(f"Error guardando corrección en Firebase: {str(firebase_error)}")
                logger.debug(traceback.format_exc())
        
        # Registrar éxito en el circuit breaker
        circuit_breaker.record_success("openai")
        
        # Éxito - devolver los datos procesados
        logger.info("Procesamiento completado con éxito")
        return data
        
    except Exception as e:
        # Capturar detalles completos del error para diagnóstico
        error_details = traceback.format_exc()
        logger.error(f"Error corrigiendo texto: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        
        # Registrar fallo en el circuit breaker
        circuit_breaker.record_failure("openai", error_type=str(type(e).__name__))
        
        # Crear respuesta de error con información útil
        error_response = {
            "error": True,
            "mensaje": f"Se produjo un error durante la corrección: {str(e)}",
            "texto_original": texto_input if 'texto_input' in locals() else "No disponible"
        }
        
        # Añadir información detallada de depuración
        from config.settings import IS_DEV
        if IS_DEV:
            error_response["debug_info"] = {
                "error_message": str(e),
                "error_type": str(type(e)),
                "traceback": error_details
            }
            
        return error_response

def mostrar_resultado_correccion(resultado):
    """
    Muestra el resultado de la corrección en la interfaz.
    Delega la visualización a la función display_correccion_result.
    
    Args:
        resultado (dict): Resultado de la corrección
        
    Returns:
        None
    """
    try:
        # Importación local para evitar importaciones circulares
        from features.correccion_utils import display_correccion_result
        
        # Verificar si hay un error en el resultado
        if not resultado:
            st.error("No se recibió respuesta del servicio de corrección")
            return
            
        if "error" in resultado and resultado["error"]:
            mensaje_error = resultado.get("mensaje", "Error desconocido durante la corrección")
            st.error(mensaje_error)
            
            # Información de depuración (solo en desarrollo)
            if "debug_info" in resultado:
                with st.expander("Información de depuración"):
                    st.json(resultado["debug_info"])
                    
            # Sugerencias de acciones para el usuario
            st.info("Sugerencias: Intenta con un texto más corto o verifica tu conexión a internet.")
            
            # Mostrar el texto original si está disponible
            if "texto_original" in resultado:
                with st.expander("Tu texto original"):
                    st.write(resultado["texto_original"])
            
            return
        
        # Si no hay error, mostrar el resultado normal
        display_correccion_result(resultado)
        
    except Exception as e:
        # Capturar cualquier error en la visualización
        error_details = traceback.format_exc()
        logger.error(f"Error mostrando resultado: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        
        # Mostrar mensaje al usuario
        st.error(f"Error mostrando el resultado: {str(e)}")
        
        # Si tenemos el resultado original, intentar mostrar al menos el texto
        if isinstance(resultado, dict):
            if "texto_corregido" in resultado:
                st.subheader("Texto corregido")
                st.write(resultado["texto_corregido"])
            elif "texto_original" in resultado:
                with st.expander("Tu texto original"):
                    st.write(resultado["texto_original"])
