#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo de exportación de informes
---------------------------------
Este módulo contiene funciones para exportar correcciones y reportes en diferentes formatos.
"""

import base64
import io
import json
import logging
import pandas as pd
import streamlit as st
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from core.session_manager import get_session_var, get_user_info
from utils.text_processing import clean_html_tags

logger = logging.getLogger(__name__)

def generar_pdf_base64(html_content, filename="correccion_ele"):
    """
    Convierte contenido HTML a PDF y lo devuelve como string base64.
    
    Args:
        html_content (str): Contenido HTML a convertir
        filename (str): Nombre del archivo (sin extensión)
        
    Returns:
        str: String base64 del PDF generado
    """
    try:
        # Utilizamos pdfkit para la conversión de HTML a PDF
        import pdfkit
        
        # Configuración para pdfkit
        options = {
            'page-size': 'A4',
            'margin-top': '1cm',
            'margin-right': '1cm',
            'margin-bottom': '1cm',
            'margin-left': '1cm',
            'encoding': 'UTF-8',
        }
        
        # Crear el PDF en memoria
        pdf_bytes = pdfkit.from_string(html_content, False, options=options)
        
        # Convertir a base64
        b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        return b64_pdf
    except Exception as e:
        logger.error(f"Error generando PDF: {str(e)}")
        return None

def download_link_pdf(b64_pdf, filename="correccion_ele.pdf", text="Descargar PDF"):
    """
    Crea un enlace de descarga para un PDF en base64.
    
    Args:
        b64_pdf (str): PDF en formato base64
        filename (str): Nombre del archivo de descarga
        text (str): Texto del enlace
        
    Returns:
        str: HTML con el enlace de descarga
    """
    if b64_pdf is None:
        return "Error generando PDF para descargar."
    
    href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{filename}">{text}</a>'
    return href

def exportar_a_word(data, filename="correccion_ele"):
    """
    Exporta una corrección a un documento Word.
    
    Args:
        data (dict): Datos de la corrección
        filename (str): Nombre base del archivo
        
    Returns:
        bytes: Documento Word en formato de bytes
    """
    try:
        # Crear un nuevo documento Word
        doc = Document()
        
        # Configurar márgenes del documento
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)
        
        # Título
        titulo = doc.add_heading("Corrección de Texto ELE", level=1)
        titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Información del alumno
        info_alumno = get_user_info()
        if info_alumno:
            p = doc.add_paragraph()
            p.add_run("Alumno: ").bold = True
            p.add_run(f"{info_alumno.get('nombre', 'No especificado')} {info_alumno.get('apellido', '')}")
            
            p = doc.add_paragraph()
            p.add_run("Nivel: ").bold = True
            p.add_run(f"{info_alumno.get('nivel', 'No especificado')}")
        
        # Fecha y hora
        p = doc.add_paragraph()
        p.add_run("Fecha: ").bold = True
        p.add_run(datetime.now().strftime("%d/%m/%Y %H:%M"))
        
        doc.add_paragraph()  # Espacio
        
        # Texto original
        doc.add_heading("Texto Original", level=2)
        doc.add_paragraph(data.get("texto_original", ""))
        
        doc.add_paragraph()  # Espacio
        
        # Texto corregido
        doc.add_heading("Texto Corregido", level=2)
        corregido_limpio = clean_html_tags(data.get("texto_corregido", ""))
        doc.add_paragraph(corregido_limpio)
        
        doc.add_paragraph()  # Espacio
        
        # Resumen de errores
        doc.add_heading("Resumen de Errores", level=2)
        
        errores = data.get("errores", [])
        if errores:
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            
            # Encabezados
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = "Categoría"
            hdr_cells[1].text = "Cantidad"
            
            # Contenido
            for error in errores:
                row_cells = table.add_row().cells
                row_cells[0].text = error.get("categoria", "")
                row_cells[1].text = str(error.get("cantidad", 0))
        else:
            doc.add_paragraph("No se detectaron errores.")
        
        doc.add_paragraph()  # Espacio
        
        # Comentarios
        doc.add_heading("Comentarios del Profesor", level=2)
        doc.add_paragraph(data.get("retroalimentacion", ""))
        
        # Guardar el documento en memoria
        f = io.BytesIO()
        doc.save(f)
        f.seek(0)
        
        return f.getvalue()
    except Exception as e:
        logger.error(f"Error exportando a Word: {str(e)}")
        return None

def download_link_word(doc_bytes, filename="correccion_ele.docx"):
    """
    Crea un enlace de descarga para un documento Word.
    
    Args:
        doc_bytes (bytes): Documento Word en bytes
        filename (str): Nombre del archivo de descarga
        
    Returns:
        str: HTML con el enlace de descarga
    """
    if doc_bytes is None:
        return "Error generando documento Word para descargar."
    
    b64_doc = base64.b64encode(doc_bytes).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64_doc}" download="{filename}">Descargar Word</a>'
    return href

def exportar_informe_progreso(user_id, periodo=None):
    """
    Genera un informe de progreso del estudiante.
    
    Args:
        user_id (str): ID del usuario
        periodo (str, opcional): Periodo para el informe (semana, mes, trimestre)
        
    Returns:
        pandas.DataFrame: DataFrame con el informe de progreso
    """
    try:
        from core.firebase_client import get_correcciones_usuario
        
        # Obtener correcciones del usuario
        correcciones = get_correcciones_usuario(user_id)
        
        if not correcciones:
            return pd.DataFrame()
        
        # Convertir a DataFrame
        df = pd.DataFrame(correcciones)
        
        # Aplicar filtro por periodo si es necesario
        if periodo:
            ahora = datetime.now()
            if periodo == "semana":
                dias_atras = 7
            elif periodo == "mes":
                dias_atras = 30
            elif periodo == "trimestre":
                dias_atras = 90
            else:
                dias_atras = None
                
            if dias_atras:
                fecha_limite = ahora - pd.Timedelta(days=dias_atras)
                df['fecha'] = pd.to_datetime(df['fecha'])
                df = df[df['fecha'] >= fecha_limite]
        
        # Procesar los datos para el informe
        if not df.empty:
            # Calcular estadísticas de errores
            if 'errores' in df.columns:
                # Expandir la columna de errores (que contiene listas de diccionarios)
                errores_expandidos = []
                for _, row in df.iterrows():
                    fecha = row.get('fecha')
                    for error in row.get('errores', []):
                        error_data = {
                            'fecha': fecha,
                            'categoria': error.get('categoria', ''),
                            'cantidad': error.get('cantidad', 0)
                        }
                        errores_expandidos.append(error_data)
                
                if errores_expandidos:
                    df_errores = pd.DataFrame(errores_expandidos)
                    
                    # Agrupar por categoría
                    resumen_errores = df_errores.groupby('categoria')['cantidad'].sum().reset_index()
                    
                    # Ordenar por cantidad de errores (descendente)
                    resumen_errores = resumen_errores.sort_values('cantidad', ascending=False)
                    
                    return resumen_errores
        
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error generando informe de progreso: {str(e)}")
        return pd.DataFrame()

def guardar_informe_como_json(data, filename="informe_progreso.json"):
    """
    Guarda un informe como archivo JSON.
    
    Args:
        data (dict): Datos del informe
        filename (str): Nombre del archivo
        
    Returns:
        str: Enlace HTML para descargar el archivo
    """
    try:
        # Convertir a JSON
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        # Convertir a base64
        b64 = base64.b64encode(json_str.encode()).decode()
        
        # Crear enlace HTML
        href = f'<a href="data:application/json;base64,{b64}" download="{filename}">Descargar JSON</a>'
        return href
    except Exception as e:
        logger.error(f"Error guardando informe como JSON: {str(e)}")
        return "Error al generar el archivo JSON."

def exportar_csv_desde_dataframe(df, filename="informe_ele.csv"):
    """
    Exporta un DataFrame a CSV y genera un enlace de descarga.
    
    Args:
        df (pandas.DataFrame): DataFrame a exportar
        filename (str): Nombre del archivo CSV
        
    Returns:
        str: Enlace HTML para descargar el CSV
    """
    try:
        if df.empty:
            return "No hay datos para exportar."
        
        # Convertir DataFrame a CSV
        csv = df.to_csv(index=False)
        
        # Convertir a base64
        b64 = base64.b64encode(csv.encode()).decode()
        
        # Crear enlace HTML
        href = f'<a href="data:text/csv;base64,{b64}" download="{filename}">Descargar CSV</a>'
        return href
    except Exception as e:
        logger.error(f"Error exportando CSV: {str(e)}")
        return "Error al generar el archivo CSV."

def mostrar_opciones_exportacion(data, prefix="correccion"):
    """
    Muestra las opciones de exportación en la interfaz de Streamlit.
    
    Args:
        data (dict): Datos a exportar
        prefix (str): Prefijo para los nombres de archivo
        
    Returns:
        None
    """
    try:
        st.write("### Exportar")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Botón para Word
            if st.button("Exportar a Word"):
                doc_bytes = exportar_a_word(data, f"{prefix}_{datetime.now().strftime('%Y%m%d')}")
                if doc_bytes:
                    # Crear enlace de descarga
                    link = download_link_word(doc_bytes, f"{prefix}_{datetime.now().strftime('%Y%m%d')}.docx")
                    st.markdown(link, unsafe_allow_html=True)
                else:
                    st.error("Error al generar el documento Word.")
        
        with col2:
            # Botón para PDF
            if st.button("Exportar a PDF"):
                # Crear contenido HTML desde los datos
                html_content = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 2cm; }}
                        h1 {{ color: #0066cc; text-align: center; }}
                        h2 {{ color: #0066cc; margin-top: 20px; }}
                        .info {{ margin-bottom: 20px; }}
                        .text-block {{ margin-bottom: 20px; }}
                    </style>
                </head>
                <body>
                    <h1>Corrección de Texto ELE</h1>
                    
                    <div class="info">
                        <p><strong>Fecha:</strong> {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
                    </div>
                    
                    <h2>Texto Original</h2>
                    <div class="text-block">
                        {data.get("texto_original", "")}
                    </div>
                    
                    <h2>Texto Corregido</h2>
                    <div class="text-block">
                        {data.get("texto_corregido", "")}
                    </div>
                    
                    <h2>Resumen de Errores</h2>
                    <div class="text-block">
                        <table border="1" cellpadding="5" cellspacing="0" width="100%">
                            <tr>
                                <th>Categoría</th>
                                <th>Cantidad</th>
                            </tr>
                """
                
                # Añadir filas de errores
                errores = data.get("errores", [])
                for error in errores:
                    html_content += f"""
                            <tr>
                                <td>{error.get("categoria", "")}</td>
                                <td>{error.get("cantidad", 0)}</td>
                            </tr>
                    """
                
                # Cerrar tabla y añadir el resto del contenido
                html_content += f"""
                        </table>
                    </div>
                    
                    <h2>Comentarios del Profesor</h2>
                    <div class="text-block">
                        {data.get("retroalimentacion", "")}
                    </div>
                </body>
                </html>
                """
                
                # Generar PDF
                b64_pdf = generar_pdf_base64(html_content, f"{prefix}_{datetime.now().strftime('%Y%m%d')}")
                
                # Mostrar enlace de descarga
                if b64_pdf:
                    link = download_link_pdf(b64_pdf, f"{prefix}_{datetime.now().strftime('%Y%m%d')}.pdf", "Descargar PDF")
                    st.markdown(link, unsafe_allow_html=True)
                else:
                    st.error("Error al generar el PDF. Asegúrate de tener wkhtmltopdf instalado.")
    except Exception as e:
        logger.error(f"Error mostrando opciones de exportación: {str(e)}")
        st.error(f"Error al mostrar opciones de exportación: {str(e)}")
