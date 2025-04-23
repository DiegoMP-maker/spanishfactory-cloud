#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Procesamiento y análisis de textos
----------------------------------
Este módulo contiene funciones para procesar y analizar textos en español.
"""

import logging
import re
import unicodedata
import html
import json
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

def clean_html_tags(text: str) -> str:
    """
    Elimina etiquetas HTML de un texto.
    
    Args:
        text (str): Texto con etiquetas HTML
        
    Returns:
        str: Texto sin etiquetas HTML
    """
    if not text:
        return ""
    
    try:
        # Patrón para encontrar etiquetas HTML
        clean = re.compile('<.*?>')
        # Reemplazar etiquetas con espacio
        text_without_tags = re.sub(clean, ' ', text)
        # Decodificar entidades HTML
        text_decoded = html.unescape(text_without_tags)
        # Eliminar espacios múltiples
        text_clean = re.sub(r'\s+', ' ', text_decoded).strip()
        return text_clean
    except Exception as e:
        logger.error(f"Error limpiando etiquetas HTML: {str(e)}")
        return text

def normalize_text(text: str) -> str:
    """
    Normaliza un texto: elimina acentos, convierte a minúsculas y elimina caracteres especiales.
    
    Args:
        text (str): Texto a normalizar
        
    Returns:
        str: Texto normalizado
    """
    if not text:
        return ""
    
    try:
        # Convertir a minúsculas
        text = text.lower()
        
        # Normalizar caracteres Unicode (NFD descompone los caracteres acentuados)
        text = unicodedata.normalize('NFD', text)
        
        # Eliminar diacríticos (acentos)
        text = ''.join([c for c in text if not unicodedata.combining(c)])
        
        # Eliminar caracteres no alfanuméricos (excepto espacios)
        text = re.sub(r'[^\w\s]', '', text)
        
        # Eliminar espacios múltiples
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    except Exception as e:
        logger.error(f"Error normalizando texto: {str(e)}")
        return text

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extrae palabras clave de un texto en español.
    
    Args:
        text (str): Texto del que extraer palabras clave
        max_keywords (int): Número máximo de palabras clave a extraer
        
    Returns:
        list: Lista de palabras clave
    """
    if not text:
        return []
    
    try:
        # Lista de palabras vacías (stopwords) en español
        stopwords = [
            'a', 'al', 'algo', 'algunas', 'algunos', 'ante', 'antes', 'como', 'con', 'contra',
            'cual', 'cuando', 'de', 'del', 'desde', 'donde', 'durante', 'e', 'el', 'ella',
            'ellas', 'ellos', 'en', 'entre', 'era', 'erais', 'eran', 'eras', 'eres', 'es',
            'esa', 'esas', 'ese', 'eso', 'esos', 'esta', 'estaba', 'estabais', 'estaban',
            'estabas', 'estad', 'estada', 'estadas', 'estado', 'estados', 'estamos',
            'estando', 'estar', 'estaremos', 'estará', 'estarán', 'estarás', 'estaré',
            'estaréis', 'estaría', 'estaríais', 'estaríamos', 'estarían', 'estarías',
            'estas', 'este', 'estemos', 'esto', 'estos', 'estoy', 'estuve', 'estuviera',
            'estuvierais', 'estuvieran', 'estuvieras', 'estuvieron', 'estuviese',
            'estuvieseis', 'estuviesen', 'estuvieses', 'estuvimos', 'estuviste',
            'estuvisteis', 'estuviéramos', 'estuviésemos', 'estuvo', 'está', 'estábamos',
            'estáis', 'están', 'estás', 'esté', 'estéis', 'estén', 'estés', 'fue', 'fuera',
            'fuerais', 'fueran', 'fueras', 'fueron', 'fuese', 'fueseis', 'fuesen', 'fueses',
            'fui', 'fuimos', 'fuiste', 'fuisteis', 'fuéramos', 'fuésemos', 'ha', 'habéis',
            'haber', 'había', 'habíais', 'habíamos', 'habían', 'habías', 'habida', 'habidas',
            'habido', 'habidos', 'habiendo', 'habremos', 'habrá', 'habrán', 'habrás', 'habré',
            'habréis', 'habría', 'habríais', 'habríamos', 'habrían', 'habrías', 'han', 'has',
            'hasta', 'hay', 'haya', 'hayamos', 'hayan', 'hayas', 'hayáis', 'he', 'hemos',
            'hube', 'hubiera', 'hubierais', 'hubieran', 'hubieras', 'hubieron', 'hubiese',
            'hubieseis', 'hubiesen', 'hubieses', 'hubimos', 'hubiste', 'hubisteis',
            'hubiéramos', 'hubiésemos', 'hubo', 'la', 'las', 'le', 'les', 'lo', 'los',
            'me', 'mi', 'mis', 'mucho', 'muchos', 'muy', 'más', 'mí', 'mía', 'mías', 'mío',
            'míos', 'nada', 'ni', 'no', 'nos', 'nosotras', 'nosotros', 'nuestra', 'nuestras',
            'nuestro', 'nuestros', 'o', 'os', 'otra', 'otras', 'otro', 'otros', 'para',
            'pero', 'poco', 'por', 'porque', 'que', 'quien', 'quienes', 'qué', 'se', 'sea',
            'seamos', 'sean', 'seas', 'seremos', 'será', 'serán', 'serás', 'seré', 'seréis',
            'sería', 'seríais', 'seríamos', 'serían', 'serías', 'seáis', 'si', 'sido', 'siendo',
            'sin', 'sobre', 'sois', 'somos', 'son', 'soy', 'su', 'sus', 'suya', 'suyas', 'suyo',
            'suyos', 'sí', 'también', 'tanto', 'te', 'tendremos', 'tendrá', 'tendrán', 'tendrás',
            'tendré', 'tendréis', 'tendría', 'tendríais', 'tendríamos', 'tendrían', 'tendrías',
            'tened', 'tenemos', 'tenga', 'tengamos', 'tengan', 'tengas', 'tengo', 'tengáis',
            'tenida', 'tenidas', 'tenido', 'tenidos', 'teniendo', 'tenéis', 'tenía', 'teníais',
            'teníamos', 'tenían', 'tenías', 'ti', 'tiene', 'tienen', 'tienes', 'todo', 'todos',
            'tu', 'tus', 'tuve', 'tuviera', 'tuvierais', 'tuvieran', 'tuvieras', 'tuvieron',
            'tuviese', 'tuvieseis', 'tuviesen', 'tuvieses', 'tuvimos', 'tuviste', 'tuvisteis',
            'tuviéramos', 'tuviésemos', 'tuvo', 'tuya', 'tuyas', 'tuyo', 'tuyos', 'tú', 'un',
            'una', 'uno', 'unos', 'vosotras', 'vosotros', 'vuestra', 'vuestras', 'vuestro',
            'vuestros', 'y', 'ya', 'yo', 'él', 'éramos'
        ]
        
        # Limpiar y normalizar el texto
        clean_text = clean_html_tags(text)
        
        # Tokenizar (dividir en palabras)
        words = re.findall(r'\b\w+\b', clean_text.lower())
        
        # Filtrar stopwords y palabras cortas
        filtered_words = [word for word in words if word not in stopwords and len(word) > 3]
        
        # Contar frecuencia de palabras
        word_freq = {}
        for word in filtered_words:
            if word in word_freq:
                word_freq[word] += 1
            else:
                word_freq[word] = 1
        
        # Ordenar por frecuencia y limitar al número máximo
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:max_keywords]
        
        return [word for word, _ in keywords]
    except Exception as e:
        logger.error(f"Error extrayendo palabras clave: {str(e)}")
        return []

