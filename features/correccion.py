#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de corrección de textos
------------------------------
Este módulo contiene la lógica para corregir textos usando el Asistente de OpenAI.
"""

import logging
import json
from datetime import datetime
import time
import streamlit as st
import re

from config.settings import OPENAI_ASSISTANT_CORRECCION
from config.prompts import PROMPT_CORRECCION, PROMPT_CLASIFICACION_ERRORES
from core.assistant_client import get_assistant_client
from core.firebase_client import guardar_correccion_firebase
from utils.text_processing import extract_errores_from_json
from core.openai_utils import clean_openai_clients_from_session

logger = logging.getLogger(__name__)

def extract_json_from_content(content):
    """
    Extrae JSON válido de una cadena de texto que puede contener otros elementos.
    Versión robusta que maneja múltiples casos de error.
    
    Args:
        content (str): Contenido que puede incluir JSON
        
    Returns:
        dict/None: Diccionario con el JSON extraído o None si no se encuentra
    """
    if not content:
        return None
    
    # Verificar si content es un string
    if not isinstance(content, str):
        try:
            content = str(content)  # Intentar convertir a string
        except Exception as e:
            logger.error(f"Error convirtiendo contenido a string: {e}")
            return None
    
    # Lista para almacenar posibles cadenas JSON
    json_candidates = []
    
    try:
        # 1. Estrategia 1: Buscar JSON en bloques de código Markdown
        try:
            json_code_blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)```', content)
            for block in json_code_blocks:
                json_candidates.append(block.strip())
        except Exception as e:
            logger.warning(f"Error buscando bloques de código JSON: {e}")
        
        # 2. Estrategia 2: Buscar JSON delimitado por llaves
        if not json_candidates:
            try:
                # Buscar todos los pares de llaves balanceados
                stack = []
                start_indices = []
                
                for i, char in enumerate(content):
                    if char == '{':
                        if len(stack) == 0:  # Inicio de un posible objeto JSON
                            start_indices.append(i)
                        stack.append('{')
                    elif char == '}' and stack:
                        stack.pop()
                        if len(stack) == 0:  # Fin de un posible objeto JSON
                            start_idx = start_indices.pop() if start_indices else -1
                            if start_idx != -1:
                                json_candidates.append(content[start_idx:i+1])
            except Exception as e:
                logger.warning(f"Error buscando pares de llaves balanceados: {e}")
        
        # 3. Estrategia 3: Intento directo (por si el contenido es directamente JSON)
        json_candidates.append(content.strip())
        
        # 4. Estrategia 4: Buscar fragmentos que parezcan JSON
        try:
            # Buscar algo que parezca un objeto JSON
            json_like_pattern = r'(\{\s*"[^"]+"\s*:.*\})'
            matches = re.findall(json_like_pattern, content)
            for match in matches:
                if match not in json_candidates:
                    json_candidates.append(match)
        except Exception as e:
            logger.warning(f"Error buscando fragmentos tipo JSON: {e}")
        
        # Probar cada candidato
        for candidate in json_candidates:
            try:
                parsed_json = json.loads(candidate)
                if isinstance(parsed_json, dict) and len(parsed_json) > 0:
                    return parsed_json
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Error al parsear candidato JSON: {e}")
        
        # Estrategia de último recurso: arreglar comillas y caracteres problemáticos
        for candidate in json_candidates:
            try:
                # Reemplazar comillas simples por dobles
                fixed_json = re.sub(r"'([^']*)':", r'"\1":', candidate)
                fixed_json = re.sub(r": '([^']*)'", r': "\1"', fixed_json)
                
                # Escapar comillas dentro de strings
                fixed_json = re.sub(r'([^\\])"([^"]*)"', r'\1\"\2\"', fixed_json)
                
                # Eliminar caracteres de control
                fixed_json = ''.join(ch for ch in fixed_json if ord(ch) >= 32 or ch == '\n')
                
                # Intento final
                parsed_json = json.loads(fixed_json)
                if isinstance(parsed_json, dict) and len(parsed_json) > 0:
                    return parsed_json
            except Exception:
                continue
        
        # Si llegamos aquí, no se encontró JSON válido
        logger.warning("No se pudo extraer JSON válido del contenido")
        
        # Último recurso: Intentar construir un JSON básico a partir del contenido
        try:
            # Buscar pares clave-valor con regex
            patterns = [
                r'"([^"]+)"\s*:\s*"([^"]*)"',  # "key": "value"
                r'"([^"]+)"\s*:\s*(\d+)',      # "key": 123
                r'"([^"]+)"\s*:\s*(\{.*\})'    # "key": {...}
            ]
            
            result_dict = {}
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for key, value in matches:
                    # Intentar convertir value a int si parece un número
                    if value.isdigit():
                        value = int(value)
                    result_dict[key] = value
            
            if result_dict:
                return result_dict
        except Exception as e:
            logger.warning(f"Error en extracción de emergencia: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error extrayendo JSON del contenido: {str(e)}")
        return None
    
def corregir_texto(texto, parametros, uid=None):
    """
    Corrige un texto utilizando el Asistente de OpenAI y actualiza estadísticas de errores.
    Adaptado para el formato JSON del asistente ELE.
    
    Args:
        texto (str): Texto a corregir
        parametros (dict): Parámetros para la corrección (nivel, tipo_texto, detalle, etc.)
        uid (str, opcional): ID del usuario
        
    Returns:
        dict: Resultado de la corrección o error
    """
    try:
        # Limpiar cualquier cliente inválido que pudiera estar en session_state
        from core.openai_utils import clean_openai_clients_from_session
        clean_openai_clients_from_session()
        
        # Obtener cliente del asistente
        client = get_assistant_client()
        if not client:
            return {"error": "No se pudo obtener el cliente del asistente"}
        
        # Extraer parámetros
        nivel = parametros.get("nivel", "B1")
        tipo_texto = parametros.get("tipo_texto", "General")
        detalle = parametros.get("detalle", "Intermedio")
        enfoque = parametros.get("enfoque", None)
        instrucciones = parametros.get("instrucciones", None)
        
        # Determinar el idioma de las explicaciones (por defecto español)
        idioma = "español"
        
        # Definir el prompt del profesor ELE
        prompt = """
