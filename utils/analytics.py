#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Funciones para análisis y estadísticas
--------------------------------------
Este módulo contiene funciones para analizar datos de usuarios y generar estadísticas.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)

def calcular_metricas_progreso(correcciones, simulacros, ejercicios):
    """
    Calcula métricas de progreso del estudiante basadas en su actividad.
    
    Args:
        correcciones (list): Lista de correcciones realizadas
        simulacros (list): Lista de simulacros realizados
        ejercicios (list): Lista de ejercicios completados
        
    Returns:
        dict: Diccionario con las métricas calculadas
    """
    try:
        metricas = {}
        
        # Verificar si hay datos suficientes para calcular métricas
        if not correcciones and not simulacros and not ejercicios:
            return {}
        
        # Calcular la tasa de mejora basada en la puntuación de las correcciones
        if len(correcciones) >= 2:
            # Ordenar correcciones por fecha
            correcciones_ordenadas = sorted(correcciones, key=lambda x: x.get('fecha', datetime.min))
            
            # Obtener puntuaciones inicial y final
            puntuaciones = [c.get('puntuacion', 0) for c in correcciones_ordenadas if 'puntuacion' in c]
            
            if len(puntuaciones) >= 2:
                puntuacion_inicial = puntuaciones[0]
                puntuacion_final = puntuaciones[-1]
                
                if puntuacion_inicial > 0:  # Evitar división por cero
                    tasa_mejora = ((puntuacion_final - puntuacion_inicial) / puntuacion_inicial) * 100
                    metricas['tasa_mejora'] = max(0, min(100, tasa_mejora))  # Limitar entre 0 y 100
        
        # Calcular palabras promedio por sesión de escritura
        if correcciones:
            palabras_totales = sum([len(c.get('texto_original', '').split()) for c in correcciones])
            palabras_por_sesion = palabras_totales / len(correcciones)
            metricas['palabras_por_sesion'] = palabras_por_sesion
        
        # Calcular consistencia (frecuencia de uso)
        todas_actividades = correcciones + simulacros + ejercicios
        if todas_actividades:
            # Convertir fechas a objetos datetime si son strings
            for actividad in todas_actividades:
                if 'fecha' in actividad and isinstance(actividad['fecha'], str):
                    try:
                        actividad['fecha'] = datetime.fromisoformat(actividad['fecha'].replace('Z', '+00:00'))
                    except ValueError:
                        actividad['fecha'] = datetime.now()
            
            # Ordenar por fecha
            todas_actividades = sorted(todas_actividades, key=lambda x: x.get('fecha', datetime.min))
            
            if len(todas_actividades) >= 2:
                # Calcular diferencias entre fechas consecutivas
                fechas = [a.get('fecha', datetime.min) for a in todas_actividades if 'fecha' in a]
                
                if len(fechas) >= 2:
                    # Calcular diferencias en días
                    diferencias = [(fechas[i+1] - fechas[i]).days for i in range(len(fechas)-1)]
                    
                    # Calcular regularidad (inverso de la desviación estándar de las diferencias)
                    if diferencias:
                        std_diff = np.std(diferencias) if len(diferencias) > 1 else 0
                        if std_diff == 0:  # Evitar división por cero
                            consistencia = 10.0  # Máxima consistencia
                        else:
                            # A menor desviación estándar, mayor consistencia
                            consistencia = min(10.0, 10.0 / (1 + 0.5 * std_diff))
                        
                        metricas['consistencia'] = consistencia
                
                # Calcular frecuencia promedio (días entre sesiones)
                if fechas and len(fechas) >= 2:
                    primer_fecha = min(fechas)
                    ultima_fecha = max(fechas)
                    dias_totales = (ultima_fecha - primer_fecha).days
                    
                    if dias_totales > 0:
                        sesiones_por_semana = (len(fechas) / dias_totales) * 7
                        metricas['sesiones_por_semana'] = min(7, sesiones_por_semana)  # Máximo 7 (una por día)
        
        # Calcular diversidad de temas tratados
        todos_temas = []
        for actividad in correcciones + ejercicios + simulacros:
            if 'tema' in actividad:
                todos_temas.append(actividad['tema'])
        
        if todos_temas:
            # Contar frecuencia de cada tema
            contador_temas = Counter(todos_temas)
            
            # Calcular índice de diversidad (basado en entropía de Shannon)
            N = len(todos_temas)
            if N > 0:
                diversidad = 0
                for tema, count in contador_temas.items():
                    p = count / N
                    diversidad -= p * np.log(p)
                
                # Normalizar a escala 0-10
                diversidad_normalizada = min(10, diversidad * 3)  # Factor de escala
                metricas['diversidad_temas'] = diversidad_normalizada
        
        return metricas
    except Exception as e:
        logger.error(f"Error calculando métricas de progreso: {str(e)}")
        return {}

