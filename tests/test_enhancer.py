"""
Pruebas funcionales y unitarias para FASE 2: Mejora de Contenido y Reglas Anti-Alucinación.
"""

import pytest
from cv_improver.schema import ResumeSchema, ContactInfo, ExperienceItem, BulletItem
from cv_improver.enhancer import (
    LLMProvider,
    improve_bullet_point,
    enhance_summary,
    enhance_resume_content
)


class MockEnhancerProvider(LLMProvider):
    """Mock con lógica predecible para probar reglas de mejora y anti-alucinación."""

    def generate_text(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=4096) -> str:
        import json
        if "Resumen profesional original" in prompt:
            return json.dumps({
                "summary_improved": "Ingeniero de Software Senior especializado en arquitecturas cloud y microservicios de alta concurrencia."
            })

        # Evaluar viñeta
        if "sin métricas" in prompt.lower() or "encargado de" in prompt.lower():
            return json.dumps({
                "improved": "Diseñé la arquitectura de microservicios usando Python y FastAPI.",
                "action_verb": "diseñé",
                "suggestion": "¿En qué porcentaje disminuyó la latencia o cuántos endpoints creaste?"
            })
        else:
            return json.dumps({
                "improved": "Reduje la latencia de respuesta en un 35% mediante la optimización de consultas SQL.",
                "action_verb": "reduje",
                "suggestion": None
            })


def test_improve_bullet_with_metrics_no_suggestion():
    provider = MockEnhancerProvider()
    used_verbs = set()
    item = improve_bullet_point(
        bullet_text="Optimización de base de datos con 35% de mejora",
        company="Tech Corp",
        position="Backend Dev",
        used_verbs=used_verbs,
        provider=provider
    )
    assert item.original == "Optimización de base de datos con 35% de mejora"
    assert "reduje" in item.improved.lower()
    assert item.suggestion is None
    assert "reduje" in used_verbs


def test_improve_bullet_without_metrics_adds_suggestion():
    provider = MockEnhancerProvider()
    used_verbs = set()
    item = improve_bullet_point(
        bullet_text="Encargado de hacer los microservicios sin métricas",
        company="Tech Corp",
        position="Backend Dev",
        used_verbs=used_verbs,
        provider=provider
    )
    assert "diseñé" in item.improved.lower()
    assert item.suggestion is not None
    assert "porcentaje" in item.suggestion.lower()
    assert "diseñé" in used_verbs


def test_verbs_tracking_per_experience():
    provider = MockEnhancerProvider()
    used_verbs = {"diseñé"}
    item = improve_bullet_point(
        bullet_text="Otra tarea importante",
        company="Tech Corp",
        position="Backend Dev",
        used_verbs=used_verbs,
        provider=provider
    )
    assert "reduje" in used_verbs
    assert "diseñé" in used_verbs


def test_enhance_summary():
    provider = MockEnhancerProvider()
    original_sum = "Soy desarrollador y me gusta programar."
    improved = enhance_summary(original_sum, provider)
    assert "Ingeniero de Software Senior" in improved


def test_enhance_entire_resume():
    provider = MockEnhancerProvider()
    resume = ResumeSchema(
        contact=ContactInfo(name="Laura Perez", email="laura@example.com"),
        summary="Desarrolladora con 5 años de experiencia.",
        experience=[
            ExperienceItem(
                company="Empresa A",
                position="Dev",
                bullets=[
                    BulletItem(original="Encargado de los microservicios sin métricas"),
                    BulletItem(original="Optimización de base de datos con 35% de mejora")
                ]
            )
        ]
    )

    enhanced = enhance_resume_content(resume, provider)
    assert enhanced.summary_improved is not None
    assert len(enhanced.experience[0].bullets) == 2
    
    b1 = enhanced.experience[0].bullets[0]
    b2 = enhanced.experience[0].bullets[1]
    
    assert b1.improved is not None
    assert b1.suggestion is not None
    assert b2.improved is not None
    assert b2.suggestion is None


def test_fallback_when_provider_fails():
    class FailingProvider(LLMProvider):
        def generate_text(self, prompt, system_prompt=None, temperature=0.2, max_tokens=4096):
            raise ConnectionError("Fallo de red simulado")

    failing_provider = FailingProvider()
    used_verbs = set()
    item = improve_bullet_point(
        bullet_text="Responsable de coordinar despliegues en producción",
        company="Firma B",
        position="DevOps",
        used_verbs=used_verbs,
        provider=failing_provider
    )
    # Debe eliminar 'Responsable de' en el fallback sin romperse
    assert not item.improved.lower().startswith("responsable de")
    assert item.suggestion is not None
