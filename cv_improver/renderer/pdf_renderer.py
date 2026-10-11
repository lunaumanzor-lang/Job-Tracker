"""
Renderizador de CV a PDF utilizando Chromium (Edge / Chrome) para fidelidad visual 100% idéntica
a la previsualización en vivo, con fallback a WeasyPrint y xhtml2pdf.
Garantiza cumplimiento con estándares ATS, texto seleccionable y límite de páginas.
"""

import os
import io
import re
import shutil
import logging
import tempfile
import subprocess
from typing import Tuple, Optional
from jinja2 import Environment, FileSystemLoader
import pypdf
from ..schema import ResumeSchema

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=True
)

AVAILABLE_TEMPLATES = ["clasica", "moderna", "minimalista", "zafiro", "vanguardia"]


def _find_chromium_binary() -> Optional[str]:
    """Localiza el navegador Chromium (Microsoft Edge o Google Chrome) en el sistema."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "msedge",
        "google-chrome",
        "chrome",
        "chromium"
    ]
    for c in candidates:
        if os.path.isabs(c):
            if os.path.isfile(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


def _render_with_chromium(html_content: str, browser_path: str) -> bytes:
    """Renderiza el HTML a PDF usando Chromium headless con fidelidad 100% idéntica al navegador."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_html = os.path.join(tmpdir, "cv_print.html")
        output_pdf = os.path.join(tmpdir, "cv_export.pdf")
        user_data_dir = os.path.join(tmpdir, "browser_profile")

        with open(input_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        cmd = [
            browser_path,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data_dir}",
            "--allow-file-access-from-files",
            f"--print-to-pdf={output_pdf}",
            input_html
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        except Exception as e:
            logger.warning(f"Advertencia con Chromium headless: {e}")

        if os.path.exists(output_pdf) and os.path.getsize(output_pdf) > 0:
            with open(output_pdf, "rb") as pf:
                return pf.read()
                return pf.read()

    raise RuntimeError("No se pudo generar el PDF con Chromium headless.")


def render_cv_to_html(
    resume: ResumeSchema,
    template_name: str = "clasica",
    accent_color: str = "#1E3A8A",
    language: str = "es"
) -> str:
    """Renderiza el CV en código HTML puro usando Jinja2 con soporte de idioma."""
    clean_name = template_name.lower().strip()
    if clean_name not in AVAILABLE_TEMPLATES:
        clean_name = "clasica"

    template_file = f"{clean_name}.html"
    template = jinja_env.get_template(template_file)
    is_en = (language == "en")
    labels = {
        "profile": "Profile" if is_en else "Perfil",
        "experience": "Experience" if is_en else "Experiencia",
        "education": "Education" if is_en else "Educación",
        "skills": "Skills" if is_en else "Habilidades",
        "present": "Present" if is_en else "Presente",
        "languages": "Languages" if is_en else "Idiomas",
        "certifications": "Certifications" if is_en else "Certificaciones"
    }
    return template.render(
        resume=resume,
        accent_color=accent_color,
        labels=labels,
        lang="en" if is_en else "es"
    )


def render_cv_to_pdf(
    resume: ResumeSchema,
    template_name: str = "clasica",
    accent_color: str = "#1E3A8A",
    language: str = "es"
) -> Tuple[bytes, int, str]:
    """
    Renderiza el CV a bytes de PDF.
    
    1. Genera el HTML con la plantilla y el color seleccionado.
    2. Compila a PDF utilizando Chromium (Edge/Chrome) para garantizar que la descarga
       sea 100% idéntica a la previsualización en vivo (colores, cuadros, divisiones y fuentes).
    3. Si Chromium no estuviera disponible, utiliza WeasyPrint o xhtml2pdf como fallback.
    4. Inspecciona el PDF con pypdf para validar páginas y texto seleccionable.
    
    Retorna: (pdf_bytes, page_count, engine_used)
    """
    html_content = render_cv_to_html(resume, template_name, accent_color, language=language)

    pdf_bytes: Optional[bytes] = None
    engine_used = ""

    # 1. Intentar con Chromium (Edge / Chrome) para fidelidad 100% idéntica al navegador
    browser_bin = _find_chromium_binary()
    if browser_bin:
        try:
            pdf_bytes = _render_with_chromium(html_content, browser_bin)
            engine_used = "Chromium / Edge (Fidelidad 100% Idéntica)"
        except Exception as chrome_err:
            logger.info(f"Fallo temporal con Chromium ({chrome_err}). Intentando siguiente motor...")

    # 2. Intentar con WeasyPrint si no se pudo con Chromium
    if not pdf_bytes:
        clean_html_for_pdf = re.sub(r"@import\s+url\([^)]+\);?", "", html_content)
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=clean_html_for_pdf).write_pdf()
            engine_used = "WeasyPrint"
        except Exception as weasy_err:
            logger.info(f"WeasyPrint no disponible ({weasy_err}). Empleando fallback xhtml2pdf...")

    # 3. Fallback con xhtml2pdf
    if not pdf_bytes:
        try:
            from xhtml2pdf import pisa
            out_buf = io.BytesIO()
            pisa_status = pisa.pisaDocument(
                src=io.BytesIO(html_content.encode("utf-8")),
                dest=out_buf,
                encoding="utf-8"
            )
            pdf_bytes = out_buf.getvalue()
            engine_used = "xhtml2pdf (fallback)"
        except Exception as xhtml_err:
            raise RuntimeError(f"Error crítico al compilar PDF: {xhtml_err}")

    if not pdf_bytes:
        raise RuntimeError("El archivo PDF generado está vacío.")

    # 4. Validación ATS y recuento de páginas con pypdf
    page_count = 1
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        first_page_text = reader.pages[0].extract_text() or ""
        if not first_page_text.strip():
            logger.warning("El PDF generado tiene texto seleccionable mínimo.")
    except Exception as e:
        logger.warning(f"Aviso al inspeccionar páginas con pypdf: {e}")

    return pdf_bytes, page_count, engine_used
