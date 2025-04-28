#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cliente Firebase
--------------
Este módulo proporciona funciones para interactuar con Firebase (Firestore y Authentication).
"""

import logging
import time
import os
import traceback
import re
import json

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import requests

# Importar configuración
from config.settings import FIREBASE_COLLECTION_USERS, FIREBASE_COLLECTION_CORRECTIONS
from config.settings import FIREBASE_CONFIG as DEFAULT_FIREBASE_CONFIG
from config.settings import FIREBASE_WEB_CONFIG as DEFAULT_FIREBASE_WEB_CONFIG
from config.settings import IS_DEV
# Importar la instancia del circuit breaker y la función de retry
from core.circuit_breaker import circuit_breaker, retry_with_backoff

logger = logging.getLogger(__name__)

# Excepción personalizada para API key faltante
class FirebaseWebAPIKeyMissingError(Exception):
    """Excepción lanzada cuando no se encuentra la API key de Firebase Web"""
    pass

# Variables globales
firebase_initialized = False
db = None

# Definición de estructura y valores por defecto para el perfil extendido del estudiante
STUDENT_PROFILE_SCHEMA = {
    # Datos básicos del perfil
    "nivel": "B1",  # Nivel MCER por defecto (A1-C2)
    "idioma_nativo": "",  # Idioma nativo del estudiante
    
    # Objetivos de aprendizaje y preferencias
    "objetivos_aprendizaje": [],  # Lista de objetivos específicos (ej. ["Mejorar fluidez", "Preparar DELE"])
    "areas_interes": [],  # Áreas de interés temático (ej. ["Literatura", "Negocios"])
    
    # Preferencias de feedback
    "preferencias_feedback": {
        "estilo": "detallado",  # Opciones: "detallado", "resumido", "enfocado"
        "priorizar_areas": []   # Áreas a priorizar en feedback (ej. ["gramática", "vocabulario"])
    },
    
    # Datos de progreso y estadísticas
    "errores_por_tipo": {
        "gramatica": 0,
        "lexico": 0,
        "puntuacion": 0,
        "estructura_textual": 0,
        "estilo": 0
    },
    "numero_correcciones": 0,
    "ultima_correccion": None
}

def initialize_firebase():
    """
    Inicializa la conexión con Firebase.
    
    Configura el cliente de Firestore utilizando las credenciales almacenadas en st.secrets.
    
    Returns:
        tuple: (db_client, success) - Cliente de Firestore y booleano indicando éxito
    """
    try:
        # Verificar si Firebase ya está inicializado
        global firebase_initialized, db
        
        if firebase_initialized:
            return db, True
        
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return None, False
        
        # Obtener credenciales desde st.secrets
        try:
            logger.info("Inicializando Firebase con credenciales desde st.secrets")
            
            # Leer las credenciales desde st.secrets como string JSON
            firebase_credentials_json = st.secrets.get("FIREBASE_CREDENTIALS_JSON")
            
            if not firebase_credentials_json:
                logger.error("No se encontraron credenciales de Firebase en st.secrets['FIREBASE_CREDENTIALS_JSON']")
                raise ValueError("Credenciales de Firebase no encontradas en st.secrets")
            
            # SOLUCIÓN: Limpiar caracteres problemáticos del JSON antes de parsearlo
            # Eliminar caracteres de control que pueden causar problemas de parseo
            import re
            # Esta expresión regular elimina todos los caracteres de control, excepto \n y \t
            cleaned_json = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1F\x7F-\x9F]', '', firebase_credentials_json)
            
            # Intenta parsear el JSON limpio
            try:
                firebase_credentials = json.loads(cleaned_json)
            except json.JSONDecodeError as e:
                # Si aún falla, intenta un enfoque diferente - extraer manualmente usando regex
                logger.warning(f"Error al parsear JSON limpio: {e}. Intentando extraer manualmente...")
                
                # Crear un diccionario vacío para ir agregando los campos
                firebase_credentials = {}
                
                # Patrones para extraer los campos obligatorios
                patterns = {
                    "type": r'"type"\s*:\s*"([^"]*)"',
                    "project_id": r'"project_id"\s*:\s*"([^"]*)"',
                    "private_key_id": r'"private_key_id"\s*:\s*"([^"]*)"',
                    "private_key": r'"private_key"\s*:\s*"(.*?)(?:"\s*,|\"\s*})', # Caso especial, maneja comillas internas
                    "client_email": r'"client_email"\s*:\s*"([^"]*)"',
                    "client_id": r'"client_id"\s*:\s*"([^"]*)"',
                    "auth_uri": r'"auth_uri"\s*:\s*"([^"]*)"',
                    "token_uri": r'"token_uri"\s*:\s*"([^"]*)"',
                    "auth_provider_x509_cert_url": r'"auth_provider_x509_cert_url"\s*:\s*"([^"]*)"',
                    "client_x509_cert_url": r'"client_x509_cert_url"\s*:\s*"([^"]*)"'
                }
                
                # Extraer cada campo usando su patrón correspondiente
                for field, pattern in patterns.items():
                    match = re.search(pattern, cleaned_json, re.DOTALL)
                    if match:
                        value = match.group(1)
                        # Caso especial para private_key: reemplazar \\n por \n reales
                        if field == "private_key":
                            value = value.replace("\\\\n", "\n").replace("\\n", "\n")
                            # Asegurar que la clave privada tenga el formato correcto
                            if not value.startswith("-----BEGIN PRIVATE KEY-----"):
                                value = "-----BEGIN PRIVATE KEY-----\n" + value
                            if not value.endswith("-----END PRIVATE KEY-----"):
                                value = value + "\n-----END PRIVATE KEY-----"
                        
                        firebase_credentials[field] = value
                        logger.info(f"Campo '{field}' extraído correctamente")
                    else:
                        logger.warning(f"No se pudo extraer el campo '{field}'")
                
                # Si falta token_uri, establecer valor por defecto (obligatorio)
                if "token_uri" not in firebase_credentials:
                    firebase_credentials["token_uri"] = "https://oauth2.googleapis.com/token"
                    logger.info("Campo 'token_uri' agregado con valor por defecto")
                
                # Si falta auth_uri, establecer valor por defecto
                if "auth_uri" not in firebase_credentials:
                    firebase_credentials["auth_uri"] = "https://accounts.google.com/o/oauth2/auth"
                    logger.info("Campo 'auth_uri' agregado con valor por defecto")
                
                # Si falta auth_provider_x509_cert_url, establecer valor por defecto
                if "auth_provider_x509_cert_url" not in firebase_credentials:
                    firebase_credentials["auth_provider_x509_cert_url"] = "https://www.googleapis.com/oauth2/v1/certs"
                    logger.info("Campo 'auth_provider_x509_cert_url' agregado con valor por defecto")
                
                # Verificar que se han extraído los campos críticos
                for critical_field in ["type", "project_id", "private_key", "client_email"]:
                    if critical_field not in firebase_credentials:
                        raise ValueError(f"No se pudo extraer el campo crítico '{critical_field}'")
            
            # Asegurar que la private_key tenga \n reales, no literales
            if "private_key" in firebase_credentials:
                # Reemplazar los \n literales por saltos de línea reales
                private_key = firebase_credentials["private_key"]
                # Aplicar reemplazo tanto para \\n como para \n
                private_key = private_key.replace("\\\\n", "\n").replace("\\n", "\n")
                firebase_credentials["private_key"] = private_key
                logger.info(f"Clave privada formateada correctamente (longitud: {len(private_key)} caracteres)")
            
            # Verificar que tenemos las credenciales necesarias
            required_fields = ["type", "project_id", "private_key", "client_email", "token_uri"]
            for field in required_fields:
                if field not in firebase_credentials:
                    logger.error(f"Falta campo requerido: {field}")
                    raise ValueError(f"Credenciales de Firebase incompletas: falta {field}")
            
            # Inicializar Firebase con las credenciales
            if not firebase_admin._apps:
                cred = credentials.Certificate(firebase_credentials)
                app = firebase_admin.initialize_app(cred)
            else:
                # Si ya hay una app, obtener la existente
                app = firebase_admin.get_app()
            
            db = firestore.client()
            
            # Marcar como inicializado
            firebase_initialized = True
            
            # Actualizar estado de servicio en session state
            st.session_state.firebase_status = True
            
            # Registrar éxito
            circuit_breaker.record_success("firebase")
            
            logger.info("Firebase inicializado correctamente")
            return db, True
            
        except Exception as e:
            logger.error(f"Error inicializando Firebase con credenciales desde st.secrets: {e}")
            
            # Si estamos en modo desarrollo, usar configuración predeterminada
            if IS_DEV:
                try:
                    logger.warning("Modo desarrollo: usando configuración predeterminada")
                    firebase_credentials = DEFAULT_FIREBASE_CONFIG
                    
                    # Verificar que tenemos las credenciales necesarias
                    required_fields = ["type", "project_id", "private_key", "client_email", "token_uri"]
                    for field in required_fields:
                        if field not in firebase_credentials:
                            logger.error(f"Falta campo requerido en credenciales predeterminadas: {field}")
                            raise ValueError(f"Credenciales predeterminadas incompletas: falta {field}")
                    
                    # Asegurar que la private_key tenga \n reales en las credenciales predeterminadas
                    if "private_key" in firebase_credentials:
                        firebase_credentials["private_key"] = firebase_credentials["private_key"].replace("\\n", "\n")
                    
                    # Inicializar con credenciales predeterminadas
                    if not firebase_admin._apps:
                        cred = credentials.Certificate(firebase_credentials)
                        app = firebase_admin.initialize_app(cred)
                    else:
                        app = firebase_admin.get_app()
                        
                    db = firestore.client()
                    
                    # Marcar como inicializado
                    firebase_initialized = True
                    st.session_state.firebase_status = True
                    
                    logger.info("Firebase inicializado con configuración predeterminada")
                    return db, True
                except Exception as dev_error:
                    logger.error(f"Error inicializando Firebase con configuración predeterminada: {dev_error}")
                    circuit_breaker.record_failure("firebase", "initialization")
                    st.session_state.firebase_status = False
                    st.error("No se pudo inicializar Firebase. Revisa las credenciales.")
                    return None, False
            else:
                # En producción, registrar fallo
                circuit_breaker.record_failure("firebase", "initialization")
                st.session_state.firebase_status = False
                st.error("No se pudo inicializar Firebase. Revisa las credenciales.")
                return None, False
    
    except Exception as e:
        logger.error(f"Error general inicializando Firebase: {e}")
        circuit_breaker.record_failure("firebase", "initialization")
        
        # Actualizar estado de servicio en session state
        st.session_state.firebase_status = False
        st.error("No se pudo inicializar Firebase. Revisa las credenciales.")
        
        return None, False

# Función auxiliar para depurar la solicitud a Firebase Auth
def debug_firebase_auth_request(api_key, payload, headers=None):
    """
    Función auxiliar para depurar la solicitud a Firebase Auth.
    Registra en el log los detalles de la solicitud.
    """
    try:
        # Registrar URL completa (sin mostrar la clave API completa)
        safe_api_key = api_key[:8] + "..." if api_key and len(api_key) > 10 else "[no-key]"
        logger.debug(f"URL de autenticación: https://identitytoolkit.googleapis.com/v1/accounts:XX?key={safe_api_key}")
        
        # Registrar headers
        if headers:
            logger.debug(f"Headers: {json.dumps(headers)}")
        
        # Registrar payload sin contraseñas
        safe_payload = json.loads(payload)
        if "password" in safe_payload:
            safe_payload["password"] = "********"
        logger.debug(f"Payload: {json.dumps(safe_payload)}")
    except Exception as e:
        logger.error(f"Error en debug_firebase_auth_request: {e}")

def get_firebase_web_api_key():
    """
    Obtiene la API key web de Firebase necesaria para autenticación REST.
    
    Busca la API key en el siguiente orden de prioridad:
    1. st.secrets["FIREBASE_WEB_API_KEY"] (mayúsculas)
    2. st.secrets["firebase_web_api_key"] (minúsculas)
    3. st.secrets["firebase"]["web_api_key"] (dentro de sección firebase)
    4. os.environ["FIREBASE_WEB_API_KEY"] (variables de entorno)
    5. SOLO en modo DEV → FIREBASE_WEB_CONFIG del código base

    Returns:
        str: API key web de Firebase

    Raises:
        FirebaseWebAPIKeyMissingError: Si no se encuentra la API key y estamos en producción
    """
    try:
        # Mostrar en debug las claves disponibles en secrets
        try:
            available_secrets = list(st.secrets.keys())
            if "firebase" in available_secrets:
                firebase_keys = list(st.secrets.firebase.keys())
                logger.debug(f"Keys disponibles en st.secrets: {available_secrets}")
                logger.debug(f"Keys disponibles en st.secrets.firebase: {firebase_keys}")
        except Exception as e:
            logger.debug(f"No se pudieron listar los secrets: {e}")
        
        # Opción 1: Buscar en nivel superior (mayúsculas)
        try:
            api_key = st.secrets["FIREBASE_WEB_API_KEY"]
            logger.info("API key encontrada en secrets como 'FIREBASE_WEB_API_KEY'")
            return api_key
        except Exception:
            logger.debug("No se encontró FIREBASE_WEB_API_KEY en secrets")
        
        # Opción 2: Buscar en nivel superior (minúsculas)
        try:
            api_key = st.secrets["firebase_web_api_key"]
            logger.info("API key encontrada en secrets como 'firebase_web_api_key'")
            return api_key
        except Exception:
            logger.debug("No se encontró firebase_web_api_key en secrets")
        
        # Opción 3: Buscar dentro de sección firebase
        try:
            api_key = st.secrets["firebase"]["web_api_key"]
            logger.info("API key encontrada dentro de sección firebase como 'web_api_key'")
            return api_key
        except Exception:
            logger.debug("No se encontró web_api_key en firebase secrets")
        
        # Opción 4: Buscar en variables de entorno
        try:
            api_key = os.environ.get("FIREBASE_WEB_API_KEY")
            if api_key:
                logger.info("API key encontrada en variable de entorno FIREBASE_WEB_API_KEY")
                return api_key
        except Exception:
            logger.debug("No se encontró FIREBASE_WEB_API_KEY en variables de entorno")
        
        # Opción 5: Usar configuración por defecto SOLO EN DESARROLLO
        if IS_DEV:
            try:
                api_key = DEFAULT_FIREBASE_WEB_CONFIG.get("apiKey")
                if api_key:
                    logger.info("API key obtenida de DEFAULT_FIREBASE_WEB_CONFIG (modo desarrollo)")
                    return api_key
            except Exception:
                logger.debug("No se pudo obtener API key de DEFAULT_FIREBASE_WEB_CONFIG")
        
        # Si no se encuentra, lanzar excepción
        error_msg = "Firebase Web API Key no encontrada en ninguna configuración"
        logger.error(error_msg)
        
        if IS_DEV:
            logger.warning("Ejecutando en modo desarrollo sin API key de Firebase Web")
            return None
        else:
            raise FirebaseWebAPIKeyMissingError(error_msg)
            
    except FirebaseWebAPIKeyMissingError:
        # Propagamos esta excepción específica hacia arriba
        raise
    except Exception as e:
        logger.error(f"Error inesperado al obtener API key web de Firebase: {e}")
        if not IS_DEV:
            raise FirebaseWebAPIKeyMissingError(f"Error al obtener API key: {str(e)}")
        return None

def login_user(email: str, password: str):
    """
    Autentica un usuario con Firebase usando email y contraseña.
    
    Args:
        email: Email del usuario
        password: Contraseña del usuario
        
    Returns:
        dict: Información del usuario autenticado o error
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase_auth"):
            logger.warning("Circuit breaker abierto para Firebase Auth")
            return {"error": "Servicio de autenticación temporalmente no disponible"}
        
        # Obtener API key de Firebase Web
        try:
            api_key = get_firebase_web_api_key()
            
            if not api_key:
                if IS_DEV:
                    # En desarrollo, permitimos un mensaje de error pero no rompemos
                    error_msg = "Firebase Web API Key no configurada correctamente. Necesaria para autenticación."
                    logger.error(error_msg)
                    return {"error": error_msg}
                else:
                    # En producción, esto no debería ocurrir ya que get_firebase_web_api_key lanzaría excepción
                    error_msg = "Error crítico de configuración: Firebase Web API Key no encontrada"
                    logger.error(error_msg)
                    return {"error": error_msg}
                    
        except FirebaseWebAPIKeyMissingError as e:
            error_msg = f"Error de configuración: {str(e)}"
            logger.error(error_msg)
            # No registramos esto como fallo en circuit_breaker, es un problema de configuración
            return {"error": error_msg}
        
        # URL para autenticación con email/password
        auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        
        # Datos de la solicitud - Asegurar el formato correcto
        payload = json.dumps({
            "email": email,
            "password": password,
            "returnSecureToken": True
        })
        
        # Cabeceras
        headers = {"Content-Type": "application/json"}
        
        # Depurar la solicitud (sin mostrar datos sensibles)
        debug_firebase_auth_request(api_key, payload, headers)
        
        # Realizar solicitud con manejo de errores mejorado
        try:
            response = requests.post(auth_url, headers=headers, data=payload, timeout=10)
            logger.debug(f"Respuesta de Firebase Auth: código {response.status_code}")
            
            # Intentar obtener más información si hay error
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_details = error_data.get('error', {})
                    logger.error(f"Error de Firebase Auth: {error_details}")
                except Exception:
                    logger.error(f"Error de Firebase Auth: Código {response.status_code}, cuerpo: {response.text[:100]}...")
        except requests.RequestException as e:
            logger.error(f"Error en la solicitud HTTP a Firebase: {str(e)}")
            return {"error": f"Error de comunicación con Firebase: {str(e)}"}
        
        # Verificar respuesta
        if response.status_code == 200:
            # Autenticación exitosa
            data = response.json()
            uid = data.get("localId")
            id_token = data.get("idToken")
            
            # Actualizar último login en Firestore
            try:
                db, success = initialize_firebase()
                if success and db:
                    # Actualizar información de login
                    update_data = {
                        "ultimo_login": time.time()
                    }
                    
                    # Verificar si hay que completar campos de perfil
                    ensure_profile_fields(uid)
                    
                    # Actualizar documento
                    db.collection(FIREBASE_COLLECTION_USERS).document(uid).update(update_data)
            except Exception as e:
                logger.warning(f"No se pudo actualizar último login: {e}")
            
            # Registrar éxito
            circuit_breaker.record_success("firebase_auth")
            
            return {
                "uid": uid,
                "token": id_token,
                "email": email
            }
        else:
            # Error de autenticación
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Error de autenticación desconocido")
            
            # Mapear códigos de error a mensajes amigables
            error_messages = {
                "EMAIL_NOT_FOUND": "No existe ninguna cuenta con este email",
                "INVALID_PASSWORD": "Contraseña incorrecta",
                "USER_DISABLED": "Esta cuenta ha sido deshabilitada"
            }
            
            friendly_message = error_messages.get(error_message, f"Error de autenticación: {error_message}")
            
            # Registrar fallo
            circuit_breaker.record_failure("firebase_auth", error_type=error_message)
            
            return {"error": friendly_message}
    
    except FirebaseWebAPIKeyMissingError as e:
        error_msg = f"Error de configuración: {str(e)}"
        logger.error(error_msg)
        # No registramos esto como fallo en circuit_breaker, es un problema de configuración
        return {"error": error_msg}
    except Exception as e:
        logger.error(f"Error en login_user: {str(e)}")
        circuit_breaker.record_failure("firebase_auth", error_type="general")
        return {"error": f"Error durante el proceso de login: {str(e)}"}

