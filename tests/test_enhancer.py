"""
Pruebas funcionales y unitarias para FASE 2: Mejora de Contenido y Reglas Anti-Alucinación.
"""

import json
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

        # Evaluar lote de viñetas
        if "optimiza la siguiente lista" in prompt.lower() or "following bullet points" in prompt.lower() or "[id:" in prompt.lower():
            bullets_out = []
            for line in prompt.splitlines():
                if "[id:" in line:
                    import re
                    m = re.search(r"\[id:\s*(\d+)\]", line)
                    if m:
                        b_id = int(m.group(1))
                        if "ayudé" in line.lower() or "colaboré" in line.lower() or "participé" in line.lower():
                            bullets_out.append({
                                "id": b_id,
                                "improved": "Colaboré en la migración a contenedores Docker para mejorar los despliegues.",
                                "action_verb": "colaboré",
                                "suggestion": "¿En qué porcentaje mejoraron los tiempos de despliegue o cuántos contenedores se migraron?"
                            })
                        elif "sin métricas" in line.lower() or "encargado de" in line.lower():
                            bullets_out.append({
                                "id": b_id,
                                "improved": "Diseñé la arquitectura de microservicios usando Python y FastAPI.",
                                "action_verb": "diseñé",
                                "suggestion": "¿En qué porcentaje disminuyó la latencia o cuántos endpoints creaste?"
                            })
                        else:
                            bullets_out.append({
                                "id": b_id,
                                "improved": "Reduje la latencia de respuesta en un 35% mediante la optimización de consultas SQL.",
                                "action_verb": "reduje",
                                "suggestion": None
                            })
            return json.dumps({"bullets": bullets_out})

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


def test_enhance_resume_content_deadline_fallback_with_simulated_monotonic_clock():
    """Verifica que simular el avance de time.monotonic() por encima del deadline activa el fallback sin llamar a la IA."""
    from unittest.mock import patch
    call_count = {"count": 0}

    class CountingProvider(LLMProvider):
        def generate_text(self, prompt, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs):
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
                    BulletItem(original="Responsable de monitorear servidores")
                ]
            )
        ]
    )

    fake_clock = [100.0]

    def fake_monotonic():
        return fake_clock[0]

    with patch("time.monotonic", side_effect=fake_monotonic):
        # Reloj avanza a 110.0 superando el deadline fijado en 105.0
        fake_clock[0] = 110.0
        res = enhance_resume_content(resume, provider, deadline=105.0)

    assert call_count["count"] == 0
    assert not res.experience[0].bullets[0].improved.lower().startswith("responsable de")
    assert res.summary_improved is None


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


def test_post_validation_discards_model_output_elevating_participation_level():
    """
    Verifica la validación posterior: si el texto original empieza con un verbo de apoyo
    ('ayudé', 'colaboré', 'participé', 'apoyé', 'asistí') y la salida simulada del modelo
    sube el nivel a autoría o liderazgo ('implementé', 'lideré', 'diseñé', 'desarrollé', 'creé', 'dirigí'),
    dicha salida se descarta y se aplica el respaldo determinista para esa viñeta.
    """
    class ElevatingMockProvider(LLMProvider):
        def __init__(self, elevated_verb: str):
            self.elevated_verb = elevated_verb

        def generate_text(self, prompt, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs):
            return json.dumps({
                "improved": f"{self.elevated_verb.capitalize()} la arquitectura completa de microservicios en Kubernetes.",
                "action_verb": self.elevated_verb,
                "suggestion": "¿Tienes métricas del proyecto?"
            })

    # Probar con varios verbos de autoría/liderazgo
    for forbidden_verb in ["implementé", "lideré", "diseñé", "desarrollé", "creé", "dirigí"]:
        provider = ElevatingMockProvider(forbidden_verb)
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
        # La salida del modelo que subió el nivel debió ser descartada
        assert not improved_lower.startswith(forbidden_verb)
        assert forbidden_verb not in used_verbs

        # Debe haberse aplicado el respaldo determinista (conserva colaboración)
        assert improved_lower.startswith("colaboré en")
        assert "migración a contenedores docker" in improved_lower


