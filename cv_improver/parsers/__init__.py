"""
Submódulo de extracción y parseo de CVs para PDF, DOCX y TXT.
"""

from .base import (
    FileValidationError,
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    ScannedPDFError,
    CorruptFileError,
    validate_uploaded_file
)
from .pdf_parser import extract_text_from_pdf
from .docx_parser import extract_text_from_docx
from .txt_parser import extract_text_from_txt
from .extractor import extract_text_from_file, parse_resume_to_schema, detect_resume_language

__all__ = [
    "FileValidationError",
    "EmptyFileError",
    "FileTooLargeError",
    "UnsupportedFileTypeError",
    "ScannedPDFError",
    "CorruptFileError",
    "validate_uploaded_file",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "extract_text_from_txt",
    "extract_text_from_file",
    "parse_resume_to_schema",
    "detect_resume_language"
]
