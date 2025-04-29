#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Servicio unificado de corrección de textos
------------------------------------------
Este módulo unifica la lógica de corrección de textos usando OpenAI Assistants v2,
garantizando el formato JSON en las respuestas y el correcto uso de function calling.
"""

import logging
import json
import time
import traceback
import streamlit as st

# Importaciones del proyecto
from core.clean_openai_assistant import get_clean_openai_assistants_client, extract_json_safely
from core.session_manager import get_user_info, get_session_var, set_session_var
from core.circuit_breaker import circuit_breaker
from features.functions_definitions import ASSISTANT_FUNCTIONS, get_user_profile
from core.firebase_client import save_correction_with_stats, get_user_data
from core.json_extractor import validate_error_classification

logger = logging.getLogger(__name__)

# System prompt mejorado para el asistente de corrección con instrucciones explícitas de clasificación
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
Actúas como evaluador crítico pero constructivo de ELE, y tu misión es detectar errores y brindar explicaciones claras y pedagógicas.

🔍 CLASIFICACIÓN ESTRICTA DE ERRORES:

Es CRÍTICO que clasifiques correctamente cada error en su categoría específica:

1. Gramática: SOLO errores de conjugación verbal, concordancia de género/número, uso incorrecto de tiempos verbales, artículos, pronombres y preposiciones.
   Ejemplo correcto: "yo ir" → "yo voy" (error de conjugación)
   Ejemplo correcto: "los casa" → "las casas" (error de concordancia)
   Ejemplo correcto: "voy en Madrid" → "voy a Madrid" (error de preposición)

2. Léxico: SOLO errores de vocabulario, palabras inexistentes, falsos amigos, confusión entre palabras similares, palabras mal escritas.
   Ejemplo correcto: "agusto" → "agosto" (error léxico de palabra mal escrita)
   Ejemplo correcto: "soy embarazada" → "estoy embarazada" (falso amigo)
   Ejemplo correcto: "realizar una fiesta" → "celebrar una fiesta" (selección léxica inapropiada)

3. Puntuación: SOLO errores de comas, puntos, tildes, mayúsculas, signos de interrogación/exclamación.
   Ejemplo correcto: "yo muy feliz" → "Yo muy feliz" (error de mayúscula inicial)
   Ejemplo correcto: "Como estas" → "¿Cómo estás?" (error de signos y acentuación)
   Ejemplo correcto: "fui al cine vi una película" → "Fui al cine. Vi una película." (error de puntuación)

4. Estructura textual: SOLO errores de organización, párrafos, coherencia global, uso de conectores.
   Ejemplo correcto: "nosotros ir a Malaga es muy calor" → "Nosotros vamos a Málaga. Hace mucho calor" (error de estructura, frases no separadas)
   Ejemplo correcto: "Primero... Luego... Finalmente... Por otro lado..." → "Primero... Luego... Por otro lado... Finalmente..." (orden ilógico de conectores)

IMPORTANTE: Cada error debe ser clasificado en UNA SOLA categoría. NO repitas el mismo error en múltiples categorías. Revisa cuidadosamente cada error y colócalo en su categoría correcta. NUNCA agrupes todos los errores en una sola categoría.

CRÍTICO - NO INCLUYAS CORRECCIONES VACÍAS: Si no hay error en alguna de las categorías, simplemente deja la lista vacía ([]). NUNCA incluyas un "error" donde el fragmento_erroneo y la correccion sean exactamente iguales. Tampoco incluyas explicaciones que digan "No se identificaron errores".

ESTRUCTURA TEXTUAL - INSTRUCCIÓN ESPECIAL: Siempre debes evaluar si el texto podría beneficiarse de mejoras estructurales. Si el texto carece de conectores o transiciones adecuadas, organización por párrafos o elementos para mejorar coherencia/cohesión, DEBES proponer al menos una mejora en la categoría "Estructura textual", incluso si no hay errores graves. Por ejemplo:
- Fragmento: "Fui a la playa. Nadé mucho."
- Corrección: "Fui a la playa donde nadé mucho."
- Explicación: "Puedes conectar estas ideas usando 'donde' para mejorar la fluidez del texto."

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
- Asegúrate que tus clasificaciones de errores son CORRECTAS y PRECISAS. NO clasifiques errores de léxico como gramática, o puntuación como estructura.
- SIEMPRE propón mejoras de "Estructura textual" para textos que carezcan de conectores adecuados o buena organización, incluso si no hay errores graves.


OBLIGATORIO: Devuelve tu respuesta solo como un objeto JSON válido, sin texto adicional antes ni después. El JSON debe contener la palabra "json" para asegurar un procesamiento correcto."""