Eres Diego, un profesor experto en ELE (Español como Lengua Extranjera) especializado en análisis lingüístico contextual.
Tu objetivo es corregir textos adaptando tu feedback al nivel del estudiante y cumpliendo rigurosamente con el formato de respuesta.

RESPONDE SIEMPRE EN JSON. No escribas texto introductorio ni explicaciones fuera del JSON.

OBLIGATORIAMENTE debes entregar tu respuesta siguiendo esta estructura JSON exacta:
{
  "saludo": "string",                // en español - personalizado para el estudiante
  "tipo_texto": "string",            // en español
  "errores": {
       "Gramática": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en español
           }
           // más errores de Gramática (o [] si ninguno)
       ],
       "Léxico": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en español
           }
       ],
       "Puntuación": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en español
           }
       ],
       "Estructura textual": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en español
           }
       ]
  },
  "texto_corregido": "string",       // siempre en español
  "analisis_contextual": {
       "coherencia": {
           "puntuacion": number,     // del 1 al 10
           "comentario": "string",   // en español
           "sugerencias": [          // listado de sugerencias en español
               "string",
               "string"
           ]
       },
       "cohesion": {
           "puntuacion": number,     // del 1 al 10
           "comentario": "string",   // en español
           "sugerencias": [          // listado de sugerencias en español
               "string",
               "string"
           ]
       },
       "registro_linguistico": {
           "puntuacion": number,     // del 1 al 10
           "tipo_detectado": "string", // tipo de registro detectado en español
           "adecuacion": "string",   // evaluación de adecuación en español
           "sugerencias": [          // listado de sugerencias en español
               "string",
               "string"
           ]
       },
       "adecuacion_cultural": {
           "puntuacion": number,     // del 1 al 10
           "comentario": "string",   // en español
           "elementos_destacables": [  // elementos culturales destacables en español
               "string",
               "string"
           ],
           "sugerencias": [          // listado de sugerencias en español
               "string",
               "string"
           ]
       }
  },
  "consejo_final": "string",         // en español
  "fin": "Fin de texto corregido."
}

INSTRUCCIONES CRÍTICAS:
- Las explicaciones y comentarios DEBEN estar en español.
- El texto corregido completo SIEMPRE debe estar en español.
- El consejo final SIEMPRE debe estar en español.
- Adapta tus explicaciones y sugerencias al nivel indicado del estudiante.
- Considera el tipo de texto y el contexto cultural en tu análisis.
- Cada error debe incluir un fragmento específico del texto original, no generalidades.
- Las puntuaciones deben basarse en criterios objetivos y ser consistentes con el nivel.
- Sugerencias concretas y aplicables que el estudiante pueda implementar.
- Asegúrate de que el texto corregido mantenga la voz y estilo del estudiante.

NIVELES Y ENFOQUE:
- Para nivel principiante (A1-A2): Enfócate en estructuras básicas, vocabulario fundamental y errores comunes. Utiliza explicaciones simples y claras. Evita terminología lingüística compleja.
- Para nivel intermedio (B1-B2): Puedes señalar errores más sutiles de concordancia, uso de tiempos verbales y preposiciones. Puedes usar alguna terminología lingüística básica en las explicaciones.
- Para nivel avanzado (C1-C2): Céntrate en matices, coloquialismos, registro lingüístico y fluidez. Puedes usar terminología lingüística específica y dar explicaciones más detalladas y técnicas.