def test_process_and_enhance_cv_catches_ai_time_budget_exceeded():
    """
    Verifica que process_and_enhance_cv captura AITimeBudgetExceeded,
    activa el indicador de timed_out y carga el CV estructurado sin bloquear.
    """
    from unittest.mock import patch
    from ai_client import AITimeBudgetExceeded
    from cv_improver.ui import process_and_enhance_cv

    fake_session = {}

    class TimeoutProvider(LLMProvider):
        def generate_text(self, *args, **kwargs):
            raise AITimeBudgetExceeded("Presupuesto agotado")

    with patch("streamlit.session_state", fake_session), \
         patch("streamlit.rerun", return_value=None), \
         patch("cv_improver.ui.get_active_llm_provider", return_value=(TimeoutProvider(), "Gemini")), \
         patch("cv_improver.ui.persist_active_cv_draft", return_value=None), \
         patch("cv_improver.ui.st.toast", return_value=None):
        raw_text = "Juan Perez\njuan@example.com\nExperiencia:\nSoftware Dev en ABC (2020-2022)\n- Desarrollé software"
        process_and_enhance_cv(raw_text)

        assert "cv_improver_notice" in fake_session
        assert "90 s" in fake_session["cv_improver_notice"]
        assert fake_session["cv_improver_active_schema"] is not None


def test_batch_enhancement_fifteen_bullets_make_single_call():
    """
    Regla (6a): 15 viñetas se procesan en 1 sola llamada en lote con timeout_per_call=45.
    """
    call_records = []

    class BatchFifteenProvider(LLMProvider):
        def generate_text(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs) -> str:
            call_records.append({
                "prompt": prompt,
                "kwargs": kwargs
            })
            bullets_resp = [
                {
                    "id": i,
                    "improved": f"Optimizé el microservicio {i} reduciendo la latencia.",
                    "action_verb": "optimizé",
                    "suggestion": f"¿En qué porcentaje mejoró el microservicio {i}?"
                }
                for i in range(1, 16)
            ]
            return json.dumps({"bullets": bullets_resp})

    provider = BatchFifteenProvider()
    resume = ResumeSchema(
        contact=ContactInfo(name="Ana Gomez", email="ana@example.com"),
        summary=None,
        experience=[
            ExperienceItem(
                company="Empresa Cloud",
                position="Backend Engineer",
                bullets=[BulletItem(original=f"Responsable de componente {i}") for i in range(1, 16)]
            )
        ]
    )

    res = enhance_resume_content(resume, provider)

    # Exactamente 1 llamada al proveedor de IA para procesar las 15 viñetas
    assert len(call_records) == 1
    assert call_records[0]["kwargs"].get("timeout_per_call") == 45.0

    all_bullets = res.experience[0].bullets
    assert len(all_bullets) == 15
    for idx, b in enumerate(all_bullets, 1):
        assert b.improved == f"Optimizé el microservicio {idx} reduciendo la latencia."
        assert b.suggestion == f"¿En qué porcentaje mejoró el microservicio {idx}?"