def obtener_perfil_estudiante(user_id):
    """
    Obtiene el perfil del estudiante de manera robusta.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Perfil del estudiante
    """
    try:
        if not user_id:
            logger.warning("ID de usuario vacío en obtener_perfil_estudiante")
            return {
                "nivel_mcer": "B1",
                "idioma_nativo": "No especificado",
                "estadisticas_errores": {}
            }
        
        # Obtener perfil usando la función de funciones_definitions
        perfil = get_user_profile(user_id)
        
        if perfil and "error" not in perfil:
            logger.info(f"Perfil obtenido correctamente para usuario {user_id}")
            return perfil
        
        # Plan B: Obtener datos directamente de Firebase
        user_data = get_user_data(user_id)
        
        if not user_data:
            logger.warning(f"No se pudieron obtener datos para usuario {user_id}")
            return {
                "nivel_mcer": "B1",
                "idioma_nativo": "No especificado",
                "estadisticas_errores": {}
            }
        
        # Construir perfil desde los datos del usuario
        perfil = {
            "nivel_mcer": user_data.get("nivel", "B1"),
            "idioma_nativo": user_data.get("idioma_nativo", "No especificado"),
            "objetivos_aprendizaje": user_data.get("objetivos_aprendizaje", []),
            "areas_interes": user_data.get("areas_interes", []),
            "estadisticas_errores": user_data.get("errores_por_tipo", {}),
            "numero_correcciones": user_data.get("numero_correcciones", 0)
        }
        
        logger.info(f"Perfil construido desde los datos del usuario para {user_id}")
        return perfil
        
    except Exception as e:
        logger.error(f"Error en obtener_perfil_estudiante: {str(e)}")
        return {
            "nivel_mcer": "B1",
            "idioma_nativo": "No especificado",
            "estadisticas_errores": {}
        }

def process_function_calls(assistant_id, thread_id, run_id, client):
    """
    Procesa las llamadas a funciones del asistente.
    
    Args:
        assistant_id (str): ID del asistente
        thread_id (str): ID del thread
        run_id (str): ID de la ejecución
        client: Cliente de OpenAI Assistants
        
    Returns:
        bool: True si el procesamiento fue exitoso
    """
    try:
        # Verificar que tenemos un cliente válido
        if not client:
            logger.error("Cliente no válido en process_function_calls")
            return False
        
        # Obtener detalles de la ejecución
        run_details = client.get_run(thread_id, run_id)
        
        if "required_action" not in run_details:
            logger.error("La ejecución no requiere acción")
            return False
        
        required_action = run_details["required_action"]
        if "submit_tool_outputs" not in required_action.get("type", ""):
            logger.error(f"Tipo de acción no soportado: {required_action.get('type')}")
            return False
        
        # Obtener las llamadas a funciones pendientes
        tool_calls = required_action.get("submit_tool_outputs", {}).get("tool_calls", [])
        
        if not tool_calls:
            logger.warning("No hay llamadas a funciones pendientes")
            return False
        
        # Procesar cada llamada a función
        tool_outputs = []
        
        for tool_call in tool_calls:
            function_name = tool_call.get("function", {}).get("name")
            function_args = tool_call.get("function", {}).get("arguments", "{}")
            
            # Parsear argumentos
            try:
                args = json.loads(function_args)
            except json.JSONDecodeError:
                logger.error(f"Error al parsear argumentos: {function_args}")
                args = {}
            
            # Ejecutar la función correspondiente
            from features.functions_definitions import execute_function
            result = execute_function(function_name, args)
            
            # Añadir resultado a los outputs
            tool_outputs.append({
                "tool_call_id": tool_call.get("id"),
                "output": json.dumps(result)
            })
        
        # Enviar los resultados a la API
        submit_response = client._api_request(
            "POST",
            f"/threads/{thread_id}/runs/{run_id}/submit_tool_outputs",
            data={"tool_outputs": tool_outputs},
            timeout=60
        )
        
        if not submit_response:
            logger.error("Error al enviar los resultados de las funciones")
            return False
        
        logger.info(f"Resultados de funciones enviados correctamente: {len(tool_outputs)} funciones")
        return True
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error en process_function_calls: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return False

