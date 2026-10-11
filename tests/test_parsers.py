"""
Pruebas funcionales y unitarias para FASE 1: Parsers y Esquema Pydantic.
"""

import os
import pytest
from cv_improver.parsers import (
    validate_uploaded_file,
    extract_text_from_file,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
    parse_resume_to_schema,
    EmptyFileError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    ScannedPDFError,
    CorruptFileError
)
from cv_improver.schema import (
    ResumeSchema,
    ContactInfo,
    ExperienceItem,
    BulletItem
)
from cv_improver.enhancer.provider_base import LLMProvider

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class MockLLMProvider(LLMProvider):
    """Proveedor mock para pruebas unitarias sin llamadas a APIs externas."""

    def __init__(self, json_to_return: dict):
        self.json_to_return = json_to_return

    def generate_text(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=4096) -> str:
        import json
        return json.dumps(self.json_to_return)


@pytest.fixture
def txt_bytes():
    with open(os.path.join(FIXTURES_DIR, "sample_cv.txt"), "rb") as f:
        return f.read()


@pytest.fixture
def docx_bytes():
    with open(os.path.join(FIXTURES_DIR, "sample_cv.docx"), "rb") as f:
        return f.read()


@pytest.fixture
def pdf_bytes():
    with open(os.path.join(FIXTURES_DIR, "sample_cv.pdf"), "rb") as f:
        return f.read()


@pytest.fixture
def scanned_pdf_bytes():
    with open(os.path.join(FIXTURES_DIR, "scanned_blank_cv.pdf"), "rb") as f:
        return f.read()


# ------------------------------------------------------------------------------
# 1. PRUEBAS DE VALIDACIÓN DE ARCHIVOS
# ------------------------------------------------------------------------------
def test_validation_empty_file():
    with pytest.raises(EmptyFileError):
        validate_uploaded_file(b"", "cv.pdf")


def test_validation_file_too_large():
    huge_bytes = b"%PDF-" + b"0" * (6 * 1024 * 1024)
    with pytest.raises(FileTooLargeError):
        validate_uploaded_file(huge_bytes, "cv.pdf", max_size_mb=5.0)


def test_validation_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        validate_uploaded_file(b"contenido", "cv.exe")


def test_validation_corrupt_pdf_magic_bytes():
    with pytest.raises(CorruptFileError):
        validate_uploaded_file(b"Esto no es un pdf", "cv.pdf")


def test_validation_corrupt_docx_magic_bytes():
    with pytest.raises(CorruptFileError):
        validate_uploaded_file(b"Esto no es un docx zip", "cv.docx")


# ------------------------------------------------------------------------------
# 2. PRUEBAS DE EXTRACCIÓN DE TEXTO
# ------------------------------------------------------------------------------
def test_extract_txt(txt_bytes):
    text = extract_text_from_txt(txt_bytes, "sample_cv.txt")
    assert "Juan Perez" in text
    assert "juan.perez@example.com" in text
    assert "Python" in text


def test_extract_docx(docx_bytes):
    text = extract_text_from_docx(docx_bytes, "sample_cv.docx")
    assert "Juan Perez" in text
    assert "Tech Solutions Inc." in text


def test_extract_pdf(pdf_bytes):
    text = extract_text_from_pdf(pdf_bytes, "sample_cv.pdf")
    assert "Juan Perez" in text
    assert "Tech Solutions" in text or "Python" in text


def test_extract_scanned_pdf(scanned_pdf_bytes):
    with pytest.raises(ScannedPDFError):
        extract_text_from_pdf(scanned_pdf_bytes, "scanned_blank_cv.pdf")


def test_extract_orchestrator(txt_bytes, docx_bytes, pdf_bytes):
    t1 = extract_text_from_file(txt_bytes, "sample_cv.txt")
    t2 = extract_text_from_file(docx_bytes, "sample_cv.docx")
    t3 = extract_text_from_file(pdf_bytes, "sample_cv.pdf")
    assert len(t1) > 100
    assert len(t2) > 100
    assert len(t3) > 100


