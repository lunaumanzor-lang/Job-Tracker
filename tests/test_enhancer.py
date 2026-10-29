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

    def generate_text(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs) -> str:
        import json
        if "Resumen profesional original" in prompt:
            return json.dumps({
                "summary_improved": "Ingeniero de Software Senior especializado en arquitecturas cloud y microservicios de alta concurrencia."
            })

        # Evaluar viñeta
        if "ayudé" in prompt.lower() or "colaboré" in prompt.lower() or "participé" in prompt.lower():
            return json.dumps({
                "improved": "Colaboré en la migración a contenedores Docker para mejorar los despliegues.",
                "action_verb": "colaboré",
                "suggestion": "¿En qué porcentaje mejoraron los tiempos de despliegue o cuántos contenedores se migraron?"
            })
        elif "sin métricas" in prompt.lower() or "encargado de" in prompt.lower():
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


def test_enhance_resume_content_deadline_fallback():
    """Verifica que si se supera el deadline, enhance_resume_content recurre al fallback determinista sin llamar a la IA."""
    call_count = {"count": 0}

    class CountingProvider(LLMProvider):
        def generate_text(self, prompt, system_prompt=None, temperature=0.2, max_tokens=4096):
            call_count["count"] += 1
            return "{}"

    provider = CountingProvider()
    resume = ResumeSchema(
        contact=ContactInfo(name="Carlos Test", email="carlos@example.com"),
        summary="Resumen de prueba",
        experience=[
            ExperienceItem(
                company="Empresa C",
                position="Developer",
                bullets=[
                    BulletItem(original="Responsable de monitorear servidores"),
                    BulletItem(original="Desarrollé APIs REST")
                ]
            )
        ]
    )

    # Pasamos un deadline ya expirado (hace 10 segundos)
    import time
    expired_deadline = time.monotonic() - 10.0
    res = enhance_resume_content(resume, provider, deadline=expired_deadline)

    # No debe haberse llamado a la IA
    assert call_count["count"] == 0
    # Los bullets deben haber sido procesados con el fallback determinista
    assert len(res.experience[0].bullets) == 2
    assert not res.experience[0].bullets[0].improved.lower().startswith("responsable de")
    assert res.summary_improved is None  # Resumen conservó el original sin alterar


def test_improve_bullet_starting_with_ayude_en_preserves_collaboration_level():
    """
    Verifica que una viñeta que empiece con 'Ayudé en' conserve el nivel de participación
    (colaborativo) y que la salida simulada no suba el nivel a 'implementé', 'lideré' ni 'diseñé'.
    """
    provider = MockEnhancerProvider()
    used_verbs = set()
    bullet = "Ayudé en la migración a contenedores Docker para mejorar los despliegues."
    item = improve_bullet_point(
        bullet_text=bullet,
        company="Tech Corp",
        position="Backend Dev",
        used_verbs=used_verbs,
        provider=provider
    )
    improved_lower = item.improved.lower()
    # (1) Conserva el nivel de participación del original: 'ayudé', 'colaboré' o 'participé' nunca pasan a 'implementé', 'lideré' ni 'diseñé'
    assert any(verb in improved_lower for verb in ["colaboré", "ayudé", "participé", "apoyé", "asistí"])
    assert "implementé" not in improved_lower
    assert "lideré" not in improved_lower
    assert "diseñé" not in improved_lower
    # (4) Si falta un resultado cuantitativo, la sugerencia lo pide en vez de inventarlo
    assert item.suggestion is not None


def test_fallback_starting_with_ayude_en_preserves_collaboration_level():
    """
    Verifica que el fallback determinista ante fallo del LLM también conserve el nivel
    de participación colaborativo para viñetas que empiezan con 'Ayudé en'.
    """
    class FailingProvider(LLMProvider):
        def generate_text(self, prompt, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs):
            raise RuntimeError("Fallo simulado del proveedor")

    failing_provider = FailingProvider()
    used_verbs = set()
    bullet = "Ayudé en la migración a contenedores Docker para mejorar los despliegues."
    item = improve_bullet_point(
        bullet_text=bullet,
        company="Tech Corp",
        position="Backend Dev",
        used_verbs=used_verbs,
        provider=failing_provider
    )
    improved_lower = item.improved.lower()
    assert any(verb in improved_lower for verb in ["colaboré", "ayudé", "participé", "apoyé", "asistí"])
    assert "implementé" not in improved_lower
    assert "lideré" not in improved_lower
    assert "diseñé" not in improved_lower