def corregir_texto(texto_input, nivel, detalle="Intermedio", user_id=None, idioma="español"):
    """
    Procesa un texto con OpenAI Assistants v2 para obtener correcciones.
    Implementación unificada con mejor manejo de errores y garantía de formato JSON.
    
    Args:
        texto_input (str): Texto a corregir
        nivel (str): Nivel de español del estudiante
        detalle (str): Nivel de detalle para las correcciones
        user_id (str, opcional): ID del usuario
        idioma (str, opcional): Idioma para las explicaciones
        
    Returns:
        dict: Resultado de la corrección o diccionario con información de error
    """
    # Iniciar temporizador para métricas
    start_time = time.time()
    
    try:
        # Validación inicial del texto
        if not texto_input or not isinstance(texto_input, str) or not texto_input.strip():
            return {
                "error": True,
                "mensaje": "No se proporcionó texto válido para corregir",
                "texto_original": texto_input if texto_input else ""
            }
        
        # Validación de nivel
        if not nivel or not isinstance(nivel, str):
            nivel = "B1"  # Valor por defecto
        
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("openai"):
            return {
                "error": True, 
                "mensaje": "Servicio temporalmente no disponible. Por favor, inténtalo de nuevo más tarde.",
                "texto_original": texto_input
            }
        
        # Obtener información de perfil del usuario
        perfil_usuario = obtener_perfil_estudiante(user_id) if user_id else {
            "nivel_mcer": nivel,
            "idioma_nativo": "No especificado",
            "estadisticas_errores": {}
        }
        
        # Personalizar mensaje con información contextual
        info_contextual = f"""
CONTEXTO DEL ESTUDIANTE:
- Nivel MCER: {nivel}
- Idioma nativo: {perfil_usuario.get('idioma_nativo', 'No especificado')}
- Correcciones previas: {perfil_usuario.get('numero_correcciones', 0)}
"""
        # Añadir info de errores frecuentes si está disponible
        if "estadisticas_errores" in perfil_usuario and perfil_usuario["estadisticas_errores"]:
            errores = perfil_usuario["estadisticas_errores"]
            info_contextual += "- Áreas de mejora: "
            areas_mejora = []
            for tipo, cantidad in errores.items():
                if cantidad > 0:
                    areas_mejora.append(f"{tipo} ({cantidad})")
            if areas_mejora:
                info_contextual += ", ".join(areas_mejora)
            else:
                info_contextual += "No hay datos previos"
        
        # Crear mensaje para el asistente
        user_message = f"""
{info_contextual}

Texto para revisar (nivel declarado del estudiante: {nivel}):
"{texto_input}"

Nivel de detalle deseado: {detalle}
Idioma para explicaciones: {idioma}

IMPORTANTE: 
1. Tu respuesta DEBE ser ÚNICAMENTE un objeto JSON válido con la estructura exacta solicitada en tus instrucciones.
2. Al evaluar, considera que los errores deben penalizarse de manera diferente según el nivel del estudiante.
3. Un error básico en un estudiante de nivel avanzado debe tener mayor impacto en la puntuación que el mismo error en un principiante.
4. NO incluyas texto adicional fuera del JSON. Tu respuesta debe comenzar con '{' y terminar con '}'.
5. CLASIFICA CORRECTAMENTE cada error en su categoría apropiada (Gramática, Léxico, Puntuación o Estructura textual).
6. NO agrupes todos los errores en una sola categoría.
7. Asegúrate de distribuir los errores en todas las categorías que correspondan.
"""
        
        # Obtener cliente de OpenAI Assistants
        client = get_clean_openai_assistants_client()
        if not client:
            return {
                "error": True,
                "mensaje": "No se pudo inicializar el cliente de OpenAI",
                "texto_original": texto_input
            }
        
        # Obtener thread_id actual si existe
        thread_id = get_session_var("thread_id")
        thread_valid = False
        
        # Verificar si el thread es válido
        if thread_id:
            thread_valid = client.verify_thread(thread_id)
            logger.info(f"Thread existente verificado: {thread_id}, válido: {thread_valid}")
        
        # Si no hay thread o no es válido, crear uno nuevo
        if not thread_valid:
            # Crear thread con información del perfil
            thread_response = client.create_thread(user_id=user_id)
            
            if not thread_response or "id" not in thread_response:
                return {
                    "error": True,
                    "mensaje": "No se pudo crear un nuevo thread",
                    "texto_original": texto_input
                }
                
            thread_id = thread_response["id"]
            # Guardar en session_state
            set_session_var("thread_id", thread_id)
            logger.info(f"Nuevo thread creado: {thread_id}")
        else:
            # Si el thread ya existe, considerar actualizarlo con información del perfil
            if user_id:
                # Actualizar cada 10 mensajes o si se han modificado los datos del perfil
                messages_count = get_session_var(f"thread_{thread_id}_messages_count", 0)
                if messages_count % 10 == 0:
                    client.update_thread_with_profile(thread_id, user_id)
                    logger.info(f"Perfil actualizado en thread existente: {thread_id}")
                
                # Incrementar contador de mensajes
                set_session_var(f"thread_{thread_id}_messages_count", messages_count + 1)
        
        # Añadir mensaje al thread
        message_response = client.add_message_to_thread(thread_id, user_message)
        
        if not message_response or "id" not in message_response:
            return {
                "error": True,
                "mensaje": "No se pudo añadir el mensaje al thread",
                "texto_original": texto_input
            }
            
        logger.info(f"Mensaje añadido al thread: {thread_id}")
        
        # Obtener ID del asistente usando el system prompt completo
        try:
            assistant_id = client.get_assistant_id("correccion_texto", SYSTEM_PROMPT_CORRECTION)
            logger.info(f"ID del asistente obtenido: {assistant_id}")
        except Exception as e:
            logger.error(f"Error obteniendo ID del asistente: {str(e)}")
            return {
                "error": True,
                "mensaje": f"Error obteniendo asistente: {str(e)}",
                "texto_original": texto_input
            }
        
        # Ejecutar asistente con las funciones disponibles
        run_response = client._api_request(
            "POST", 
            f"/threads/{thread_id}/runs", 
            data={
                "assistant_id": assistant_id,
                "tools": ASSISTANT_FUNCTIONS,
                # Forzar formato JSON para garantizar estructura
                "response_format": {"type": "json_object"}
            },
            timeout=60
        )
        
        if not run_response or "id" not in run_response:
            return {
                "error": True,
                "mensaje": "Error iniciando la ejecución del asistente",
                "texto_original": texto_input
            }
            
        run_id = run_response["id"]
        logger.info(f"Ejecución iniciada: {run_id}")
        
        # Esperar a que la ejecución se complete
        max_wait_time = 180  # 3 minutos máximo
        start_wait_time = time.time()
        polling_interval = 1
        max_polling_interval = 5
        polling_count = 0
        
        # Bucle de polling para esperar la respuesta
        while True:
            # Verificar timeout
            if time.time() - start_wait_time > max_wait_time:
                return {
                    "error": True,
                    "mensaje": f"La operación tardó demasiado tiempo (más de {max_wait_time} segundos)",
                    "texto_original": texto_input
                }
            
            # Consultar estado de la ejecución
            run_status_response = client.get_run(thread_id, run_id)
            
            if not run_status_response or "status" not in run_status_response:
                return {
                    "error": True,
                    "mensaje": "Error al verificar el estado de la ejecución",
                    "texto_original": texto_input
                }
                
            status = run_status_response["status"]
            polling_count += 1
            
            # Mostrar estado solo cada 5 consultas para reducir ruido en logs
            if polling_count % 5 == 0:
                logger.info(f"Estado de ejecución ({polling_count}): {status}")
            
            # Verificar si ha terminado
            if status == "completed":
                logger.info(f"Ejecución completada después de {polling_count} consultas")
                break
                
            # Verificar si ha fallado
            if status in ["failed", "cancelled", "expired"]:
                error_detail = run_status_response.get("last_error", {})
                error_message = error_detail.get("message", "Unknown error")
                return {
                    "error": True,
                    "mensaje": f"La ejecución falló: {error_message}",
                    "texto_original": texto_input
                }
            
            # Verificar si requiere acción (función)
            if status == "requires_action":
                logger.info("La ejecución requiere acción (function calling)")
                
                # Procesar llamadas a funciones
                function_success = process_function_calls(assistant_id, thread_id, run_id, client)
                
                if not function_success:
                    return {
                        "error": True,
                        "mensaje": "Error procesando llamadas a funciones",
                        "texto_original": texto_input
                    }
                
                # Continuar con el siguiente ciclo (no dormir)
                continue
            
            # Esperar antes de verificar estado de nuevo
            time.sleep(polling_interval)
            
            # Ajustar intervalo de polling (espera adaptativa)
            polling_interval = min(polling_interval * 1.5, max_polling_interval)
        
        # Obtener mensajes
        messages_response = client.list_messages(thread_id)
        
        if not messages_response or "data" not in messages_response:
            return {
                "error": True,
                "mensaje": "Error al obtener mensajes del thread",
                "texto_original": texto_input
            }
            
        # Buscar el mensaje más reciente del asistente
        assistant_message = None
        for message in messages_response["data"]:
            if message["role"] == "assistant":
                assistant_message = message
                break
        
        if not assistant_message:
            return {
                "error": True,
                "mensaje": "No se encontró respuesta del asistente",
                "texto_original": texto_input
            }
            
        # Extraer contenido del mensaje
        content_text = ""
        for content_item in assistant_message.get("content", []):
            if content_item["type"] == "text":
                content_text += content_item["text"]["value"]
        
        if not content_text:
            return {
                "error": True,
                "mensaje": "El asistente no generó una respuesta",
                "texto_original": texto_input
            }
            
        # Extraer JSON del contenido garantizando un análisis profundo
        json_data = extract_json_safely(content_text)
        
        # Si no se pudo extraer JSON o está vacío, crear error
        if not json_data or not isinstance(json_data, dict) or "errores" not in json_data:
            return {
                "error": True,
                "mensaje": "No se pudo extraer una respuesta JSON válida del asistente",
                "texto_original": texto_input,
                "respuesta_raw": content_text[:500] + ("..." if len(content_text) > 500 else "")
            }
        
        # Añadir texto original si no está incluido
        if "texto_original" not in json_data:
            json_data["texto_original"] = texto_input
        
        # Verificar estructura mínima del JSON
        categorias_errores = ["Gramática", "Léxico", "Puntuación", "Estructura textual"]
        for categoria in categorias_errores:
            if categoria not in json_data.get("errores", {}):
                # Asegurar que existe la categoría aunque esté vacía
                json_data.setdefault("errores", {})[categoria] = []
        
        # Aplicar la validación de clasificación de errores
        json_data = validate_error_classification(json_data)
        logger.info("Validación de clasificación de errores aplicada")
        
        # Guardar corrección en Firebase
        if user_id:
            try:
                # Contar errores por categoría
                errores_conteo = {}
                for categoria, lista_errores in json_data.get("errores", {}).items():
                    # Normalizar nombres a minúsculas para consistencia
                    errores_conteo[categoria.lower()] = len(lista_errores) if isinstance(lista_errores, list) else 0
                
                # Calcular puntuación global
                puntuacion_global = 0
                num_puntuaciones = 0
                
                analisis = json_data.get("analisis_contextual", {})
                for seccion in ["coherencia", "cohesion", "registro_linguistico", "adecuacion_cultural"]:
                    if seccion in analisis and "puntuacion" in analisis[seccion]:
                        try:
                            puntuacion_global += float(analisis[seccion]["puntuacion"])
                            num_puntuaciones += 1
                        except (TypeError, ValueError):
                            pass
                
                # Calcular promedio
                if num_puntuaciones > 0:
                    puntuacion_global = round(puntuacion_global / num_puntuaciones, 1)
                else:
                    puntuacion_global = 5.0  # Valor por defecto
                
                # Guardar en Firebase usando la función mejorada
                correction_id = save_correction_with_stats(
                    user_id=user_id,
                    texto_original=texto_input,
                    texto_corregido=json_data.get("texto_corregido", ""),
                    nivel=nivel,
                    errores=errores_conteo,
                    puntuacion=puntuacion_global
                )
                
                if correction_id:
                    logger.info(f"Corrección guardada con ID: {correction_id}")
                    # Añadir ID al resultado
                    json_data["correction_id"] = correction_id
                else:
                    logger.warning("No se pudo guardar la corrección en Firebase")
            except Exception as e:
                logger.error(f"Error guardando corrección en Firebase: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # Registrar éxito en circuit breaker
        circuit_breaker.record_success("openai")
        
        # Calcular tiempo total
        elapsed_time = time.time() - start_time
        logger.info(f"Corrección completada en {elapsed_time:.2f} segundos")
        
        # Añadir información de thread_id al resultado
        json_data["thread_id"] = thread_id
        
        # Devolver resultado exitoso
        return json_data
        
    except Exception as e:
        # Capturar error general
        error_details = traceback.format_exc()
        logger.error(f"Error general en corregir_texto: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        
        # Detectar errores 500 del servidor de OpenAI
        is_server_error = False
        error_str = str(e).lower()
        if "500" in error_str or "internal server error" in error_str:
            is_server_error = True
            logger.warning("Detectado error 500 del servidor OpenAI. Reiniciando thread...")
            # Importar función de reinicio
            from core.clean_openai_assistant import reset_thread
            # Reiniciar thread
            new_thread_id = reset_thread(user_id)
            if new_thread_id:
                logger.info(f"Thread reiniciado exitosamente. ID: {new_thread_id}")
                # Mensaje específico para errores de servidor
                error_response = {
                    "error": True,
                    "mensaje": "Hubo un problema en el servidor. Se ha reiniciado la sesión. Por favor, intenta nuevamente.",
                    "texto_original": texto_input if 'texto_input' in locals() else "No disponible",
                    "thread_reiniciado": True
                }
            else:
                # Falló el reinicio
                error_response = {
                    "error": True,
                    "mensaje": "Error en el servidor de OpenAI. No se pudo reiniciar la sesión.",
                    "texto_original": texto_input if 'texto_input' in locals() else "No disponible"
                }
        else:
            # Para otros errores, comportamiento estándar
            circuit_breaker.record_failure("openai", error_type=str(type(e).__name__))
            
            # Crear respuesta de error con información útil
            error_response = {
                "error": True,
                "mensaje": f"Se produjo un error durante la corrección: {str(e)}",
                "texto_original": texto_input if 'texto_input' in locals() else "No disponible"
            }
        
        return error_response

def mostrar_resultado_correccion(resultado):
    """
    Muestra el resultado de la corrección en la interfaz.
    
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
            
            # Si el thread se reinició, mostrar mensaje específico
            if resultado.get("thread_reiniciado"):
                st.info("La sesión ha sido reiniciada debido a un error interno. Por favor, intenta nuevamente tu corrección.")
            
            # Mostrar respuesta raw si está disponible (para diagnóstico)
            if "respuesta_raw" in resultado:
                with st.expander("Detalles técnicos (para desarrolladores)"):
                    st.code(resultado["respuesta_raw"])
                    
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
