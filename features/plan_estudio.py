#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de generación de planes de estudio
----------------------------------------
Este módulo contiene funciones para generar planes de estudio personalizados,
utilizando el Asistente de OpenAI.
"""

import logging
from typing import Dict, Any, Optional, Tuple

import streamlit as st

from core.session_manager import get_session_var, set_session_var
from core.assistant_client import get_assistant_client
from config.prompts import get_plan_estudio_prompt

logger = logging.getLogger(__name__)

def generar_plan_estudio(nivel: str) -> Tuple[str, bool]:
    """
    Genera un plan de estudio personalizado para el nivel del estudiante.
    
    Args:
        nivel: Nivel del estudiante (principiante, intermedio, avanzado)
        
    Returns:
        tuple: (plan_estudio, éxito)
    """
    try:
        # Obtener el prompt para el plan de estudio
        system_prompt = get_plan_estudio_prompt(nivel)
        
        # Crear mensaje del usuario
        user_prompt = f"""
        Genera un plan de estudio para un estudiante de español de nivel {nivel}.
        El plan debe ser completo pero conciso, con recomendaciones prácticas y específicas.
        """
        
        # Obtener el UID del usuario para asociar thread
        uid = get_session_var("uid_usuario", "")
        
        # Obtener el thread_id si existe para el usuario
        thread_id = get_session_var("thread_id", "")
        
        # Obtener el cliente de asistentes
        assistant_client = get_assistant_client()
        if not assistant_client:
            return crear_plan_fallback(nivel), False
            
        # Procesar con el asistente
        raw_output, data_json = assistant_client.process_with_assistant(
            system_prompt,
            user_prompt,
            task_type="plan_estudio",
            thread_id=thread_id,
            user_uid=uid
        )
        
        # Si hay un error pero tenemos la respuesta raw, usarla
        if "error" in data_json and raw_output:
            plan = raw_output
        # Si hay un error y no tenemos respuesta raw, usar plan de fallback
        elif "error" in data_json:
            plan = crear_plan_fallback(nivel)
            return plan, False
        # Si tenemos datos json pero no están en formato esperado
        elif isinstance(data_json, dict) and ("plan" in data_json or "content" in data_json):
            plan = data_json.get("plan", data_json.get("content", ""))
        # Si los datos JSON son el contenido directamente (poco probable)
        elif isinstance(data_json, str) and len(data_json) > 200:
            plan = data_json
        # Si llegamos aquí y tenemos raw_output, usarlo
        elif raw_output:
            plan = raw_output
        # En último caso, usar plan de fallback
        else:
            plan = crear_plan_fallback(nivel)
            return plan, False
        
        # Si se generó un nuevo thread_id, guardarlo en session_state
        if not thread_id and assistant_client.client:
            thread_id_nuevo = get_session_var("thread_id", "")
            if thread_id_nuevo:
                set_session_var("thread_id", thread_id_nuevo)
        
        # Guardar en session_state
        set_session_var("plan_estudio_generado", plan)
        
        # También guardar en Firebase si está disponible
        try:
            from core.firebase_client import initialize_firebase
            db, success = initialize_firebase()
            
            if success and db:
                uid = get_session_var("uid_usuario", "")
                if uid:
                    # Guardar en colección de planes de estudio del usuario
                    import uuid
                    from datetime import datetime
                    plan_id = str(uuid.uuid4())
                    plan_data = {
                        "fecha": datetime.now().isoformat(),
                        "nivel": nivel,
                        "plan_texto": plan
                    }
                    db.collection("usuarios").document(uid).collection("planes_estudio").document(plan_id).set(plan_data)
                    logger.info(f"Plan de estudio guardado en Firebase para usuario {uid}")
        except Exception as firebase_error:
            logger.error(f"Error al guardar plan de estudio en Firebase: {str(firebase_error)}")
            # Continuar sin guardar en Firebase
        
        return plan, True
        
    except Exception as e:
        logger.error(f"Error en generar_plan_estudio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Devolver plan de fallback
        return crear_plan_fallback(nivel), False

def crear_plan_fallback(nivel: str) -> str:
    """
    Crea un plan de estudio básico en caso de que la generación con OpenAI falle.
    
    Args:
        nivel: Nivel del estudiante
        
    Returns:
        str: Plan de estudio básico
    """
    # Planes por nivel
    planes = {
        "principiante": """
# Plan de Estudio para Nivel Principiante (A1-A2)

## Objetivos
- Desarrollar vocabulario básico para situaciones cotidianas
- Aprender estructuras gramaticales fundamentales
- Practicar la comprensión de textos y audios sencillos
- Comunicarse en situaciones de la vida diaria

## Actividades Recomendadas
### Diarias (20-30 minutos)
- Practicar con flashcards de vocabulario nuevo
- Escuchar audios cortos en español
- Escribir oraciones sencillas con el vocabulario aprendido

### Semanales
- Leer un texto corto adaptado a tu nivel
- Ver un video o episodio de serie para principiantes
- Completar ejercicios de gramática básica
- Practicar conversación con frases memorizadas

## Recursos
- Aplicaciones: Duolingo, Memrise, Babbel
- Sitios web: ProfeDeELE.es, VerdesMontañas.com
- Canales de YouTube: Español con Juan, Dreaming Spanish
- Libros: "Aula Internacional 1", "Gente Hoy 1"