def test_batch_enhancement_invalid_json_or_missing_triggers_fallback_only_for_missing():
    """
    Regla (6b): Si el JSON del lote falta alguna viñeta (ej. solo devuelve 3 de 5),
    el respaldo de una llamada individual se activa SOLO para las 2 viñetas faltantes.
    """
    call_log = []

    class PartialBatchProvider(LLMProvider):
        def generate_text(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs) -> str:
            call_log.append(prompt)
            # Primera llamada: lote que solo contiene viñetas 1, 2, 3 (faltan 4 y 5)
            if "optimiza la siguiente lista" in prompt.lower() or "[id:" in prompt.lower():
                return json.dumps({
                    "bullets": [
                        {"id": 1, "improved": "Optimizé la base de datos.", "action_verb": "optimizé", "suggestion": None},
                        {"id": 2, "improved": "Automaticé despliegues CI/CD.", "action_verb": "automaticé", "suggestion": None},
                        {"id": 3, "improved": "Monitoreé la infraestructura.", "action_verb": "monitoreé", "suggestion": None},
                    ]
                })
            # Llamadas individuales de respaldo para las faltantes
            return json.dumps({
                "improved": f"Reescribí viñeta individual desde respaldo: {prompt[:30]}.",
                "action_verb": "reescribí",
                "suggestion": "¿Tienes métricas?"
            })

    provider = PartialBatchProvider()
    resume = ResumeSchema(
        contact=ContactInfo(name="Dev Tester", email="tester@example.com"),
        summary=None,
        experience=[
            ExperienceItem(
                company="Tech Co",
                position="Developer",
                bullets=[BulletItem(original=f"Tarea número {i}") for i in range(1, 6)]
            )
        ]
    )

    res = enhance_resume_content(resume, provider)

    # 1 llamada por lote + 2 llamadas individuales para viñetas 4 y 5 = 3 llamadas en total
    assert len(call_log) == 3

    bullets = res.experience[0].bullets
    assert len(bullets) == 5
    # Las primeras 3 vienen del lote
    assert bullets[0].improved == "Optimizé la base de datos."
    assert bullets[1].improved == "Automaticé despliegues CI/CD."
    assert bullets[2].improved == "Monitoreé la infraestructura."
    # Las últimas 2 vienen del respaldo individual
    assert "Reescribí viñeta individual desde respaldo" in bullets[3].improved
    assert "Reescribí viñeta individual desde respaldo" in bullets[4].improved


def test_batch_enhancement_fallback_respects_deadline():
    """
    Regla (6c): El respaldo de viñetas faltantes respeta el deadline y no llama a la IA
    si el tiempo expira, aplicando el respaldo determinista.
    """
    from unittest.mock import patch
    call_log = []
    fake_clock = [100.0]

    class MissingBatchWithClockProvider(LLMProvider):
        def generate_text(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs) -> str:
            call_log.append(prompt)
            # Primera llamada en lote: solo devuelve viñeta 1 (faltan viñeta 2 y 3)
            if "optimiza la siguiente lista" in prompt.lower() or "[id:" in prompt.lower():
                return json.dumps({
                    "bullets": [
                        {"id": 1, "improved": "Lote exitoso 1.", "action_verb": "diseñé", "suggestion": None}
                    ]
                })
            # Si se llama al respaldo individual, avanzamos el reloj simulado más allá del deadline
            fake_clock[0] = 200.0
            return json.dumps({
                "improved": "Respaldo individual.",
                "action_verb": "diseñé",
                "suggestion": None
            })

    provider = MissingBatchWithClockProvider()
    resume = ResumeSchema(
        contact=ContactInfo(name="Clock Tester", email="clock@example.com"),
        summary=None,
        experience=[
            ExperienceItem(
                company="Time Co",
                position="DevOps",
                bullets=[
                    BulletItem(original="Primera viñeta"),
                    BulletItem(original="Segunda viñeta que usará respaldo individual"),
                    BulletItem(original="Responsable de tercera viñeta que superará deadline")
                ]
            )
        ]
    )

    # Deadline fijado en 150.0.
    # Viñeta 1: viene del lote (reloj en 100.0).
    # Viñeta 2: falta en el lote, hace 1 llamada de respaldo y fake_clock salta a 200.0.
    # Viñeta 3: falta en el lote, pero como fake_clock=200 >= 150 (deadline), NO llama a la IA y aplica determinista.
    with patch("time.monotonic", side_effect=lambda: fake_clock[0]):
        res = enhance_resume_content(resume, provider, deadline=150.0)

    # 1 llamada de lote + 1 llamada de respaldo individual para viñeta 2 = 2 llamadas en total
    assert len(call_log) == 2
    bullets = res.experience[0].bullets
    assert bullets[0].improved == "Lote exitoso 1."
    assert bullets[1].improved == "Respaldo individual."
    # Viñeta 3 se resolvió determinísticamente sin 'responsable de'
    assert not bullets[2].improved.lower().startswith("responsable de")


