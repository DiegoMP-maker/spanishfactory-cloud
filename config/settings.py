#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuraciones globales para la aplicación Textocorrector ELE
-------------------------------------------------------------
Este archivo contiene todas las constantes y configuraciones utilizadas en la aplicación.
"""

import os
import streamlit as st

# Información de la aplicación
APP_NAME = "Textocorrector ELE"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Herramienta de corrección y aprendizaje para Español como Lengua Extranjera"

# Configuración de OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4-turbo-preview"  # Modelo principal para correcciones, ejercicios, etc.
OPENAI_VISION_MODEL = "gpt-4-vision-preview"  # Modelo para transcripción de imágenes
OPENAI_DALLE_MODEL = "dall-e-3"  # Modelo para generación de imágenes

# Configuración de Firebase
FIREBASE_CONFIG = {
    "project_id": os.environ.get("FIREBASE_PROJECT_ID", "") or st.secrets.get("FIREBASE_PROJECT_ID", ""),
    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY", "") or st.secrets.get("FIREBASE_PRIVATE_KEY", ""),
    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL", "") or st.secrets.get("FIREBASE_CLIENT_EMAIL", "")
}

# Configuración de Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 60  # segundos

# OpenAI Assistants IDs
OPENAI_ASSISTANT_CORRECCION = os.environ.get("OPENAI_ASSISTANT_CORRECCION", "") or st.secrets.get("OPENAI_ASSISTANT_CORRECCION", "")
OPENAI_ASSISTANT_EJERCICIOS = os.environ.get("OPENAI_ASSISTANT_EJERCICIOS", "") or st.secrets.get("OPENAI_ASSISTANT_EJERCICIOS", "")
OPENAI_ASSISTANT_SIMULACRO = os.environ.get("OPENAI_ASSISTANT_SIMULACRO", "") or st.secrets.get("OPENAI_ASSISTANT_SIMULACRO", "")

# Constantes para reintentos y timeouts
MAX_RETRIES = 3
EXTENDED_TIMEOUT = 120  # segundos

# Límites de tokens para diferentes operaciones
MAX_TOKENS_CORRECTION = 4000
MAX_TOKENS_EJERCICIOS = 2000
MAX_TOKENS_SIMULACRO = 4000

# Constantes para niveles de español (MCER)
NIVELES_ESPANOL = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Tipos de errores para clasificación
TIPOS_ERROR = [
    "Ortografía",
    "Gramática",
    "Vocabulario",
    "Cohesión",
    "Coherencia",
    "Puntuación",
    "Otro"
]

# Rutas de archivos
ASSETS_DIR = "assets"
LOGO_PATH = f"{ASSETS_DIR}/Spanish_FactorIA_Logo.png"

# Configuración de correos (si se implementa)
EMAIL_SENDER = "info@textocorrectorele.com"
EMAIL_SUBJECT_WELCOME = "Bienvenido/a a Textocorrector ELE"