def calculate_text_metrics(text: str) -> Dict[str, Any]:
    """
    Calcula métricas sobre un texto en español.
    
    Args:
        text (str): Texto a analizar
        
    Returns:
        dict: Diccionario con diferentes métricas del texto
    """
    if not text:
        return {
            "caracteres": 0,
            "palabras": 0,
            "oraciones": 0,
            "parrafos": 0,
            "promedio_palabras_oracion": 0,
            "promedio_caracteres_palabra": 0
        }
    
    try:
        # Limpiar el texto
        clean_text = clean_html_tags(text)
        
        # Contar caracteres (sin espacios)
        caracteres = len(re.sub(r'\s', '', clean_text))
        
        # Contar palabras
        palabras = len(re.findall(r'\b\w+\b', clean_text))
        
        # Contar oraciones (terminan con ., !, ? y sus combinaciones)
        oraciones = len(re.split(r'[.!?]+', clean_text))
        
        # Contar párrafos (separados por líneas en blanco)
        parrafos = len(re.split(r'\n\s*\n', clean_text))
        
        # Calcular promedios
        promedio_palabras_oracion = palabras / max(1, oraciones)
        promedio_caracteres_palabra = caracteres / max(1, palabras)
        
        return {
            "caracteres": caracteres,
            "palabras": palabras,
            "oraciones": oraciones,
            "parrafos": parrafos,
            "promedio_palabras_oracion": round(promedio_palabras_oracion, 2),
            "promedio_caracteres_palabra": round(promedio_caracteres_palabra, 2)
        }
    except Exception as e:
        logger.error(f"Error calculando métricas de texto: {str(e)}")
        return {
            "caracteres": 0,
            "palabras": 0,
            "oraciones": 0,
            "parrafos": 0,
            "promedio_palabras_oracion": 0,
            "promedio_caracteres_palabra": 0
        }