def test_batch_enhancement_elevating_verb_is_discarded_in_batch():
    """
    Regla (6d) y Regla (5): Aplica a cada viñeta del lote la validación que descarta
    salidas que suben de verbo de apoyo ('Ayudé en...') a autoría/liderazgo ('Implementé...'),
    usando el respaldo determinista para esa viñeta.
    """
    class ElevatingBatchProvider(LLMProvider):
        def generate_text(self, prompt: str, system_prompt=None, temperature=0.2, max_tokens=4096, **kwargs) -> str:
            return json.dumps({
                "bullets": [
                    {
                        "id": 1,
                        "improved": "Diseñé la arquitectura de microservicios usando FastAPI.",
                        "action_verb": "diseñé",
                        "suggestion": None
                    },
                    {
                        "id": 2,
                        "improved": "Implementé y lideré la migración completa a contenedores Docker.",
                        "action_verb": "implementé",
                        "suggestion": None
                    }
                ]
            })

    provider = ElevatingBatchProvider()
    resume = ResumeSchema(
        contact=ContactInfo(name="Validation Tester", email="val@example.com"),
        summary=None,
        experience=[
            ExperienceItem(
                company="Validation Corp",
                position="Backend Engineer",
                bullets=[
                    BulletItem(original="Encargado de los microservicios sin métricas"),
                    BulletItem(original="Ayudé en la migración a contenedores Docker para mejorar los despliegues.")
                ]
            )
        ]
    )

    res = enhance_resume_content(resume, provider)
    bullets = res.experience[0].bullets
    assert len(bullets) == 2

    # Viñeta 1: aceptó 'Diseñé...'
    assert bullets[0].improved.startswith("Diseñé")

    # Viñeta 2: empezaba con 'Ayudé en', la salida del lote 'Implementé...' fue descartada
    # y se aplicó el respaldo determinista
    assert not bullets[1].improved.lower().startswith("implementé")
    assert not bullets[1].improved.lower().startswith("lideré")
    assert bullets[1].improved.lower().startswith("colaboré en")
    assert "migración a contenedores docker" in bullets[1].improved.lower()


def test_verb_anti_exaggeration_managed_to_directed_rejected():
    """
    Verifica que 'Managed' (Nivel 2) no pueda escalar a 'Directed' (Nivel 3).
    Si el modelo insiste en 'Directed', la viñeta mejorada es rechazada y se devuelve el original sin cambios.
    """
    class DirectedMockProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Directed VMware Infrastructure Operations across all datacenters.",
                "action_verb": "directed",
                "suggestion": None
            })

    bullet = "Managed VMware Infrastructure"
    item = improve_bullet_point(
        bullet_text=bullet,
        company="Enterprise Corp",
        position="Systems Engineer",
        used_verbs=set(),
        provider=DirectedMockProvider(),
        language="en"
    )
    assert not item.improved.lower().startswith("directed")
    assert not item.improved.lower().startswith("led")
    assert item.improved.startswith("Managed")


def test_verb_anti_exaggeration_managed_to_administered_accepted():
    """
    Verifica que 'Managed' (Nivel 2) puede pasar a un sinónimo del mismo nivel como 'Administered' (Nivel 2).
    """
    class AdministeredMockProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Administered VMware Infrastructure and virtualization cluster environments.",
                "action_verb": "administered",
                "suggestion": None
            })

    bullet = "Managed VMware Infrastructure"
    item = improve_bullet_point(
        bullet_text=bullet,
        company="Enterprise Corp",
        position="Systems Engineer",
        used_verbs=set(),
        provider=AdministeredMockProvider(),
        language="en"
    )
    assert item.improved.startswith("Administered")
    assert "administered" in item.improved.lower()


