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
    "trabajé en",
    "mi rol era",
    "funciones incluían",
    "responsible for",
    "in charge of",
    "worked on"
]


def _clean_bullet_fallback(bullet_text: str, is_en: bool = False) -> str:
    """Fallback determinista para viñetas que limpia frases pasivas y preserva el nivel colaborativo sin inventar."""
    cleaned = bullet_text.strip()
    cleaned_lower = cleaned.lower()

    # Conservar el nivel de colaboración: 'ayudé', 'colaboré', 'participé' nunca se pierden ni se escalan
    if is_en:
        collab_prefixes = [
            ("helped with", "Collaborated on"),
            ("helped to", "Collaborated on"),
            ("assisted with", "Collaborated on"),
            ("assisted in", "Collaborated on"),
            ("collaborated on", "Collaborated on"),
            ("participated in", "Collaborated on"),
            ("supported in", "Collaborated on"),
        ]
    else:
        collab_prefixes = [
            ("ayudé a", "Colaboré en"),
            ("ayudé en", "Colaboré en"),
            ("colaboré en", "Colaboré en"),
            ("colaboré con", "Colaboré con"),
            ("participé en", "Colaboré en"),
            ("apoyé en", "Colaboré en"),
            ("asistí en", "Colaboré en"),
        ]

    for prefix, replacement in collab_prefixes:
        if cleaned_lower.startswith(prefix):
            rest = cleaned[len(prefix):].strip()
            return f"{replacement} {rest}" if rest else replacement

    passive_phrases = [
        "responsable de",
        "encargado de",
        "encargada de",
        "trabajé en",
        "mi rol era",
        "funciones incluían",
        "responsible for",
        "in charge of",
        "worked on"
    ]
    for phrase in passive_phrases:
        if cleaned_lower.startswith(phrase):
            cleaned = cleaned[len(phrase):].strip()
            return cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned

    return cleaned


SUPPORT_VERBS = {
    "ayudé", "ayude",
    "colaboré", "colabore",
    "participé", "participe",
    "apoyé", "apoye",
    "asistí", "asisti",
    "helped",
    "assisted",
    "collaborated",
    "participated",
    "supported",
}

LEADERSHIP_AUTHORSHIP_VERBS = {
    "implementé", "implemente",
    "lideré", "lidere",
    "diseñé", "disene",
    "desarrollé", "desarrolle",
    "creé", "cree",
    "dirigí", "dirigi",
    "implemented",
    "led",
    "designed",
    "developed",
    "created",
    "directed",
}


def _extract_first_verb(text: str) -> str:
    """Extrae la primera palabra o verbo en minúsculas ignorando viñetas y puntuación."""
    cleaned = text.strip().lstrip("-*•·\t ").strip()
    tokens = cleaned.split()
    if not tokens:
        return ""
    return tokens[0].lower().strip(".,:;¿?¡!'\"()[]{}")


def _get_deterministic_bullet_fallback(bullet_text: str, is_en: bool = False) -> BulletItem:
    """Genera el respaldo determinista para una viñeta preservando el nivel colaborativo sin inventar."""
    cleaned = _clean_bullet_fallback(bullet_text, is_en=is_en)
    has_numbers = bool(re.search(r"\d+%?", bullet_text))
    if is_en:
        suggestion = None if has_numbers else "Can you quantify the result with a metric, percentage, or measurable outcome?"
    else:
        suggestion = None if has_numbers else "¿Puedes indicar el resultado obtenido o cuantificarlo con alguna métrica o porcentaje?"

    return BulletItem(
        original=bullet_text,
        improved=cleaned,
        suggestion=suggestion
    )


