"""
Lógica de mejora y reescritura de viñetas (bullets) y resumen profesional con IA.
Aplica estrictamente reglas ATS, verbos de acción, estructura Acción + Contexto + Resultado,
y la regla crítica anti-alucinación (nunca inventar métricas).
"""

import logging
import re
import time
from typing import Optional, Set, Dict, Any, List
from ..schema import ResumeSchema, ExperienceItem, BulletItem
from .provider_base import LLMProvider

logger = logging.getLogger(__name__)

WEAK_PHRASES = [
    "responsable de",
    "encargado de",
    "encargada de",
    "ayudé a",
    "trabajé en",
    "participé en",
    "mi rol era",
    "funciones incluían",
    "responsible for",
    "in charge of",
    "assisted with",
    "worked on"
]

BULLET_ENHANCEMENT_SYSTEM_PROMPT_ES = """Eres un consultor de carrera y redactor experto en currículums de alto impacto (ATS).
Tu misión es transformar cada viñeta o responsabilidad en un logro profesional conciso y convincente.

REGLAS ESTRICTAS DE REDACCIÓN:
1. ESTRUCTURA: Comienza siempre con un verbo de acción fuerte en tiempo pasado (ej. 'Implementé', 'Diseñé', 'Optimizé', 'Desplegué', 'Lideré', 'Construí').
2. FÓRMULA: Acción + Contexto + Resultado (máximo 2 líneas, entre 120 y 200 caracteres aprox).
3. PROHIBICIONES: Elimina absolutamente frases vacías o pasivas como "responsable de", "encargado de", "trabajé en", "participé en", "ayudé a".
4. SIN REPETICIÓN: NO repitas ninguno de los verbos de acción ya utilizados en la misma experiencia.
5. IDIOMA: Redacta estrictamente en Español impecable y profesional.
6. REGLA CRÍTICA ANTI-INVENCIÓN:
   - NUNCA inventes números, porcentajes, cifras de dinero, nombres de clientes ni logros que no aparezcan en el texto original.
   - Si la viñeta original NO incluye métricas cuantitativas, mejora la redacción, acción y claridad sin inventar datos, y GENERA una pregunta puntual en el campo "suggestion" preguntándole al usuario qué dato cuantificable puede añadir (ej. '¿En qué porcentaje redujo los tiempos de carga?' o '¿Cuántos miembros del equipo colaboraron?').
   - Si la viñeta original ya incluye cifras y logros suficientes, el campo "suggestion" debe ser null.

Devuelve ÚNICAMENTE un objeto JSON con este formato:
{
  "improved": "Texto del bullet mejorado en español",
  "action_verb": "verbo utilizado en pasado (en minúsculas)",
  "suggestion": "Pregunta al usuario sobre la métrica faltante o null si ya tenía métricas"
}"""

BULLET_ENHANCEMENT_SYSTEM_PROMPT_EN = """You are an executive career advisor and expert ATS resume writer.
Your mission is to transform each bullet point or job duty into a concise, compelling, high-impact professional achievement.

STRICT WRITING RULES:
1. STRUCTURE: Always begin with a strong, dynamic action verb in the past tense (e.g., 'Engineered', 'Architected', 'Spearheaded', 'Optimized', 'Deployed', 'Implemented', 'Built', 'Led').
2. FORMULA: Action + Context + Result (maximum 1-2 lines, approx 120-200 characters).
3. PROHIBITIONS: Completely eliminate passive or weak phrasing like "responsible for", "in charge of", "worked on", "assisted with", "participated in".
4. NO REPETITION: Do NOT repeat any action verbs already used within the same company/experience.
5. LANGUAGE: Write strictly in professional, flawless English.
6. CRITICAL ANTI-HALLUCINATION RULE:
   - NEVER invent numbers, percentages, dollar amounts, client names, or achievements not present in the original text.
   - If the original bullet lacks quantitative metrics, improve the active structure, clarity, and impact without fabricating data, and formulate a targeted question in the "suggestion" field asking the candidate for the missing metric (e.g., 'What was the percentage increase in efficiency?' or 'How many engineers or stakeholders did you collaborate with?').
   - If the original bullet point already includes sufficient quantifiable metrics, "suggestion" must be null.

Return ONLY a valid JSON object with this exact format:
{
  "improved": "Enhanced bullet point text in English",
  "action_verb": "action verb used in past tense (lowercase)",
  "suggestion": "Targeted question asking for missing quantifiable metric or null if already quantified"
}"""

