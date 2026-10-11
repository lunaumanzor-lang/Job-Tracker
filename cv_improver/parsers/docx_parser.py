"""
Extractor de texto para archivos DOCX utilizando python-docx.
Procesa párrafos y contenido dentro de tablas.
"""

import io
import logging
from docx import Document
from .base import CorruptFileError, EmptyFileError

logger = logging.getLogger(__name__)


def extract_text_from_docx(file_bytes: bytes, filename: str = "documento.docx") -> str:
    """
    Extrae texto plano estructurado de un archivo DOCX en memoria.
    
    Lanza:
    - EmptyFileError: Si el archivo está vacío o no contiene texto en párrafos ni tablas.
    - CorruptFileError: Si el archivo no es un zip/docx válido o está dañado.
    """
    if not file_bytes:
        raise EmptyFileError(f"El archivo DOCX '{filename}' está vacío.")

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        logger.error(f"Error abriendo DOCX '{filename}': {e}", exc_info=True)
        raise CorruptFileError(f"No se pudo procesar el archivo DOCX '{filename}'. Es posible que esté corrupto: {e}")

    extracted_lines = []

    # 1. Extraer texto de párrafos
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            extracted_lines.append(text)

    # 2. Extraer texto de celdas de tablas (comunes en CVs maquetados en Word)
    for table in doc.tables:
        for row in table.rows:
            row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_texts:
                # Evitar duplicados consecutivos comunes en celdas unidas
                deduped = []
                for t in row_texts:
                    if not deduped or deduped[-1] != t:
                        deduped.append(t)
                extracted_lines.append(" | ".join(deduped))

    full_text = "\n\n".join(extracted_lines).strip()

    if not full_text:
        raise EmptyFileError(f"El archivo DOCX '{filename}' no contiene texto visible en párrafos ni tablas.")

    return full_text