def identificar_nivel_complexidad(text: str) -> str:
    """
    Identifica el nivel de complejidad aproximado de un texto en español.
    
    Args:
        text (str): Texto a analizar
        
    Returns:
        str: Nivel de complejidad estimado (A1, A2, B1, B2, C1, C2)
    """
    if not text:
        return "A1"
    
    try:
        # Calcular métricas
        metricas = calculate_text_metrics(text)
        
        # Criterios de complejidad basados en métricas simples
        prom_palabras_oracion = metricas["promedio_palabras_oracion"]
        prom_caracteres_palabra = metricas["promedio_caracteres_palabra"]
        
        # Estimación muy simplificada del nivel
        if prom_palabras_oracion <= 6 and prom_caracteres_palabra <= 4:
            return "A1"
        elif prom_palabras_oracion <= 8 and prom_caracteres_palabra <= 4.5:
            return "A2"
        elif prom_palabras_oracion <= 12 and prom_caracteres_palabra <= 5:
            return "B1"
        elif prom_palabras_oracion <= 15 and prom_caracteres_palabra <= 5.5:
            return "B2"
        elif prom_palabras_oracion <= 20 and prom_caracteres_palabra <= 6:
            return "C1"
        else:
            return "C2"
    except Exception as e:
        logger.error(f"Error identificando nivel de complejidad: {str(e)}")
        return "B1"  # Nivel por defecto

