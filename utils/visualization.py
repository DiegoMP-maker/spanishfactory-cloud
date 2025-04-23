#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Funciones para visualización de datos
------------------------------------
Este módulo contiene funciones para crear visualizaciones a partir de los datos
de correcciones, errores y progreso del estudiante.
"""

import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def crear_grafico_errores(errores, titulo="Distribución de Errores"):
    """
    Crea un gráfico de barras para visualizar la distribución de errores.
    
    Args:
        errores (list): Lista de errores con categoría y cantidad
        titulo (str): Título del gráfico
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico
    """
    try:
        if not errores:
            # Devolver gráfico vacío
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de errores para mostrar",
                template="plotly_white"
            )
            return fig
        
        # Convertir a DataFrame
        df = pd.DataFrame(errores)
        
        # Ordenar por cantidad (descendente)
        df = df.sort_values('cantidad', ascending=False)
        
        # Crear gráfico de barras
        fig = px.bar(
            df, 
            x='categoria', 
            y='cantidad',
            color='categoria',
            title=titulo,
            labels={'categoria': 'Categoría', 'cantidad': 'Cantidad de Errores'}
        )
        
        # Personalizar diseño
        fig.update_layout(
            template="plotly_white",
            xaxis={'categoryorder': 'total descending'},
            showlegend=False
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creando gráfico de errores: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def crear_grafico_progreso(datos, campo_x, campo_y, titulo, color=None):
    """
    Crea un gráfico de líneas para visualizar el progreso en el tiempo.
    
    Args:
        datos (list): Lista de datos con valores temporales
        campo_x (str): Nombre del campo para el eje X (fecha)
        campo_y (str): Nombre del campo para el eje Y (métrica)
        titulo (str): Título del gráfico
        color (str, opcional): Campo para colorear las líneas
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico
    """
    try:
        if not datos:
            # Devolver gráfico vacío
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de progreso para mostrar",
                template="plotly_white"
            )
            return fig
        
        # Convertir a DataFrame
        df = pd.DataFrame(datos)
        
        # Asegurarse de que la fecha está en formato datetime
        if campo_x in df.columns:
            if df[campo_x].dtype == 'object':
                df[campo_x] = pd.to_datetime(df[campo_x])
        
        # Ordenar por fecha
        if campo_x in df.columns:
            df = df.sort_values(campo_x)
        
        # Crear gráfico
        if color and color in df.columns:
            fig = px.line(
                df, 
                x=campo_x, 
                y=campo_y,
                color=color,
                markers=True,
                title=titulo,
                labels={campo_x: 'Fecha', campo_y: 'Valor'}
            )
        else:
            fig = px.line(
                df, 
                x=campo_x, 
                y=campo_y,
                markers=True,
                title=titulo,
                labels={campo_x: 'Fecha', campo_y: 'Valor'}
            )
        
        # Personalizar diseño
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Fecha",
            yaxis_title="Valor",
            hovermode="x unified"
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creando gráfico de progreso: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def crear_radar_habilidades(datos, categorias=None, valor_max=10, titulo="Perfil de Habilidades"):
    """
    Crea un gráfico de radar (araña) para visualizar el perfil de habilidades.
    
    Args:
        datos (dict): Diccionario con valores por categoría
        categorias (list, opcional): Lista de categorías a incluir
        valor_max (int): Valor máximo para la escala
        titulo (str): Título del gráfico
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico
    """
    try:
        if not datos:
            # Devolver gráfico vacío
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de habilidades para mostrar",
                template="plotly_white"
            )
            return fig
        
        # Si no se especifican categorías, usar todas las del diccionario
        if not categorias:
            categorias = list(datos.keys())
        
        # Asegurarse de que todas las categorías están en los datos
        valores = [datos.get(cat, 0) for cat in categorias]
        
        # Crear gráfico de radar
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=valores,
            theta=categorias,
            fill='toself',
            name='Nivel actual'
        ))
        
        # Personalizar diseño
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, valor_max]
                )
            ),
            title=titulo,
            template="plotly_white"
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creando gráfico de radar: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def crear_mapa_calor_actividad(datos, titulo="Mapa de Actividad"):
    """
    Crea un mapa de calor para visualizar la actividad por día de la semana y hora.
    
    Args:
        datos (list): Lista de actividades con timestamps
        titulo (str): Título del gráfico
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico
    """
    try:
        if not datos:
            # Devolver gráfico vacío
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de actividad para mostrar",
                template="plotly_white"
            )
            return fig
        
        # Convertir a DataFrame
        df = pd.DataFrame(datos)
        
        # Asegurarse de que la fecha está en formato datetime
        if 'fecha' in df.columns:
            if df['fecha'].dtype == 'object':
                df['fecha'] = pd.to_datetime(df['fecha'])
        
        # Extraer día de la semana y hora
        df['dia_semana'] = df['fecha'].dt.day_name()
        df['hora'] = df['fecha'].dt.hour
        
        # Contar actividades por día y hora
        heatmap_data = df.groupby(['dia_semana', 'hora']).size().reset_index(name='count')
        
        # Pivotear para formato de matriz
        heatmap_pivot = heatmap_data.pivot(index='dia_semana', columns='hora', values='count')
        
        # Ordenar días de la semana (lunes a domingo)
        orden_dias = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_pivot = heatmap_pivot.reindex(orden_dias)
        
        # Crear etiquetas en español
        dias_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        heatmap_pivot.index = dias_es
        
        # Llenar NaN con 0
        heatmap_pivot = heatmap_pivot.fillna(0)
        
        # Crear gráfico de mapa de calor
        fig = px.imshow(
            heatmap_pivot,
            title=titulo,
            labels=dict(x="Hora del día", y="Día de la semana", color="Actividades"),
            x=[f"{h}:00" for h in range(24)],
            y=dias_es,
            aspect="auto",
            color_continuous_scale="YlOrRd"
        )
        
        # Personalizar diseño
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Hora del día",
            yaxis_title="Día de la semana"
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creando mapa de calor: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def crear_grafico_comparativo(antes, despues, etiquetas, titulo="Comparación Antes vs Después"):
    """
    Crea un gráfico de barras comparativo entre dos conjuntos de valores.
    
    Args:
        antes (list): Lista de valores "antes"
        despues (list): Lista de valores "después"
        etiquetas (list): Lista de etiquetas para las categorías
        titulo (str): Título del gráfico
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico
    """
    try:
        if not antes or not despues or not etiquetas:
            # Devolver gráfico vacío
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos comparativos para mostrar",
                template="plotly_white"
            )
            return fig
        
        # Crear DataFrame
        df = pd.DataFrame({
            'Categoría': etiquetas * 2,
            'Valor': antes + despues,
            'Grupo': ['Antes'] * len(antes) + ['Después'] * len(despues)
        })
        
        # Crear gráfico de barras agrupadas
        fig = px.bar(
            df, 
            x='Categoría', 
            y='Valor', 
            color='Grupo',
            barmode='group',
            title=titulo,
            labels={'Valor': 'Cantidad', 'Categoría': 'Categoría', 'Grupo': ''}
        )
        
        # Personalizar diseño
        fig.update_layout(
            template="plotly_white",
            xaxis={'categoryorder': 'total descending'}
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creando gráfico comparativo: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def crear_grafico_pastel(datos, campo_valores, campo_etiquetas, titulo="Distribución"):
    """
    Crea un gráfico circular (pastel) para visualizar distribuciones.
    
    Args:
        datos (list): Lista de datos
        campo_valores (str): Campo que contiene los valores
        campo_etiquetas (str): Campo que contiene las etiquetas
        titulo (str): Título del gráfico
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el gráfico
    """
    try:
        if not datos:
            # Devolver gráfico vacío
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos para mostrar",
                template="plotly_white"
            )
            return fig
        
        # Convertir a DataFrame
        df = pd.DataFrame(datos)
        
        # Crear gráfico de pastel
        fig = px.pie(
            df, 
            values=campo_valores, 
            names=campo_etiquetas,
            title=titulo,
            hole=0.3
        )
        
        # Personalizar diseño
        fig.update_layout(
            template="plotly_white"
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creando gráfico de pastel: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando gráfico: {str(e)}",
            template="plotly_white"
        )
        return fig

def crear_indicador_progreso(valor, min_val=0, max_val=100, titulo="Progreso", umbral=None):
    """
    Crea un indicador de progreso tipo gauge.
    
    Args:
        valor (float): Valor actual
        min_val (float): Valor mínimo
        max_val (float): Valor máximo
        titulo (str): Título del indicador
        umbral (float, opcional): Valor de umbral para marcar
        
    Returns:
        plotly.graph_objects.Figure: Figura de Plotly con el indicador
    """
    try:
        # Crear gráfico de indicador
        fig = go.Figure()
        
        # Añadir indicador tipo gauge
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=valor,
            title={'text': titulo},
            gauge={
                'axis': {'range': [min_val, max_val]},
                'bar': {'color': "royalblue"},
                'steps': [
                    {'range': [min_val, max_val*0.3], 'color': "lightgray"},
                    {'range': [max_val*0.3, max_val*0.7], 'color': "gray"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': umbral if umbral is not None else max_val*0.8
                }
            }
        ))
        
        # Personalizar diseño
        fig.update_layout(
            template="plotly_white",
            height=300
        )
        
        return fig
    except Exception as e:
        logger.error(f"Error creando indicador de progreso: {str(e)}")
        # Devolver gráfico vacío en caso de error
        fig = go.Figure()
        fig.update_layout(
            title=f"Error creando indicador: {str(e)}",
            template="plotly_white",
            height=300
        )
        return fig

def mostrar_metricas_en_tarjetas(datos, num_columnas=3):
    """
    Muestra métricas en tarjetas utilizando columnas de Streamlit.
    
    Args:
        datos (dict): Diccionario con {título: valor} para cada métrica
        num_columnas (int): Número de columnas para mostrar las tarjetas
        
    Returns:
        None
    """
    try:
        if not datos:
            st.info("No hay métricas para mostrar")
            return
        
        # Crear columnas
        cols = st.columns(num_columnas)
        
        # Distribuir métricas en las columnas
        for i, (titulo, valor) in enumerate(datos.items()):
            col_idx = i % num_columnas
            with cols[col_idx]:
                st.metric(titulo, valor)
    except Exception as e:
        logger.error(f"Error mostrando métricas en tarjetas: {str(e)}")
        st.error(f"Error mostrando métricas: {str(e)}")

def generar_informe_visual(correcciones, periodo=30):
    """
    Genera un informe visual completo con múltiples gráficos.
    
    Args:
        correcciones (list): Lista de correcciones
        periodo (int): Período de tiempo en días para el análisis
        
    Returns:
        dict: Diccionario con figuras de Plotly organizadas por sección
    """
    try:
        if not correcciones:
            return {
                "mensaje": "No hay suficientes datos para generar un informe visual."
            }
        
        # Filtrar por período
        fecha_limite = datetime.now() - timedelta(days=periodo)
        correcciones_filtradas = []
        
        for correccion in correcciones:
            if 'fecha' in correccion:
                fecha = correccion['fecha']
                if isinstance(fecha, str):
                    try:
                        fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
                    except ValueError:
                        continue
                if fecha >= fecha_limite:
                    correcciones_filtradas.append(correccion)
        
        if not correcciones_filtradas:
            return {
                "mensaje": f"No hay datos en los últimos {periodo} días para generar un informe visual."
            }
        
        # Preparar datos para gráficos
        
        # 1. Distribución de errores
        errores_totales = []
        categorias_error = set()
        
        for correccion in correcciones_filtradas:
            for error in correccion.get('errores', []):
                categoria = error.get('categoria', 'Otro')
                categorias_error.add(categoria)
                errores_totales.append({
                    'categoria': categoria,
                    'cantidad': error.get('cantidad', 0)
                })
        
        # Agrupar errores por categoría
        errores_agrupados = {}
        for error in errores_totales:
            categoria = error['categoria']
            cantidad = error['cantidad']
            
            if categoria in errores_agrupados:
                errores_agrupados[categoria] += cantidad
            else:
                errores_agrupados[categoria] = cantidad
        
        # Convertir a formato de lista para el gráfico
        errores_para_grafico = [
            {'categoria': cat, 'cantidad': cant} 
            for cat, cant in errores_agrupados.items()
        ]
        
        # 2. Progreso en el tiempo
        datos_progreso = []
        
        for correccion in correcciones_filtradas:
            if 'fecha' not in correccion:
                continue
                
            fecha = correccion['fecha']
            if isinstance(fecha, str):
                try:
                    fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
                except ValueError:
                    continue
            
            puntuacion = correccion.get('puntuacion', 0)
            
            datos_progreso.append({
                'fecha': fecha,
                'puntuacion': puntuacion
            })
        
        # 3. Actividad por categoría
        datos_actividad = []
        
        for correccion in correcciones_filtradas:
            if 'fecha' not in correccion:
                continue
                
            fecha = correccion['fecha']
            if isinstance(fecha, str):
                try:
                    fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
                except ValueError:
                    continue
            
            tipo = correccion.get('tipo', 'Texto')
            palabras = len(correccion.get('texto_original', '').split())
            
            datos_actividad.append({
                'fecha': fecha,
                'tipo': tipo,
                'palabras': palabras
            })
        
        # 4. Perfil de habilidades (basado en puntuaciones por categoría)
        habilidades = {
            'Gramática': 0,
            'Vocabulario': 0,
            'Ortografía': 0,
            'Coherencia': 0,
            'Cohesión': 0,
            'Puntuación': 0
        }
        
        # Calcular inverso de los errores (más errores = menor puntuación)
        total_errores = sum(errores_agrupados.values()) if errores_agrupados else 0
        
        if total_errores > 0:
            for categoria in habilidades.keys():
                errores_categoria = errores_agrupados.get(categoria, 0)
                # Fórmula: 10 - (errores_categoria / total_errores) * 10
                # Esto da un valor entre 0-10, donde más errores = puntuación más baja
                habilidades[categoria] = max(0, min(10, 10 - (errores_categoria / total_errores) * 10))
        else:
            # Si no hay errores, asignar un valor por defecto
            for categoria in habilidades.keys():
                habilidades[categoria] = 5  # Valor neutral
        
        # Crear gráficos
        graficos = {}
        
        # Gráfico de distribución de errores
        if errores_para_grafico:
            graficos['errores'] = crear_grafico_errores(
                errores_para_grafico, 
                titulo=f"Distribución de Errores (Últimos {periodo} días)"
            )
        
        # Gráfico de progreso
        if datos_progreso:
            graficos['progreso'] = crear_grafico_progreso(
                datos_progreso,
                'fecha',
                'puntuacion',
                titulo=f"Evolución de Puntuaciones (Últimos {periodo} días)"
            )
        
        # Gráfico de actividad
        if datos_actividad:
            graficos['actividad'] = crear_grafico_progreso(
                datos_actividad,
                'fecha',
                'palabras',
                titulo=f"Palabras por Sesión (Últimos {periodo} días)",
                color='tipo'
            )
        
        # Gráfico de perfil de habilidades
        graficos['habilidades'] = crear_radar_habilidades(
            habilidades,
            titulo="Perfil de Habilidades Lingüísticas"
        )
        
        # Gráfico de mapa de calor de actividad
        if datos_actividad:
            graficos['mapa_calor'] = crear_mapa_calor_actividad(
                datos_actividad,
                titulo="Patrón de Actividad por Día y Hora"
            )
        
        return graficos
    except Exception as e:
        logger.error(f"Error generando informe visual: {str(e)}")
        return {
            "mensaje": f"Error generando informe visual: {str(e)}"
        }
    