SUMMARY_ENHANCEMENT_SYSTEM_PROMPT_ES = """Eres un consultor de carrera experto en redacción de perfiles profesionales.
Reescribe el resumen profesional del candidato para que sea de alto impacto:
- Máximo 3 a 4 líneas.
- Orientado al valor profesional, fortalezas técnicas y solución de problemas.
- Estrictamente en Español impecable.
- Sin frases vacías ni superlativos no fundamentados.
- NO inventes años de experiencia ni empresas que no estén mencionadas.

Devuelve ÚNICAMENTE un objeto JSON con este formato:
{
  "summary_improved": "Texto del resumen profesional mejorado en español"
}"""

SUMMARY_ENHANCEMENT_SYSTEM_PROMPT_EN = """You are an executive career consultant specializing in high-impact professional profiles.
Rewrite the candidate's professional summary to be compelling and executive-ready:
- Maximum 3 to 4 lines.
- Focused on core value proposition, technical strengths, and problem-solving impact.
- Strictly in professional English.
- No filler phrases or unfounded superlatives.
- DO NOT invent years of experience or employers not mentioned.

Return ONLY a valid JSON object with this format:
{
  "summary_improved": "Enhanced professional summary in English"
}"""

# Compatibilidad
BULLET_ENHANCEMENT_SYSTEM_PROMPT = BULLET_ENHANCEMENT_SYSTEM_PROMPT_ES
SUMMARY_ENHANCEMENT_SYSTEM_PROMPT = SUMMARY_ENHANCEMENT_SYSTEM_PROMPT_ES


def improve_bullet_point(
    bullet_text: str,
    company: str,
    position: str,
    used_verbs: Set[str],
    provider: LLMProvider,
    language: str = "es",
    deadline: Optional[float] = None
) -> BulletItem:
    """
    Reescribe una viñeta individual siguiendo las reglas de acción, contexto y resultado en el idioma indicado ('es' o 'en').
    Garantiza no repetir verbos de acción en la misma empresa y no inventar datos.
    """
    if not bullet_text or not bullet_text.strip():
        return BulletItem(original=bullet_text or "", improved=bullet_text, suggestion=None)

    is_en = (language == "en")
    sys_prompt = BULLET_ENHANCEMENT_SYSTEM_PROMPT_EN if is_en else BULLET_ENHANCEMENT_SYSTEM_PROMPT_ES

    if is_en:
        prompt = f"""Company: {company}
Position: {position}
Action verbs already used in this experience (DO NOT USE THESE): {list(used_verbs) if used_verbs else 'None'}
Original bullet point:
"{bullet_text.strip()}"

Generate the JSON with the enhanced bullet point in English and the targeted metric suggestion if applicable."""
    else:
        prompt = f"""Empresa: {company}
Cargo: {position}
Verbos de acción ya usados en esta experiencia (NO USAR ESTOS): {list(used_verbs) if used_verbs else 'Ninguno'}
Viñeta original:
"{bullet_text.strip()}"

Genera el JSON con el bullet mejorado en español y la sugerencia de métrica si aplica."""

    try:
        data = provider.generate_json(
            prompt=prompt,
            system_prompt=sys_prompt,
            temperature=0.2,
            deadline=deadline
        )
        improved_text = data.get("improved") or bullet_text
        suggestion = data.get("suggestion")
        action_verb = (data.get("action_verb") or "").lower().strip()

        # Registrar el verbo usado para evitar repetición en las siguientes viñetas de la misma experiencia
        if action_verb:
            used_verbs.add(action_verb)
        else:
            first_word = improved_text.split()[0].lower().strip(".,:;") if improved_text.split() else ""
            if first_word:
                used_verbs.add(first_word)

        return BulletItem(
            original=bullet_text,
            improved=improved_text,
            suggestion=suggestion if suggestion and suggestion.strip() else None
        )

    except Exception as e:
        logger.error(f"Error al mejorar viñeta con LLM: {e}", exc_info=True)
        # Fallback determinista seguro sin inventar nada
        cleaned = bullet_text.strip()
        for phrase in WEAK_PHRASES:
            if cleaned.lower().startswith(phrase):
                cleaned = cleaned[len(phrase):].strip()
                # Capitalizar primera letra
                cleaned = cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned
                break

        has_numbers = bool(re.search(r"\d+%?", bullet_text))
        if is_en:
            suggestion = None if has_numbers else "Can you quantify this result with a metric, percentage, or measurable impact?"
        else:
            suggestion = None if has_numbers else "¿Puedes cuantificar el resultado con alguna métrica o porcentaje?"

        return BulletItem(
            original=bullet_text,
            improved=cleaned,
            suggestion=suggestion
        )