OBLIGATORIO: Devuelve tu respuesta solo como un objeto JSON válido, sin texto adicional antes ni después.

Nivel del estudiante: """ + nivel + """
Tipo de texto: """ + tipo_texto + """
"""
        
        # Registrar inicio de corrección
        start_time = time.time()
        logger.info(f"Iniciando corrección de texto para nivel {nivel}")
        
        # Procesar con el asistente
        contenido, datos_json = client.process_with_assistant(
            system_message=prompt,
            user_message=texto,
            task_type="correccion_texto",
            user_uid=uid
        )
        
        # Registrar tiempo de procesamiento
        elapsed_time = time.time() - start_time
        logger.info(f"Corrección completada en {elapsed_time:.2f} segundos")
        
        # Verificar si hay error
        if not contenido or 'error' in datos_json:
            error_msg = datos_json.get('error', 'Error desconocido durante la corrección')
            logger.error(f"Error en corrección: {error_msg}")
            return {"error": error_msg}
        
        # Extraer resultado en formato JSON si está disponible
        try:
            # Función robusta para extraer JSON
            def extraer_json_seguro(contenido):
                """Extrae JSON válido de cualquier formato de respuesta."""
                # Verificar si contenido es None o vacío
                if not contenido:
                    return {}
                
                # Asegurar que contenido sea string
                if not isinstance(contenido, str):
                    try:
                        contenido = str(contenido)
                    except Exception as e:
                        logger.error(f"No se pudo convertir contenido a string: {e}")
                        return {}
                
                try:
                    # 1. Intento directo: parsear todo el contenido como JSON
                    try:
                        return json.loads(contenido)
                    except json.JSONDecodeError:
                        pass
                    
                    # 2. Buscar JSON entre llaves
                    inicio = contenido.find('{')
                    fin = contenido.rfind('}')
                    
                    if inicio != -1 and fin != -1 and inicio < fin:
                        json_texto = contenido[inicio:fin+1]
                        try:
                            return json.loads(json_texto)
                        except json.JSONDecodeError:
                            pass
                    
                    # 3. Buscar bloques de código JSON
                    matches = re.findall(r'```(?:json)?\s*([\s\S]*?)```', contenido)
                    for match in matches:
                        try:
                            return json.loads(match.strip())
                        except json.JSONDecodeError:
                            continue
                    
                    # 4. Fallback: crear objeto simple con el contenido original
                    logger.warning("No se pudo extraer JSON, retornando objeto simple")
                    return {
                        "texto_corregido": contenido,
                        "error_extraccion": True
                    }
                    
                except Exception as e:
                    logger.error(f"Error extracting JSON: {e}")
                    return {
                        "texto_corregido": contenido[:200] + "..." if len(contenido) > 200 else contenido,
                        "error_extraccion": True,
                        "error": str(e)
                    }
            
            # Usar la función robusta para extraer JSON
            json_data = extraer_json_seguro(contenido)
            
            # Guardar JSON completo para referencia
            json_errores = json.dumps(json_data)
            
            # Extraer el texto corregido del nuevo formato
            texto_corregido = json_data.get("texto_corregido", contenido)
            
            # Extraer retroalimentación - combinar diferentes partes del análisis
            retroalimentacion_parts = []
            
            # Consejo final (priorizar)
            if "consejo_final" in json_data and json_data["consejo_final"]:
                retroalimentacion_parts.append(f"**Consejo final:** {json_data['consejo_final']}")
            
            # Análisis contextual si existe
            if "analisis_contextual" in json_data and isinstance(json_data["analisis_contextual"], dict):
                analisis = json_data["analisis_contextual"]
                
                # Coherencia
                if "coherencia" in analisis and isinstance(analisis["coherencia"], dict):
                    coherencia = analisis["coherencia"]
                    retroalimentacion_parts.append(f"**Coherencia:** {coherencia.get('comentario', '')}")
                    
                # Cohesión
                if "cohesion" in analisis and isinstance(analisis["cohesion"], dict):
                    cohesion = analisis["cohesion"]
                    retroalimentacion_parts.append(f"**Cohesión:** {cohesion.get('comentario', '')}")
                    
                # Registro lingüístico
                if "registro_linguistico" in analisis and isinstance(analisis["registro_linguistico"], dict):
                    registro = analisis["registro_linguistico"]
                    retroalimentacion_parts.append(f"**Registro lingüístico:** {registro.get('adecuacion', '')}")
            
            # Unir partes de retroalimentación
            retroalimentacion = "\n\n".join(retroalimentacion_parts) if retroalimentacion_parts else ""
            
            # Calcular puntuación general (promedio de puntuaciones en análisis contextual)
            puntuaciones = []
            
            if "analisis_contextual" in json_data and isinstance(json_data["analisis_contextual"], dict):
                analisis = json_data["analisis_contextual"]
                
                for categoria in ["coherencia", "cohesion", "registro_linguistico", "adecuacion_cultural"]:
                    if categoria in analisis and isinstance(analisis[categoria], dict):
                        if "puntuacion" in analisis[categoria]:
                            try:
                                puntuacion = float(analisis[categoria]["puntuacion"])
                                puntuaciones.append(puntuacion)
                            except (ValueError, TypeError):
                                pass
            
            # Calcular promedio de puntuaciones
            puntuacion_general = sum(puntuaciones) / len(puntuaciones) if puntuaciones else 0
            
            # Convertir errores al formato esperado por las funciones existentes
            errores_formateados = []
            
            if "errores" in json_data and isinstance(json_data["errores"], dict):
                errores = json_data["errores"]
                
                for categoria, lista_errores in errores.items():
                    if isinstance(lista_errores, list):
                        ejemplos = []
                        
                        for error in lista_errores:
                            if isinstance(error, dict):
                                ejemplo = {
                                    "texto": error.get("fragmento_erroneo", ""),
                                    "sugerencia": error.get("correccion", ""),
                                    "explicacion": error.get("explicacion", "")
                                }
                                ejemplos.append(ejemplo)
                        
                        errores_formateados.append({
                            "categoria": categoria,
                            "cantidad": len(lista_errores),
                            "ejemplos": ejemplos
                        })
            
            # Convertir a formato JSON para el histórico
            errores_json = json.dumps(errores_formateados)
            
            # Extraer conteo de errores para estadísticas
            conteo_errores = {}
            
            # Mapeo de nombres de categorías
            categoria_mapping = {
                "Gramática": "gramatica",
                "Léxico": "lexico",
                "Puntuación": "puntuacion",
                "Estructura textual": "estructura_textual",
                "Estilo": "estilo"
            }
            
            if "errores" in json_data and isinstance(json_data["errores"], dict):
                errores = json_data["errores"]
                
                for categoria, lista_errores in errores.items():
                    if isinstance(lista_errores, list):
                        # Usar nombre normalizado si existe en el mapeo
                        categoria_norm = categoria_mapping.get(categoria, categoria.lower())
                        conteo_errores[categoria_norm] = len(lista_errores)
            
            # Actualizar estadísticas en Firestore si hay conteo de errores y UID
            if conteo_errores and uid:
                try:
                    from core.firebase_client import actualizar_conteo_errores
                    actualizar_conteo_errores(uid, conteo_errores)
                    logger.info(f"Conteo de errores actualizado para usuario {uid}: {conteo_errores}")
                except Exception as e:
                    logger.error(f"Error actualizando conteo de errores: {e}")
            
            # Construir resultado
            resultado = {
                "texto_original": texto,
                "texto_corregido": texto_corregido,
                "retroalimentacion": retroalimentacion,
                "puntuacion": puntuacion_general,
                "json_errores": json_errores,
                "errores": errores_formateados,
                "nivel": nivel,
                "tipo_texto": tipo_texto,
                "conteo_errores": conteo_errores
            }
            
            # Guardar corrección en Firebase si hay UID
            if uid:
                try:
                    guardar_datos = {
                        "uid": uid,
                        "texto_original": texto,
                        "texto_corregido": texto_corregido,
                        "retroalimentacion": retroalimentacion,
                        "errores": errores_formateados,
                        "nivel": nivel,
                        "tipo_texto": tipo_texto,
                        "timestamp": time.time(),
                        "fecha": datetime.now().isoformat(),
                        "puntuacion": puntuacion_general,
                        "conteo_errores": conteo_errores
                    }
                    from core.firebase_client import guardar_correccion_firebase
                    guardar_correccion_firebase(guardar_datos)
                except Exception as e:
                    logger.error(f"Error guardando corrección en Firebase: {e}")
            
            return resultado
            
        except Exception as e:
            logger.error(f"Error procesando resultado: {e}")
            # En caso de error, devolver un resultado básico
            return {
                "texto_original": texto,
                "texto_corregido": contenido if isinstance(contenido, str) else str(contenido),
                "retroalimentacion": "Error procesando la respuesta del asistente.",
                "puntuacion": 0,
                "json_errores": "",
                "errores": [],
                "nivel": nivel,
                "tipo_texto": tipo_texto,
                "conteo_errores": {}
            }
            
    except Exception as e:
        logger.error(f"Error en corrección de texto: {str(e)}")
        return {"error": f"Error procesando la corrección: {str(e)}"}