def comparar_textos(texto_original: str, texto_corregido: str) -> Dict[str, Any]:
    """
    Compara un texto original con su versión corregida y extrae diferencias.
    
    Args:
        texto_original (str): Texto original
        texto_corregido (str): Texto corregido (sin etiquetas HTML)
        
    Returns:
        dict: Análisis de diferencias
    """
    if not texto_original or not texto_corregido:
        return {
            "diferencias_total": 0,
            "porcentaje_cambio": 0,
            "metricas_original": {},
            "metricas_corregido": {}
        }
    
    try:
        # Limpiar textos
        original_limpio = clean_html_tags(texto_original)
        corregido_limpio = clean_html_tags(texto_corregido)
        
        # Tokenizar (dividir en palabras)
        palabras_original = re.findall(r'\b\w+\b', original_limpio.lower())
        palabras_corregido = re.findall(r'\b\w+\b', corregido_limpio.lower())
        
        # Calcular métricas para ambos textos
        metricas_original = calculate_text_metrics(original_limpio)
        metricas_corregido = calculate_text_metrics(corregido_limpio)
        
        # Calcular diferencias
        palabras_diferentes = 0
        for i in range(min(len(palabras_original), len(palabras_corregido))):
            if palabras_original[i] != palabras_corregido[i]:
                palabras_diferentes += 1
        
        # Diferencia en longitud
        diff_longitud = abs(len(palabras_original) - len(palabras_corregido))
        
        # Total de diferencias
        diferencias_total = palabras_diferentes + diff_longitud
        
        # Porcentaje de cambio
        total_palabras = max(len(palabras_original), 1)
        porcentaje_cambio = (diferencias_total / total_palabras) * 100
        
        return {
            "diferencias_total": diferencias_total,
            "porcentaje_cambio": round(porcentaje_cambio, 2),
            "metricas_original": metricas_original,
            "metricas_corregido": metricas_corregido
        }
    except Exception as e:
        logger.error(f"Error comparando textos: {str(e)}")
        return {
            "diferencias_total": 0,
            "porcentaje_cambio": 0,
            "metricas_original": {},
            "metricas_corregido": {}
        }

def extract_errores_from_json(json_str: str) -> List[Dict[str, Any]]:
    """
    Extrae información de errores desde una respuesta JSON del Asistente.
    
    Args:
        json_str (str): String con formato JSON que contiene información de errores
        
    Returns:
        list: Lista de errores estructurados
    """
    try:
        if not json_str:
            return []
        
        # Limpiar el string (a veces viene con caracteres adicionales)
        # Buscar el primer '{' y el último '}'
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}')
        
        if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
            logger.warning(f"Formato JSON inválido: {json_str}")
            return []
        
        json_clean = json_str[start_idx:end_idx+1]
        
        # Parsear JSON
        datos = json.loads(json_clean)
        
        # Extraer errores
        if 'errores' in datos and isinstance(datos['errores'], list):
            return datos['errores']
        
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decodificando JSON: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error extrayendo errores: {str(e)}")
        return []

