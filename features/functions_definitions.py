#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Definiciones de funciones para OpenAI Assistants API
---------------------------------------------------
Este módulo contiene definiciones de funciones que pueden ser
llamadas por el Assistant durante la corrección de textos.
"""

import logging
import json

logger = logging.getLogger(__name__)

# Definición de funciones disponibles para el Assistant
ASSISTANT_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Obtiene el perfil completo del estudiante, incluyendo nivel MCER, idioma nativo, objetivos de aprendizaje, áreas de interés, y estadísticas de errores previos.",
            "strict": False,  # Añadimos este parámetro para que coincida con la configuración del asistente
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "ID del usuario cuyo perfil se quiere obtener."
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_evaluation_criteria",
            "description": "Obtiene los criterios de evaluación específicos para un nivel MCER determinado.",
            "strict": False,  # Añadimos este parámetro
            "parameters": {
                "type": "object",
                "properties": {
                    "nivel_mcer": {
                        "type": "string",
                        "description": "Nivel MCER (A1, A2, B1, B2, C1, C2) para el cual se desean obtener los criterios de evaluación.",
                        "enum": ["A1", "A2", "B1", "B2", "C1", "C2"]
                    }
                },
                "required": ["nivel_mcer"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_error_statistics",
            "description": "Obtiene estadísticas detalladas de errores previos del estudiante.",
            "strict": False,  # Añadimos este parámetro
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "ID del usuario cuyas estadísticas se quieren obtener."
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_assessment_examples",
            "description": "Obtiene ejemplos concretos de errores críticos y evaluaciones para un nivel MCER específico.",
            "strict": False,  # Añadimos este parámetro
            "parameters": {
                "type": "object",
                "properties": {
                    "nivel_mcer": {
                        "type": "string",
                        "description": "Nivel MCER (A1, A2, B1, B2, C1, C2) para el cual se desean obtener ejemplos de evaluación.",
                        "enum": ["A1", "A2", "B1", "B2", "C1", "C2"]
                    },
                    "tipo": {
                        "type": "string",
                        "description": "Tipo de ejemplos a obtener: 'errores' para errores críticos, 'puntuacion' para ejemplos de puntuación, 'todos' para ambos.",
                        "enum": ["errores", "puntuacion", "todos"]
                    }
                },
                "required": ["nivel_mcer"]
            }
        }
    }
]

# Criterios de evaluación resumidos por nivel MCER
CRITERIA_BY_LEVEL = {
    "A1": {
        "competencias_esperadas": [
            "Frases simples y aisladas",
            "Vocabulario básico limitado a necesidades concretas",
            "Conjugación de verbos regulares en presente",
            "Uso básico de artículos y preposiciones más comunes"
        ],
        "errores_aceptables": [
            "Confusión ocasional en conjugaciones",
            "Omisión de artículos en algunos contextos",
            "Errores de concordancia género/número",
            "Vocabulario limitado y repetitivo"
        ],
        "errores_inaceptables": [
            "Mezcla caótica de tiempos verbales sin lógica",
            "Ausencia sistemática de sujetos cuando son necesarios",
            "Incomprensibilidad general del texto"
        ],
        "puntuacion_maxima": {
            "muchos_errores": 5,
            "errores_moderados": 6,
            "pocos_errores": 7
        },
        "ejemplos_criticos": []
    },
    "A2": {
        "competencias_esperadas": [
            "Frases conectadas con recursos simples",
            "Uso de presente, pasado y futuro simple",
            "Vocabulario suficiente para situaciones cotidianas",
            "Uso correcto de preposiciones comunes y artículos"
        ],
        "errores_aceptables": [
            "Errores ocasionales en concordancia",
            "Confusión en tiempos verbales complejos",
            "Limitaciones léxicas en temas no cotidianos",
            "Uso básico de conectores"
        ],
        "errores_inaceptables": [
            "Errores sistemáticos en estructuras básicas",
            "Ausencia repetida de artículos determinados/indeterminados",
            "Conjugaciones incorrectas de verbos regulares en presente",
            "Confusión constante ser/estar, por/para"
        ],
        "puntuacion_maxima": {
            "muchos_errores": 4,
            "errores_moderados": 6,
            "pocos_errores": 7
        },
        "ejemplos_criticos": []
    },
    "B1": {
        "competencias_esperadas": [
            "Textos coherentes sobre temas familiares",
            "Uso adecuado de pasado, presente y futuro",
            "Introducción al subjuntivo en estructuras comunes",
            "Conectores para relacionar ideas (pero, porque, cuando, etc.)",
            "Vocabulario suficiente para describir experiencias, deseos y opiniones"
        ],
        "errores_aceptables": [
            "Uso incorrecto del subjuntivo en casos complejos",
            "Confusión ocasional en preposiciones menos comunes",
            "Limitaciones al expresar matices",
            "Fallos ocasionales en concordancia en estructuras complejas"
        ],
        "errores_inaceptables": [
            "Errores básicos en conjugaciones regulares",
            "Errores sistemáticos con artículos",
            "Estructura de frases simplista tipo sujeto-verbo-objeto",
            "Ausencia de conectores básicos",
            "Errores graves con ser/estar, por/para",
            "Confusión presente/pasado sin lógica"
        ],
        "puntuacion_maxima": {
            "muchos_errores": 3,
            "errores_moderados": 5,
            "pocos_errores": 6
        },
        "ejemplos_criticos": [
            {"error": "Yo ir a la playa", "correccion": "Yo voy a la playa"},
            {"error": "Nosotros quiere", "correccion": "Nosotros queremos"},
            {"error": "Yo no gusta", "correccion": "A mí no me gusta"},
            {"error": "Es muy calor", "correccion": "Hace mucho calor"},
            {"error": "Ir a playa", "correccion": "Ir a la playa"},
            {"error": "Cerca de mar", "correccion": "Cerca del mar"}
        ]
    },
    "B2": {
        "competencias_esperadas": [
            "Textos claros y detallados sobre temas diversos",
            "Distinción entre usos de indicativo/subjuntivo",
            "Capacidad para argumentar y defender opiniones",
            "Uso de conectores para crear textos coherentes",
            "Variedad léxica y precisión en la expresión"
        ],
        "errores_aceptables": [
            "Algunos errores en estructuras complejas del subjuntivo",
            "Uso incorrecto ocasional de expresiones idiomáticas",
            "Pequeños fallos de registro",
            "Imprecisiones estilísticas menores"
        ],
        "errores_inaceptables": [
            "Errores de concordancia básicos",
            "Fallos en conjugaciones regulares",
            "Problemas con preposiciones comunes",
            "Conectores mal empleados",
            "Limitación severa de vocabulario"
        ],
        "puntuacion_maxima": {
            "muchos_errores": 2,
            "errores_moderados": 4,
            "pocos_errores": 6
        },
        "ejemplos_criticos": [
            {"error": "Yo ha comido", "correccion": "Yo he comido"},
            {"error": "La gente son", "correccion": "La gente es"},
            {"error": "Yo pienso que es bueno que vienes", "correccion": "Yo pienso que es bueno que vengas"},
            {"error": "Yo soy estudiando", "correccion": "Yo estoy estudiando"}
        ]
    },
    "C1": {
        "competencias_esperadas": [
            "Textos bien estructurados y fluidos sobre temas complejos",
            "Control gramatical consistente",
            "Amplio repertorio léxico con expresiones idiomáticas",
            "Uso flexible y efectivo del lenguaje",
            "Buena estructuración y cohesión textual"
        ],
        "errores_aceptables": [
            "Errores ocasionales en expresiones idiomáticas poco comunes",
            "Pequeños fallos de registro en situaciones muy específicas",
            "Imprecisiones mínimas en estructuras muy complejas"
        ],
        "errores_inaceptables": [
            "Cualquier error gramatical básico o intermedio",
            "Fallos de concordancia",
            "Vocabulario limitado o impreciso",
            "Falta de matices en la expresión",
            "Conectores mal empleados"
        ],
        "puntuacion_maxima": {
            "muchos_errores": 2,
            "errores_moderados": 3,
            "pocos_errores": 5
        },
        "ejemplos_criticos": [
            {"error": "Si tendría dinero, viajaría", "correccion": "Si tuviera dinero, viajaría"},
            {"error": "Antes que llegue", "correccion": "Antes de que llegue"},
            {"error": "Aunque llueve (para hipótesis)", "correccion": "Aunque llueva"}
        ]
    },
    "C2": {
        "competencias_esperadas": [
            "Precisión y naturalidad cercanas a las de un hablante nativo culto",
            "Expresión de matices de significado con exactitud",
            "Dominio de expresiones idiomáticas y coloquiales",
            "Capacidad para reformular con distintos registros",
            "Textos cohesionados con estructura lógica clara"
        ],
        "errores_aceptables": [
            "Rarísimos fallos en expresiones muy idiomáticas",
            "Ocasionales imprecisiones en registros muy específicos"
        ],
        "errores_inaceptables": [
            "Prácticamente cualquier error gramatical",
            "Imprecisiones significativas en léxico",
            "Errores en expresiones idiomáticas comunes",
            "Problemas de cohesión textual"
        ],
        "puntuacion_maxima": {
            "muchos_errores": 1,
            "errores_moderados": 2,
            "pocos_errores": 4
        },
        "ejemplos_criticos": []
    }
}

# Implementaciones de las funciones que serán llamadas por el Assistant
def get_user_profile(user_id):
    """
    Obtiene el perfil completo del estudiante.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Perfil completo del estudiante
    """
    try:
        # Importar dinámicamente para evitar dependencias circulares
        from core.firebase_client import get_user_data
        
        # Obtener datos del usuario
        user_data = get_user_data(user_id)
        
        if not user_data:
            logger.warning(f"No se encontraron datos para el usuario {user_id}")
            return {
                "error": "Perfil no encontrado",
                "nivel_mcer": "B1",  # Valor por defecto
                "idioma_nativo": "No especificado",
                "objetivos_aprendizaje": [],
                "areas_interes": [],
                "estadisticas_errores": {
                    "gramatica": 0,
                    "lexico": 0,
                    "puntuacion": 0,
                    "estructura_textual": 0
                },
                "numero_correcciones": 0
            }
        
        # Construir perfil en formato estándar
        profile = {
            "nivel_mcer": user_data.get("nivel", "B1"),
            "idioma_nativo": user_data.get("idioma_nativo", "No especificado"),
            "objetivos_aprendizaje": user_data.get("objetivos_aprendizaje", []),
            "areas_interes": user_data.get("areas_interes", []),
            "estadisticas_errores": user_data.get("errores_por_tipo", {
                "gramatica": 0,
                "lexico": 0,
                "puntuacion": 0,
                "estructura_textual": 0
            }),
            "preferencias_feedback": user_data.get("preferencias_feedback", {
                "estilo": "detallado",
                "priorizar_areas": []
            }),
            "numero_correcciones": user_data.get("numero_correcciones", 0)
        }
        
        logger.info(f"Perfil recuperado para usuario {user_id}: nivel={profile['nivel_mcer']}")
        return profile
    
    except Exception as e:
        logger.error(f"Error en get_user_profile: {str(e)}")
        # Devolver perfil mínimo por defecto
        return {
            "error": f"Error obteniendo perfil: {str(e)}",
            "nivel_mcer": "B1",
            "idioma_nativo": "No especificado",
            "estadisticas_errores": {},
            "numero_correcciones": 0
        }

def get_evaluation_criteria(nivel_mcer):
    """
    Obtiene los criterios de evaluación para un nivel MCER específico.
    
    Args:
        nivel_mcer (str): Nivel MCER (A1-C2)
        
    Returns:
        dict: Criterios de evaluación para el nivel
    """
    try:
        # Verificar nivel
        nivel = nivel_mcer.upper()
        if nivel not in CRITERIA_BY_LEVEL:
            logger.warning(f"Nivel MCER no válido: {nivel_mcer}")
            nivel = "B1"  # Nivel por defecto
            
        # Obtener criterios
        criterios = CRITERIA_BY_LEVEL[nivel]
        
        logger.info(f"Criterios recuperados para nivel {nivel}")
        return criterios
    
    except Exception as e:
        logger.error(f"Error en get_evaluation_criteria: {str(e)}")
        return {
            "error": f"Error obteniendo criterios: {str(e)}",
            "competencias_esperadas": [],
            "errores_aceptables": [],
            "errores_inaceptables": [],
            "puntuacion_maxima": {}
        }

def get_error_statistics(user_id):
    """
    Obtiene estadísticas detalladas de errores del estudiante.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Estadísticas de errores
    """
    try:
        # Importar dinámicamente para evitar dependencias circulares
        from core.firebase_client import get_user_data
        
        # Obtener datos del usuario
        user_data = get_user_data(user_id)
        
        if not user_data or "errores_por_tipo" not in user_data:
            logger.warning(f"No se encontraron estadísticas para el usuario {user_id}")
            return {
                "errores_por_tipo": {
                    "gramatica": 0,
                    "lexico": 0,
                    "puntuacion": 0,
                    "estructura_textual": 0
                },
                "total_correcciones": 0,
                "areas_problematicas": []
            }
        
        # Obtener estadísticas
        errores_por_tipo = user_data.get("errores_por_tipo", {})
        numero_correcciones = user_data.get("numero_correcciones", 0)
        
        # Identificar áreas problemáticas (más de 5 errores)
        areas_problematicas = []
        for tipo, cantidad in errores_por_tipo.items():
            if cantidad > 5:
                areas_problematicas.append({
                    "tipo": tipo,
                    "cantidad": cantidad
                })
        
        # Ordenar por cantidad descendente
        areas_problematicas.sort(key=lambda x: x["cantidad"], reverse=True)
        
        estadisticas = {
            "errores_por_tipo": errores_por_tipo,
            "total_correcciones": numero_correcciones,
            "areas_problematicas": areas_problematicas
        }
        
        logger.info(f"Estadísticas recuperadas para usuario {user_id}")
        return estadisticas
    
    except Exception as e:
        logger.error(f"Error en get_error_statistics: {str(e)}")
        return {
            "error": f"Error obteniendo estadísticas: {str(e)}",
            "errores_por_tipo": {},
            "total_correcciones": 0,
            "areas_problematicas": []
        }

def get_assessment_examples(nivel_mcer, tipo="todos"):
    """
    Obtiene ejemplos concretos de errores críticos y evaluaciones para un nivel MCER.
    
    Args:
        nivel_mcer (str): Nivel MCER (A1-C2)
        tipo (str): Tipo de ejemplos (errores, puntuacion, todos)
        
    Returns:
        dict: Ejemplos de evaluación
    """
    try:
        # Verificar nivel
        nivel = nivel_mcer.upper()
        if nivel not in CRITERIA_BY_LEVEL:
            logger.warning(f"Nivel MCER no válido: {nivel_mcer}")
            nivel = "B1"  # Nivel por defecto
            
        # Obtener ejemplos según tipo
        ejemplos = {}
        
        if tipo in ["errores", "todos"]:
            ejemplos["errores_criticos"] = CRITERIA_BY_LEVEL[nivel]["ejemplos_criticos"]
            
        if tipo in ["puntuacion", "todos"]:
            ejemplos["puntuacion_maxima"] = CRITERIA_BY_LEVEL[nivel]["puntuacion_maxima"]
            
        logger.info(f"Ejemplos recuperados para nivel {nivel}, tipo {tipo}")
        return ejemplos
    
    except Exception as e:
        logger.error(f"Error en get_assessment_examples: {str(e)}")
        return {
            "error": f"Error obteniendo ejemplos: {str(e)}",
            "errores_criticos": [],
            "puntuacion_maxima": {}
        }

# Función para obtener todas las definiciones de funciones
def get_functions_definitions():
    """
    Obtiene todas las definiciones de funciones para OpenAI Assistants.
    
    Returns:
        list: Lista de definiciones de funciones
    """
    return ASSISTANT_FUNCTIONS

# Mapa de funciones para routing
FUNCTIONS_MAP = {
    "get_user_profile": get_user_profile,
    "get_evaluation_criteria": get_evaluation_criteria,
    "get_error_statistics": get_error_statistics,
    "get_assessment_examples": get_assessment_examples
}

# Función para ejecutar una función basada en su nombre
def execute_function(function_name, arguments):
    """
    Ejecuta una función basada en su nombre y argumentos.
    
    Args:
        function_name (str): Nombre de la función a ejecutar
        arguments (dict): Argumentos para la función
        
    Returns:
        Any: Resultado de la función ejecutada
    """
    try:
        # Verificar si la función existe
        if function_name not in FUNCTIONS_MAP:
            logger.error(f"Función no encontrada: {function_name}")
            return {"error": f"Función no encontrada: {function_name}"}
            
        # Obtener la función
        func = FUNCTIONS_MAP[function_name]
        
        # Ejecutar la función con los argumentos
        result = func(**arguments)
        
        logger.info(f"Función {function_name} ejecutada correctamente")
        return result
    
    except Exception as e:
        logger.error(f"Error ejecutando función {function_name}: {str(e)}")
        return {"error": f"Error ejecutando función: {str(e)}"}
