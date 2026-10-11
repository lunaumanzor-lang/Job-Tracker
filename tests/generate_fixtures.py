# Script para generar fixtures de prueba
import os
import io
from docx import Document
import pypdf

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
os.makedirs(FIXTURES_DIR, exist_ok=True)

SAMPLE_TEXT = """Juan Perez
juan.perez@example.com | +52 55 1234 5678 | Ciudad de México
https://linkedin.com/in/juanperez | https://github.com/juanperez

RESUMEN PROFESIONAL
Ingeniero de Software Senior con más de 6 años de experiencia desarrollando aplicaciones web escalables en Python, TypeScript y arquitectura en la nube con AWS.

EXPERIENCIA LABORAL
Tech Solutions Inc. | Desarrollador Backend Senior | 2021 - Presente
- Lideré la migración de microservicios en Python reduciendo la latencia de respuesta en un 35%.
- Diseñé pipelines de CI/CD automatizados usando GitHub Actions y Terraform.
- Implementé autenticación OAuth2 y control de acceso basado en roles para 50,000 usuarios activos.

Innovate Soft | Desarrollador de Software | 2018 - 2021
- Desarrollé endpoints RESTful con Django y PostgreSQL.
- Colaboré con el equipo de frontend para integrar interfaces de usuario reactivas.

EDUCACIÓN
Universidad Nacional Autónoma de México | Licenciatura en Ciencias de la Computación | 2014 - 2018

HABILIDADES
Lenguajes: Python, SQL, TypeScript, Bash
Cloud & DevOps: AWS (EC2, S3, RDS), Docker, GitHub Actions, Terraform
Bases de Datos: PostgreSQL, Redis, SQLite

IDIOMAS
Español: Nativo
Inglés: C1 Avanzado

CERTIFICACIONES
AWS Certified Solutions Architect – Associate | Amazon Web Services | 2023
"""

# 1. Guardar TXT
with open(os.path.join(FIXTURES_DIR, "sample_cv.txt"), "w", encoding="utf-8") as f:
    f.write(SAMPLE_TEXT)

# 2. Guardar DOCX
doc = Document()
for line in SAMPLE_TEXT.splitlines():
    if line.strip():
        doc.add_paragraph(line)
doc.save(os.path.join(FIXTURES_DIR, "sample_cv.docx"))

# 3. Guardar PDF con texto
# Usamos reportlab o pypdfium o xhtml2pdf para compilar un PDF real con texto
from xhtml2pdf import pisa
pdf_bytes = io.BytesIO()
html_content = f"<html><body><pre>{SAMPLE_TEXT}</pre></body></html>"
pisa.pisaDocument(io.BytesIO(html_content.encode("utf-8")), pdf_bytes)
with open(os.path.join(FIXTURES_DIR, "sample_cv.pdf"), "wb") as f:
    f.write(pdf_bytes.getvalue())

# 4. Guardar PDF 'escaneado' / vacío de texto (solo una página en blanco sin texto)
writer = pypdf.PdfWriter()
writer.add_blank_page(width=612, height=792)
scanned_pdf_path = os.path.join(FIXTURES_DIR, "scanned_blank_cv.pdf")
with open(scanned_pdf_path, "wb") as f:
    writer.write(f)

print("Fixtures creadas exitosamente.")
