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

def validate_error_classification(correction_result):
    """
    Valida y mejora la clasificación de errores para garantizar que estén
    correctamente distribuidos en sus categorías.
    
    Args:
        correction_result (dict): Resultado de la corrección
        
    Returns:
        dict: Resultado de corrección con errores correctamente clasificados
    """
    if not correction_result or "errores" not in correction_result:
        logger.warning("No se pudo validar la clasificación de errores: estructura JSON incompleta")
        return correction_result
        
    errores = correction_result["errores"]
    
    # Verificar si todas las categorías existen
    categorias_errores = ["Gramática", "Léxico", "Puntuación", "Estructura textual"]
    for categoria in categorias_errores:
        if categoria not in errores:
            errores[categoria] = []
            
    # Limpiar errores redundantes o vacíos (donde fragmento_erroneo = correccion)
    for categoria in categorias_errores:
        if not isinstance(errores[categoria], list):
            errores[categoria] = []
            continue
            
        # Filtrar errores válidos
        errores_validos = []
        for error in errores[categoria]:
            if not isinstance(error, dict):
                continue
                
            fragmento = error.get("fragmento_erroneo", "")
            correccion = error.get("correccion", "")
            
            # Si el fragmento erróneo y la corrección son idénticos, o la explicación indica que no hay errores,
            # no incluir este error
            if fragmento != correccion and "no se identificaron errores" not in error.get("explicacion", "").lower():
                errores_validos.append(error)
        
        # Reemplazar con la lista filtrada
        errores[categoria] = errores_validos
    
    # Contar errores por categoría
    total_errores = sum(len(errores[cat]) for cat in categorias_errores)
    errores_por_categoria = {cat: len(errores[cat]) for cat in categorias_errores}
    
    # Detectar si todos o la mayoría de los errores están en una sola categoría
    categoria_principal = max(errores_por_categoria, key=errores_por_categoria.get) if errores_por_categoria else "Gramática"
    porcentaje_principal = (errores_por_categoria[categoria_principal] / total_errores * 100) if total_errores > 0 else 0
    
    logger.info(f"Distribución de errores inicial: {errores_por_categoria}")
    logger.info(f"Categoría principal: {categoria_principal} ({porcentaje_principal:.1f}%)")
    
    # Si más del 80% de los errores están en una sola categoría y hay al menos 3 errores, 
    # o si hay una sola categoría con errores y el resto vacías, reclasificar
    if (porcentaje_principal > 80 and total_errores >= 3) or (len([c for c, e in errores_por_categoria.items() if e > 0]) <= 1 and total_errores >= 2):
        logger.info(f"Detectada distribución desequilibrada de errores. Reclasificando...")
        
        # Recolectar todos los errores
        todos_errores = []
        for categoria in categorias_errores:
            todos_errores.extend((error, categoria) for error in errores[categoria])
            # Vaciar la categoría
            errores[categoria] = []
        
        # Indicadores y patrones para cada tipo de error
        indicadores = {
            "Léxico": [
                "vocabulario", "palabra", "término", "significado", "léxico", 
                "falso amigo", "selección léxica", "término incorrecto", 
                "palabra inexistente", "palabra mal escrita", "confusión entre palabras"
            ],
            "Puntuación": [
                "coma", "punto", "tilde", "acento", "mayúscula", "minúscula", 
                "puntuación", "signo", "interrogación", "exclamación", "ortografía",
                "acentuación", "mayúscula inicial"
            ],
            "Estructura textual": [
                "párrafo", "estructura", "organización", "conectores", "coherencia", 
                "orden", "distribución", "separación", "disposición", "cohesión",
                "flujo textual", "ordenación"
            ],
            "Gramática": [
                "conjugación", "verbo", "tiempo verbal", "concordancia", "género", 
                "número", "preposición", "artículo", "pronombre", "adverbio", 
                "subjuntivo", "condicional", "singular", "plural", "masculino", "femenino"
            ]
        }
        
        # Reclasificar cada error basado en su explicación y fragmentos
        for error, cat_original in todos_errores:
            if not isinstance(error, dict):
                logger.warning(f"Error con formato inválido ignorado: {error}")
                continue
                
            fragmento = error.get("fragmento_erroneo", "").lower()
            correccion = error.get("correccion", "").lower()
            explicacion = error.get("explicacion", "").lower()
            
            # Combinar todo el texto para análisis
            texto_completo = f"{fragmento} {correccion} {explicacion}"
            
            # Determinar categoría basada en el análisis de palabras clave
            nueva_categoria = None
            max_score = 0
            
            for categoria, palabras_clave in indicadores.items():
                # Calcular puntuación basada en coincidencias de palabras clave
                score = sum(1 for palabra in palabras_clave if palabra.lower() in texto_completo)
                
                # Dar prioridad a la categoría original si no hay una clara mejor opción
                if categoria == cat_original:
                    score += 0.5
                
                if score > max_score:
                    max_score = score
                    nueva_categoria = categoria
            
            # Si no se encontró categoría clara, mantener la original o usar Gramática como fallback
            if nueva_categoria is None or max_score == 0:
                nueva_categoria = cat_original if cat_original else "Gramática"
            
            # Casos especiales basados en patrones específicos
            # 1. Errores de puntuación
            if re.search(r'[.,;:!¡?¿]', fragmento) or re.search(r'[.,;:!¡?¿]', correccion):
                puntuacion_pattern = r'(?:coma|punto|signo|interrogación|exclamación|mayúscula)'
                if re.search(puntuacion_pattern, explicacion) or "may" in explicacion or "min" in explicacion:
                    nueva_categoria = "Puntuación"
            
            # 2. Errores de estructura claros
            if len(fragmento.split()) >= 4 and len(correccion.split()) >= 4:
                if abs(len(fragmento.split()) - len(correccion.split())) <= 1 and "orden" in explicacion:
                    nueva_categoria = "Estructura textual"
            
            # 3. Errores de léxico claros
            if fragmento in correccion or correccion in fragmento:
                if len(fragmento) - len(correccion) <= 3 and len(correccion) - len(fragmento) <= 3:
                    if not any(word in explicacion for word in indicadores["Gramática"]):
                        nueva_categoria = "Léxico"
            
            # 4. Preposiciones siempre son gramática
            if re.search(r'\b(a|de|en|por|para|con|sin)\b', fragmento) and re.search(r'\b(a|de|en|por|para|con|sin)\b', correccion):
                if len(fragmento.split()) <= 3 and len(correccion.split()) <= 3:
                    nueva_categoria = "Gramática"
            
            # Añadir a la categoría correcta
            errores[nueva_categoria].append(error)
        
        # Registrar la nueva distribución
        nueva_distribucion = {cat: len(errores[cat]) for cat in categorias_errores}
        logger.info(f"Nueva distribución de errores después de reclasificación: {nueva_distribucion}")
    
    # Verificar si hay propuestas de estructura textual
    # Si no hay ninguna propuesta de estructura y hay al menos un error, inventar una propuesta
    if len(errores["Estructura textual"]) == 0 and total_errores > 0:
        logger.info("No hay propuestas de estructura textual. Generando una propuesta básica.")
        
        # Extraer el texto corregido para analizarlo
        texto_corregido = correction_result.get("texto_corregido", "")
        
        if texto_corregido:
            # Detectar frases cortas y separadas que podrían conectarse
            frases = re.split(r'[.!?]+\s+', texto_corregido)
            frases = [f.strip() for f in frases if f.strip()]
            
            # Si hay al menos dos frases cortas y consecutivas
            if len(frases) >= 2:
                for i in range(len(frases) - 1):
                    # Si ambas frases son cortas (menos de 10 palabras)
                    if len(frases[i].split()) < 10 and len(frases[i+1].split()) < 10:
                        fragmento = f"{frases[i]}. {frases[i+1]}"
                        correccion = f"{frases[i]} porque {frases[i+1].lower()}" if frases[i+1][0].isupper() else f"{frases[i]} porque {frases[i+1]}"
                        
                        # Crear propuesta de estructura
                        propuesta = {
                            "fragmento_erroneo": fragmento,
                            "correccion": correccion,
                            "explicacion": "Para mejorar la cohesión de tu texto, puedes conectar estas ideas usando conectores como 'porque', 'donde', 'ya que', etc."
                        }
                        
                        errores["Estructura textual"].append(propuesta)
                        logger.info("Generada propuesta de estructura textual")
                        break
            
            # Si no se pudo hacer propuesta con frases, buscar oraciones sin conectores
            if len(errores["Estructura textual"]) == 0 and len(texto_corregido) > 100:
                # Buscar párrafos sin conectores
                conectores = ["además", "sin embargo", "por lo tanto", "en consecuencia", "es decir", 
                              "por ejemplo", "en primer lugar", "finalmente", "en conclusión"]
                
                # Si no hay ningún conector común en un texto largo
                if not any(conector in texto_corregido.lower() for conector in conectores):
                    # Tomar las primeras dos oraciones
                    match = re.search(r'^([^.!?]+[.!?])\s+([^.!?]+[.!?])', texto_corregido)
                    if match:
                        primera = match.group(1)
                        segunda = match.group(2)
                        
                        # Proponer mejora
                        propuesta = {
                            "fragmento_erroneo": f"{primera} {segunda}",
                            "correccion": f"{primera} Además, {segunda.lower() if segunda[0].isupper() else segunda}",
                            "explicacion": "Tu texto mejoraría con el uso de conectores para enlazar las ideas. Puedes usar 'además', 'por otra parte', 'sin embargo', etc."
                        }
                        
                        errores["Estructura textual"].append(propuesta)
                        logger.info("Generada propuesta de estructura textual basada en conectores")
    
    correction_result["errores"] = errores
    return correction_result
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
    
    # Aplicar la validación de clasificación de errores
    json_data = validate_error_classification(json_data)
    
    # Normalizar claves para backend
    normalized_json = normalize_json_keys(json_data)
    
    # Añadir texto original si se proporciona y no existe
    if texto_original and "texto_original" not in normalized_json:
        normalized_json["texto_original"] = texto_original
        
    return normalized_json