def analizar_errores(correcciones):
    """
    Analiza los errores comunes en las correcciones del estudiante.
    
    Args:
        correcciones (list): Lista de correcciones realizadas
        
    Returns:
        dict: Análisis de errores por categoría
    """
    try:
        if not correcciones:
            return {}
        
        # Estructura para almacenar errores por categoría
        errores_por_categoria = {}
        
        # Procesar cada corrección
        for correccion in correcciones:
            # Extraer errores
            for error in correccion.get('errores', []):
                categoria = error.get('categoria', 'Otro')
                cantidad = error.get('cantidad', 0)
                
                # Añadir a la categoría correspondiente
                if categoria in errores_por_categoria:
                    errores_por_categoria[categoria]['total'] += cantidad
                    errores_por_categoria[categoria]['frecuencia'] += 1
                else:
                    errores_por_categoria[categoria] = {
                        'total': cantidad,
                        'frecuencia': 1,
                        'ejemplos': []
                    }
                
                # Añadir ejemplos si están disponibles
                if 'ejemplos' in error and len(error['ejemplos']) > 0:
                    # Limitar a máximo 5 ejemplos por categoría
                    nuevos_ejemplos = error['ejemplos'][:min(5, 5 - len(errores_por_categoria[categoria]['ejemplos']))]
                    errores_por_categoria[categoria]['ejemplos'].extend(nuevos_ejemplos)
        
        # Calcular porcentajes y ordenar por frecuencia
        total_errores = sum(cat['total'] for cat in errores_por_categoria.values())
        
        if total_errores > 0:
            for categoria in errores_por_categoria:
                errores_por_categoria[categoria]['porcentaje'] = (errores_por_categoria[categoria]['total'] / total_errores) * 100
        
        # Ordenar por total de errores (descendente)
        errores_ordenados = {
            k: v for k, v in sorted(
                errores_por_categoria.items(), 
                key=lambda item: item[1]['total'], 
                reverse=True
            )
        }
        
        return errores_ordenados
    except Exception as e:
        logger.error(f"Error analizando errores: {str(e)}")
        return {}

