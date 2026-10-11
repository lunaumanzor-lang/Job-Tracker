"""
Submódulo de renderizado de CV en PDF y DOCX.
"""

from .pdf_renderer import render_cv_to_pdf, render_cv_to_html
from .docx_renderer import render_cv_to_docx

__all__ = [
    "render_cv_to_pdf",
    "render_cv_to_html",
    "render_cv_to_docx"
]
