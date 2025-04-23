#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilidades para manejo de archivos
---------------------------------
Este módulo contiene funciones para el manejo de archivos, incluyendo carga,
procesamiento y exportación de diferentes tipos de archivos.
"""

import logging
import base64
import io
import os
import tempfile
from datetime import datetime
from pathlib import Path
import streamlit as st
from PIL import Image

logger = logging.getLogger(__name__)

def procesar_imagen_subida(uploaded_file, resize=None):
    """
    Procesa una imagen subida por el usuario.
    
    Args:
        uploaded_file (UploadedFile): Archivo subido desde streamlit
        resize (tuple, opcional): Tamaño para redimensionar (ancho, alto)
        
    Returns:
        tuple: (imagen_procesada, base64_str)
    """
    try:
        if uploaded_file is None:
            return None, None
        
        # Leer imagen
        image = Image.open(uploaded_file)
        
        # Redimensionar si es necesario
        if resize:
            image = image.resize(resize)
        
        # Convertir a bytes
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        byte_img = buf.getvalue()
        
        # Convertir a base64
        base64_str = base64.b64encode(byte_img).decode()
        
        return image, base64_str
    except Exception as e:
        logger.error(f"Error procesando imagen: {str(e)}")
        return None, None

def guardar_imagen_temporal(image, prefix="ele_img"):
    """
    Guarda una imagen en un archivo temporal.
    
    Args:
        image (PIL.Image): Imagen a guardar
        prefix (str): Prefijo para el nombre del archivo
        
    Returns:
        str: Ruta al archivo temporal
    """
    try:
        if image is None:
            return None
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join(tempfile.gettempdir(), "textocorrector_ele")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generar nombre único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(temp_dir, filename)
        
        # Guardar imagen
        image.save(filepath)
        
        return filepath
    except Exception as e:
        logger.error(f"Error guardando imagen: {str(e)}")
        return None

def leer_archivo_texto(uploaded_file):
    """
    Lee un archivo de texto subido por el usuario.
    
    Args:
        uploaded_file (UploadedFile): Archivo subido desde streamlit
        
    Returns:
        str: Contenido del archivo
    """
    try:
        if uploaded_file is None:
            return ""
        
        # Leer como texto
        content = uploaded_file.read()
        
        # Detectar codificación
        try:
            # Intentar como UTF-8
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                # Intentar como Latin-1
                text = content.decode('latin-1')
            except UnicodeDecodeError:
                # Si todo falla, usar UTF-8 con manejo de errores
                text = content.decode('utf-8', errors='replace')
        
        return text
    except Exception as e:
        logger.error(f"Error leyendo archivo de texto: {str(e)}")
        return ""

def obtener_tipo_archivo(filename):
    """
    Determina el tipo de archivo basado en su extensión.
    
    Args:
        filename (str): Nombre del archivo
        
    Returns:
        str: Tipo de archivo (imagen, texto, desconocido)
    """
    try:
        if not filename:
            return "desconocido"
        
        # Obtener extensión
        ext = Path(filename).suffix.lower()
        
        # Determinar tipo
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            return "imagen"
        elif ext in ['.txt', '.md', '.rtf', '.csv', '.json']:
            return "texto"
        elif ext in ['.pdf']:
            return "pdf"
        elif ext in ['.doc', '.docx']:
            return "word"
        else:
            return "desconocido"
    except Exception as e:
        logger.error(f"Error determinando tipo de archivo: {str(e)}")
        return "desconocido"

def get_base64_from_file(file_path):
    """
    Convierte un archivo a base64.
    
    Args:
        file_path (str): Ruta al archivo
        
    Returns:
        str: String base64 del archivo
    """
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            return base64.b64encode(data).decode()
    except Exception as e:
        logger.error(f"Error convirtiendo archivo a base64: {str(e)}")
        return None

def get_file_download_link(bin_data, filename, text="Descargar archivo"):
    """
    Genera un enlace HTML para descargar datos binarios como archivo.
    
    Args:
        bin_data (bytes): Datos binarios
        filename (str): Nombre del archivo de descarga
        text (str): Texto del enlace
        
    Returns:
        str: HTML con el enlace de descarga
    """
    try:
        b64 = base64.b64encode(bin_data).decode()
        extension = Path(filename).suffix.lower()
        
        # Determinar MIME type
        mime_types = {
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.json': 'application/json',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png'
        }
        
        mime = mime_types.get(extension, 'application/octet-stream')
        
        href = f'<a href="data:{mime};base64,{b64}" download="{filename}">{text}</a>'
        return href
    except Exception as e:
        logger.error(f"Error generando enlace de descarga: {str(e)}")
        return "Error generando enlace de descarga."

def mostrar_upload_area(tipo, key, help_text=None, accept_multiple_files=False):
    """
    Muestra un área para subir archivos con estilo personalizado.
    
    Args:
        tipo (str): Tipo de archivos a aceptar (texto, imagen, cualquiera)
        key (str): Clave única para el componente
        help_text (str, opcional): Texto de ayuda
        accept_multiple_files (bool): Si acepta múltiples archivos
        
    Returns:
        UploadedFile: Archivo(s) subido(s)
    """
    try:
        # Configurar tipos MIME aceptados
        if tipo == "imagen":
            accept_types = ["image/jpeg", "image/png", "image/gif", "image/bmp"]
            file_types = [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
            mensaje = "Arrastra o sube una imagen"
        elif tipo == "texto":
            accept_types = ["text/plain", "text/markdown", "text/csv"]
            file_types = [".txt", ".md", ".csv"]
            mensaje = "Arrastra o sube un archivo de texto"
        elif tipo == "document":
            accept_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
            file_types = [".pdf", ".docx"]
            mensaje = "Arrastra o sube un documento"
        else:
            accept_types = None
            file_types = None
            mensaje = "Arrastra o sube un archivo"
        
        # Texto de ayuda por defecto si no se proporciona
        if help_text is None:
            if tipo == "imagen":
                help_text = "Formatos aceptados: JPG, PNG, GIF, BMP"
            elif tipo == "texto":
                help_text = "Formatos aceptados: TXT, MD, CSV"
            elif tipo == "document":
                help_text = "Formatos aceptados: PDF, DOCX"
            else:
                help_text = "Sube un archivo"
        
        # Mostrar área de upload con estilo personalizado
        uploaded_file = st.file_uploader(
            mensaje,
            type=file_types,
            accept_multiple_files=accept_multiple_files,
            key=key,
            help=help_text
        )
        
        return uploaded_file
    except Exception as e:
        logger.error(f"Error mostrando área de upload: {str(e)}")
        # En caso de error, mostrar el uploader estándar
        return st.file_uploader(
            "Sube un archivo",
            key=f"{key}_fallback",
            accept_multiple_files=accept_multiple_files
        )

def limpiar_archivos_temporales(dias=1):
    """
    Limpia archivos temporales más antiguos que cierto número de días.
    
    Args:
        dias (int): Número de días de antigüedad para eliminar
        
    Returns:
        int: Número de archivos eliminados
    """
    try:
        # Directorio temporal de la aplicación
        temp_dir = os.path.join(tempfile.gettempdir(), "textocorrector_ele")
        
        if not os.path.exists(temp_dir):
            return 0
        
        # Fecha límite
        limite = datetime.now().timestamp() - (dias * 24 * 60 * 60)
        
        # Contar archivos eliminados
        eliminados = 0
        
        # Recorrer archivos y eliminar antiguos
        for filename in os.listdir(temp_dir):
            filepath = os.path.join(temp_dir, filename)
            
            # Verificar si es un archivo
            if os.path.isfile(filepath):
                # Verificar fecha de modificación
                if os.path.getmtime(filepath) < limite:
                    os.remove(filepath)
                    eliminados += 1
        
        return eliminados
    except Exception as e:
        logger.error(f"Error limpiando archivos temporales: {str(e)}")
        return 0

def crear_archivo_zip(files, output_filename="archivos_ele.zip"):
    """
    Crea un archivo ZIP con los archivos proporcionados.
    
    Args:
        files (dict): Diccionario {nombre_archivo: contenido_bytes}
        output_filename (str): Nombre del archivo ZIP resultante
        
    Returns:
        bytes: Contenido del archivo ZIP
    """
    try:
        import zipfile
        
        # Crear archivo ZIP en memoria
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in files.items():
                zip_file.writestr(filename, content)
        
        # Posicionar puntero al inicio del buffer
        zip_buffer.seek(0)
        
        return zip_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error creando archivo ZIP: {str(e)}")
        return None

def get_app_file_path(relative_path):
    """
    Obtiene la ruta absoluta a un archivo de la aplicación.
    
    Args:
        relative_path (str): Ruta relativa desde la raíz de la aplicación
        
    Returns:
        str: Ruta absoluta
    """
    try:
        # Obtener directorio base de la aplicación usando pathlib
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent
        return str(base_dir / relative_path)
    except Exception as e:
        logger.error(f"Error obteniendo ruta de archivo: {str(e)}")
        return relative_path
    