def calcular_nivel_estimado(correcciones, simulacros):
    """
    Estima el nivel de español del estudiante basado en correcciones y simulacros.
    
    Args:
        correcciones (list): Lista de correcciones realizadas
        simulacros (list): Lista de simulacros realizados
        
    Returns:
        dict: Nivel estimado y confianza
    """
    try:
        if not correcciones and not simulacros:
            return {
                'nivel': None,
                'confianza': 0,
                'puntuacion': 0
            }
        
        # Recopilar puntuaciones y niveles de todas las actividades
        puntuaciones_por_nivel = {
            'A1': [],
            'A2': [],
            'B1': [],
            'B2': [],
            'C1': [],
            'C2': []
        }
        
        # Procesar correcciones
        for correccion in correcciones:
            nivel = correccion.get('nivel')
            puntuacion = correccion.get('puntuacion')
            
            if nivel in puntuaciones_por_nivel and puntuacion is not None:
                puntuaciones_por_nivel[nivel].append(puntuacion)
        
        # Procesar simulacros (tienen más peso)
        for simulacro in simulacros:
            nivel = simulacro.get('nivel')
            puntuacion = simulacro.get('puntuacion')
            
            if nivel in puntuaciones_por_nivel and puntuacion is not None:
                # Los simulacros tienen doble peso
                puntuaciones_por_nivel[nivel].append(puntuacion)
                puntuaciones_por_nivel[nivel].append(puntuacion)
        
        # Calcular promedio por nivel
        promedios = {}
        for nivel, puntuaciones in puntuaciones_por_nivel.items():
            if puntuaciones:
                promedios[nivel] = sum(puntuaciones) / len(puntuaciones)
            else:
                promedios[nivel] = 0
        
        # Determinar nivel con mayor puntuación promedio
        nivel_max = max(promedios.items(), key=lambda x: x[1])
        
        if nivel_max[1] == 0:
            return {
                'nivel': None,
                'confianza': 0,
                'puntuacion': 0
            }
        
        # Calcular confianza (qué tan superior es respecto al segundo mayor)
        promedios_ordenados = sorted(promedios.items(), key=lambda x: x[1], reverse=True)
        
        if len(promedios_ordenados) >= 2 and promedios_ordenados[1][1] > 0:
            ratio = promedios_ordenados[0][1] / promedios_ordenados[1][1]
            confianza = min(100, (ratio - 1) * 100)
        else:
            confianza = 90  # Alta confianza si solo hay un nivel con puntuaciones
        
        return {
            'nivel': nivel_max[0],
            'confianza': confianza,
            'puntuacion': nivel_max[1]
        }
    except Exception as e:
        logger.error(f"Error calculando nivel estimado: {str(e)}")
        return {
            'nivel': None,
            'confianza': 0,
            'puntuacion': 0
        }