def create_user(email: str, password: str, user_data: dict):
    """
    Crea un nuevo usuario en Firebase Authentication y Firestore.
    
    Args:
        email: Email del usuario
        password: Contraseña del usuario
        user_data: Datos adicionales del usuario para Firestore
        
    Returns:
        dict: Información del usuario creado o error
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase_auth"):
            logger.warning("Circuit breaker abierto para Firebase Auth")
            return {"error": "Servicio de autenticación temporalmente no disponible"}
        
        # Obtener API key de Firebase Web
        try:
            api_key = get_firebase_web_api_key()
            
            if not api_key:
                if IS_DEV:
                    # En desarrollo, permitimos un mensaje de error pero no rompemos
                    error_msg = "Firebase Web API Key no configurada correctamente. Necesaria para registro de usuarios."
                    logger.error(error_msg)
                    return {"error": error_msg}
                else:
                    # En producción, esto no debería ocurrir ya que get_firebase_web_api_key lanzaría excepción
                    error_msg = "Error crítico de configuración: Firebase Web API Key no encontrada"
                    logger.error(error_msg)
                    return {"error": error_msg}
                    
        except FirebaseWebAPIKeyMissingError as e:
            error_msg = f"Error de configuración: {str(e)}"
            logger.error(error_msg)
            # No registramos esto como fallo en circuit_breaker, es un problema de configuración
            return {"error": error_msg}
        
        # URL para crear cuenta con email/password
        auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
        
        # Datos de la solicitud
        payload = json.dumps({
            "email": email,
            "password": password,
            "returnSecureToken": True
        })
        
        # Cabeceras
        headers = {"Content-Type": "application/json"}
        
        # Realizar solicitud
        response = requests.post(auth_url, headers=headers, data=payload)
        
        # Verificar respuesta
        if response.status_code == 200:
            # Creación exitosa
            data = response.json()
            uid = data.get("localId")
            id_token = data.get("idToken")
            
            # Guardar datos adicionales en Firestore
            db, success = initialize_firebase()
            
            if success and db:
                # Añadir uid y email a los datos
                user_data["uid"] = uid
                user_data["email"] = email
                
                # Añadir timestamps
                current_time = time.time()
                user_data["creado"] = current_time
                user_data["ultimo_login"] = current_time
                
                # Añadir campos del perfil expandido
                user_data = initialize_user_profile(user_data)
                
                # Guardar en Firestore
                db.collection(FIREBASE_COLLECTION_USERS).document(uid).set(user_data)
            else:
                logger.error("No se pudo inicializar Firebase para guardar datos de usuario")
                # Continuar aún sin guardar datos adicionales
            
            # Registrar éxito
            circuit_breaker.record_success("firebase_auth")
            
            return {
                "uid": uid,
                "token": id_token,
                "email": email
            }
        else:
            # Error al crear usuario
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Error al crear usuario")
            
            # Mapear códigos de error a mensajes amigables
            error_messages = {
                "EMAIL_EXISTS": "Ya existe una cuenta con este email",
                "OPERATION_NOT_ALLOWED": "El inicio de sesión con contraseña está deshabilitado",
                "TOO_MANY_ATTEMPTS_TRY_LATER": "Demasiados intentos fallidos. Inténtalo más tarde",
                "WEAK_PASSWORD": "La contraseña debe tener al menos 6 caracteres"
            }
            
            friendly_message = error_messages.get(error_message, f"Error al crear usuario: {error_message}")
            
            # Registrar fallo
            circuit_breaker.record_failure("firebase_auth", error_type=error_message)
            
            return {"error": friendly_message}
    
    except FirebaseWebAPIKeyMissingError as e:
        error_msg = f"Error de configuración: {str(e)}"
        logger.error(error_msg)
        # No registramos esto como fallo en circuit_breaker, es un problema de configuración
        return {"error": error_msg}
    except Exception as e:
        logger.error(f"Error en create_user: {str(e)}")
        circuit_breaker.record_failure("firebase_auth", error_type="general")
        return {"error": f"Error durante el proceso de crear usuario: {str(e)}"}

def initialize_user_profile(user_data: dict) -> dict:
    """
    Inicializa los campos de perfil expandido para un nuevo usuario.
    
    Args:
        user_data: Datos básicos del usuario
        
    Returns:
        dict: Datos del usuario con campos de perfil expandido añadidos
    """
    # Clonar datos del usuario para no modificar el original
    profile_data = user_data.copy()
    
    # Iterar sobre el esquema del perfil
    for field, default_value in STUDENT_PROFILE_SCHEMA.items():
        # Si el campo ya existe en user_data, respetarlo
        if field not in profile_data:
            profile_data[field] = default_value
    
    logger.info(f"Perfil inicializado para nuevo usuario")
    return profile_data

def ensure_profile_fields(uid):
    """
    Asegura que el usuario tenga todos los campos del perfil expandido.
    Si algún campo falta, lo añade con valor por defecto.
    
    Args:
        uid: ID del usuario
        
    Returns:
        bool: True si se actualizó el perfil, False en caso contrario
    """
    try:
        # Validación de entrada
        if not uid:
            logger.warning("UID vacío en ensure_profile_fields")
            return False
        
        logger.info(f"Verificando campos de perfil para usuario {uid}")
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en ensure_profile_fields")
            return False
        
        # Obtener documento del usuario
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid)
        doc = doc_ref.get()
        
        if not doc.exists:
            logger.warning(f"No se encontró documento para uid: {uid}")
            # Intentar crear el documento con el esquema completo
            try:
                data = STUDENT_PROFILE_SCHEMA.copy()
                data["uid"] = uid
                data["creado"] = time.time()
                
                doc_ref.set(data)
                logger.info(f"Creado perfil completo para usuario {uid}")
                return True
            except Exception as create_error:
                logger.error(f"Error creando perfil: {create_error}")
                return False
        
        # Obtener datos actuales
        user_data = doc.to_dict()
        
        # Verificar si faltan campos del perfil o si algún campo es None
        missing_fields = {}
        for field, default_value in STUDENT_PROFILE_SCHEMA.items():
            if field not in user_data or user_data[field] is None:
                missing_fields[field] = default_value
                logger.info(f"Campo '{field}' faltante o None, se asignará valor por defecto")
        
        # Si hay campos faltantes, actualizarlos
        if missing_fields:
            logger.info(f"Añadiendo {len(missing_fields)} campos faltantes al perfil del usuario {uid}")
            doc_ref.update(missing_fields)
            return True
        
        logger.info(f"El perfil del usuario {uid} ya tiene todos los campos necesarios")
        return False
    
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error en ensure_profile_fields: {e}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return False

def get_user_data(uid):
    """
    Obtiene los datos de un usuario desde Firestore con
    validaciones adicionales y logging detallado para diagnóstico.
    
    Args:
        uid: ID del usuario
        
    Returns:
        dict: Datos del usuario o diccionario vacío si no se encuentra
    """
    try:
        # Validación de entrada
        if not uid:
            logger.warning("UID vacío en get_user_data")
            return {}
        
        # Registro detallado para diagnóstico
        logger.info(f"Obteniendo datos para usuario con UID: {uid}")
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en get_user_data")
            return {}
        
        # Obtener documento del usuario
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid)
        doc = doc_ref.get()
        
        if doc.exists:
            # Convertir a diccionario
            user_data = doc.to_dict()
            logger.info(f"Datos obtenidos correctamente para usuario {uid}")
            
            # Log detallado de campos críticos para diagnóstico
            if "nivel" in user_data:
                logger.info(f"Nivel del usuario en Firebase: {user_data['nivel']}")
            else:
                logger.warning(f"Campo 'nivel' no encontrado en datos del usuario {uid}")
            
            if "numero_correcciones" in user_data:
                logger.info(f"Número de correcciones en Firebase: {user_data['numero_correcciones']}")
            else:
                logger.warning(f"Campo 'numero_correcciones' no encontrado en datos del usuario {uid}")
            
            # Verificar y completar campos faltantes
            campos_faltantes = {}
            for campo, valor_default in STUDENT_PROFILE_SCHEMA.items():
                if campo not in user_data:
                    campos_faltantes[campo] = valor_default
                    logger.warning(f"Campo '{campo}' faltante, usando valor por defecto: {valor_default}")
            
            # Si faltan campos, actualizar silenciosamente en Firebase
            if campos_faltantes:
                try:
                    logger.info(f"Actualizando {len(campos_faltantes)} campos faltantes para usuario {uid}")
                    doc_ref.update(campos_faltantes)
                    
                    # Combinar los datos actuales con los campos faltantes
                    user_data.update(campos_faltantes)
                except Exception as update_error:
                    logger.error(f"Error actualizando campos faltantes: {update_error}")
            
            return user_data
        else:
            logger.warning(f"No se encontró documento para uid: {uid}")
            
            # En caso de no encontrar el usuario, intentar crearlo con los valores por defecto
            try:
                logger.info(f"Intentando crear usuario con UID {uid} y valores por defecto")
                data = STUDENT_PROFILE_SCHEMA.copy()
                data["uid"] = uid
                data["creado"] = time.time()
                
                doc_ref.set(data)
                logger.info(f"Usuario {uid} creado con valores por defecto")
                return data
            except Exception as create_error:
                logger.error(f"Error creando usuario: {create_error}")
                return {}
    
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error en get_user_data: {e}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return {}

def update_user_data(uid: str, data: dict) -> bool:
    """
    Actualiza los datos de un usuario en Firestore.
    
    Args:
        uid: ID del usuario
        data: Datos a actualizar
        
    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario
    """
    try:
        if not uid:
            logger.warning("UID vacío en update_user_data")
            return False
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en update_user_data")
            return False
        
        # Actualizar documento
        db.collection(FIREBASE_COLLECTION_USERS).document(uid).update(data)
        
        logger.info(f"Datos actualizados para usuario {uid}")
        return True
    
    except Exception as e:
        logger.error(f"Error en update_user_data: {e}")
        return False

def update_user_profile(uid: str, profile_data: dict) -> bool:
    """
    Actualiza los datos de perfil de un usuario, validando la estructura.
    
    Args:
        uid: ID del usuario
        profile_data: Datos de perfil a actualizar
        
    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario
    """
    try:
        if not uid:
            logger.warning("UID vacío en update_user_profile")
            return False
        
        # Validar campos permitidos
        valid_fields = set(STUDENT_PROFILE_SCHEMA.keys())
        update_data = {}
        
        for field, value in profile_data.items():
            if field in valid_fields:
                update_data[field] = value
            else:
                logger.warning(f"Campo de perfil no reconocido: {field} - ignorado")
        
        # Si no hay campos válidos, salir
        if not update_data:
            logger.warning("No se encontraron campos válidos para actualizar")
            return False
        
        # Actualizar datos
        return update_user_data(uid, update_data)
    
    except Exception as e:
        logger.error(f"Error en update_user_profile: {e}")
        return False

def get_user_thread(uid: str):
    """
    Obtiene el thread_id asociado a un usuario desde Firestore.
    
    Args:
        uid: ID del usuario
        
    Returns:
        str: ID del thread o None si no se encuentra
    """
    try:
        if not uid:
            logger.warning("UID vacío en get_user_thread")
            return None
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en get_user_thread")
            return None
        
        # Obtener documento del usuario
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid)
        doc = doc_ref.get()
        
        if doc.exists:
            # Obtener thread_id
            user_data = doc.to_dict()
            thread_id = user_data.get("thread_id")
            
            if thread_id:
                logger.info(f"Thread existente encontrado para usuario {uid}: {thread_id}")
                return thread_id
            
            return None
        else:
            logger.warning(f"No se encontró documento para uid: {uid}")
            return None
    
    except Exception as e:
        logger.error(f"Error en get_user_thread: {e}")
        return None
        

def get_thread_message_count(thread_id):
    """
    Obtiene el número de mensajes en un thread.
    
    Args:
        thread_id (str): ID del thread
        
    Returns:
        int: Número de mensajes o None si hay error
    """
    if not thread_id:
        return None
        
    try:
        # Obtener cliente OpenAI para listar mensajes
        from core.clean_openai_assistant import get_clean_openai_assistants_client
        client = get_clean_openai_assistants_client()
        
        if not client:
            logger.error("No se pudo obtener cliente para contar mensajes")
            return None
            
        # Listar mensajes con límite alto para contar todos
        messages_response = client.list_messages(thread_id, limit=100)
        
        if not messages_response or "data" not in messages_response:
            logger.warning(f"No se pudieron obtener mensajes para thread {thread_id}")
            return None
            
        # Contar mensajes
        message_count = len(messages_response.get("data", []))
        logger.info(f"Thread {thread_id} tiene {message_count} mensajes")
        
        # Guardar conteo en caché para futura referencia
        if hasattr(st, "session_state"):
            st.session_state[f"thread_{thread_id}_message_count"] = message_count
            st.session_state[f"thread_{thread_id}_count_updated_at"] = time.time()
            
        return message_count
        
    except Exception as e:
        logger.error(f"Error obteniendo conteo de mensajes para thread {thread_id}: {e}")
        return None

def save_thread_metrics(thread_id, user_id, message_count=None, token_estimate=None):
    """
    Guarda métricas del thread en Firebase para análisis y optimización.
    
    Args:
        thread_id (str): ID del thread
        user_id (str): ID del usuario
        message_count (int, opcional): Número de mensajes
        token_estimate (int, opcional): Estimación de tokens consumidos
        
    Returns:
        bool: True si se guardó correctamente
    """
    if not thread_id or not user_id:
        return False
        
    try:
        # Obtener BD si está disponible
        if not firebase_admin._apps:
            logger.warning("Firebase no inicializado para guardar métricas de thread")
            return False
            
        db = firestore.client()
        
        # Si no se proporciona conteo, intentar obtenerlo
        if message_count is None:
            message_count = get_thread_message_count(thread_id) or 0
            
        # Estimar tokens si no se proporcionan (muy aproximado)
        if token_estimate is None and message_count:
            # Estimación simple: ~800 tokens por mensaje en promedio
            token_estimate = message_count * 800
            
        # Crear documento de métricas
        metrics_data = {
            "thread_id": thread_id,
            "user_id": user_id,
            "message_count": message_count,
            "token_estimate": token_estimate,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "is_active": True
        }
        
        # Guardar en colección de métricas
        db.collection("thread_metrics").document(thread_id).set(metrics_data)
        logger.info(f"Métricas guardadas para thread {thread_id}: {message_count} mensajes, ~{token_estimate} tokens")
        
        return True
        
    except Exception as e:
        logger.error(f"Error guardando métricas de thread: {e}")
        return False

def mark_thread_inactive(thread_id):
    """
    Marca un thread como inactivo en la base de datos.
    Útil para seguimiento de threads rotados.
    
    Args:
        thread_id (str): ID del thread a marcar
        
    Returns:
        bool: True si se marcó correctamente
    """
    if not thread_id:
        return False
        
    try:
        # Obtener BD si está disponible
        if not firebase_admin._apps:
            logger.warning("Firebase no inicializado para marcar thread")
            return False
            
        db = firestore.client()
        
        # Actualizar estado en métricas
        db.collection("thread_metrics").document(thread_id).update({
            "is_active": False,
            "deactivated_at": firestore.SERVER_TIMESTAMP
        })
        
        logger.info(f"Thread {thread_id} marcado como inactivo")
        return True
        
    except Exception as e:
        logger.error(f"Error marcando thread como inactivo: {e}")
        return False

# Agregar esta funcionalidad a save_user_thread existente
def save_user_thread_enhanced(user_id, thread_id):
    """
    Versión mejorada de save_user_thread que también registra métricas.
    
    Args:
        user_id (str): ID del usuario
        thread_id (str): ID del thread
        
    Returns:
        bool: True si se guardó correctamente
    """
    try:
        # Primero guardar thread normalmente 
        from core.firebase_client import save_user_thread
        result = save_user_thread(user_id, thread_id)
        
        # Si se guardó correctamente y hay thread_id (no es None)
        if result and thread_id:
            # Guardar métricas adicionales
            save_thread_metrics(thread_id, user_id)
            
            # Si hay thread anterior, marcarlo como inactivo
            previous_thread = st.session_state.get("previous_thread_id")
            if previous_thread and previous_thread != thread_id:
                mark_thread_inactive(previous_thread)
                
            # Actualizar referencia al thread anterior
            st.session_state["previous_thread_id"] = thread_id
            
        return result
        
    except Exception as e:
        logger.error(f"Error en save_user_thread_enhanced: {e}")
        return False

def save_correction(correction_data: dict) -> str:
    """
    Guarda una corrección de texto en Firestore.
    
    Args:
        correction_data: Datos de la corrección
        
    Returns:
        str: ID del documento creado o None si hubo error
    """
    try:
        # Verificar datos mínimos
        if not correction_data or "uid" not in correction_data:
            logger.warning("Datos de corrección inválidos")
            return None
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en save_correction")
            return None
        
        # Obtener UID
        uid = correction_data["uid"]
        
        # Añadir timestamp si no existe
        if "timestamp" not in correction_data:
            correction_data["timestamp"] = time.time()
        
        # Guardar en colección de correcciones del usuario
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                    .collection(FIREBASE_COLLECTION_CORRECTIONS).document()
        
        # Guardar
        doc_ref.set(correction_data)
        
        logger.info(f"Corrección guardada para usuario {uid}: {doc_ref.id}")
        return doc_ref.id
    
    except Exception as e:
        logger.error(f"Error en save_correction: {e}")
        return None

def get_corrections(uid: str, limit: int = 10) -> list:
    """
    Obtiene las correcciones de un usuario desde Firestore.
    
    Args:
        uid: ID del usuario
        limit: Número máximo de correcciones a obtener
        
    Returns:
        list: Lista de correcciones o lista vacía si no se encuentran
    """
    try:
        if not uid:
            logger.warning("UID vacío en get_corrections")
            return []
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en get_corrections")
            return []
        
        # Obtener correcciones
        corrections_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                            .collection(FIREBASE_COLLECTION_CORRECTIONS) \
                            .order_by("timestamp", direction=firestore.Query.DESCENDING) \
                            .limit(limit)
        
        corrections = []
        for doc in corrections_ref.stream():
            correction = doc.to_dict()
            correction["id"] = doc.id
            corrections.append(correction)
        
        return corrections
    
    except Exception as e:
        logger.error(f"Error en get_corrections: {e}")
        return []

def save_model_metrics(modelo: str, tiempo_respuesta: float, longitud_texto: int, resultado_exitoso: bool):
    """
    Guarda métricas de uso de modelos en Firestore para análisis posterior.
    
    Args:
        modelo: Nombre del modelo usado
        tiempo_respuesta: Tiempo de respuesta en segundos
        longitud_texto: Longitud del texto procesado (tokens o palabras)
        resultado_exitoso: Si la operación fue exitosa
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Inicializar Firebase sin forzar
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.warning("No se pudo inicializar Firebase para métricas")
            return False
        
        # Datos a guardar
        metrics_data = {
            "modelo": modelo,
            "tiempo_respuesta": tiempo_respuesta,
            "longitud_texto": longitud_texto,
            "resultado_exitoso": resultado_exitoso,
            "timestamp": time.time()
        }
        
        # Guardar en colección de métricas
        db.collection("metricas").add(metrics_data)
        
        return True
    
    except Exception as e:
        logger.error(f"Error guardando métricas: {e}")
        return False