BULLET_ENHANCEMENT_SYSTEM_PROMPT_ES = """Eres un consultor de carrera y redactor experto en currículums de alto impacto (ATS).
Tu misión es optimizar la redacción de cada viñeta o responsabilidad laboral haciéndola concisa, profesional y de alto impacto, respetando estrictamente la veracidad del contenido original.

REGLAS ESTRICTAS DE REDACCIÓN:
1. CONSERVAR EL NIVEL DE PARTICIPACIÓN (REGLA FUNDAMENTAL):
   - Si la viñeta original indica apoyo, colaboración o asistencia ("ayudé", "colaboré", "participé", "apoyé", "asistí"):
     * NUNCA subas ni exageres el nivel de responsabilidad. “ayudé”, “colaboré” o “participé” NUNCA deben pasar a “implementé”, “lideré”, “diseñé”, “construí” ni “arquitecté”.
     * Conserva estrictamente el rol colaborativo utilizando verbos de acción colaborativos en pasado (ej. 'Colaboré en', 'Contribuí a', 'Apoyé en', 'Asistí en').
   - Solo cuando la viñeta original exprese autoría individual directa o liderazgo, utiliza verbos de acción individuales en pasado (ej. 'Implementé', 'Diseñé', 'Optimizé', 'Desplegué', 'Lideré').

2. NO AGREGAR RESULTADOS, BENEFICIOS, TECNOLOGÍAS NI DETALLES INVENTADOS:
   - NUNCA agregues tecnologías, herramientas, metodologías, clientes ni tareas que no figuren explícitamente en el texto original.
   - NUNCA inventes resultados, métricas, porcentajes, impactos ni frases genéricas de beneficio (como "para acelerar los despliegues", "mejorando la eficiencia operativa", "garantizando alta disponibilidad" o "estandarizando procesos") si el original no los menciona explícitamente.
   - Limítate con fidelidad absoluta a lo que el candidato realmente escribió.

3. FÓRMULA DE ESTRUCTURA:
   - Verbo de acción + Contexto real + Resultado (solo si el resultado ya está presente en el texto original).
   - Longitud máxima: 1 a 2 líneas (aproximadamente entre 100 y 180 caracteres).

4. SI FALTA UN RESULTADO O MÉTRICA, SOLICÍTALO EN LA SUGERENCIA ATS EN VEZ DE INVENTARLO:
   - Si la viñeta original NO incluye un resultado medible o métrica cuantitativa:
     * NO inventes ningún resultado ni consecuencia en el texto de "improved".
     * Genera una pregunta concreta y puntual en el campo "suggestion" pidiéndole al candidato el resultado o métrica faltante (ej. "¿Qué impacto, métrica o porcentaje de mejora obtuviste con esta tarea?").
   - Si la viñeta original ya contiene un resultado o métrica cuantitativa suficiente, el campo "suggestion" debe ser null.

5. PROHIBICIONES DE ESTILO:
   - Elimina frases pasivas o burocráticas como "responsable de", "encargado de", "encargada de", "mi rol era", "funciones incluían".

6. SIN REPETICIÓN: NO repitas ninguno de los verbos de acción ya utilizados en la misma experiencia.
7. IDIOMA: Redacta estrictamente en Español impecable y profesional.

Devuelve ÚNICAMENTE un objeto JSON con este formato:
{
  "improved": "Texto del bullet mejorado en español",
  "action_verb": "verbo utilizado en pasado (en minúsculas)",
  "suggestion": "Pregunta al usuario sobre la métrica o resultado faltante, o null si ya tenía resultados suficientes"
}"""

BULLET_ENHANCEMENT_SYSTEM_PROMPT_EN = """You are an executive career advisor and expert ATS resume writer.
Your mission is to optimize each bullet point or job duty into a concise, professional, high-impact achievement, strictly preserving truthfulness and factual accuracy.

STRICT WRITING RULES:
1. PRESERVE LEVEL OF INVOLVEMENT (CRITICAL RULE):
   - If the original bullet indicates support, collaboration, or participation ("helped", "assisted", "collaborated", "participated", "supported"):
     * NEVER elevate or exaggerate the level of responsibility. “helped”, “collaborated”, or “participated” must NEVER become “implemented”, “led”, “designed”, “architected”, or “spearheaded”.
     * Strictly preserve the collaborative role using strong collaborative action verbs in past tense (e.g., 'Collaborated on', 'Contributed to', 'Assisted with', 'Supported').
   - Only when the original bullet explicitly reflects direct individual ownership or leadership should you use direct individual action verbs in past tense (e.g., 'Engineered', 'Optimized', 'Deployed', 'Implemented', 'Led').

2. DO NOT ADD FABRICATED RESULTS, BENEFITS, TECHNOLOGIES, OR DETAILS:
   - NEVER add technologies, tools, methodologies, client names, or duties not present in the original text.
   - NEVER invent results, metrics, percentages, business impact, or generic benefit phrases (such as "to accelerate delivery cycles", "improving operational efficiency", "ensuring high availability", or "standardizing processes") unless explicitly stated in the source text.
   - Stick with absolute fidelity to what the candidate wrote.

3. STRUCTURE FORMULA:
   - Action Verb + Factual Context + Result (only if the result is already present in the original text).
   - Maximum 1-2 lines (approx 100-180 characters).

4. ASK FOR MISSING RESULTS IN ATS SUGGESTION INSTEAD OF INVENTING THEM:
   - If the original bullet DOES NOT include a measurable result or quantitative metric:
     * DO NOT fabricate any outcome or result in the "improved" bullet.
     * Generate a targeted, clear question in the "suggestion" field asking the candidate for the missing metric or outcome (e.g., 'What measurable impact, percentage improvement, or metric resulted from this?').
   - If the original bullet already includes sufficient measurable results or metrics, "suggestion" must be null.

5. PHRASING PROHIBITIONS:
   - Eliminate passive or bureaucratic phrasing like "responsible for", "in charge of", "my duties included", "worked on".

6. NO REPETITION: Do NOT repeat any action verbs already used within the same experience.
7. LANGUAGE: Write strictly in professional, flawless English.

Return ONLY a valid JSON object with this exact format:
{
  "improved": "Enhanced bullet point text in English",
  "action_verb": "action verb used in past tense (lowercase)",
  "suggestion": "Targeted question asking for missing result/metric, or null if already quantified"
}"""

