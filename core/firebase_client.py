#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cliente para Firebase/Firestore
------------------------------
Este módulo proporciona funciones para interactuar con Firebase y Firestore,
permitiendo guardar y recuperar datos de usuario, correcciones e historial.
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
from firebase_admin.exceptions import FirebaseError

from config.settings import FIREBASE_CONFIG
from core.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# Circuit breaker para Firebase
circuit_breaker = CircuitBreaker("firebase")

# Variable global para cliente de Firestore
db = None
firebase_app = None

def initialize_firebase():
    """
    Inicializa la conexión con Firebase.
    
    Returns:
        bool: True si la inicialización fue exitosa, False en caso contrario
    """
    global db, firebase_app
    
    try:
        # Verificar si ya está inicializado
        if db is not None:
            return True
        
        # Verificar si hay credenciales en las variables de entorno o secrets
        project_id = os.environ.get("FIREBASE_PROJECT_ID", None)
        private_key = os.environ.get("FIREBASE_PRIVATE_KEY", None)
        client_email = os.environ.get("FIREBASE_CLIENT_EMAIL", None)
        
        # Si no están en variables de entorno, intentar obtenerlas de secrets
        if not all([project_id, private_key, client_email]):
            try:
                project_id = st.secrets.get("FIREBASE_PROJECT_ID", None)
                private_key = st.secrets.get("FIREBASE_PRIVATE_KEY", None)
                client_email = st.secrets.get("FIREBASE_CLIENT_EMAIL", None)
            except:
                logger.warning("No se pudieron obtener credenciales de Firebase desde secrets")
        
        # Si aún no tenemos credenciales, buscar en la configuración importada
        if not all([project_id, private_key, client_email]):
            project_id = FIREBASE_CONFIG.get("project_id")
            private_key = FIREBASE_CONFIG.get("private_key")
            client_email = FIREBASE_CONFIG.get("client_email")
        
        # Verificar que tenemos credenciales
        if not all([project_id, private_key, client_email]):
            logger.error("Credenciales de Firebase no configuradas")
            return False
        
        # Crear objeto de credenciales
        cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        
        # Inicializar Firebase
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(cred_dict)
            firebase_app = firebase_admin.initialize_app(cred)
        
        # Obtener cliente de Firestore
        db = firestore.client()
        logger.info("Firebase inicializado correctamente")
        
        # Registrar éxito en circuit breaker
        circuit_breaker.record_success("firebase")
        
        return True
    except Exception as e:
        logger.error(f"Error inicializando Firebase: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="init")
        return False

# Funciones de autenticación
def login_user(email: str, password: str) -> Dict[str, Any]:
    """
    Autentica a un usuario con email y contraseña.
    
    Args:
        email: Email del usuario
        password: Contraseña del usuario
        
    Returns:
        dict: Información del usuario o error
    """
    # Por ahora, implementación simulada para pruebas
    # En una implementación real, esto usaría Firebase Auth
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            return {"error": "Servicio Firebase temporalmente no disponible"}
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return {"error": "No se pudo inicializar Firebase"}
        
        # En una implementación real:
        # user = auth.get_user_by_email(email)
        # Verificar contraseña, etc.
        
        # Simulación para pruebas
        # En un entorno de producción, se usaría Firebase Auth
        if email == "demo@example.com" and password == "password":
            return {
                "uid": "demo_user_123",
                "email": email,
                "nombre": "Usuario",
                "apellido": "Demo"
            }
        
        # Si llega aquí, las credenciales son incorrectas
        return {"error": "Credenciales inválidas"}
    except Exception as e:
        logger.error(f"Error en login: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="auth")
        return {"error": f"Error en autenticación: {str(e)}"}

def create_user(email: str, password: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crea un nuevo usuario en Firebase.
    
    Args:
        email: Email del usuario
        password: Contraseña del usuario
        user_data: Datos adicionales del usuario
        
    Returns:
        dict: Información del usuario creado o error
    """
    # Por ahora, implementación simulada para pruebas
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            return {"error": "Servicio Firebase temporalmente no disponible"}
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return {"error": "No se pudo inicializar Firebase"}
        
        # En una implementación real:
        # user = auth.create_user(email=email, password=password)
        # user_id = user.uid
        # Guardar datos en Firestore
        
        # Simulación para pruebas
        # En un entorno de producción, se usaría Firebase Auth
        user_id = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Guardar datos del usuario en dict para simulación
        user_info = {
            "uid": user_id,
            "email": email,
            **user_data
        }
        
        # En implementación real, guardar en Firestore
        
        return user_info
    except Exception as e:
        logger.error(f"Error creando usuario: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="auth")
        return {"error": f"Error creando usuario: {str(e)}"}

# Funciones para datos de usuario
def get_user_data(uid: str) -> Dict[str, Any]:
    """
    Obtiene los datos de un usuario desde Firestore.
    
    Args:
        uid: UID del usuario
        
    Returns:
        dict: Datos del usuario o diccionario vacío
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return {}
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return {}
        
        # En una implementación real:
        # doc_ref = db.collection('usuarios').document(uid)
        # doc = doc_ref.get()
        # if doc.exists:
        #     return doc.to_dict()
        
        # Simulación para pruebas
        if uid == "demo_user_123":
            return {
                "uid": uid,
                "email": "demo@example.com",
                "nombre": "Usuario",
                "apellido": "Demo",
                "nivel": "B1",
                "objetivo": "Mejorar en general",
                "fecha_registro": "2023-01-01T00:00:00.000Z"
            }
        
        return {}
    except Exception as e:
        logger.error(f"Error obteniendo datos de usuario: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="read")
        return {}

def update_user_data(uid: str, data: Dict[str, Any]) -> bool:
    """
    Actualiza los datos de un usuario en Firestore.
    
    Args:
        uid: UID del usuario
        data: Datos a actualizar
        
    Returns:
        bool: True si la actualización fue exitosa, False en caso contrario
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return False
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return False
        
        # En una implementación real:
        # doc_ref = db.collection('usuarios').document(uid)
        # doc_ref.update(data)
        
        # Simulación para pruebas
        logger.info(f"Simulando actualización de datos para usuario {uid}: {data}")
        
        # Registrar éxito en circuit breaker
        circuit_breaker.record_success("firebase")
        
        return True
    except Exception as e:
        logger.error(f"Error actualizando datos de usuario: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="write")
        return False

# Funciones para threads de OpenAI
def get_user_thread(uid: str) -> Optional[str]:
    """
    Obtiene el ID del thread de OpenAI asociado a un usuario.
    
    Args:
        uid: UID del usuario
        
    Returns:
        str: ID del thread o None si no existe
    """
    try:
        # Obtener datos del usuario
        user_data = get_user_data(uid)
        
        # Extraer thread_id
        return user_data.get('thread_id')
    except Exception as e:
        logger.error(f"Error obteniendo thread de usuario: {str(e)}")
        return None

def save_user_thread(uid: str, thread_id: str, email: Optional[str] = None) -> bool:
    """
    Guarda el ID del thread de OpenAI asociado a un usuario.
    
    Args:
        uid: UID del usuario
        thread_id: ID del thread de OpenAI
        email: Email del usuario (opcional)
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Actualizar datos del usuario
        data = {'thread_id': thread_id}
        if email:
            data['email'] = email
        
        return update_user_data(uid, data)
    except Exception as e:
        logger.error(f"Error guardando thread de usuario: {str(e)}")
        return False

# Funciones para correcciones
def guardar_correccion_firebase(datos: Dict[str, Any]) -> bool:
    """
    Guarda una corrección en Firestore.
    
    Args:
        datos: Datos de la corrección
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return False
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return False
        
        # Extraer UID
        uid = datos.get('uid')
        if not uid:
            logger.error("UID no proporcionado para guardar corrección")
            return False
        
        # En una implementación real:
        # doc_ref = db.collection('usuarios').document(uid).collection('correcciones').document()
        # doc_ref.set(datos)
        
        # Simulación para pruebas
        logger.info(f"Simulando guardado de corrección para usuario {uid}")
        
        # Registrar éxito en circuit breaker
        circuit_breaker.record_success("firebase")
        
        return True
    except Exception as e:
        logger.error(f"Error guardando corrección: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="write")
        return False

def obtener_historial_correcciones(uid: str) -> List[Dict[str, Any]]:
    """
    Obtiene el historial de correcciones de un usuario.
    
    Args:
        uid: UID del usuario
        
    Returns:
        list: Lista de correcciones
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return []
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return []
        
        # En una implementación real:
        # docs = db.collection('usuarios').document(uid).collection('correcciones').order_by('fecha', direction='DESCENDING').get()
        # return [doc.to_dict() for doc in docs]
        
        # Simulación para pruebas
        if uid == "demo_user_123":
            return [
                {
                    "uid": uid,
                    "texto_original": "Hola, como estas? Yo estoi bien. Ayer fui a el parque.",
                    "texto_corregido": "Hola, ¿cómo estás? Yo estoy bien. Ayer fui al parque.",
                    "retroalimentacion": "Buen trabajo, solo necesitas mejorar la ortografía y algunas contracciones.",
                    "nivel": "B1",
                    "tipo_texto": "General",
                    "errores": [
                        {"categoria": "Ortografía", "cantidad": 2},
                        {"categoria": "Puntuación", "cantidad": 1}
                    ],
                    "fecha": "2023-04-01T10:30:00.000Z",
                    "puntuacion": 7.5
                }
            ]
        
        return []
    except Exception as e:
        logger.error(f"Error obteniendo historial de correcciones: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="read")
        return []

# Funciones para ejercicios
def guardar_ejercicio(datos: Dict[str, Any]) -> bool:
    """
    Guarda un ejercicio completado en Firestore.
    
    Args:
        datos: Datos del ejercicio
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return False
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return False
        
        # Extraer UID
        uid = datos.get('uid')
        if not uid:
            logger.error("UID no proporcionado para guardar ejercicio")
            return False
        
        # En una implementación real:
        # doc_ref = db.collection('usuarios').document(uid).collection('ejercicios').document()
        # doc_ref.set(datos)
        
        # Simulación para pruebas
        logger.info(f"Simulando guardado de ejercicio para usuario {uid}")
        
        # Registrar éxito en circuit breaker
        circuit_breaker.record_success("firebase")
        
        return True
    except Exception as e:
        logger.error(f"Error guardando ejercicio: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="write")
        return False

def get_ejercicios_usuario(uid: str) -> List[Dict[str, Any]]:
    """
    Obtiene los ejercicios completados por un usuario.
    
    Args:
        uid: UID del usuario
        
    Returns:
        list: Lista de ejercicios
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return []
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return []
        
        # En una implementación real:
        # docs = db.collection('usuarios').document(uid).collection('ejercicios').order_by('fecha', direction='DESCENDING').get()
        # return [doc.to_dict() for doc in docs]
        
        # Simulación para pruebas
        if uid == "demo_user_123":
            return [
                {
                    "uid": uid,
                    "tipo": "Gramática",
                    "nivel": "B1",
                    "puntuacion": 8.0,
                    "fecha": "2023-04-02T15:45:00.000Z"
                }
            ]
        
        return []
    except Exception as e:
        logger.error(f"Error obteniendo ejercicios de usuario: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="read")
        return []

# Funciones para simulacros
def guardar_resultado_simulacro(datos: Dict[str, Any]) -> bool:
    """
    Guarda el resultado de un simulacro en Firestore.
    
    Args:
        datos: Datos del simulacro
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return False
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return False
        
        # Extraer UID
        uid = datos.get('uid')
        if not uid:
            logger.error("UID no proporcionado para guardar simulacro")
            return False
        
        # En una implementación real:
        # doc_ref = db.collection('usuarios').document(uid).collection('simulacros').document()
        # doc_ref.set(datos)
        
        # Simulación para pruebas
        logger.info(f"Simulando guardado de simulacro para usuario {uid}")
        
        # Registrar éxito en circuit breaker
        circuit_breaker.record_success("firebase")
        
        return True
    except Exception as e:
        logger.error(f"Error guardando simulacro: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="write")
        return False

def get_simulacros_usuario(uid: str) -> List[Dict[str, Any]]:
    """
    Obtiene los simulacros realizados por un usuario.
    
    Args:
        uid: UID del usuario
        
    Returns:
        list: Lista de simulacros
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return []
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return []
        
        # En una implementación real:
        # docs = db.collection('usuarios').document(uid).collection('simulacros').order_by('fecha', direction='DESCENDING').get()
        # return [doc.to_dict() for doc in docs]
        
        # Simulación para pruebas
        if uid == "demo_user_123":
            return [
                {
                    "uid": uid,
                    "nivel": "B1",
                    "puntuacion": 75.0,
                    "fecha": "2023-04-03T09:15:00.000Z"
                }
            ]
        
        return []
    except Exception as e:
        logger.error(f"Error obteniendo simulacros de usuario: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="read")
        return []

# Función para guardar métricas de modelo
def save_model_metrics(modelo: str, tiempo_respuesta: float, longitud_texto: int, resultado_exitoso: bool) -> bool:
    """
    Guarda métricas de uso del modelo de OpenAI para análisis.
    
    Args:
        modelo: Nombre del modelo utilizado
        tiempo_respuesta: Tiempo de respuesta en segundos
        longitud_texto: Longitud del texto procesado (palabras)
        resultado_exitoso: Si la operación fue exitosa
        
    Returns:
        bool: True si se guardó correctamente, False en caso contrario
    """
    try:
        # Verificar circuit breaker
        if not circuit_breaker.can_execute("firebase"):
            logger.warning("Circuit breaker abierto para Firebase")
            return False
        
        # Inicializar Firebase si es necesario
        if not initialize_firebase():
            return False
        
        # Preparar datos
        metrica = {
            "modelo": modelo,
            "tiempo_respuesta": tiempo_respuesta,
            "longitud_texto": longitud_texto,
            "resultado_exitoso": resultado_exitoso,
            "fecha": datetime.now().isoformat()
        }
        
        # En una implementación real:
        # doc_ref = db.collection('metricas').document()
        # doc_ref.set(metrica)
        
        # Simulación para pruebas
        logger.info(f"Simulando guardado de métrica: {metrica}")
        
        # Registrar éxito en circuit breaker
        circuit_breaker.record_success("firebase")
        
        return True
    except Exception as e:
        logger.error(f"Error guardando métrica: {str(e)}")
        circuit_breaker.record_failure("firebase", error_type="write")
        return False
    