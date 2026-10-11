"""
Validación básica y excepciones personalizadas para la subida de archivos de CV.
"""

import os
from typing import Tuple

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class FileValidationError(Exception):
    """Excepción base para errores de validación de archivos."""
    pass


class EmptyFileError(FileValidationError):
    """El archivo subido no contiene bytes o su contenido de texto está vacío."""
    pass


class FileTooLargeError(FileValidationError):
    """El archivo supera el tamaño máximo permitido (5 MB)."""
    pass


class UnsupportedFileTypeError(FileValidationError):
    """El tipo o formato del archivo no está soportado (solo PDF, DOCX, TXT)."""
    pass


class ScannedPDFError(FileValidationError):
    """El PDF es una imagen escaneada o no contiene texto digital seleccionable."""
    pass


class CorruptFileError(FileValidationError):
    """El archivo está corrupto o no se puede leer con el parser correspondiente."""
    pass


def validate_uploaded_file(file_bytes: bytes, filename: str, max_size_mb: float = 5.0) -> str:
    """
    Valida el archivo subido antes del procesamiento:
    1. Verifica que no esté vacío.
    2. Comprueba que no supere el tamaño máximo (por defecto 5 MB).
    3. Valida la extensión permitida (.pdf, .docx, .txt).
    4. Valida firmas mágicas para prevenir extensiones falseadas.

    Retorna la extensión normalizada sin punto ('pdf', 'docx', 'txt').
    """
    if not file_bytes or len(file_bytes) == 0:
        raise EmptyFileError(f"El archivo '{filename}' está vacío (0 bytes).")

    max_bytes = int(max_size_mb * 1024 * 1024)
    if len(file_bytes) > max_bytes:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise FileTooLargeError(
            f"El archivo '{filename}' pesa {size_mb:.2f} MB, lo que supera el límite máximo permitido de {max_size_mb:.1f} MB."
        )

    _, ext = os.path.splitext(filename or "")
    clean_ext = ext.lower().strip()

    if clean_ext not in [".pdf", ".docx", ".txt"]:
        raise UnsupportedFileTypeError(
            f"El formato '{clean_ext or 'desconocido'}' no está soportado. Formatos admitidos: .pdf, .docx, .txt."
        )

    # Verificación de cabeceras mágicas para evitar archivos corruptos o disfrazados
    if clean_ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            raise CorruptFileError(f"El archivo '{filename}' no tiene una cabecera válida de PDF.")
    elif clean_ext == ".docx":
        # Los archivos DOCX son contenedores ZIP que inician con 'PK\x03\x04'
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise CorruptFileError(f"El archivo '{filename}' no es un documento de Word (.docx) válido o está corrupto.")

    return clean_ext.lstrip(".")