def get_correcciones_usuario(uid: str) -> list:
    """
    Obtiene todas las correcciones de un usuario.
    
    Args:
        uid: ID del usuario
        
    Returns:
        list: Lista de correcciones
    """
    try:
        if not uid:
            return []
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            return []
        
        # Obtener correcciones
        correcciones_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                            .collection(FIREBASE_COLLECTION_CORRECTIONS) \
                            .order_by("fecha", direction=firestore.Query.DESCENDING)
        
        correcciones = []
        for doc in correcciones_ref.stream():
            correccion = doc.to_dict()
            correccion["id"] = doc.id
            correcciones.append(correccion)
        
        return correcciones
    
    except Exception as e:
        logger.error(f"Error obteniendo correcciones: {e}")
        return []

def get_simulacros_usuario(uid: str) -> list:
    """
    Obtiene todos los simulacros de un usuario.
    
    Args:
        uid: ID del usuario
        
    Returns:
        list: Lista de simulacros
    """
    try:
        if not uid:
            return []
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            return []
        
        # Obtener simulacros
        simulacros_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                           .collection("simulacros") \
                           .order_by("fecha", direction=firestore.Query.DESCENDING)
        
        simulacros = []
        for doc in simulacros_ref.stream():
            simulacro = doc.to_dict()
            simulacro["id"] = doc.id
            simulacros.append(simulacro)
        
        return simulacros
    
    except Exception as e:
        logger.error(f"Error obteniendo simulacros: {e}")
        return []

