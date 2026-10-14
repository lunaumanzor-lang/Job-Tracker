"""
Extractor de texto para archivos PDF usando pdfplumber con soporte de OCR inteligente (Gemini Vision).
Detecta automáticamente documentos escaneados o páginas aplanadas como imágenes (ej. Canva).
"""

import io
import os
import logging
from typing import Optional
import pdfplumber
from .base import ScannedPDFError, CorruptFileError, EmptyFileError
from ai_client import get_ai_api_key, generate_content_with_retry

logger = logging.getLogger(__name__)

# Mínimo de caracteres legibles esperados en un CV para descartar escaneos vacíos
MIN_READABLE_CHARS = 40


def _try_ocr_page_image(page, page_num: int) -> Optional[str]:
    """
    Si una página del PDF no contiene texto seleccionable (ej. Canva o diseño exportado como imagen),
    intenta extraer el contenido usando Gemini Vision OCR.
    """
    # Solo procesar OCR en las primeras 2 páginas (los CVs estándar no tienen más de 2 páginas
    # y evita procesar páginas vacías/márgenes de Canva con imágenes en blanco)
    if page_num > 2:
        return None

    images = getattr(page, "images", [])
    if not images:
        return None

    # Verificar si al menos una imagen tiene resolución o peso significativo
    has_large_image = any(img.get("width", 0) > 100 and img.get("height", 0) > 100 for img in images)
    if not has_large_image:
        return None

    try:
        api_key = get_ai_api_key("gemini")
        if not api_key:
            return None

        # Renderizar la página a imagen PIL y optimizar dimensiones para transmisión rápida
        page_img = page.to_image(resolution=150).original
        page_img.thumbnail((1024, 1024))

        prompt_ocr = (
            "Extrae todo el texto de esta página de currículum exactamente como aparece. "
            "Conserva íntegramente nombres, correos, enlaces, experiencia laboral, empresas, cargos, fechas y viñetas (bullets). "
            "Responde ÚNICAMENTE con el texto extraído sin añadir introducciones ni comentarios."
        )

        resp = generate_content_with_retry(
            contents=[prompt_ocr, page_img],
            candidate_models=["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"],
            api_key=api_key,
            request_options={"timeout": 45}
        )
        if resp and resp.text and len(resp.text.strip()) > 30:
            logger.info(f"OCR exitoso en página {page_num} ({len(resp.text)} caracteres).")
            return resp.text.strip()
    except Exception as e:
        logger.warning(f"No se pudo realizar OCR en página {page_num}: {e}")
    return None


def extract_text_from_pdf(file_bytes: bytes, filename: str = "documento.pdf") -> str:
    """
    Extrae el texto seleccionable de un archivo PDF utilizando pdfplumber.
    Si una página no tiene capa de texto pero contiene imágenes (ej. exportaciones gráficas de Canva),
    aplica OCR visual automáticamente con Gemini Vision.
    
    Lanza:
    - CorruptFileError: Si el PDF está dañado y no puede abrirse.
    - ScannedPDFError: Si el PDF es un escaneo/imagen sin capa de texto seleccionable y sin API key de OCR.
    - EmptyFileError: Si no contiene páginas o texto utilizable.
    """
    if not file_bytes:
        raise EmptyFileError(f"El archivo PDF '{filename}' está vacío.")

    extracted_pages = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                raise EmptyFileError(f"El archivo PDF '{filename}' no contiene páginas legibles.")

            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    # 1. Preferir extract_text() estándar para flujo de lectura natural
                    text = page.extract_text() or page.extract_text(layout=True) or ""

                    # 2. Si la página tiene poco o nada de texto pero contiene imágenes (ej. Canva / diseño aplanado),
                    # recurrir al OCR visual
                    if len(text.strip()) < 40 and getattr(page, "images", None):
                        ocr_text = _try_ocr_page_image(page, page_num)
                        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text

                    if text.strip():
                        extracted_pages.append(text.strip())
                except Exception as page_err:
                    logger.warning(f"Aviso al extraer texto de la página {page_num} en '{filename}': {page_err}")

    except (ScannedPDFError, EmptyFileError):
        raise
    except Exception as e:
        logger.error(f"Error al procesar el archivo PDF '{filename}': {e}", exc_info=True)
        raise CorruptFileError(f"No se pudo leer el archivo PDF '{filename}'. Es posible que esté dañado: {e}")

    full_text = "\n\n".join(extracted_pages).strip()

    # Si la suma de caracteres de todas las páginas es casi nula, es un escaneo sin OCR disponible
    if len(full_text) < MIN_READABLE_CHARS:
        raise ScannedPDFError(
            f"El archivo PDF '{filename}' no contiene texto seleccionable (solo {len(full_text)} caracteres detectados). "
            "Parece ser un documento escaneado o una imagen. Por favor, sube un PDF generado digitalmente, o en formato DOCX o TXT."
        )

    return full_text
