"""
Pruebas unitarias y funcionales para la adaptación de CV a vacantes específicas.
Cubre:
1. Una sola llamada a IA por adaptación.
2. Rechazo robusto de respuestas JSON inválidas o esquemas corruptos.
3. Marcado en código de líneas sospechosas (cifras o tecnologías inventadas).
4. Aislamiento estricto por usuario (multi-tenant RLS en base de datos).
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from ai_service import adapt_resume_to_job, _detect_suspicious_additions
from database import (
    save_tailored_cv_version,
    get_tailored_cv_versions,
    get_tailored_cv_version_by_id,
    delete_tailored_cv_version
)


# ------------------------------------------------------------------------------
# FIXTURES Y DATOS DE PRUEBA
# ------------------------------------------------------------------------------

@pytest.fixture
def sample_resume():
    return {
        "summary": "Desarrollador backend con 3 años de experiencia en Python y Django.",
        "skills": [
            {"category": "Backend", "skills": ["Python", "Django", "PostgreSQL"]}
        ],
        "experience": [
            {
                "company": "Tech Sol",
                "position": "Backend Developer",
                "bullets": [
                    {"original": "Mantenimiento de APIs internas y depuración de errores."}
                ]
            }
        ]
    }


@pytest.fixture
def sample_job_text():
    return """
    Buscamos un Ingeniero Backend Python para optimizar sistemas distribuidos.
    Requisitos: Python, APIs REST, bases de datos relacionales, trabajo en equipo.
    """


# ------------------------------------------------------------------------------
# 1. PRUEBA: UNA SOLA LLAMADA A IA POR ADAPTACIÓN
# ------------------------------------------------------------------------------

def test_single_ai_call_per_adaptation(sample_resume, sample_job_text):
    """
    Verifica que todo el proceso de adaptación de resumen y viñetas
    se ejecute en un único lote con exactamente una llamada a la IA.
    """
    mock_ai_response = MagicMock()
    mock_ai_response.text = json.dumps({
        "summary_adapted": "Desarrollador backend especializado en Python y diseño de APIs robustas.",
        "skills_highlighted": ["Python", "Django", "PostgreSQL"],
        "experiences": [
            {
                "experience_id": 0,
                "company": "Tech Sol",
                "position": "Backend Developer",
                "bullets": [
                    {
                        "original": "Mantenimiento de APIs internas y depuración de errores.",
                        "adapted": "Desarrollo y mantenimiento de APIs internas asegurando alta disponibilidad.",
                        "explanation": "Enfocado en estabilidad de servicios."
                    }
                ]
            }
        ]
    })

    with patch("ai_service.generate_content_with_retry", return_value=mock_ai_response) as mock_gen:
        result = adapt_resume_to_job(
            resume_data=sample_resume,
            job_text=sample_job_text,
            target_company="Empresa Demo",
            target_position="Backend Engineer",
            user_id="user-123"
        )

        # Debe llamarse a la IA exactamente UNA sola vez
        assert mock_gen.call_count == 1
        assert "summary_adapted" in result
        assert len(result["experiences"]) == 1
        assert len(result["experiences"][0]["bullets"]) == 1
        assert result["experiences"][0]["bullets"][0]["suspicious"] is False


# ------------------------------------------------------------------------------
# 2. PRUEBA: RECHAZO DE JSON INVÁLIDO O ESQUEMA CORRUPTO
# ------------------------------------------------------------------------------

def test_rejection_of_invalid_json(sample_resume, sample_job_text):
    """Verifica que el servicio rechace texto plano que no contenga JSON válido."""
    mock_ai_response = MagicMock()
    mock_ai_response.text = "Lo siento, aquí tienes una sugerencia pero no en JSON: Cambia el resumen..."

    with patch("ai_service.generate_content_with_retry", return_value=mock_ai_response):
        with pytest.raises(ValueError, match="no contiene una estructura JSON válida"):
            adapt_resume_to_job(sample_resume, sample_job_text)


def test_rejection_of_missing_schema_keys(sample_resume, sample_job_text):
    """Verifica que se rechace una respuesta JSON que carezca de campos obligatorios del esquema."""
    # Falta 'experiences'
    mock_ai_response = MagicMock()
    mock_ai_response.text = json.dumps({
        "summary_adapted": "Resumen adaptado sin la sección de experiencias."
    })

    with patch("ai_service.generate_content_with_retry", return_value=mock_ai_response):
        with pytest.raises(ValueError, match="carece del campo 'experiences'"):
            adapt_resume_to_job(sample_resume, sample_job_text)


# ------------------------------------------------------------------------------
# 3. PRUEBA: MARCADO EN CÓDIGO DE LÍNEAS SOSPECHOSAS (ANTI-ALUCINACIÓN)
# ------------------------------------------------------------------------------

def test_detect_suspicious_line_with_hallucinated_numbers_and_tech():
    """
    Verifica que si la IA introduce métricas numéricas o herramientas
    no presentes en el CV original, el verificador en código las marque como sospechosas.
    """
    orig = "Mantenimiento de APIs internas y soporte técnico."
    # La IA alucina: 45% y herramientas Docker y AWS
    invented = "Mantenimiento de APIs usando Docker y AWS incrementando rendimiento un 45%."

    is_susp, reasons = _detect_suspicious_additions(
        original_text=orig,
        adapted_text=invented,
        original_context="Python Django PostgreSQL"
    )

    assert is_susp is True
    reasons_str = " ".join(reasons).lower()
    assert "45%" in reasons_str or "45" in reasons_str
    assert "docker" in reasons_str or "aws" in reasons_str


def test_legitimate_line_not_flagged():
    """Verifica que una reformulación fiel sin cifras o herramientas nuevas no sea marcada."""
    orig = "Optimización de consultas en base de datos PostgreSQL."
    adapted = "Optimización y afinamiento de consultas relacionales en PostgreSQL."

    is_susp, reasons = _detect_suspicious_additions(
        original_text=orig,
        adapted_text=adapted,
        original_context="PostgreSQL Python"
    )

    assert is_susp is False
    assert len(reasons) == 0


def test_adapt_resume_flags_suspicious_bullet_end_to_end(sample_resume, sample_job_text):
    """Verifica de extremo a extremo que el resultado de adapt_resume_to_job marque el bullet sospechoso."""
    mock_ai_response = MagicMock()
    mock_ai_response.text = json.dumps({
        "summary_adapted": "Desarrollador backend con 3 años de experiencia en Python.",
        "skills_highlighted": ["Python"],
        "experiences": [
            {
                "experience_id": 0,
                "company": "Tech Sol",
                "position": "Backend Developer",
                "bullets": [
                    {
                        "original": "Mantenimiento de APIs internas y depuración de errores.",
                        "adapted": "Lideré despliegues en Kubernetes reduciendo incidencias en un 50%.",
                        "explanation": "Destaca Kubernetes y métricas."
                    }
                ]
            }
        ]
    })

    with patch("ai_service.generate_content_with_retry", return_value=mock_ai_response):
        result = adapt_resume_to_job(sample_resume, sample_job_text)
        b = result["experiences"][0]["bullets"][0]
        assert b["suspicious"] is True
        assert any("50%" in r or "kubernetes" in r.lower() for r in b["suspicious_reasons"])


# ------------------------------------------------------------------------------
# 4. PRUEBA: AISLAMIENTO ESTRICTO POR USUARIO (MULTI-TENANT)
# ------------------------------------------------------------------------------

def test_user_isolation_in_database_operations():
    """
    Verifica que las funciones de base de datos filtren estrictamente
    por el user_id del usuario autenticado actual, imposibilitando cross-tenant leaks.
    """
    mock_client = MagicMock()
    user_a = "11111111-1111-1111-1111-111111111111"
    user_b = "22222222-2222-2222-2222-222222222222"

    # 1. Guardar para Usuario A
    mock_insert_builder = MagicMock()
    mock_client.table.return_value = mock_insert_builder
    mock_insert_builder.insert.return_value.execute.return_value.data = [
        {"id": 42, "user_id": user_a, "version_name": "CV Version 1"}
    ]

    saved = save_tailored_cv_version(
        version_name="CV Version 1",
        tailored_cv={"summary": "Demo"},
        user_id=user_a,
        client=mock_client
    )

    # Verificar que el payload insertado contenga explícitamente el user_id de A
    insert_call_args = mock_insert_builder.insert.call_args[0][0]
    assert insert_call_args["user_id"] == user_a
    assert insert_call_args["updated_at"] is not None

    # 2. Consultar lista para Usuario B
    mock_query_builder = MagicMock()
    mock_client.table.return_value = mock_query_builder
    mock_query_builder.select.return_value = mock_query_builder
    mock_query_builder.eq.return_value = mock_query_builder
    mock_query_builder.order.return_value.execute.return_value.data = []

    get_tailored_cv_versions(user_id=user_b, client=mock_client)

    # Verificar que se filtró por user_id = user_b
    mock_query_builder.eq.assert_called_with("user_id", user_b)

    # 3. Eliminar versión de Usuario A desde sesión de Usuario A
    mock_del_builder = MagicMock()
    mock_client.table.return_value = mock_del_builder
    mock_del_builder.delete.return_value = mock_del_builder
    mock_del_builder.eq.return_value = mock_del_builder
    mock_del_builder.execute.return_value.data = [{"id": 42}]

    delete_tailored_cv_version(version_id=42, user_id=user_a, client=mock_client)

    # Verificar que el delete incluye tanto .eq("id", 42) como .eq("user_id", user_a)
    eq_calls = mock_del_builder.eq.call_args_list
    assert any(call[0] == ("id", 42) for call in eq_calls)
    assert any(call[0] == ("user_id", user_a) for call in eq_calls)