def get_ejercicios_usuario(uid: str) -> list:
    """
    Obtiene todos los ejercicios de un usuario.
    
    Args:
        uid: ID del usuario
        
    Returns:
        list: Lista de ejercicios
    """
    try:
        if not uid:
            return []
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            return []
        
        # Obtener ejercicios
        ejercicios_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                           .collection("ejercicios") \
                           .order_by("fecha", direction=firestore.Query.DESCENDING)
        
        ejercicios = []
        for doc in ejercicios_ref.stream():
            ejercicio = doc.to_dict()
            ejercicio["id"] = doc.id
            ejercicios.append(ejercicio)
        
        return ejercicios
    
    except Exception as e:
        logger.error(f"Error obteniendo ejercicios: {e}")
        return []
    
def obtener_historial_correcciones(uid):
    """
    Obtiene el historial de correcciones de un usuario.
    
    Args:
        uid (str): ID del usuario
        
    Returns:
        list: Lista de correcciones o lista vacía en caso de error
    """
    try:
        if not uid:
            return []
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            return []
        
        # Obtener correcciones
        correcciones_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                            .collection(FIREBASE_COLLECTION_CORRECTIONS) \
                            .order_by("fecha", direction=firestore.Query.DESCENDING)
        
        correcciones = []
        for doc in correcciones_ref.stream():
            correccion = doc.to_dict()
            correccion["id"] = doc.id
            correcciones.append(correccion)
        
        return correcciones
    
    except Exception as e:
        logger.error(f"Error obteniendo correcciones: {e}")
        return []