def enhance_summary(
    summary_text: str,
    provider: LLMProvider,
    language: str = "es",
    deadline: Optional[float] = None
) -> str:
    """Reescribe el resumen profesional haciéndolo de alto impacto (3-4 líneas) en el idioma seleccionado ('es' o 'en')."""
    if not summary_text or not summary_text.strip():
        return ""

    is_en = (language == "en")
    sys_prompt = SUMMARY_ENHANCEMENT_SYSTEM_PROMPT_EN if is_en else SUMMARY_ENHANCEMENT_SYSTEM_PROMPT_ES

    if is_en:
        prompt = f"""Original professional summary:
"{summary_text.strip()}"

Rewrite the high-impact professional summary in English."""
    else:
        prompt = f"""Resumen profesional original:
"{summary_text.strip()}"

Genera el resumen profesional mejorado en español."""

    try:
        data = provider.generate_json(
            prompt=prompt,
            system_prompt=sys_prompt,
            temperature=0.3,
            deadline=deadline
        )
        return data.get("summary_improved") or summary_text
    except Exception as e:
        logger.error(f"Error al mejorar resumen con LLM: {e}", exc_info=True)
        return summary_text


def enhance_resume_content(
    resume: ResumeSchema,
    provider: LLMProvider,
    language: str = "es",
    deadline: Optional[float] = None
) -> ResumeSchema:
    """
    Mejora todos los bullets y el resumen profesional de un ResumeSchema en el idioma solicitado ('es' o 'en').
    Retorna el mismo ResumeSchema con campos 'improved' y 'suggestion' completados.
    Si se especifica un deadline y el tiempo expira, aplica un fallback determinista inmediato sin llamar a la IA.
    """
    is_en = (language == "en")

    # 1. Mejorar resumen profesional
    if resume.summary:
        if deadline is not None and time.time() >= deadline:
            logger.warning("Tope de tiempo alcanzado antes de mejorar resumen; conservando original.")
        else:
            resume.summary_improved = enhance_summary(resume.summary, provider, language=language, deadline=deadline)

    # 2. Mejorar bullets experiencia por experiencia
    for exp in resume.experience:
        used_verbs_for_this_company: Set[str] = set()
        new_bullets = []
        for b in exp.bullets:
            if deadline is not None and time.time() >= deadline:
                logger.warning(f"Tope de tiempo alcanzado en {exp.company}; aplicando fallback determinista para viñetas.")
                cleaned = b.original.strip()
                for phrase in WEAK_PHRASES:
                    if cleaned.lower().startswith(phrase):
                        cleaned = cleaned[len(phrase):].strip()
                        cleaned = cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned
                        break
                has_numbers = bool(re.search(r"\d+%?", b.original))
                sug = None if has_numbers else ("Can you quantify this result with a metric, percentage, or measurable impact?" if is_en else "¿Puedes cuantificar el resultado con alguna métrica o porcentaje?")
                new_bullets.append(BulletItem(original=b.original, improved=cleaned, suggestion=sug))
            else:
                improved_b = improve_bullet_point(
                    bullet_text=b.original,
                    company=exp.company,
                    position=exp.position,
                    used_verbs=used_verbs_for_this_company,
                    provider=provider,
                    language=language,
                    deadline=deadline
                )
                new_bullets.append(improved_b)
        exp.bullets = new_bullets

    return resume
