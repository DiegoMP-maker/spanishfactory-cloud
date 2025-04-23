#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cliente para Firebase
--------------------
Este módulo proporciona funciones para interactuar con los servicios de Firebase,
incluyendo autenticación, Firestore y almacenamiento.
"""

import logging
import time
from typing import Dict, Any, Tuple, List, Optional, Union

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import requests
import json

# Importar configuración
from config.settings import FIREBASE_COLLECTION_USERS, FIREBASE_COLLECTION_CORRECTIONS
from config.settings import FIREBASE_CONFIG as DEFAULT_FIREBASE_CONFIG
# Importar la instancia del circuit breaker y la función de retry
from core.circuit_breaker import circuit_breaker, retry_with_backoff

logger = logging.getLogger(__name__)

# Variables globales
firebase_initialized = False
db = None

def initialize_firebase():
    """
    Inicializa la conexión con Firebase.
    
    Configura el cliente de Firestore utilizando las credenciales almacenadas en secrets.
    
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
        
        # Obtener credenciales de Firebase desde secrets
        firebase_credentials = None
        try:
            # Intentar obtener configuración desde secrets de Streamlit
            firebase_config = st.secrets["firebase"]
            
            # Extraer credenciales relevantes
            firebase_credentials = {
                "type": firebase_config.get("type", ""),
                "project_id": firebase_config.get("project_id", ""),
                "private_key_id": firebase_config.get("private_key_id", ""),
                "private_key": firebase_config.get("private_key", ""),
                "client_email": firebase_config.get("client_email", ""),
                "client_id": firebase_config.get("client_id", ""),
                "auth_uri": firebase_config.get("auth_uri", ""),
                "token_uri": firebase_config.get("token_uri", ""),
                "auth_provider_x509_cert_url": firebase_config.get("auth_provider_x509_cert_url", ""),
                "client_x509_cert_url": firebase_config.get("client_x509_cert_url", "")
            }
        except Exception as e:
            # Si falla, usar configuración predeterminada (solo para desarrollo)
            logger.warning(f"No se pudieron obtener credenciales de Firebase desde secrets: {e}")
            logger.warning("Usando configuración predeterminada (solo para desarrollo)")
            firebase_credentials = DEFAULT_FIREBASE_CONFIG
        
        # Verificar que tenemos las credenciales necesarias
        if not firebase_credentials or not all([
            firebase_credentials.get("type"),
            firebase_credentials.get("project_id"),
            firebase_credentials.get("private_key"),
            firebase_credentials.get("client_email")
        ]):
            logger.error("Credenciales de Firebase incompletas")
            circuit_breaker.record_failure("firebase", "incomplete_credentials")
            return None, False
        
        # Asegurar que private_key está correctamente formateado con newlines
        if "private_key" in firebase_credentials:
            # Reemplazar \\n por \n si es necesario
            if "\\n" in firebase_credentials["private_key"] and "\n" not in firebase_credentials["private_key"]:
                firebase_credentials["private_key"] = firebase_credentials["private_key"].replace("\\n", "\n")
            
            # Asegurar que hay newlines al principio y final si no existen
            if not firebase_credentials["private_key"].startswith("-----BEGIN PRIVATE KEY-----\n"):
                firebase_credentials["private_key"] = firebase_credentials["private_key"].replace(
                    "-----BEGIN PRIVATE KEY-----", 
                    "-----BEGIN PRIVATE KEY-----\n"
                )
            
            if not firebase_credentials["private_key"].endswith("\n-----END PRIVATE KEY-----"):
                firebase_credentials["private_key"] = firebase_credentials["private_key"].replace(
                    "-----END PRIVATE KEY-----", 
                    "\n-----END PRIVATE KEY-----"
                )
        
        # Inicializar Firebase
        cred = credentials.Certificate(firebase_credentials)
        app = firebase_admin.initialize_app(cred)
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
        logger.error(f"Error inicializando Firebase: {e}")
        circuit_breaker.record_failure("firebase", "initialization")
        
        # Actualizar estado de servicio en session state
        st.session_state.firebase_status = False
        
        return None, False

def login_user(email: str, password: str) -> Dict[str, Any]:
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
        api_key = None
        try:
            # Intenta obtener de secrets de streamlit primero
            api_key = st.secrets["firebase_web_api_key"]
        except Exception as e:
            logger.warning(f"No se encontró firebase_web_api_key en secrets: {e}")
            # Como fallback, intenta buscarla en la sección firebase
            try:
                api_key = st.secrets["firebase"]["web_api_key"]
            except Exception as e2:
                logger.warning(f"No se encontró web_api_key en firebase secrets: {e2}")
                # Último intento: usar la configuración por defecto si está disponible
                try:
                    if DEFAULT_FIREBASE_CONFIG.get("apiKey"):
                        api_key = DEFAULT_FIREBASE_CONFIG.get("apiKey")
                        logger.info("Usando apiKey de DEFAULT_FIREBASE_CONFIG como fallback")
                except Exception as e3:
                    logger.error(f"No se pudo obtener API key de DEFAULT_FIREBASE_CONFIG: {e3}")
        
        if not api_key:
            logger.error("No se encontró Firebase Web API Key en ninguna configuración")
            return {"error": "Configuración incompleta para autenticación"}
        
        # URL para autenticación con email/password
        auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        
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
            # Autenticación exitosa
            data = response.json()
            uid = data.get("localId")
            id_token = data.get("idToken")
            
            # Actualizar último login en Firestore
            try:
                db, success = initialize_firebase()
                if success and db:
                    db.collection(FIREBASE_COLLECTION_USERS).document(uid).update({
                        "ultimo_login": time.time()
                    })
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
    
    except Exception as e:
        logger.error(f"Error en login_user: {e}")
        circuit_breaker.record_failure("firebase_auth", error_type="general")
        return {"error": f"Error durante el proceso de login: {str(e)}"}
    