SUMMARY_ENHANCEMENT_SYSTEM_PROMPT_ES = """Eres un consultor de carrera experto en redacción de perfiles profesionales para currículums de alto impacto (ATS).
Reescribe el resumen profesional del candidato haciéndolo conciso, directo y profesional:

REGLAS ESTRICTAS:
1. LONGITUD: Máximo 3 a 4 líneas (o 2 a 3 oraciones contundentes).
2. SIN FRASES GENÉRICAS DE RELLENO:
   - PROHIBIDO incluir frases genéricas de relleno, clichés y lugares comunes como: "orientado a resultados", "resolución de problemas complejos", "pensamiento estratégico", "gestión confiable", "apasionado por la tecnología", "excelentes habilidades interpersonales", "proactivo", "enfoque innovador", "capacidad de adaptación", "comprometido con la excelencia".
   - Cada oración debe basarse exclusivamente en hechos sustanciales: especialidad técnica, área de experiencia y trayectoria profesional del candidato.
3. FIDELIDAD ESTRICTA (NO INVENTAR):
   - NO agregues ni inventes años de experiencia, empresas, herramientas, tecnologías ni certificaciones que no aparezcan en el texto original.
   - No infles responsabilidades ni agregues superlativos vacíos no fundamentados.
4. IDIOMA: Estrictamente en Español impecable y profesional.

Devuelve ÚNICAMENTE un objeto JSON con este formato:
{
  "summary_improved": "Texto del resumen profesional mejorado en español"
}"""

SUMMARY_ENHANCEMENT_SYSTEM_PROMPT_EN = """You are an executive career consultant and ATS resume expert.
Rewrite the candidate's professional summary to make it concise, direct, and high-impact:

STRICT RULES:
1. LENGTH: Maximum 3 to 4 lines (or 2 to 3 strong sentences).
2. NO GENERIC FILLER PHRASES:
   - FORBIDDEN generic filler, buzzwords, and empty corporate clichés such as: "results-driven professional", "complex problem solver", "strategic thinker", "passionate technologist", "excellent communication skills", "proactive team player", "innovative mindset", "reliable data management", "committed to excellence".
   - Every sentence must be grounded in substantive facts: actual technical specialty, domain expertise, and factual experience.
3. STRICT FIDELITY (NO INVENTIONS):
   - DO NOT invent or add years of experience, companies, tools, technologies, or credentials not mentioned in the original text.
   - Do not exaggerate responsibilities or add unfounded superlatives.
4. LANGUAGE: Strictly in professional, flawless English.

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

        # Validación posterior: si el original empieza con un verbo de apoyo (ayudé, colaboré, participé, apoyé, asistí)
        # y la viñeta mejorada empieza con un verbo de autoría o liderazgo (implementé, lideré, diseñé, desarrollé, creé, dirigí),
        # descarta esa salida y usa el respaldo determinista para esa viñeta.
        orig_first_verb = _extract_first_verb(bullet_text)
        improved_first_verb = _extract_first_verb(improved_text)

        if orig_first_verb in SUPPORT_VERBS:
            if improved_first_verb in LEADERSHIP_AUTHORSHIP_VERBS or action_verb in LEADERSHIP_AUTHORSHIP_VERBS:
                logger.warning(
                    f"Salida del modelo descartada para viñeta '{bullet_text}': "
                    f"subió el nivel de participación a '{improved_text}'. Aplicando respaldo determinista."
                )
                fallback_item = _get_deterministic_bullet_fallback(bullet_text, is_en=is_en)
                fb_verb = _extract_first_verb(fallback_item.improved)
                if fb_verb:
                    used_verbs.add(fb_verb)
                return fallback_item

        # Registrar el verbo usado para evitar repetición en las siguientes viñetas de la misma experiencia
        if action_verb:
            used_verbs.add(action_verb)
        else:
            first_word = _extract_first_verb(improved_text)
            if first_word:
                used_verbs.add(first_word)

        return BulletItem(
            original=bullet_text,
            improved=improved_text,
            suggestion=suggestion if suggestion and suggestion.strip() else None
        )

    except Exception as e:
        logger.error(f"Error al mejorar viñeta con LLM: {e}", exc_info=True)
        # Fallback determinista seguro sin inventar nada y preservando nivel de participación
        return _get_deterministic_bullet_fallback(bullet_text, is_en=is_en)


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
        if deadline is not None and time.monotonic() >= deadline:
            logger.warning("Tope de tiempo alcanzado antes de mejorar resumen; conservando original.")
        else:
            resume.summary_improved = enhance_summary(resume.summary, provider, language=language, deadline=deadline)

    # 2. Mejorar bullets experiencia por experiencia
    for exp in resume.experience:
        used_verbs_for_this_company: Set[str] = set()
        new_bullets = []
        for b in exp.bullets:
            if deadline is not None and time.monotonic() >= deadline:
                logger.warning(f"Tope de tiempo alcanzado en {exp.company}; aplicando fallback determinista para viñetas.")
                new_bullets.append(_get_deterministic_bullet_fallback(b.original, is_en=is_en))
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
