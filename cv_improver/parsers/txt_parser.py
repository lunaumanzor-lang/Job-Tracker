"""
Extractor de texto para archivos TXT con detección automática de codificación.
"""

import logging
from charset_normalizer import from_bytes
from .base import EmptyFileError, CorruptFileError

logger = logging.getLogger(__name__)


def extract_text_from_txt(file_bytes: bytes, filename: str = "documento.txt") -> str:
    """
    Decodifica y extrae texto de un archivo TXT detectando su codificación de caracteres.
    
    Lanza:
    - EmptyFileError: Si el archivo está vacío o solo contiene espacios en blanco.
    - CorruptFileError: Si no es posible decodificar el contenido.
    """
    if not file_bytes or len(file_bytes.strip()) == 0:
        raise EmptyFileError(f"El archivo TXT '{filename}' está vacío.")

    # 1. Intentar detección con charset_normalizer
    try:
        results = from_bytes(file_bytes)
        best_match = results.best()
        if best_match and best_match.encoding:
            text = str(best_match).strip()
            if text:
                return text
    except Exception as e:
        logger.warning(f"Aviso al detectar codificación con charset-normalizer en '{filename}': {e}")

    # 2. Estrategia de fallback con codificaciones comunes
    encodings_to_try = ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]
    for enc in encodings_to_try:
        try:
            decoded = file_bytes.decode(enc).strip()
            if decoded:
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue

    raise CorruptFileError(f"No fue posible determinar la codificación de texto válida para el archivo '{filename}'.")