def analizar_tendencias(correcciones, periodo=30):
    """
    Analiza tendencias en el progreso del estudiante en un periodo determinado.
    
    Args:
        correcciones (list): Lista de correcciones realizadas
        periodo (int): Número de días a analizar
        
    Returns:
        dict: Análisis de tendencias
    """
    try:
        if not correcciones:
            return {}
        
        # Convertir fechas a objetos datetime si son strings
        for correccion in correcciones:
            if 'fecha' in correccion and isinstance(correccion['fecha'], str):
                try:
                    correccion['fecha'] = datetime.fromisoformat(correccion['fecha'].replace('Z', '+00:00'))
                except ValueError:
                    correccion['fecha'] = datetime.now()
        
        # Filtrar por periodo
        fecha_limite = datetime.now() - timedelta(days=periodo)
        correcciones_periodo = [c for c in correcciones if c.get('fecha', datetime.min) >= fecha_limite]
        
        if not correcciones_periodo:
            return {}
        
        # Ordenar por fecha
        correcciones_ordenadas = sorted(correcciones_periodo, key=lambda x: x.get('fecha', datetime.min))
        
        # Crear DataFrame para análisis
        datos = []
        for correccion in correcciones_ordenadas:
            fecha = correccion.get('fecha', datetime.now())
            puntuacion = correccion.get('puntuacion', 0)
            palabras = len(correccion.get('texto_original', '').split())
            
            # Errores por categoría
            errores_dict = {}
            for error in correccion.get('errores', []):
                categoria = error.get('categoria', 'Otro')
                cantidad = error.get('cantidad', 0)
                errores_dict[f"error_{categoria}"] = cantidad
            
            # Combinar datos
            fila = {
                'fecha': fecha,
                'puntuacion': puntuacion,
                'palabras': palabras,
                **errores_dict
            }
            
            datos.append(fila)
        
        # Si no hay suficientes datos, terminar
        if len(datos) < 2:
            return {
                'tendencia_general': 'estable',
                'mensaje': 'No hay suficientes datos para identificar tendencias claras'
            }
        
        # Crear DataFrame
        df = pd.DataFrame(datos)
        
        # Calcular tendencias
        tendencias = {}
        
        # Tendencia en puntuación
        if 'puntuacion' in df.columns and df['puntuacion'].notna().sum() >= 2:
            primera_puntuacion = df['puntuacion'].iloc[0]
            ultima_puntuacion = df['puntuacion'].iloc[-1]
            
            if ultima_puntuacion > primera_puntuacion * 1.1:
                tendencias['puntuacion'] = 'mejora'
            elif ultima_puntuacion < primera_puntuacion * 0.9:
                tendencias['puntuacion'] = 'deterioro'
            else:
                tendencias['puntuacion'] = 'estable'
        
        # Tendencia en cantidad de palabras
        if 'palabras' in df.columns and df['palabras'].notna().sum() >= 2:
            primeras_palabras = df['palabras'].iloc[:len(df)//2].mean()
            ultimas_palabras = df['palabras'].iloc[len(df)//2:].mean()
            
            if ultimas_palabras > primeras_palabras * 1.2:
                tendencias['palabras'] = 'aumento'
            elif ultimas_palabras < primeras_palabras * 0.8:
                tendencias['palabras'] = 'disminución'
            else:
                tendencias['palabras'] = 'estable'
        
        # Tendencias en errores por categoría
        columnas_errores = [col for col in df.columns if col.startswith('error_')]
        tendencias_errores = {}
        
        for columna in columnas_errores:
            if df[columna].notna().sum() >= 2:
                primeros_errores = df[columna].iloc[:len(df)//2].mean()
                ultimos_errores = df[columna].iloc[len(df)//2:].mean()
                
                categoria = columna.replace('error_', '')
                
                if primeros_errores == 0:
                    if ultimos_errores > 0:
                        tendencias_errores[categoria] = 'aumento'
                    else:
                        tendencias_errores[categoria] = 'estable'
                else:
                    ratio = ultimos_errores / primeros_errores
                    
                    if ratio < 0.7:
                        tendencias_errores[categoria] = 'mejora'
                    elif ratio > 1.3:
                        tendencias_errores[categoria] = 'deterioro'
                    else:
                        tendencias_errores[categoria] = 'estable'
        
        # Determinar tendencia general
        if tendencias.get('puntuacion') == 'mejora' and all(v != 'deterioro' for v in tendencias_errores.values()):
            tendencia_general = 'mejora'
        elif tendencias.get('puntuacion') == 'deterioro' or any(v == 'deterioro' for v in tendencias_errores.values()):
            tendencia_general = 'deterioro'
        else:
            tendencia_general = 'estable'
        
        return {
            'tendencia_general': tendencia_general,
            'tendencias_detalladas': {
                **tendencias,
                'errores': tendencias_errores
            },
            'mensaje': generar_mensaje_tendencia(tendencia_general, tendencias, tendencias_errores)
        }
    except Exception as e:
        logger.error(f"Error analizando tendencias: {str(e)}")
        return {
            'tendencia_general': 'estable',
            'mensaje': 'Error al analizar las tendencias'
        }

def generar_mensaje_tendencia(tendencia_general, tendencias, tendencias_errores):
    """
    Genera un mensaje explicativo basado en las tendencias detectadas.
    
    Args:
        tendencia_general (str): Tendencia general detectada
        tendencias (dict): Tendencias en métricas principales
        tendencias_errores (dict): Tendencias en errores por categoría
        
    Returns:
        str: Mensaje explicativo
    """
    if tendencia_general == 'mejora':
        mensaje = "Tu español está mejorando. "
        
        # Detalles sobre errores que han mejorado
        categorias_mejora = [cat for cat, tend in tendencias_errores.items() if tend == 'mejora']
        if categorias_mejora:
            if len(categorias_mejora) == 1:
                mensaje += f"Has reducido los errores de {categorias_mejora[0]}. "
            else:
                cats = ", ".join(categorias_mejora[:-1]) + " y " + categorias_mejora[-1]
                mensaje += f"Has reducido los errores de {cats}. "
        
        # Detalles sobre fluidez
        if tendencias.get('palabras') == 'aumento':
            mensaje += "Estás escribiendo textos más extensos, lo que muestra mayor fluidez. "
        
        mensaje += "¡Sigue así!"
    
    elif tendencia_general == 'deterioro':
        mensaje = "Hemos detectado algunos aspectos a mejorar. "
        
        # Detalles sobre errores que han empeorado
        categorias_deterioro = [cat for cat, tend in tendencias_errores.items() if tend == 'deterioro']
        if categorias_deterioro:
            if len(categorias_deterioro) == 1:
                mensaje += f"Has aumentado los errores de {categorias_deterioro[0]}. "
            else:
                cats = ", ".join(categorias_deterioro[:-1]) + " y " + categorias_deterioro[-1]
                mensaje += f"Has aumentado los errores de {cats}. "
        
        mensaje += "Te recomendamos practicar más estos aspectos."
    
    else:  # estable
        mensaje = "Tu nivel de español se mantiene estable. "
        
        if tendencias.get('palabras') == 'aumento':
            mensaje += "Estás escribiendo textos más extensos, lo que es positivo. "
        
        mensaje += "Para seguir mejorando, te recomendamos enfocarte en ejercicios específicos."
    
    return mensaje

def generar_informe_profesor(correcciones, simulacros, ejercicios, user_info):
    """
    Genera un informe completo para el profesor sobre el progreso del estudiante.
    
    Args:
        correcciones (list): Lista de correcciones realizadas
        simulacros (list): Lista de simulacros realizados
        ejercicios (list): Lista de ejercicios completados
        user_info (dict): Información del usuario
        
    Returns:
        dict: Informe completo
    """
    try:
        # Si no hay datos, devolver mensaje
        if not correcciones and not simulacros and not ejercicios:
            return {
                "mensaje": "El estudiante no ha realizado actividades suficientes para generar un informe.",
                "recomendaciones": ["Animar al estudiante a utilizar la plataforma regularmente."]
            }
        
        informe = {
            "estudiante": {
                "nombre": f"{user_info.get('nombre', '')} {user_info.get('apellido', '')}",
                "email": user_info.get('email', ''),
                "nivel_declarado": user_info.get('nivel', 'No especificado'),
                "objetivo": user_info.get('objetivo', 'No especificado'),
                "lengua_materna": user_info.get('lengua_materna', 'No especificada')
            },
            "actividad": {
                "total_correcciones": len(correcciones),
                "total_simulacros": len(simulacros),
                "total_ejercicios": len(ejercicios),
                "ultima_actividad": None,
                "frecuencia_semanal": 0
            },
            "nivel": {},
            "errores": {},
            "tendencias": {},
            "fortalezas": [],
            "debilidades": [],
            "recomendaciones": []
        }
        
        # Calcular fecha de última actividad
        todas_fechas = []
        for actividad in correcciones + simulacros + ejercicios:
            if 'fecha' in actividad:
                fecha = actividad['fecha']
                if isinstance(fecha, str):
                    try:
                        fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
                    except ValueError:
                        continue
                todas_fechas.append(fecha)
        
        if todas_fechas:
            informe["actividad"]["ultima_actividad"] = max(todas_fechas).strftime("%d/%m/%Y")
            
            # Calcular frecuencia semanal
            if len(todas_fechas) >= 2:
                fecha_min = min(todas_fechas)
                fecha_max = max(todas_fechas)
                
                dias_totales = (fecha_max - fecha_min).days
                if dias_totales > 0:
                    frecuencia = (len(todas_fechas) / dias_totales) * 7
                    informe["actividad"]["frecuencia_semanal"] = round(frecuencia, 1)
        
        # Calcular nivel estimado
        nivel_estimado = calcular_nivel_estimado(correcciones, simulacros)
        if nivel_estimado.get('nivel'):
            informe["nivel"] = {
                "estimado": nivel_estimado.get('nivel'),
                "confianza": f"{round(nivel_estimado.get('confianza', 0), 1)}%",
                "puntuacion": round(nivel_estimado.get('puntuacion', 0), 1)
            }
        
        # Análisis de errores
        errores_analizados = analizar_errores(correcciones)
        if errores_analizados:
            # Convertir a formato simplificado
            errores_formateados = {}
            for categoria, datos in errores_analizados.items():
                errores_formateados[categoria] = {
                    "total": datos['total'],
                    "porcentaje": round(datos.get('porcentaje', 0), 1),
                    "ejemplos": datos.get('ejemplos', [])
                }
            
            informe["errores"] = errores_formateados
            
            # Identificar debilidades (categorías con más errores)
            top_errores = sorted(errores_analizados.items(), key=lambda x: x[1]['total'], reverse=True)
            for categoria, datos in top_errores[:3]:
                informe["debilidades"].append(f"Errores de {categoria}")
        
        # Análisis de tendencias
        tendencias = analizar_tendencias(correcciones)
        if tendencias:
            informe["tendencias"] = tendencias
        
        # Identificar fortalezas
        if correcciones:
            # Buscar categorías con pocos errores o en mejora
            if errores_analizados:
                # Categorías con menos errores
                pocos_errores = sorted(errores_analizados.items(), key=lambda x: x[1]['total'])
                for categoria, datos in pocos_errores[:2]:
                    if datos['total'] < 5:  # Umbral arbitrario
                        informe["fortalezas"].append(f"Buen dominio de {categoria}")
            
            # Buscar tendencias positivas
            if tendencias and "tendencias_detalladas" in tendencias and "errores" in tendencias["tendencias_detalladas"]:
                for categoria, tend in tendencias["tendencias_detalladas"]["errores"].items():
                    if tend == 'mejora':
                        informe["fortalezas"].append(f"Mejora en {categoria}")
        
        # Generar recomendaciones
        if informe["debilidades"]:
            for debilidad in informe["debilidades"]:
                categoria = debilidad.replace("Errores de ", "")
                
                if categoria == "Ortografía":
                    informe["recomendaciones"].append(
                        "Realizar ejercicios de dictado y revisión ortográfica para mejorar la escritura."
                    )
                elif categoria == "Gramática":
                    informe["recomendaciones"].append(
                        "Enfocarse en ejercicios de gramática, especialmente en los tiempos verbales y concordancias."
                    )
                elif categoria == "Vocabulario":
                    informe["recomendaciones"].append(
                        "Ampliar vocabulario mediante lecturas y ejercicios temáticos contextualizados."
                    )
                elif categoria in ["Coherencia", "Cohesión"]:
                    informe["recomendaciones"].append(
                        "Practicar la organización textual y el uso de conectores para mejorar la estructura de los textos."
                    )
        
        # Recomendación sobre frecuencia
        if informe["actividad"]["frecuencia_semanal"] < 2:
            informe["recomendaciones"].append(
                "Animar al estudiante a utilizar la plataforma con mayor regularidad (mínimo 2-3 veces por semana)."
            )
        
        # Si no hay recomendaciones específicas, añadir una general
        if not informe["recomendaciones"]:
            informe["recomendaciones"].append(
                "Continuar con la práctica regular de escritura y realizar ejercicios variados para mantener el progreso."
            )
        
        return informe
    except Exception as e:
        logger.error(f"Error generando informe de profesor: {str(e)}")
        return {
            "mensaje": f"Error generando informe: {str(e)}",
            "recomendaciones": ["Contactar al soporte técnico si el problema persiste."]
        }
    