def test_verb_anti_exaggeration_helped_to_led_rejected():
    """
    Verifica que 'helped' (Nivel 1) no pueda escalar a 'led' (Nivel 3).
    """
    class LedMockProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Led engineering team during container deployment and testing.",
                "action_verb": "led",
                "suggestion": None
            })

    bullet = "Helped deployment team during release cycles."
    item = improve_bullet_point(
        bullet_text=bullet,
        company="Startup Inc",
        position="Junior Dev",
        used_verbs=set(),
        provider=LedMockProvider(),
        language="en"
    )
    assert not item.improved.lower().startswith("led")
    assert not item.improved.lower().startswith("directed")


def test_verb_anti_exaggeration_unknown_verb_conserved_english():
    """
    Si el verbo original no está en la lista (desconocido), la viñeta mejorada debe conservar ese mismo verbo.
    """
    class UnknownVerbChangerProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Directed resolution of critical network latency outages.",
                "action_verb": "directed",
                "suggestion": None
            })

    class UnknownVerbKeeperProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Troubleshot critical network outages to ensure high service availability.",
                "action_verb": "troubleshot",
                "suggestion": None
            })

    bullet = "Troubleshot critical network outages"

    # Caso A: Modelo intenta cambiar el verbo desconocido a 'Directed' -> Rechazado
    item_rejected = improve_bullet_point(
        bullet_text=bullet,
        company="Net Corp",
        position="Net Admin",
        used_verbs=set(),
        provider=UnknownVerbChangerProvider(),
        language="en"
    )
    assert not item_rejected.improved.lower().startswith("directed")
    assert item_rejected.improved.startswith("Troubleshot")

    # Caso B: Modelo conserva el verbo desconocido 'Troubleshot' -> Aceptado
    item_accepted = improve_bullet_point(
        bullet_text=bullet,
        company="Net Corp",
        position="Net Admin",
        used_verbs=set(),
        provider=UnknownVerbKeeperProvider(),
        language="en"
    )
    assert item_accepted.improved.startswith("Troubleshot")
    assert "high service availability" in item_accepted.improved


def test_verb_anti_exaggeration_spanish_cases():
    """
    Prueba los mismos casos en español:
    - Gestioné → Dirigí (rechazado, Nivel 2 -> Nivel 3)
    - Gestioné → Administré (aceptado, Nivel 2 -> Nivel 2)
    - Ayudé → Lideré (rechazado, Nivel 1 -> Nivel 3)
    - Verbo desconocido conservado (Diagnosticamos → Dirigí rechazado; Diagnosticamos → Diagnosticamos aceptado)
    """
    class DirigiMockProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Dirigí la infraestructura de virtualización VMware en múltiples centros de datos.",
                "action_verb": "dirigí",
                "suggestion": None
            })

    class AdministreMockProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Administré la infraestructura de virtualización VMware y servidores ESXi.",
                "action_verb": "administré",
                "suggestion": None
            })

    class LidereMockProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Lideré el despliegue del pipeline de entrega continua.",
                "action_verb": "lideré",
                "suggestion": None
            })

    class DiagnosticamosChangerProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Dirigí la resolución de fallas de conectividad en enlaces de fibra.",
                "action_verb": "dirigí",
                "suggestion": None
            })

    class DiagnosticamosKeeperProvider(LLMProvider):
        def generate_text(self, prompt, **kwargs):
            return json.dumps({
                "improved": "Diagnosticamos fallas críticas de conectividad en enlaces de fibra garantizando el enlace.",
                "action_verb": "diagnosticamos",
                "suggestion": None
            })

    # 1. Gestioné → Dirigí rechazado
    item1 = improve_bullet_point(
        bullet_text="Gestioné la infraestructura VMware",
        company="Empresa SA",
        position="Ingeniero de Sistemas",
        used_verbs=set(),
        provider=DirigiMockProvider(),
        language="es"
    )
    assert not item1.improved.lower().startswith("dirigí")
    assert not item1.improved.lower().startswith("dirigi")
    assert not item1.improved.lower().startswith("lideré")
    assert item1.improved.startswith("Gestioné")

    # 2. Gestioné → Administré aceptado
    item2 = improve_bullet_point(
        bullet_text="Gestioné la infraestructura VMware",
        company="Empresa SA",
        position="Ingeniero de Sistemas",
        used_verbs=set(),
        provider=AdministreMockProvider(),
        language="es"
    )
    assert item2.improved.startswith("Administré")

    # 3. Ayudé → Lideré rechazado
    item3 = improve_bullet_point(
        bullet_text="Ayudé en el despliegue del pipeline de entrega continua.",
        company="Empresa SA",
        position="Desarrollador Junior",
        used_verbs=set(),
        provider=LidereMockProvider(),
        language="es"
    )
    assert not item3.improved.lower().startswith("lideré")
    assert not item3.improved.lower().startswith("lidere")

    # 4. Verbo desconocido conservado:
    # 4a. Cambiado a 'Dirigí' -> Rechazado
    item4a = improve_bullet_point(
        bullet_text="Diagnosticamos fallas críticas de conectividad en enlaces de fibra.",
        company="Telecom Corp",
        position="Ingeniero NOC",
        used_verbs=set(),
        provider=DiagnosticamosChangerProvider(),
        language="es"
    )
    assert not item4a.improved.lower().startswith("dirigí")
    assert item4a.improved.startswith("Diagnosticamos")

    # 4b. Conservado 'Diagnosticamos' -> Aceptado
    item4b = improve_bullet_point(
        bullet_text="Diagnosticamos fallas críticas de conectividad en enlaces de fibra.",
        company="Telecom Corp",
        position="Ingeniero NOC",
        used_verbs=set(),
        provider=DiagnosticamosKeeperProvider(),
        language="es"
    )
    assert item4b.improved.startswith("Diagnosticamos")
    assert "fallas críticas de conectividad" in item4b.improved


