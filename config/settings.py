#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuración global
------------------
Este módulo contiene configuraciones y constantes globales para toda la aplicación.
"""

import os

# --- CHANGE START ---
# Verificación de entorno de desarrollo
IS_DEV = bool(os.getenv("DEV_MODE", False))
# --- CHANGE END ---

# Información de la aplicación
APP_NAME = "Textocorrector ELE"
APP_VERSION = "1.0.0"

# Configuración de modelos OpenAI
DEFAULT_OPENAI_MODEL = "gpt-4-turbo-preview"
DEFAULT_TIMEOUT = 60
EXTENDED_TIMEOUT = 120
MAX_RETRIES = 3

# Listas de modelos preferidos para diferentes casos de uso
OPENAI_MODELS_PREFERIDOS_ECONOMICOS = [
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-1106",
    "gpt-4o-mini",
    "gpt-4-turbo-preview"
]

OPENAI_MODELS_PREFERIDOS_CAPACIDAD = [
    "gpt-4-turbo-preview",
    "gpt-4o",
    "gpt-4",
    "gpt-4-0125-preview",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo"
]

# IDs de asistentes de OpenAI
OPENAI_ASSISTANT_CORRECCION = "asst_abc123" # Reemplazar con IDs reales
OPENAI_ASSISTANT_EJERCICIOS = "asst_def456" # Reemplazar con IDs reales
OPENAI_ASSISTANT_SIMULACRO = "asst_ghi789"  # Reemplazar con IDs reales

# Configuración de Firebase
# Esta es una variable ficticia que se reemplazará con las credenciales reales de secrets
FIREBASE_CONFIG = {
    "type": "service_account",
    "project_id": "textocorrector-ele",
    "private_key_id": "xxxxx",
    "private_key": "-----BEGIN PRIVATE KEY-----\nXXXXX\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk@textocorrector-ele.iam.gserviceaccount.com",
    "client_id": "xxxxx",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk%40textocorrector-ele.iam.gserviceaccount.com"
}

# Configuración de Firebase Web (para autenticación)
# --- CHANGE START ---
# Esta configuración solo debe usarse en entorno de desarrollo
FIREBASE_WEB_CONFIG = {
    "apiKey": "AIzaSyBcxIiPx0QxBx0gRP7M9XpbKzy_zWqYo0Y",
    "authDomain": "spanish-factoria.firebaseapp.com",
    "projectId": "spanish-factoria",
    "storageBucket": "spanish-factoria.appspot.com",
    "messagingSenderId": "123456789012",
    "appId": "1:123456789012:web:abc123def456"
}
# --- CHANGE END ---

# Configuración del circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 3  # Número de fallos antes de abrir el circuito
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 30  # Segundos antes de intentar recuperar

# Configuración de niveles de español
NIVELES_ESPANOL = {
    "A1": "Principiante",
    "A2": "Elemental",
    "B1": "Intermedio",
    "B2": "Intermedio alto",
    "C1": "Avanzado",
    "C2": "Maestría"
}

# Mapeo de idiomas
IDIOMA_MAP = {
    "Español": "es",
    "Inglés": "en",
    "Francés": "fr",
    "Alemán": "de",
    "Italiano": "it",
    "Portugués": "pt"
}

# Tipos de errores gramaticales
TIPOS_ERROR = [
    "Ortografía",
    "Gramática",
    "Vocabulario",
    "Coherencia",
    "Cohesión",
    "Puntuación",
    "Registro lingüístico",
    "Otro"
]

# Colores para tipos de errores
COLORES_ERROR = {
    "Ortografía": "#ffccd5",
    "Gramática": "#ffe8cc",
    "Vocabulario": "#e2f0cb",
    "Coherencia": "#d0d1ff",
    "Cohesión": "#cce5ff",
    "Puntuación": "#fff2cc",
    "Registro lingüístico": "#f9d9ff",
    "Otro": "#f0f0f0"
}

# Configuración de la interfaz
SIDEBAR_WIDTH = 300
MAX_UPLOAD_SIZE = 5  # MB

# Rutas de archivos
TEMPLATES_DIR = "templates"
ASSETS_DIR = "assets"
DATA_DIR = "data"

# Configuración de tiempo
DEFAULT_SIMULACRO_DURACION = 60  # minutos

# Configuración de Firebase
FIREBASE_COLLECTION_USERS = "usuarios"
FIREBASE_COLLECTION_CORRECTIONS = "correcciones"
FIREBASE_COLLECTION_EXERCISES = "ejercicios"
FIREBASE_COLLECTION_SIMULATIONS = "simulacros"

# Configuración de logging
LOG_LEVEL = "INFO"
LOG_FILE = "textocorrector_ele.log"

# Urls para ejemplos de textos por nivel
TEXTOS_EJEMPLO_URLS = {
    "A1": "https://www.profedeele.es/wp-content/uploads/2019/10/ejemplo-texto-a1-1.pdf",
    "A2": "https://www.profedeele.es/wp-content/uploads/2019/10/ejemplo-texto-a2-1.pdf",
    "B1": "https://www.profedeele.es/wp-content/uploads/2019/10/ejemplo-texto-b1-1.pdf",
    "B2": "https://www.profedeele.es/wp-content/uploads/2019/10/ejemplo-texto-b2-1.pdf",
    "C1": "https://www.profedeele.es/wp-content/uploads/2019/10/ejemplo-texto-c1-1.pdf",
    "C2": "https://www.profedeele.es/wp-content/uploads/2019/10/ejemplo-texto-c2-1.pdf"
}