# ------------------------------------------------------------------------------
# 3. PRUEBAS DE ESQUEMA PYDANTIC Y PARSEO ESTRUCTURADO
# ------------------------------------------------------------------------------
def test_resume_schema_manual_instantiation():
    resume = ResumeSchema(
        contact=ContactInfo(
            name="Ana Gomez",
            email="ana@example.com",
            phone="+34 600 000 000",
            location="Madrid, España"
        ),
        summary="Desarrolladora Full Stack con experiencia en React y Python.",
        experience=[
            ExperienceItem(
                company="Startup X",
                position="Full Stack Developer",
                start_date="2022",
                end_date="Presente",
                current=True,
                bullets=[
                    BulletItem(
                        original="Desarrollo de nuevas funcionalidades en la plataforma.",
                        improved=None,
                        suggestion=None
                    )
                ]
            )
        ]
    )
    assert resume.contact.name == "Ana Gomez"
    assert len(resume.experience) == 1
    assert len(resume.experience[0].bullets) == 1


def test_parse_resume_to_schema_with_mock_llm():
    mock_payload = {
        "contact": {
            "name": "Juan Perez",
            "email": "juan.perez@example.com",
            "phone": "+52 55 1234 5678",
            "location": "Ciudad de México",
            "linkedin": "https://linkedin.com/in/juanperez",
            "github": "https://github.com/juanperez",
            "portfolio": None
        },
        "summary": "Ingeniero de Software Senior con más de 6 años de experiencia.",
        "experience": [
            {
                "company": "Tech Solutions Inc.",
                "position": "Desarrollador Backend Senior",
                "start_date": "2021",
                "end_date": "Presente",
                "current": True,
                "location": None,
                "bullets": [
                    {
                        "original": "Lideré la migración de microservicios en Python reduciendo la latencia de respuesta en un 35%.",
                        "improved": None,
                        "suggestion": None
                    }
                ]
            }
        ],
        "education": [
            {
                "institution": "UNAM",
                "degree": "Licenciatura en Ciencias de la Computación",
                "field_of_study": "Computación",
                "start_date": "2014",
                "end_date": "2018",
                "grade_or_details": None
            }
        ],
        "skills": [
            {
                "category": "Lenguajes",
                "skills": ["Python", "TypeScript", "SQL"]
            }
        ],
        "languages": [
            {
                "language": "Español",
                "proficiency": "Nativo"
            }
        ],
        "certifications": [
            {
                "name": "AWS Certified Solutions Architect",
                "issuer": "Amazon Web Services",
                "date": "2023",
                "credential_url": None
            }
        ]
    }

    mock_provider = MockLLMProvider(mock_payload)
    parsed = parse_resume_to_schema("Texto crudo del CV...", provider=mock_provider)

    assert isinstance(parsed, ResumeSchema)
    assert parsed.contact.name == "Juan Perez"
    assert parsed.contact.email == "juan.perez@example.com"
    assert len(parsed.experience) == 1
    assert parsed.experience[0].company == "Tech Solutions Inc."
    assert len(parsed.experience[0].bullets) == 1
    assert "35%" in parsed.experience[0].bullets[0].original
    assert len(parsed.skills) == 1
    assert parsed.skills[0].skills == ["Python", "TypeScript", "SQL"]


def test_parse_resume_to_schema_heuristic_fallback(txt_bytes):
    raw_text = extract_text_from_txt(txt_bytes)
    # Parseo sin proveedor (ejecuta el fallback determinista)
    parsed = parse_resume_to_schema(raw_text, provider=None)
    assert isinstance(parsed, ResumeSchema)
    assert "Juan Perez" in parsed.contact.name
    assert parsed.contact.email == "juan.perez@example.com"
    assert len(parsed.experience) > 0