def guardar_correccion_firebase(datos: dict) -> bool:
    """
    Guarda datos de una corrección en Firebase.
    
    Args:
        datos: Datos de la corrección
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener UID
        uid = datos.get("uid")
        if not uid:
            logger.warning("UID vacío en guardar_correccion_firebase")
            return False
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase")
            return False
        
        # Guardar en Firestore
        coleccion_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                          .collection(FIREBASE_COLLECTION_CORRECTIONS)
                          
        # Añadir documento sin ID específico
        coleccion_ref.add(datos)
        
        logger.info(f"Corrección guardada para usuario {uid}")
        return True
    
    except Exception as e:
        logger.error(f"Error guardando corrección: {e}")
        return False

def guardar_resultado_simulacro(datos: dict) -> bool:
    """
    Guarda resultados de un simulacro en Firebase.
    
    Args:
        datos: Datos del simulacro
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener UID
        uid = datos.get("uid")
        if not uid:
            logger.warning("UID vacío en guardar_resultado_simulacro")
            return False
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase")
            return False
        
        # Guardar en Firestore
        coleccion_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                          .collection("simulacros")
                          
        # Añadir documento sin ID específico
        coleccion_ref.add(datos)
        
        logger.info(f"Resultado de simulacro guardado para usuario {uid}")
        return True
    
    except Exception as e:
        logger.error(f"Error guardando resultado de simulacro: {e}")
        return False

