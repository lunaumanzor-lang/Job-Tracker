# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 5.1: Módulo de Extracción de Texto de Resumes (resume_parser.py)
# ==============================================================================

import io
import os
from typing import Union
from pypdf import PdfReader
import docx


def extract_text_from_pdf(file_source: Union[str, io.BytesIO]) -> str:
    """
    Extrae todo el texto plano de un archivo PDF usando la librería moderna pypdf.
    Itera sobre cada página extrayendo caracteres limpios con soporte Unicode.
    """
    reader = PdfReader(file_source)
    paginas_texto = []
    for num_pag, page in enumerate(reader.pages, start=1):
        texto_pagina = page.extract_text()
        if texto_pagina:
            paginas_texto.append(texto_pagina.strip())
    return "\n\n".join(paginas_texto)


def extract_text_from_docx(file_source: Union[str, io.BytesIO]) -> str:
    """
    Extrae el texto de un documento de Word (.docx) usando python-docx.
    Extrae tanto párrafos estándar como celdas de tablas estructuradas.
    """
    doc = docx.Document(file_source)
    lineas = []
    
    # 1. Párrafos
    for p in doc.paragraphs:
        if p.text.strip():
            lineas.append(p.text.strip())

    # 2. Tablas (muchos CVs usan tablas para listar skills o fechas)
    for table in doc.tables:
        for row in table.rows:
            celdas = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if celdas:
                # Unimos celdas no duplicadas de la misma fila
                lineas.append(" | ".join(dict.fromkeys(celdas)))

    return "\n".join(lineas)


def extract_text_from_txt(file_source: Union[str, io.BytesIO]) -> str:
    """
    Lee archivos de texto plano (.txt) soportando codificaciones comunes (UTF-8, Latin-1).
    """
    if isinstance(file_source, (str, os.PathLike)):
        with open(file_source, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    else:
        contenido_bytes = file_source.read() if hasattr(file_source, "read") else file_source.getvalue()
        try:
            return contenido_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return contenido_bytes.decode("latin-1", errors="replace")


def extract_resume_text(uploaded_file) -> str:
    """
    Función principal de extracción: Detecta automáticamente el tipo de archivo
    a partir de la extensión y utiliza el extractor correspondiente.
    
    Retorna:
        Un único string con todo el contenido del documento, listo para enviar al LLM.
    """
    nombre_archivo = getattr(uploaded_file, "name", str(uploaded_file)).lower()

    if nombre_archivo.endswith(".pdf"):
        # Si es un objeto de Streamlit, se puede pasar directamente como stream de bytes
        stream = io.BytesIO(uploaded_file.getvalue()) if hasattr(uploaded_file, "getvalue") else uploaded_file
        return extract_text_from_pdf(stream)

    elif nombre_archivo.endswith(".docx"):
        stream = io.BytesIO(uploaded_file.getvalue()) if hasattr(uploaded_file, "getvalue") else uploaded_file
        return extract_text_from_docx(stream)

    elif nombre_archivo.endswith(".txt"):
        return extract_text_from_txt(uploaded_file)

    else:
        raise ValueError(f"Formato no soportado: '{nombre_archivo}'. Por favor sube un archivo .pdf, .docx o .txt.")
