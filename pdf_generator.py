# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 5.6c: Generador de PDF ATS-Friendly con xhtml2pdf y Jinja2 (pdf_generator.py)
# ==============================================================================

import os
import io
from typing import Dict, List, Any, Optional, Tuple
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
import pypdf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Configurar entorno de Jinja2
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=True
)


def generate_resume_pdf(
    template_name: str = "moderno",
    accent_color: str = "#1B365D",
    user_profile: Optional[Dict[str, Any]] = None,
    user_skills: Optional[List[Dict[str, Any]]] = None,
    resume_bullets: Optional[List[Dict[str, Any]]] = None,
    language: str = "es"
) -> Tuple[Optional[bytes], str, Optional[str]]:
    """
    Renderiza el CV en formato HTML con Jinja2 y lo compila a un PDF ATS-friendly con xhtml2pdf.
    
    Verificación de calidad (defensa en profundidad):
    Antes de retornar el PDF, utiliza pypdf para inspeccionar el archivo generado y
    extraer texto real. Si el documento carece de texto seleccionable (ej. en blanco o rasterizado),
    informa el fallo inmediatamente.
    
    Retorna:
    - (pdf_bytes, texto_extraido, None) si la generación y verificación son exitosas.
    - (None, "", error_mensaje) si ocurrió algún problema.
    """
    user_profile = user_profile or {}
    user_skills = user_skills or []
    resume_bullets = resume_bullets or []

    # 1. Normalizar selección de template
    template_file = "template_moderno.html" if "modern" in template_name.lower() else "template_ejecutivo.html"

    # 2. Agrupar habilidades por categoría
    skills_by_category: Dict[str, List[str]] = {}
    for s in user_skills:
        cat = s.get("category", "General").strip()
        sk_name = s.get("skill_name", "").strip()
        if sk_name:
            skills_by_category.setdefault(cat, []).append(sk_name)

    # 3. Agrupar bullets por sección de experiencia
    bullets_by_section: Dict[str, List[Dict[str, Any]]] = {}
    for b in resume_bullets:
        sec = b.get("section", "Experiencia").strip()
        bullets_by_section.setdefault(sec, []).append(b)

    # 4. Etiquetas estándar según idioma (Requisito ATS: encabezados claros y estándar)
    if language == "en":
        labels = {
            "summary": "Professional Summary",
            "technologies": "Core Technologies",
            "experience": "Professional Experience"
        }
    else:
        labels = {
            "summary": "Resumen Profesional",
            "technologies": "Tecnologías y Habilidades Clave",
            "experience": "Experiencia Profesional"
        }

    # 5. Renderizar HTML con Jinja2
    try:
        template = jinja_env.get_template(template_file)
        rendered_html = template.render(
            profile=user_profile,
            skills_by_category=skills_by_category,
            bullets_by_section=bullets_by_section,
            accent_color=accent_color,
            labels=labels
        )
    except Exception as e:
        return None, "", f"Error renderizando template Jinja2: {e}"

    # 6. Compilar HTML a PDF con xhtml2pdf
    pdf_buffer = io.BytesIO()
    try:
        pisa_status = pisa.pisaDocument(
            src=io.BytesIO(rendered_html.encode("utf-8")),
            dest=pdf_buffer,
            encoding="utf-8"
        )
        if pisa_status.err:
            return None, "", f"xhtml2pdf reportó {pisa_status.err} error(es) durante la compilación."
    except Exception as e:
        return None, "", f"Error durante la conversión a PDF con xhtml2pdf: {e}"

    pdf_bytes = pdf_buffer.getvalue()
    if not pdf_bytes:
        return None, "", "El buffer de PDF resultante está vacío."

    # 7. Verificación Automática con pypdf (Simulación del comportamiento de un parser ATS)
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        num_paginas = len(reader.pages)
        if num_paginas == 0:
            return None, "", "El PDF generado no tiene páginas."

        texto_extraido = "".join([page.extract_text() or "" for page in reader.pages]).strip()

        # Un CV con datos reales siempre supera los 60 caracteres de texto puro
        if len(texto_extraido) < 50:
            return None, "", "Advertencia ATS: El PDF generado no contiene texto seleccionable suficiente o está vacío."

    except Exception as e:
        return None, "", f"Error en la verificación de legibilidad ATS con pypdf: {e}"

    return pdf_bytes, texto_extraido, None