def actualizar_progreso_actividad(uid: str, actividad_id: str, datos: dict) -> bool:
    """
    Actualiza el progreso de una actividad en el plan de estudio.
    
    Args:
        uid: ID del usuario
        actividad_id: ID de la actividad
        datos: Datos de progreso
        
    Returns:
        bool: True si se actualizó correctamente, False en caso contrario
    """
    try:
        if not uid or not actividad_id:
            logger.warning("UID o actividad_id vacío en actualizar_progreso_actividad")
            return False
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase")
            return False
        
        # Obtener documento del plan de estudio
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid).collection("planes_estudio").where("activo", "==", True).limit(1)
        docs = doc_ref.stream()
        
        plan_doc = None
        for doc in docs:
            plan_doc = doc
            break
        
        if not plan_doc:
            logger.warning(f"No se encontró plan de estudio activo para usuario {uid}")
            return False
        
        # Actualizar progreso
        plan_data = plan_doc.to_dict()
        progreso = plan_data.get("progreso", {})
        
        # Actualizar la actividad específica
        progreso[actividad_id] = datos
        
        # Guardar cambios
        plan_doc.reference.update({"progreso": progreso})
        
        logger.info(f"Progreso actualizado para actividad {actividad_id} de usuario {uid}")
        return True
    
    except Exception as e:
        logger.error(f"Error actualizando progreso de actividad: {e}")
        return False

