#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gestión de prompts para OpenAI Assistants
-----------------------------------------
Este módulo centraliza y optimiza los prompts utilizados con OpenAI Assistants,
proporcionando versiones optimizadas para diferentes casos de uso.
"""

import logging

logger = logging.getLogger(__name__)

# Versión ultra-concisa del prompt de corrección sin referencias al knowledge base
CORRECTION_PROMPT_ULTRA_CONCISE = """
🧩 Eres un corrector experto de español como lengua extranjera (ELE).

📋 ESTRUCTURA JSON OBLIGATORIA:
{
  "saludo": "string",            // en {idioma}
  "tipo_texto": "string",        // en {idioma}
  "errores": {
       "Gramática": [
           {
             "fragmento_erroneo": "string",
             "correccion": "string",
             "explicacion": "string"  // en {idioma}
           }
       ],
       "Léxico": [ ],
       "Puntuación": [ ],
       "Estructura textual": [ ]
  },
  "texto_corregido": "string",   // siempre en español
  "analisis_contextual": {
       "coherencia": {"puntuacion": number, "comentario": "string", "sugerencias": ["string"] },
       "cohesion": {"puntuacion": number, "comentario": "string", "sugerencias": ["string"] },
       "registro_linguistico": {"puntuacion": number, "tipo_detectado": "string", "adecuacion": "string", "sugerencias": ["string"] },
       "adecuacion_cultural": {"puntuacion": number, "comentario": "string", "elementos_destacables": ["string"], "sugerencias": ["string"] }
  },
  "consejo_final": "string"      // siempre en español
}

🔍 INSTRUCCIONES CRÍTICAS:
1. Corrige TODOS los errores y clasifícalos correctamente
2. Las explicaciones DEBEN estar en {idioma}
3. El texto corregido y consejo final SIEMPRE en español
4. Penaliza errores según nivel MCER:

| Nivel | Muchos errores | Errores moderados | Pocos errores |
|-------|----------------|-------------------|---------------|
| A1    | 5/10           | 6/10              | 7/10          |
| A2    | 4/10           | 6/10              | 7/10          |
| B1    | 3/10           | 5/10              | 6/10          |
| B2    | 2/10           | 4/10              | 6/10          |
| C1    | 2/10           | 3/10              | 5/10          |
| C2    | 1/10           | 2/10              | 4/10          |

5. El "consejo_final" debe ser en español, pedagógico, motivador pero honesto, destacando prioridades de mejora.

⚠️ Responde ÚNICAMENTE con JSON válido, sin texto adicional antes ni después.
"""

def get_optimized_correction_prompt(text_length, idioma="español"):
    """
    Obtiene un prompt optimizado para corrección según la longitud del texto.
    
    Args:
        text_length (int): Longitud del texto en palabras
        idioma (str, opcional): Idioma para las explicaciones
        
    Returns:
        str: Prompt optimizado
    """
    # Reemplazar placeholder de idioma
    prompt = CORRECTION_PROMPT_ULTRA_CONCISE.replace("{idioma}", idioma)
    
    # Loguear información sobre el prompt
    logger.info(f"Usando prompt ultra-conciso para texto de {text_length} palabras")
    logger.info(f"Longitud del prompt: {len(prompt)} caracteres")
    
    return prompt

def is_json_structure_complete(data):
    """
    Verifica si la estructura JSON recibida contiene todos los campos requeridos.
    
    Args:
        data (dict): Datos JSON a verificar
        
    Returns:
        bool: True si la estructura es completa, False en caso contrario
    """
    if not isinstance(data, dict):
        return False
    
    # Campos requeridos en el nivel principal
    required_top_fields = ["saludo", "tipo_texto", "errores", "texto_corregido", "analisis_contextual", "consejo_final"]
    
    # Verificar campos de nivel superior
    for field in required_top_fields:
        if field not in data:
            logger.warning(f"Campo requerido faltante en el JSON: {field}")
            return False
    
    # Verificar estructura de errores
    error_categories = ["Gramática", "Léxico", "Puntuación", "Estructura textual"]
    if not all(category in data.get("errores", {}) for category in error_categories):
        logger.warning("Estructura de errores incompleta en el JSON")
        return False
    
    # Verificar estructura de análisis contextual
    context_categories = ["coherencia", "cohesion", "registro_linguistico", "adecuacion_cultural"]
    if not all(category in data.get("analisis_contextual", {}) for category in context_categories):
        logger.warning("Estructura de análisis contextual incompleta en el JSON")
        return False
    
    return True