def resaltar_errores_en_texto(texto: str, errores: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Resalta errores en un texto usando spans con clases CSS.
    
    Args:
        texto (str): Texto original
        errores (list): Lista de errores con ejemplos
        
    Returns:
        tuple: (texto_resaltado, errores_con_indices)
    """
    if not texto or not errores:
        return texto, []
    
    try:
        # Copiar para preservar el original
        texto_procesado = texto
        
        # Lista para almacenar errores con índices
        errores_con_indices = []
        
        # Definir colores para cada categoría
        colores_categoria = {
            "Ortografía": "error-ortografia",
            "Gramática": "error-gramatica",
            "Vocabulario": "error-vocabulario",
            "Cohesión": "error-cohesion",
            "Coherencia": "error-coherencia",
            "Puntuación": "error-puntuacion",
            "Otro": "error-otro"
        }
        
        # Procesar cada error
        for error in errores:
            if 'ejemplos' not in error or not error['ejemplos']:
                continue
                
            categoria = error.get('categoria', 'Otro')
            clase_css = colores_categoria.get(categoria, "error-otro")
            
            # Procesar cada ejemplo
            for ejemplo in error['ejemplos']:
                if 'texto' not in ejemplo:
                    continue
                    
                texto_error = ejemplo['texto']
                
                # Buscar texto error en el texto original
                indices = [(m.start(), m.end()) for m in re.finditer(re.escape(texto_error), texto_procesado)]
                
                # Si se encontró, añadir a la lista
                if indices:
                    for inicio, fin in indices:
                        errores_con_indices.append({
                            'inicio': inicio,
                            'fin': fin,
                            'texto': texto_error,
                            'categoria': categoria,
                            'clase_css': clase_css,
                            'sugerencia': ejemplo.get('sugerencia', '')
                        })
        
        # Ordenar por índice de inicio (de mayor a menor para no afectar índices posteriores)
        errores_con_indices.sort(key=lambda x: x['inicio'], reverse=True)
        
        # Aplicar resaltado
        for error in errores_con_indices:
            inicio = error['inicio']
            fin = error['fin']
            clase_css = error['clase_css']
            sugerencia = error.get('sugerencia', '')
            
            # Crear span con tooltip
            if sugerencia:
                span = f'<span class="{clase_css}" title="{sugerencia}">{texto_procesado[inicio:fin]}</span>'
            else:
                span = f'<span class="{clase_css}">{texto_procesado[inicio:fin]}</span>'
            
            # Reemplazar en el texto
            texto_procesado = texto_procesado[:inicio] + span + texto_procesado[fin:]
        
        # Reordenar por índice original (de menor a mayor)
        errores_con_indices.sort(key=lambda x: x['inicio'])
        
        return texto_procesado, errores_con_indices
    except Exception as e:
        logger.error(f"Error resaltando errores en texto: {str(e)}")
        return texto, []

def parse_ejercicio_structure(raw_data: str) -> Dict[str, Any]:
    """
    Parsea la estructura de un ejercicio desde formato JSON o texto.
    
    Args:
        raw_data (str): Datos en bruto del ejercicio
        
    Returns:
        dict: Estructura del ejercicio parseada
    """
    try:
        # Intentar parsear directamente como JSON
        try:
            data = json.loads(raw_data)
            return data
        except json.JSONDecodeError:
            # Si falla, intentar extraer JSON del texto
            pass
        
        # Buscar estructura de JSON en el texto
        start_idx = raw_data.find('{')
        end_idx = raw_data.rfind('}')
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = raw_data[start_idx:end_idx+1]
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                pass
        
        # Si no se puede parsear como JSON, crear estructura mínima
        return {
            "titulo": "Ejercicio",
            "instrucciones": raw_data,
            "preguntas": []
        }
    except Exception as e:
        logger.error(f"Error parseando estructura de ejercicio: {str(e)}")
        return {
            "titulo": "Ejercicio",
            "instrucciones": "Error procesando el ejercicio. Por favor, inténtalo de nuevo.",
            "preguntas": []
        }

def parse_simulacro_structure(raw_data: str) -> Dict[str, Any]:
    """
    Parsea la estructura de un simulacro de examen desde formato JSON o texto.
    
    Args:
        raw_data (str): Datos en bruto del simulacro
        
    Returns:
        dict: Estructura del simulacro parseada
    """
    try:
        # Intentar parsear directamente como JSON
        try:
            data = json.loads(raw_data)
            return data
        except json.JSONDecodeError:
            # Si falla, intentar extraer JSON del texto
            pass
        
        # Buscar estructura de JSON en el texto
        start_idx = raw_data.find('{')
        end_idx = raw_data.rfind('}')
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = raw_data[start_idx:end_idx+1]
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                pass
        
        # Buscar JSON dentro de bloques de código
        json_match = re.search(r'```json\s*(.*?)\s*```', raw_data, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                pass
        
        # Si no se puede parsear como JSON, crear estructura mínima
        return {
            "titulo": "Simulacro de Examen DELE",
            "nivel": "B1",
            "duracion": 60,
            "instrucciones": raw_data,
            "secciones": []
        }
    except Exception as e:
        logger.error(f"Error parseando estructura de simulacro: {str(e)}")
        return {
            "titulo": "Simulacro de Examen DELE",
            "nivel": "B1",
            "duracion": 60,
            "instrucciones": "Error procesando el simulacro. Por favor, inténtalo de nuevo.",
            "secciones": []
        }
    