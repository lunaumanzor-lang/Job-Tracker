"""
Pruebas funcionales y unitarias para FASE 3: Renderer y Plantillas (PDF y DOCX).
"""

import io
import pytest
from docx import Document
import pypdf
from cv_improver.schema import (
    ResumeSchema,
    ContactInfo,
    ExperienceItem,
    BulletItem,
    EducationItem,
    SkillCategory,
    LanguageItem,
    CertificationItem
)
from cv_improver.renderer import (
    render_cv_to_html,
    render_cv_to_pdf,
    render_cv_to_docx
)


@pytest.fixture
def sample_resume():
    return ResumeSchema(
        contact=ContactInfo(
            name="Sofia Martinez",
            email="sofia.martinez@example.com",
            phone="+52 55 9876 5432",
            location="Guadalajara, México",
            linkedin="https://linkedin.com/in/sofiamartinez",
            github="https://github.com/sofiamartinez"
        ),
        summary="Ingeniera DevOps con 5 años de experiencia liderando automatización y despliegues en Kubernetes.",
        summary_improved="Ingeniera DevOps Senior especializada en observabilidad y despliegues continuos para arquitecturas Kubernetes de alta resiliencia.",
        experience=[
            ExperienceItem(
                company="CloudWorks Corp",
                position="DevOps Lead",
                start_date="2022",
                end_date="Presente",
                current=True,
                bullets=[
                    BulletItem(
                        original="Responsable de los clusters de Kubernetes",
                        improved="Diseñé y orquesté la infraestructura multiclúster de Kubernetes garantizando 99.99% de disponibilidad.",
                        suggestion=None
                    ),
                    BulletItem(
                        original="Hice automatización de CI/CD",
                        improved="Implementé pipelines declarativos de GitLab CI reduciendo los ciclos de despliegue en un 40%.",
                        suggestion=None
                    )
                ]
            )
        ],
        education=[
            EducationItem(
                institution="Tecnológico de Monterrey",
                degree="Ingeniería en Tecnologías Computacionales",
                start_date="2016",
                end_date="2020"
            )
        ],
        skills=[
            SkillCategory(
                category="Cloud & DevOps",
                skills=["AWS", "Kubernetes", "Terraform", "Docker", "GitLab CI"]
            )
        ],
        languages=[
            LanguageItem(language="Español", proficiency="Nativo"),
            LanguageItem(language="Inglés", proficiency="C1 Avanzado")
        ],
        certifications=[
            CertificationItem(
                name="CKA: Certified Kubernetes Administrator",
                issuer="Linux Foundation",
                date="2023"
            )
        ]
    )


def test_render_html_templates(sample_resume):
    for tpl in ["clasica", "moderna", "minimalista", "zafiro", "vanguardia"]:
        html = render_cv_to_html(sample_resume, template_name=tpl, accent_color="#0D9488")
        assert "Sofia Martinez" in html
        assert "sofia.martinez@example.com" in html
        assert "CloudWorks Corp" in html
        assert "99.99%" in html
        assert "#0D9488" in html


def test_render_pdf_compilation(sample_resume):
    for tpl in ["clasica", "moderna", "minimalista", "zafiro", "vanguardia"]:
        pdf_bytes, page_count, engine = render_cv_to_pdf(
            sample_resume,
            template_name=tpl,
            accent_color="#1E3A8A"
        )
        assert len(pdf_bytes) > 1000
        assert any(e in engine for e in ["Chromium", "Edge", "WeasyPrint", "xhtml2pdf"])

        # Validar que el PDF tiene texto seleccionable (requisito ATS)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        first_page_text = reader.pages[0].extract_text()
        assert "Sofia Martinez" in first_page_text or "CloudWorks" in first_page_text


def test_render_docx_compilation(sample_resume):
    docx_bytes = render_cv_to_docx(sample_resume, accent_hex="#1E3A8A")
    assert len(docx_bytes) > 1000

    doc = Document(io.BytesIO(docx_bytes))
    all_text = " ".join([p.text for p in doc.paragraphs])
    assert "Sofia Martinez" in all_text
    assert "CloudWorks Corp" in all_text
    assert "Kubernetes" in all_text