def obtener_plan_estudio(uid: str):
    """
    Obtiene el plan de estudio activo de un usuario.
    
    Args:
        uid: ID del usuario
        
    Returns:
        dict: Datos del plan de estudio o None si no existe
    """
    try:
        if not uid:
            logger.warning("UID vacío en obtener_plan_estudio")
            return None
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase")
            return None
        
        # Obtener plan activo
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid).collection("planes_estudio").where("activo", "==", True).limit(1)
        docs = doc_ref.stream()
        
        for doc in docs:
            plan = doc.to_dict()
            plan["id"] = doc.id
            return plan
        
        # Si no hay plan activo, intentar obtener el más reciente
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid).collection("planes_estudio").order_by("fecha_creacion", direction=firestore.Query.DESCENDING).limit(1)
        docs = doc_ref.stream()
        
        for doc in docs:
            plan = doc.to_dict()
            plan["id"] = doc.id
            return plan
        
        return None
    
    except Exception as e:
        logger.error(f"Error obteniendo plan de estudio: {e}")
        return None

def guardar_plan_estudio(datos: dict) -> bool:
    """
    Guarda un plan de estudio para un usuario.
    
    Args:
        datos: Datos del plan
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Obtener UID
        uid = datos.get("uid")
        if not uid:
            logger.warning("UID vacío en guardar_plan_estudio")
            return False
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase")
            return False
        
        # Marcar como activo
        datos["activo"] = True
        
        # Añadir timestamp si no existe
        if "fecha_creacion" not in datos:
            datos["fecha_creacion"] = time.time()
        
        # Desactivar otros planes
        planes_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid).collection("planes_estudio").where("activo", "==", True)
        for doc in planes_ref.stream():
            doc.reference.update({"activo": False})
        
        # Guardar en Firestore
        coleccion_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid).collection("planes_estudio")
        
        # Añadir documento sin ID específico
        coleccion_ref.add(datos)
        
        logger.info(f"Plan de estudio guardado para usuario {uid}")
        return True
    
    except Exception as e:
        logger.error(f"Error guardando plan de estudio: {e}")
        return False

def obtener_historial_consignas(uid: str) -> list:
    """
    Obtiene el historial de consignas de un usuario.
    
    Args:
        uid: ID del usuario
        
    Returns:
        list: Lista de consignas
    """
    try:
        if not uid:
            return []
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            return []
        
        # Obtener consignas
        consignas_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid) \
                          .collection("consignas") \
                          .order_by("fecha", direction=firestore.Query.DESCENDING)
        
        consignas = []
        for doc in consignas_ref.stream():
            consigna = doc.to_dict()
            consigna["id"] = doc.id
            consignas.append(consigna)
        
        return consignas
    
    except Exception as e:
        logger.error(f"Error obteniendo historial de consignas: {e}")
        return []

# Funciones para la corrección

def save_correccion(user_id, texto_original, texto_corregido, nivel, errores, puntuacion=None):
    """
    Guarda una corrección de texto en Firestore.
    Esta es una función wrapper que utiliza la implementación transaccional.
    
    Args:
        user_id (str): ID del usuario
        texto_original (str): Texto original sin corregir
        texto_corregido (str): Texto ya corregido
        nivel (str): Nivel de español del estudiante (A1-C2)
        errores (dict): Diccionario con conteo de errores por categoría
        puntuacion (float, opcional): Puntuación asignada a la corrección
        
    Returns:
        str: ID del documento creado o None si hubo error
    """
    return save_correction_with_stats(
        user_id=user_id,
        texto_original=texto_original,
        texto_corregido=texto_corregido,
        nivel=nivel,
        errores=errores,
        puntuacion=puntuacion
    )

def get_error_statistics(user_id):
    """
    Obtiene estadísticas detalladas de errores del estudiante.
    
    Args:
        user_id (str): ID del usuario
        
    Returns:
        dict: Estadísticas de errores
    """
    try:
        # Validar parámetro
        if not user_id:
            logger.warning("user_id vacío en get_error_statistics")
            return {}
        
        # Obtener datos del usuario
        user_data = get_user_data(user_id)
        
        if not user_data or "errores_por_tipo" not in user_data:
            logger.warning(f"No se encontraron estadísticas para el usuario {user_id}")
            return {
                "errores_por_tipo": {},
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
        error_details = traceback.format_exc()
        logger.error(f"Error en get_error_statistics: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return {
            "error": f"Error obteniendo estadísticas: {str(e)}",
            "errores_por_tipo": {},
            "total_correcciones": 0,
            "areas_problematicas": []
        }
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementación de la función save_correction_with_stats
Debe ubicarse al final del archivo core/firebase_client.py
"""

