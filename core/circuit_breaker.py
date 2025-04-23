#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Circuit Breaker para APIs externas
----------------------------------
Implementación del patrón Circuit Breaker para evitar llamadas repetidas a APIs con fallos.
Previene sobrecarga de servicios y mejora la resiliencia de la aplicación.
"""

import logging
import time
from functools import wraps
from config.settings import CIRCUIT_BREAKER_FAILURE_THRESHOLD, CIRCUIT_BREAKER_RECOVERY_TIMEOUT

logger = logging.getLogger(__name__)

class CircuitBreakerException(Exception):
    """Excepción lanzada cuando el circuit breaker está abierto"""
    pass

class CircuitBreaker:
    """
    Implementación del patrón Circuit Breaker para proteger contra fallos en servicios externos.
    """
    
    def __init__(self, name, failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD, 
                 recovery_timeout=CIRCUIT_BREAKER_RECOVERY_TIMEOUT):
        """
        Inicializa un nuevo Circuit Breaker.
        
        Args:
            name (str): Nombre identificativo del circuit breaker
            failure_threshold (int): Número de fallos consecutivos para abrir el circuito
            recovery_timeout (int): Tiempo en segundos antes de probar nuevamente
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.service_failures = {}  # Para llevar un registro por servicio
    
    def can_execute(self, service_name="default"):
        """
        Determina si se puede ejecutar una operación para un servicio específico.
        
        Args:
            service_name (str): Nombre del servicio a verificar
            
        Returns:
            bool: True si se puede ejecutar, False en caso contrario
        """
        # Obtener estado del servicio específico
        if service_name not in self.service_failures:
            self.service_failures[service_name] = {
                "failure_count": 0,
                "last_failure_time": None,
                "state": "CLOSED"
            }
        
        service_state = self.service_failures[service_name]
        
        if service_state["state"] == "CLOSED":
            return True
        
        if service_state["state"] == "OPEN":
            # Verificar si ha pasado el tiempo de recuperación
            current_time = time.time()
            if service_state["last_failure_time"] and (current_time - service_state["last_failure_time"]) > self.recovery_timeout:
                # Cambiar a estado semi-abierto para permitir un intento
                logger.info(f"Circuit Breaker '{self.name}' cambiando de OPEN a HALF-OPEN para servicio {service_name}")
                service_state["state"] = "HALF-OPEN"
                return True
            return False
        
        # En estado HALF-OPEN, permitir un intento
        return True
    
    def record_success(self, service_name="default"):
        """
        Registra una ejecución exitosa para un servicio específico.
        
        Args:
            service_name (str): Nombre del servicio
            
        Returns:
            None
        """
        if service_name not in self.service_failures:
            return
        
        service_state = self.service_failures[service_name]
        
        # Si estaba en HALF-OPEN y hay éxito, volver a CLOSED
        if service_state["state"] == "HALF-OPEN":
            logger.info(f"Circuit Breaker '{self.name}' cambiando de HALF-OPEN a CLOSED para servicio {service_name}")
            service_state["state"] = "CLOSED"
        
        # Resetear contador de fallos
        service_state["failure_count"] = 0
    
    def record_failure(self, service_name="default", error_type=None):
        """
        Registra un fallo para un servicio específico.
        
        Args:
            service_name (str): Nombre del servicio
            error_type (str, opcional): Tipo de error para registro
            
        Returns:
            None
        """
        # Inicializar servicio si no existe
        if service_name not in self.service_failures:
            self.service_failures[service_name] = {
                "failure_count": 0,
                "last_failure_time": None,
                "state": "CLOSED"
            }
        
        service_state = self.service_failures[service_name]
        
        # Incrementar contador de fallos
        service_state["failure_count"] += 1
        service_state["last_failure_time"] = time.time()
        
        # Registrar en log
        logger.warning(f"Circuit Breaker '{self.name}' registrando fallo #{service_state['failure_count']} "
                     f"para servicio {service_name}" + (f" ({error_type})" if error_type else ""))
        
        # Si alcanza el umbral, abrir el circuito
        if service_state["failure_count"] >= self.failure_threshold:
            logger.warning(f"Circuit Breaker '{self.name}' cambiando a OPEN para servicio {service_name}")
            service_state["state"] = "OPEN"

def circuit_breaker(service_name="default", failure_threshold=None, recovery_timeout=None):
    """
    Decorador para aplicar circuit breaker a funciones.
    
    Args:
        service_name (str): Nombre del servicio
        failure_threshold (int, opcional): Umbral de fallos personalizado
        recovery_timeout (int, opcional): Tiempo de recuperación personalizado
        
    Returns:
        function: Decorador configurado
    """
    def decorator(func):
        # Crear un circuit breaker específico para esta función
        breaker = CircuitBreaker(
            name=f"{func.__name__}_breaker",
            failure_threshold=failure_threshold or CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=recovery_timeout or CIRCUIT_BREAKER_RECOVERY_TIMEOUT
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not breaker.can_execute(service_name):
                raise CircuitBreakerException(f"Circuit breaker abierto para {service_name}")
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success(service_name)
                return result
            except Exception as e:
                breaker.record_failure(service_name)
                raise
        
        return wrapper
    
    return decorator

# Crear una instancia global del Circuit Breaker para uso en la aplicación
circuit_breaker = CircuitBreaker("global_circuit_breaker")

def retry_with_backoff(func, max_retries=3, initial_delay=1, backoff_factor=2):
    """
    Ejecuta una función con reintentos usando backoff exponencial.
    
    Args:
        func: Función a ejecutar
        max_retries: Número máximo de reintentos
        initial_delay: Tiempo inicial de espera entre reintentos (segundos)
        backoff_factor: Factor para aumentar el tiempo de espera
        
    Returns:
        Result: Resultado de la función o levanta la última excepción
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            logger.warning(f"Intento {attempt+1}/{max_retries} falló: {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"Esperando {delay}s antes de reintentar...")
                time.sleep(delay)
                delay *= backoff_factor
    
    # Si llegamos aquí, todos los intentos fallaron
    logger.error(f"Todos los reintentos fallaron: {str(last_exception)}")
    raise last_exception