## Cronograma Sugerido
- **Lunes**: Vocabulario nuevo + ejercicios
- **Martes**: Práctica de comprensión auditiva
- **Miércoles**: Gramática básica
- **Jueves**: Lectura y comprensión
- **Viernes**: Práctica de expresión escrita
- **Fin de semana**: Repaso general y contenido multimedia

## Consejos
- Utiliza el Textocorrector ELE para revisar tus textos
- Aprende frases completas, no solo palabras sueltas
- Intenta pensar directamente en español
- No te preocupes por los errores, son parte del aprendizaje
        """,

        "intermedio": """
# Plan de Estudio para Nivel Intermedio (B1-B2)

## Objetivos
- Ampliar vocabulario para expresar opiniones y sentimientos
- Dominar los tiempos verbales más comunes
- Mejorar fluidez en conversaciones cotidianas
- Comprender textos y audios de complejidad media

## Actividades Recomendadas
### Diarias (30-45 minutos)
- Leer noticias o artículos adaptados
- Escuchar podcasts en español
- Practicar escritura con diario personal
- Repasar conjugaciones verbales

### Semanales
- Ver un episodio de serie o película en español
- Participar en intercambios de idiomas
- Escribir textos de 250-300 palabras sobre temas diversos
- Practicar situaciones comunicativas específicas

## Recursos
- Podcasts: Radio Ambulante, Español Automático
- Sitios web: Profedeele.es, NoticiasParaTuNivel
- Canales de YouTube: WhyNotSpanish, Spanish with Vicente
- Libros: "Gente Hoy 2", "Aula Internacional 3-4"

## Cronograma Sugerido
- **Lunes**: Vocabulario temático + expresiones
- **Martes**: Gramática avanzada
- **Miércoles**: Comprensión auditiva y expresión oral
- **Jueves**: Lectura de textos y análisis
- **Viernes**: Redacción y práctica escrita
- **Fin de semana**: Inmersión en contenido auténtico

## Consejos
- Utiliza el Textocorrector ELE para identificar patrones de error
- Integra expresiones idiomáticas en tu vocabulario
- Practica el subjuntivo en contextos reales
- Busca temas que te interesen para mantener la motivación
        """,

        "avanzado": """
# Plan de Estudio para Nivel Avanzado (C1-C2)

## Objetivos
- Perfeccionar matices de expresión y registro
- Dominar estructuras complejas y usos idiomáticos
- Comunicarse con fluidez sobre temas especializados
- Comprender textos literarios y académicos

## Actividades Recomendadas
### Diarias (45-60 minutos)
- Leer literatura, prensa o textos académicos
- Escuchar podcasts o ver contenido sin subtítulos
- Practicar escritura argumentativa o creativa
- Ampliar vocabulario especializado

### Semanales
- Debatir sobre temas de actualidad
- Analizar textos literarios o periodísticos
- Redactar ensayos de 500+ palabras
- Practicar diferentes registros lingüísticos

## Recursos
- Literatura: Autores contemporáneos hispanohablantes
- Prensa: El País, BBC Mundo, periódicos locales
- Podcasts: El Podcast de Historia, TED en Español
- Academias online: Baselang, AIL Madrid (cursos específicos)

## Cronograma Sugerido
- **Lunes**: Análisis de textos complejos
- **Martes**: Refuerzo de puntos gramaticales específicos
- **Miércoles**: Práctica avanzada de conversación
- **Jueves**: Redacción especializada
- **Viernes**: Comprensión auditiva de material auténtico
- **Fin de semana**: Inmersión cultural con cine, literatura o música

## Consejos
- Utiliza el Textocorrector ELE para perfeccionar tus textos
- Especialízate en tu área de interés profesional o académico
- Practica la mediación lingüística y cultural
- Involúcrate en comunidades de hablantes nativos
        """
    }

    # Simplificar nivel
    nivel_simple = "intermedio"  # Default
    
    if "principiante" in nivel.lower():
        nivel_simple = "principiante"
    elif "intermedio" in nivel.lower():
        nivel_simple = "intermedio"
    elif "avanzado" in nivel.lower():
        nivel_simple = "avanzado"

    # Devolver el plan correspondiente al nivel o el de intermedio por defecto
    return planes.get(nivel_simple, planes["intermedio"])

def get_ultimos_planes(max_items=3) -> list:
    """
    Obtiene los últimos planes de estudio generados por el usuario.
    
    Args:
        max_items: Número máximo de planes a devolver
        
    Returns:
        list: Lista de planes con sus datos
    """
    try:
        # Intentar obtener historial de planes
        planes = get_session_var("historial_planes", [])
        
        # Devolver los últimos max_items
        return planes[-max_items:]
        
    except Exception as e:
        logger.error(f"Error al obtener últimos planes: {str(e)}")
        return []

def guardar_plan_estudio(plan: str, nivel: str) -> bool:
    """
    Guarda un plan de estudio en el historial del usuario.
    
    Args:
        plan: Texto del plan de estudio
        nivel: Nivel del estudiante
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener historial de planes
        planes = get_session_var("historial_planes", [])
        
        # Crear nueva entrada
        from datetime import datetime
        nuevo_plan = {
            "fecha": datetime.now().isoformat(),
            "plan": plan,
            "nivel": nivel
        }
        
        # Añadir al historial
        planes.append(nuevo_plan)
        
        # Limitar a 5 planes como máximo para no sobrecargar session_state
        if len(planes) > 5:
            planes = planes[-5:]
            
        # Guardar en session_state
        set_session_var("historial_planes", planes)
        
        return True
        
    except Exception as e:
        logger.error(f"Error al guardar plan de estudio: {str(e)}")
        return False
    