def save_correction_with_stats(user_id, texto_original, texto_corregido, nivel, errores, puntuacion=None):
    """
    Guarda una corrección de texto en Firestore y actualiza las estadísticas de usuario.
    Implementación transaccional para garantizar consistencia de datos.
    
    Args:
        user_id (str): ID del usuario
        texto_original (str): Texto original sin corregir
        texto_corregido (str): Texto ya corregido
        nivel (str): Nivel de español del estudiante (A1-C2)
        errores (dict): Diccionario con conteo de errores por categoría
        puntuacion (float, opcional): Puntuación asignada a la corrección
        
    Returns:
        str: ID del documento creado o None si hubo error
    """
    try:
        # Validar parámetros obligatorios
        if not user_id or not isinstance(texto_original, str) or not isinstance(texto_corregido, str):
            logger.warning("Parámetros incorrectos en save_correction_with_stats")
            return None
        
        # Normalizar nombres de categorías (asegurar minúsculas)
        errores_norm = {}
        for categoria, cantidad in errores.items():
            # Convertir a minúsculas y normalizar tildes
            cat_norm = categoria.lower().strip()
            cat_norm = cat_norm.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            errores_norm[cat_norm] = cantidad
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en save_correction_with_stats")
            return None
        
        # Datos de la corrección
        correction_data = {
            "uid": user_id,
            "texto_original": texto_original,
            "texto_corregido": texto_corregido,
            "nivel": nivel,
            "errores": errores_norm,
            "puntuacion": puntuacion if puntuacion is not None else 0.0,
            "fecha": time.time()
        }
        
        # Ejecutar en transacción para garantizar atomicidad
        @firestore.transactional
        def update_in_transaction(transaction, user_ref, correction_data):
            # Obtener datos actuales del usuario
            user_snapshot = user_ref.get(transaction=transaction)
            
            if not user_snapshot.exists:
                # Si el usuario no existe, crearlo con campos por defecto
                logger.warning(f"Usuario {user_id} no existe, creando perfil")
                user_data = initialize_user_profile({"uid": user_id})
                transaction.set(user_ref, user_data)
            else:
                user_data = user_snapshot.to_dict()
            
            # Actualizar estadísticas de errores
            if "errores_por_tipo" not in user_data:
                user_data["errores_por_tipo"] = {}
            
            # Sumar los nuevos errores a los existentes
            for categoria, cantidad in errores_norm.items():
                if categoria in user_data["errores_por_tipo"]:
                    user_data["errores_por_tipo"][categoria] += cantidad
                else:
                    user_data["errores_por_tipo"][categoria] = cantidad
            
            # Incrementar contador de correcciones
            if "numero_correcciones" not in user_data:
                user_data["numero_correcciones"] = 1
            else:
                user_data["numero_correcciones"] += 1
            
            # Actualizar timestamp de última corrección
            user_data["ultima_correccion"] = time.time()
            
            # Actualizar nivel si es distinto
            if "nivel" in user_data and user_data["nivel"] != nivel:
                user_data["nivel_anterior"] = user_data["nivel"]
                user_data["nivel"] = nivel
            elif "nivel" not in user_data:
                user_data["nivel"] = nivel
            
            # Actualizar datos del usuario
            transaction.update(user_ref, {
                "errores_por_tipo": user_data["errores_por_tipo"],
                "numero_correcciones": user_data["numero_correcciones"],
                "ultima_correccion": user_data["ultima_correccion"],
                "nivel": user_data["nivel"]
            })
            
            # Crear documento de corrección
            correction_ref = user_ref.collection(FIREBASE_COLLECTION_CORRECTIONS).document()
            transaction.set(correction_ref, correction_data)
            
            return correction_ref.id
        
        # Obtener referencia al documento del usuario
        user_ref = db.collection(FIREBASE_COLLECTION_USERS).document(user_id)
        
        # Ejecutar transacción
        transaction = db.transaction()
        correction_id = update_in_transaction(transaction, user_ref, correction_data)
        
        logger.info(f"Corrección guardada con éxito para usuario {user_id}, ID: {correction_id}")
        return correction_id
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error en save_correction_with_stats: {str(e)}")
        logger.debug(f"Detalles del error:\n{error_details}")
        return None