def create_user(email: str, password: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
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
        api_key = None
        try:
            # Intenta obtener de secrets de streamlit primero
            api_key = st.secrets["firebase_web_api_key"]
        except Exception as e:
            logger.warning(f"No se encontró firebase_web_api_key en secrets: {e}")
            # Como fallback, intenta buscarla en la sección firebase
            try:
                api_key = st.secrets["firebase"]["web_api_key"]
            except Exception as e2:
                logger.warning(f"No se encontró web_api_key en firebase secrets: {e2}")
                # Último intento: usar la configuración por defecto si está disponible
                try:
                    if DEFAULT_FIREBASE_CONFIG.get("apiKey"):
                        api_key = DEFAULT_FIREBASE_CONFIG.get("apiKey")
                        logger.info("Usando apiKey de DEFAULT_FIREBASE_CONFIG como fallback")
                except Exception as e3:
                    logger.error(f"No se pudo obtener API key de DEFAULT_FIREBASE_CONFIG: {e3}")
        
        if not api_key:
            logger.error("No se encontró Firebase Web API Key en ninguna configuración")
            return {"error": "Configuración incompleta para crear usuario"}
        
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
    
    except Exception as e:
        logger.error(f"Error en create_user: {e}")
        circuit_breaker.record_failure("firebase_auth", error_type="general")
        return {"error": f"Error durante el proceso de crear usuario: {str(e)}"}
    
def get_user_data(uid: str) -> Dict[str, Any]:
    """
    Obtiene los datos de un usuario desde Firestore.
    
    Args:
        uid: ID del usuario
        
    Returns:
        dict: Datos del usuario o diccionario vacío si no se encuentra
    """
    try:
        if not uid:
            logger.warning("UID vacío en get_user_data")
            return {}
        
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
            return user_data
        else:
            logger.warning(f"No se encontró documento para uid: {uid}")
            return {}
    
    except Exception as e:
        logger.error(f"Error en get_user_data: {e}")
        return {}

def update_user_data(uid: str, data: Dict[str, Any]) -> bool:
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

def get_user_thread(uid: str) -> Optional[str]:
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

def save_user_thread(uid: str, thread_id: str, email: str = None) -> bool:
    """
    Guarda el thread_id asociado a un usuario en Firestore.
    
    Args:
        uid: ID del usuario
        thread_id: ID del thread
        email: Email del usuario (opcional)
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        if not uid or not thread_id:
            logger.warning("UID o thread_id vacío en save_user_thread")
            return False
        
        # Inicializar Firebase
        db, success = initialize_firebase()
        
        if not success or not db:
            logger.error("No se pudo inicializar Firebase en save_user_thread")
            return False
        
        # Datos a guardar
        data = {
            "thread_id": thread_id,
            "thread_updated_at": time.time()
        }
        
        # Si tenemos email, incluirlo para asegurar que existe
        if email:
            data["email"] = email
        
        # Actualizar documento
        doc_ref = db.collection(FIREBASE_COLLECTION_USERS).document(uid)
        doc = doc_ref.get()
        
        if doc.exists:
            # Actualizar documento existente
            doc_ref.update(data)
        else:
            # Crear documento nuevo
            data["uid"] = uid
            data["creado"] = time.time()
            doc_ref.set(data)
        
        logger.info(f"Thread {thread_id} guardado para usuario {uid}")
        return True
    
    except Exception as e:
        logger.error(f"Error en save_user_thread: {e}")
        return False

def save_correction(correction_data: Dict[str, Any]) -> str:
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

def get_corrections(uid: str, limit: int = 10) -> List[Dict[str, Any]]:
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

def get_correcciones_usuario(uid: str) -> List[Dict[str, Any]]:
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

def get_simulacros_usuario(uid: str) -> List[Dict[str, Any]]:
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

def get_ejercicios_usuario(uid: str) -> List[Dict[str, Any]]:
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

def guardar_correccion_firebase(datos: Dict[str, Any]) -> bool:
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

def guardar_resultado_simulacro(datos: Dict[str, Any]) -> bool:
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

def obtener_historial_correcciones(uid: str) -> List[Dict[str, Any]]:
    """
    Obtiene el historial de correcciones de un usuario.
    
    Args:
        uid: ID del usuario
        
    Returns:
        list: Lista de correcciones
    """
    return get_correcciones_usuario(uid)

def obtener_historial_simulacros(uid: str) -> List[Dict[str, Any]]:
    """
    Obtiene el historial de simulacros de un usuario.
    
    Args:
        uid: ID del usuario
        
    Returns:
        list: Lista de simulacros
    """
    return get_simulacros_usuario(uid)

def actualizar_progreso_actividad(uid: str, actividad_id: str, datos: Dict[str, Any]) -> bool:
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

def obtener_plan_estudio(uid: str) -> Optional[Dict[str, Any]]:
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

def guardar_plan_estudio(datos: Dict[str, Any]) -> bool:
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

def obtener_historial_consignas(uid: str) -> List[Dict[str, Any]]:
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
    