def test_validate_verb_enhancement_shared_unit_cases():
    """
    Pruebas directas de la función compartida validate_verb_enhancement:
    niveles 1, 2, 3, formas verbales con/sin tilde, gerundios e infinitivos.
    """
    from cv_improver.enhancer.bullet_enhancer import validate_verb_enhancement

    # Nivel 1 no puede subir a Nivel 2 ni Nivel 3
    valid, _ = validate_verb_enhancement("Helped with testing", "Implemented automated tests", "implemented")
    assert not valid
    valid, _ = validate_verb_enhancement("Ayudé en las pruebas", "Lideré las pruebas automatizadas", "lideré")
    assert not valid

    # Nivel 2 no puede subir a Nivel 3
    valid, _ = validate_verb_enhancement("Managed VMware infrastructure", "Directed infrastructure operations", "directed")
    assert not valid
    valid, _ = validate_verb_enhancement("Managing VMware infrastructure", "Leading infrastructure operations", "leading")
    assert not valid
    valid, _ = validate_verb_enhancement("Gestioné la infraestructura", "Dirigí las operaciones", "dirigí")
    assert not valid
    valid, _ = validate_verb_enhancement("Gestione la infraestructura", "Lidere el equipo", "lidere")
    assert not valid

    # Nivel 2 puede pasar a sinónimo de Nivel 2
    valid, _ = validate_verb_enhancement("Managed VMware infrastructure", "Administered VMware cluster", "administered")
    assert valid
    valid, _ = validate_verb_enhancement("Managing VMware infrastructure", "Maintained VMware cluster", "maintained")
    assert valid
    valid, _ = validate_verb_enhancement("Gestioné servidores", "Administré servidores", "administré")
    assert valid

    # Verbo desconocido debe ser exactamente el mismo
    valid, _ = validate_verb_enhancement("Troubleshot DNS problems", "Troubleshot DNS configuration issues", "troubleshot")
    assert valid
    valid, _ = validate_verb_enhancement("Troubleshooting DNS problems", "Troubleshot DNS configuration issues", "troubleshot")
    assert valid
    valid, _ = validate_verb_enhancement("Troubleshot DNS problems", "Directed DNS resolution", "directed")
    assert not valid





