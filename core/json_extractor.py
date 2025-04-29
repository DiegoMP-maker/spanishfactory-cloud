#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extractor robusto de JSON
-------------------------
Este módulo proporciona funciones optimizadas para extraer y validar
JSON de respuestas de modelos de lenguaje, con énfasis en la recuperación
y reparación de estructuras JSON parciales o mal formateadas.
"""

import json
import re
import logging
import traceback

logger = logging.getLogger(__name__)

def extract_json_safely(content):
    """
    Extrae JSON válido de una cadena de texto con manejo de errores mejorado y reparación.
    Versión optimizada y robusta para manejar respuestas del asistente.
    
    Args:
        content (str): Contenido que puede incluir JSON
        
    Returns:
        dict: Diccionario con el JSON extraído o diccionario vacío si no se encuentra
    """
    if not content:
        logger.warning("Contenido vacío, no se puede extraer JSON")
        return {}
    
    # Guardar las primeras 100 caracteres para diagnóstico
    preview = content[:100].replace('\n', ' ') + "..." if len(content) > 100 else content
    logger.info(f"Intentando extraer JSON del contenido. Vista previa: {preview}")
    
    try:
        # 1. Primero intentar parsear directamente todo el contenido
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.debug(f"No se pudo parsear directamente como JSON: {str(e)}")
            # Mostrar detalles del error para diagnóstico
            error_position = e.pos
            error_line, error_column = 0, 0
            lines = content[:error_position].splitlines()
            if lines:
                error_line = len(lines)
                error_column = len(lines[-1]) + 1
            context_start = max(0, error_position - 20)
            context_end = min(len(content), error_position + 20)
            error_context = content[context_start:context_end]
            logger.debug(f"Error JSON en línea {error_line}, columna {error_column}: '{error_context}'")
        
        # 2. Buscar bloques de código JSON con formato markdown
        # 2.1 Buscar bloques de código con etiqueta json explícita
        json_code_blocks = re.findall(r'```json\s*([\s\S]*?)```', content)
        if json_code_blocks:
            logger.info(f"Encontrados {len(json_code_blocks)} bloques de código JSON explícitos")
            for i, block in enumerate(json_code_blocks):
                try:
                    result = json.loads(block.strip())
                    logger.info(f"✅ Éxito: JSON extraído del bloque de código JSON explícito #{i+1}")
                    return result
                except json.JSONDecodeError as e:
                    logger.debug(f"Bloque JSON explícito #{i+1} no es JSON válido: {str(e)}")
        
        # 2.2 Buscar bloques de código genéricos que podrían contener JSON
        generic_code_blocks = re.findall(r'```\s*([\s\S]*?)```', content)
        if generic_code_blocks:
            logger.info(f"Encontrados {len(generic_code_blocks)} bloques de código genéricos")
            for i, block in enumerate(generic_code_blocks):
                try:
                    # Verificar si el bloque empieza con '{'
                    if block.strip().startswith('{'):
                        result = json.loads(block.strip())
                        logger.info(f"✅ Éxito: JSON extraído del bloque de código genérico #{i+1}")
                        return result
                except json.JSONDecodeError as e:
                    logger.debug(f"Bloque genérico #{i+1} no es JSON válido: {str(e)}")
        
        # 3. Buscar entre llaves (más común para respuestas en formato JSON)
        json_pattern = r'{[\s\S]*}'
        match = re.search(json_pattern, content)
        if match:
            try:
                json_str = match.group(0)
                result = json.loads(json_str)
                logger.info("✅ Éxito: JSON extraído con regex de llaves")
                return result
            except json.JSONDecodeError as e:
                logger.debug(f"El contenido entre llaves no es JSON válido: {str(e)}")
                
                # Intentar limpiar y reparar el JSON
                cleaned_json = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', json_str)
                # Reemplazar comillas simples por dobles si hay problema de comillas
                if "'" in cleaned_json and '"' not in cleaned_json:
                    cleaned_json = cleaned_json.replace("'", '"')
                # Intentar parsear de nuevo
                try:
                    result = json.loads(cleaned_json)
                    logger.info("✅ Éxito: JSON extraído después de limpieza")
                    return result
                except json.JSONDecodeError:
                    logger.debug("La limpieza básica no fue suficiente")
                    
                    # Intentar reparaciones más agresivas
                    # 1. Cerrar llaves/corchetes desbalanceados
                    open_braces = cleaned_json.count('{')
                    close_braces = cleaned_json.count('}')
                    open_brackets = cleaned_json.count('[')
                    close_brackets = cleaned_json.count(']')
                    
                    if open_braces > close_braces:
                        # Faltan llaves de cierre
                        cleaned_json += '}' * (open_braces - close_braces)
                    
                    if open_brackets > close_brackets:
                        # Faltan corchetes de cierre
                        cleaned_json += ']' * (open_brackets - close_brackets)
                    
                    # 2. Corregir comas finales en listas/objetos
                    cleaned_json = re.sub(r',\s*}', '}', cleaned_json)
                    cleaned_json = re.sub(r',\s*]', ']', cleaned_json)
                    
                    # Intentar parsear de nuevo
                    try:
                        result = json.loads(cleaned_json)
                        logger.info("✅ Éxito: JSON extraído después de reparación estructural")
                        return result
                    except json.JSONDecodeError:
                        logger.debug("La reparación estructural no fue suficiente")
        
        # 4. MÉTODO ESPECÍFICO para respuestas de corrección ELE
        # Buscar estructura específica basada en las claves esperadas para correcciones
        expected_keys = ["saludo", "tipo_texto", "errores", "texto_corregido", "analisis_contextual", "consejo_final"]
        
        # Si encontramos un patrón que parece incluir muchas de estas claves, intentar extraerlas manualmente
        key_matches = [re.search(fr'["\']({key})["\']', content) is not None for key in expected_keys]
        if sum(key_matches) >= 3:  # Si al menos 3 claves están presentes
            logger.info(f"Detectada estructura de corrección ELE. Intentando reconstrucción manual.")
            
            # Construir un JSON mínimo viable con las claves que podamos encontrar
            manual_json = {}
            
            # Extraer texto corregido
            texto_corregido_match = re.search(r'["\']texto_corregido["\']\s*:\s*["\']([^"\']*)["\']', content)
            if texto_corregido_match:
                manual_json["texto_corregido"] = texto_corregido_match.group(1)
            
            # Extraer saludo
            saludo_match = re.search(r'["\']saludo["\']\s*:\s*["\']([^"\']*)["\']', content)
            if saludo_match:
                manual_json["saludo"] = saludo_match.group(1)
            
            # Extraer tipo_texto
            tipo_texto_match = re.search(r'["\']tipo_texto["\']\s*:\s*["\']([^"\']*)["\']', content)
            if tipo_texto_match:
                manual_json["tipo_texto"] = tipo_texto_match.group(1)
            
            # Extraer consejo_final
            consejo_match = re.search(r'["\']consejo_final["\']\s*:\s*["\']([^"\']*)["\']', content)
            if consejo_match:
                manual_json["consejo_final"] = consejo_match.group(1)
                
            # Estructura mínima para errores
            manual_json["errores"] = {
                "Gramática": [],
                "Léxico": [],
                "Puntuación": [],
                "Estructura textual": []
            }
            
            # Estructura mínima para análisis contextual
            manual_json["analisis_contextual"] = {
                "coherencia": {"puntuacion": 5, "comentario": "Extracción manual"},
                "cohesion": {"puntuacion": 5, "comentario": "Extracción manual"},
                "registro_linguistico": {"puntuacion": 5, "comentario": "Extracción manual"},
                "adecuacion_cultural": {"puntuacion": 5, "comentario": "Extracción manual"},
            }
            
            logger.info("✅ Creada estructura JSON mínima mediante reconstrucción manual")
            return manual_json
        
        # 5. Si todo falla, devolver un JSON mínimo para evitar errores
        logger.warning("No se pudo extraer JSON válido del contenido después de múltiples intentos")
        
        # Proporcionar un objeto de respuesta mínimo que evite errores posteriores
        return {
            "texto_corregido": "No se pudo procesar la respuesta correctamente.",
            "errores": {
                "Gramática": [],
                "Léxico": [],
                "Puntuación": [],
                "Estructura textual": []
            },
            "analisis_contextual": {
                "coherencia": {"puntuacion": 5, "comentario": "No disponible"},
                "cohesion": {"puntuacion": 5, "comentario": "No disponible"},
                "registro_linguistico": {"puntuacion": 5, "comentario": "No disponible"},
                "adecuacion_cultural": {"puntuacion": 5, "comentario": "No disponible"}
            },
            "consejo_final": "Hubo un problema al procesar la respuesta. Por favor, intenta nuevamente."
        }
        
    except Exception as e:
        logger.error(f"❌ Error inesperado extrayendo JSON del contenido: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Proporcionar un objeto de respuesta mínimo que evite errores posteriores
        return {
            "texto_corregido": "Error interno procesando la respuesta.",
            "errores": {
                "Gramática": [],
                "Léxico": [],
                "Puntuación": [],
                "Estructura textual": []
            },
            "consejo_final": "Ocurrió un error interno. Por favor, intenta nuevamente."
        }

def validate_correction_json(json_data):
    """
    Valida y completa un JSON de corrección para asegurar que tiene todos los campos necesarios.
    
    Args:
        json_data (dict): Datos JSON a validar
        
    Returns:
        dict: JSON validado y completado con campos por defecto si faltaban
    """
    if not json_data or not isinstance(json_data, dict):
        return {
            "texto_corregido": "No se pudo procesar la respuesta correctamente.",
            "errores": {
                "Gramática": [],
                "Léxico": [],
                "Puntuación": [],
                "Estructura textual": []
            },
            "analisis_contextual": {
                "coherencia": {"puntuacion": 5, "comentario": "No disponible"},
                "cohesion": {"puntuacion": 5, "comentario": "No disponible"},
                "registro_linguistico": {"puntuacion": 5, "comentario": "No disponible"},
                "adecuacion_cultural": {"puntuacion": 5, "comentario": "No disponible"}
            },
            "consejo_final": "Hubo un problema al procesar la respuesta."
        }
    
    # Asegurar campos obligatorios existen
    expected_fields = [
        "saludo", 
        "tipo_texto", 
        "errores", 
        "texto_corregido", 
        "analisis_contextual", 
        "consejo_final"
    ]
    
    # Contar campos que faltan
    missing_fields = [field for field in expected_fields if field not in json_data]
    
    if missing_fields:
        logger.warning(f"Campos faltantes en JSON de corrección: {', '.join(missing_fields)}")
        
        # Completar campos faltantes con valores por defecto
        for field in missing_fields:
            if field == "saludo":
                json_data["saludo"] = "¡Hola! He revisado tu texto."
            elif field == "tipo_texto":
                json_data["tipo_texto"] = "Texto general"
            elif field == "errores":
                json_data["errores"] = {
                    "Gramática": [],
                    "Léxico": [],
                    "Puntuación": [],
                    "Estructura textual": []
                }
            elif field == "texto_corregido":
                # Si no tenemos texto corregido pero tenemos el original, usarlo
                json_data["texto_corregido"] = json_data.get("texto_original", "No se generó texto corregido.")
            elif field == "analisis_contextual":
                json_data["analisis_contextual"] = {
                    "coherencia": {"puntuacion": 5, "comentario": "No disponible"},
                    "cohesion": {"puntuacion": 5, "comentario": "No disponible"},
                    "registro_linguistico": {"puntuacion": 5, "comentario": "No disponible"},
                    "adecuacion_cultural": {"puntuacion": 5, "comentario": "No disponible"}
                }
            elif field == "consejo_final":
                json_data["consejo_final"] = "Continúa practicando tu español."
    
    # Asegurar estructura correcta del campo "errores"
    if "errores" in json_data:
        categorias_errores = ["Gramática", "Léxico", "Puntuación", "Estructura textual"]
        for categoria in categorias_errores:
            if categoria not in json_data["errores"]:
                json_data["errores"][categoria] = []
    
    # Asegurar estructura correcta del campo "analisis_contextual"
    if "analisis_contextual" in json_data:
        componentes_analisis = ["coherencia", "cohesion", "registro_linguistico", "adecuacion_cultural"]
        for componente in componentes_analisis:
            if componente not in json_data["analisis_contextual"]:
                json_data["analisis_contextual"][componente] = {"puntuacion": 5, "comentario": "No disponible"}
    
    return json_data

def normalize_json_keys(json_data):
    """
    Normaliza las claves del JSON para asegurar consistencia.
    Por ejemplo, convierte claves como "Gramática" a "gramatica".
    
    Args:
        json_data (dict): Datos JSON a normalizar
        
    Returns:
        dict: JSON con claves normalizadas
    """
    if not json_data or not isinstance(json_data, dict):
        return json_data
    
    # Función recursiva para normalizar claves
    def normalize_keys(obj):
        if isinstance(obj, dict):
            new_obj = {}
            for key, value in obj.items():
                # Normalizar clave: eliminar tildes y convertir a minúsculas
                normalized_key = key
                # Si es una categoría de error, mantener mayúsculas para presentación
                if key not in ["Gramática", "Léxico", "Puntuación", "Estructura textual"]:
                    normalized_key = normalize_text(key)
                new_obj[normalized_key] = normalize_keys(value)
            return new_obj
        elif isinstance(obj, list):
            return [normalize_keys(item) for item in obj]
        else:
            return obj
    
    # Función para normalizar texto (eliminar tildes y convertir a minúsculas)
    def normalize_text(text):
        if not isinstance(text, str):
            return text
        # Tabla de reemplazo para caracteres acentuados
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U'
        }
        result = text
        for original, replacement in replacements.items():
            result = result.replace(original, replacement)
        return result.lower()
    
    # Comenzar normalización
    return normalize_keys(json_data)

def ensure_correction_structure(json_data, texto_original=None):
    """
    Asegura que la estructura del JSON de corrección sea válida y completa.
    
    Args:
        json_data (dict): Datos JSON a validar
        texto_original (str, opcional): Texto original para incluir si falta
        
    Returns:
        dict: JSON con estructura completa y válida
    """
    # Validar el JSON
    json_data = validate_correction_json(json_data)
    
    # Normalizar claves para backend
    normalized_json = normalize_json_keys(json_data)
    
    # Añadir texto original si se proporciona y no existe
    if texto_original and "texto_original" not in normalized_json:
        normalized_json["texto_original"] = texto_original
        
    return normalized_json
