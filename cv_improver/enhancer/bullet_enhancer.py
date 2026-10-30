"""
Lógica de mejora y reescritura de viñetas (bullets) y resumen profesional con IA.
Aplica estrictamente reglas ATS, verbos de acción, estructura Acción + Contexto + Resultado,
y la regla crítica anti-alucinación (nunca inventar métricas).
"""

import logging
import re
import time
import unicodedata
from typing import Optional, Set, Dict, Any, List, Tuple
from ..schema import ResumeSchema, ExperienceItem, BulletItem
from .provider_base import LLMProvider
from ai_client import AITimeBudgetExceeded

logger = logging.getLogger(__name__)

WEAK_PHRASES = [
    "responsable de hacer",
    "encargado de hacer",
    "encargada de hacer",
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


# ==============================================================================
# NIVELES DE RESPONSABILIDAD DE VERBOS (ANTI-EXAGERACIÓN)
# Nivel 1 (apoyo): helped, assisted, supported, collaborated, contributed, participated;
#                  ayudé, asistí, apoyé, colaboré, contribuí, participé.
# Nivel 2 (ejecución/gestión operativa): managed, administered, maintained, operated, handled,
#                  monitored, supervised, performed, implemented, designed, developed, created, oversaw;
#                  gestioné, administré, mantuve, operé, manejé, monitoreé, supervisé, realicé,
#                  implementé, diseñé, desarrollé, creé, ejecuté.
# Nivel 3 (liderazgo/dirección): led, directed, headed, spearheaded, orchestrated, championed;
#                  lideré, dirigí, encabecé, orquesté.
# Regla: La viñeta mejorada nunca puede usar un verbo de nivel superior al del original.
# Puede mantener el mismo verbo o usar un sinónimo del MISMO nivel.
# Si el verbo original no está en ningún nivel, la viñeta mejorada debe conservar ese mismo verbo.
# ==============================================================================

VERB_LEVEL_MAP: Dict[str, int] = {
    # Nivel 1 - Inglés
    "helped": 1, "help": 1, "helping": 1,
    "assisted": 1, "assist": 1, "assisting": 1,
    "supported": 1, "support": 1, "supporting": 1,
    "collaborated": 1, "collaborate": 1, "collaborating": 1,
    "contributed": 1, "contribute": 1, "contributing": 1,
    "participated": 1, "participate": 1, "participating": 1,
    # Nivel 1 - Español (con y sin tildes, gerundios e infinitivos)
    "ayudé": 1, "ayude": 1, "ayudar": 1, "ayudó": 1, "ayudo": 1, "ayudando": 1,
    "asistí": 1, "asisti": 1, "asistir": 1, "asistió": 1, "asisto": 1, "asistiendo": 1,
    "apoyé": 1, "apoye": 1, "apoyar": 1, "apoyó": 1, "apoyo": 1, "apoyando": 1,
    "colaboré": 1, "colabore": 1, "colaborar": 1, "colaboró": 1, "colaboro": 1, "colaborando": 1,
    "contribuí": 1, "contribui": 1, "contribuir": 1, "contribuyó": 1, "contribuyo": 1, "contribuyendo": 1,
    "participé": 1, "participe": 1, "participar": 1, "participó": 1, "participo": 1, "participando": 1,

    # Nivel 2 - Inglés
    "managed": 2, "manage": 2, "managing": 2,
    "administered": 2, "administer": 2, "administering": 2,
    "maintained": 2, "maintain": 2, "maintaining": 2,
    "operated": 2, "operate": 2, "operating": 2,
    "handled": 2, "handle": 2, "handling": 2,
    "monitored": 2, "monitor": 2, "monitoring": 2,
    "supervised": 2, "supervise": 2, "supervising": 2,
    "performed": 2, "perform": 2, "performing": 2,
    "implemented": 2, "implement": 2, "implementing": 2,
    "designed": 2, "design": 2, "designing": 2,
    "developed": 2, "develop": 2, "developing": 2,
    "created": 2, "create": 2, "creating": 2,
    "oversaw": 2, "oversee": 2, "overseeing": 2,
    # Nivel 2 - Español
    "gestioné": 2, "gestione": 2, "gestionar": 2, "gestionó": 2, "gestiono": 2, "gestionando": 2,
    "administré": 2, "administre": 2, "administrar": 2, "administró": 2, "administro": 2, "administrando": 2,
    "mantuve": 2, "mantener": 2, "mantuvo": 2, "mantengo": 2, "manteniendo": 2,
    "operé": 2, "opere": 2, "operar": 2, "operó": 2, "opero": 2, "operando": 2,
    "manejé": 2, "maneje": 2, "manejar": 2, "manejó": 2, "manejo": 2, "manejando": 2,
    "monitoreé": 2, "monitoree": 2, "monitorear": 2, "monitoreó": 2, "monitoreo": 2, "monitoreando": 2,
    "supervisé": 2, "supervise": 2, "supervisar": 2, "supervisó": 2, "superviso": 2, "supervisando": 2,
    "realicé": 2, "realice": 2, "realizar": 2, "realizó": 2, "realizo": 2, "realizando": 2,
    "implementé": 2, "implemente": 2, "implementar": 2, "implementó": 2, "implemento": 2, "implementando": 2,
    "diseñé": 2, "disene": 2, "disené": 2, "diseñe": 2, "diseñar": 2, "disenar": 2, "diseñó": 2, "diseno": 2, "diseño": 2, "diseñando": 2, "disenando": 2,
    "desarrollé": 2, "desarrolle": 2, "desarrollar": 2, "desarrolló": 2, "desarrollo": 2, "desarrollando": 2,
    "creé": 2, "cree": 2, "crear": 2, "creó": 2, "creo": 2, "creando": 2,
    "ejecuté": 2, "ejecute": 2, "ejecutar": 2, "ejecutó": 2, "ejecuto": 2, "ejecutando": 2,

    # Nivel 3 - Inglés
    "led": 3, "lead": 3, "leading": 3,
    "directed": 3, "direct": 3, "directing": 3,
    "headed": 3, "head": 3, "heading": 3,
    "spearheaded": 3, "spearhead": 3, "spearheading": 3,
    "orchestrated": 3, "orchestrate": 3, "orchestrating": 3,
    "championed": 3, "champion": 3, "championing": 3,
    # Nivel 3 - Español
    "lideré": 3, "lidere": 3, "liderar": 3, "lideró": 3, "lidero": 3, "liderando": 3,
    "dirigí": 3, "dirigi": 3, "dirigir": 3, "dirigió": 3, "dirijo": 3, "dirigiendo": 3,
    "encabecé": 3, "encabece": 3, "encabezar": 3, "encabezó": 3, "encabezo": 3, "encabezando": 3,
    "orquesté": 3, "orqueste": 3, "orquestar": 3, "orquestó": 3, "orquesto": 3, "orquestando": 3,
}

VERB_ROOT_MAP: Dict[str, str] = {
    # Nivel 1
    "helped": "help", "help": "help", "helping": "help",
    "assisted": "assist", "assist": "assist", "assisting": "assist",
    "supported": "support", "support": "support", "supporting": "support",
    "collaborated": "collaborate", "collaborate": "collaborate", "collaborating": "collaborate",
    "contributed": "contribute", "contribute": "contribute", "contributing": "contribute",
    "participated": "participate", "participate": "participate", "participating": "participate",
    "ayudé": "ayudar", "ayude": "ayudar", "ayudar": "ayudar", "ayudó": "ayudar", "ayudo": "ayudar", "ayudando": "ayudar",
    "asistí": "asistir", "asisti": "asistir", "asistir": "asistir", "asistió": "asistir", "asisto": "asistir", "asistiendo": "asistir",
    "apoyé": "apoyar", "apoye": "apoyar", "apoyar": "apoyar", "apoyó": "apoyar", "apoyo": "apoyar", "apoyando": "apoyar",
    "colaboré": "colaborar", "colabore": "colaborar", "colaborar": "colaborar", "colaboró": "colaborar", "colaboro": "colaborar", "colaborando": "colaborar",
    "contribuí": "contribuir", "contribui": "contribuir", "contribuir": "contribuir", "contribuyó": "contribuir", "contribuyo": "contribuir", "contribuyendo": "contribuir",
    "participé": "participar", "participe": "participar", "participar": "participar", "participó": "participar", "participo": "participar", "participando": "participar",

    # Nivel 2
    "managed": "manage", "manage": "manage", "managing": "manage",
    "administered": "administer", "administer": "administer", "administering": "administer",
    "maintained": "maintain", "maintain": "maintain", "maintaining": "maintain",
    "operated": "operate", "operate": "operate", "operating": "operate",
    "handled": "handle", "handle": "handle", "handling": "handle",
    "monitored": "monitor", "monitor": "monitor", "monitoring": "monitor",
    "supervised": "supervise", "supervise": "supervise", "supervising": "supervise",
    "performed": "perform", "perform": "perform", "performing": "perform",
    "implemented": "implement", "implement": "implement", "implementing": "implement",
    "designed": "design", "design": "design", "designing": "design",
    "developed": "develop", "develop": "develop", "developing": "develop",
    "created": "create", "create": "create", "creating": "create",
    "oversaw": "oversee", "oversee": "oversee", "overseeing": "oversee",
    "gestioné": "gestionar", "gestione": "gestionar", "gestionar": "gestionar", "gestionó": "gestionar", "gestiono": "gestionar", "gestionando": "gestionar",
    "administré": "administrar", "administre": "administrar", "administrar": "administrar", "administró": "administrar", "administro": "administrar", "administrando": "administrar",
    "mantuve": "mantener", "mantener": "mantener", "mantuvo": "mantener", "mantengo": "mantener", "manteniendo": "mantener",
    "operé": "operar", "opere": "operar", "operar": "operar", "operó": "operar", "opero": "operar", "operando": "operar",
    "manejé": "manejar", "maneje": "manejar", "manejar": "manejar", "manejó": "manejar", "manejo": "manejar", "manejando": "manejar",
    "monitoreé": "monitorear", "monitoree": "monitorear", "monitorear": "monitorear", "monitoreó": "monitorear", "monitoreo": "monitorear", "monitoreando": "monitorear",
    "supervisé": "supervisar", "supervise": "supervisar", "supervisar": "supervisar", "supervisó": "supervisar", "superviso": "supervisar", "supervisando": "supervisar",
    "realicé": "realizar", "realice": "realizar", "realizar": "realizar", "realizó": "realizar", "realizo": "realizar", "realizando": "realizar",
    "implementé": "implementar", "implemente": "implementar", "implementar": "implementar", "implementó": "implementar", "implemento": "implementar", "implementando": "implementar",
    "diseñé": "diseñar", "disene": "diseñar", "disené": "diseñar", "diseñe": "diseñar", "diseñar": "diseñar", "disenar": "diseñar", "diseñó": "diseñar", "diseno": "diseñar", "diseño": "diseñar", "diseñando": "diseñar", "disenando": "diseñar",
    "desarrollé": "desarrollar", "desarrolle": "desarrollar", "desarrollar": "desarrollar", "desarrolló": "desarrollar", "desarrollo": "desarrollar", "desarrollando": "desarrollar",
    "creé": "crear", "cree": "crear", "crear": "crear", "creó": "crear", "creo": "crear", "creando": "crear",
    "ejecuté": "ejecutar", "ejecute": "ejecutar", "ejecutar": "ejecutar", "ejecutó": "ejecutar", "ejecuto": "ejecutar", "ejecutando": "ejecutar",

    # Nivel 3
    "led": "lead", "lead": "lead", "leading": "lead",
    "directed": "direct", "direct": "direct", "directing": "direct",
    "headed": "head", "head": "head", "heading": "head",
    "spearheaded": "spearhead", "spearhead": "spearhead", "spearheading": "spearhead",
    "orchestrated": "orchestrate", "orchestrate": "orchestrate", "orchestrating": "orchestrate",
    "championed": "champion", "champion": "champion", "championing": "champion",
    "lideré": "liderar", "lidere": "liderar", "liderar": "liderar", "lideró": "liderar", "lidero": "liderar", "liderando": "liderar",
    "dirigí": "dirigir", "dirigi": "dirigir", "dirigir": "dirigir", "dirigió": "dirigir", "dirijo": "dirigir", "dirigiendo": "dirigir",
    "encabecé": "encabezar", "encabece": "encabezar", "encabezar": "encabezar", "encabezó": "encabezar", "encabezo": "encabezar", "encabezando": "encabezar",
    "orquesté": "orquestar", "orqueste": "orquestar", "orquestar": "orquestar", "orquestó": "orquestar", "orquesto": "orquestar", "orquestando": "orquestar",
}

# Compatibilidad con definiciones previas
SUPPORT_VERBS = {k for k, v in VERB_LEVEL_MAP.items() if v == 1}
LEADERSHIP_AUTHORSHIP_VERBS = {k for k, v in VERB_LEVEL_MAP.items() if v == 3}


def _normalize_stem(word: str) -> str:
    """Normaliza un verbo o palabra no catalogada para comparar raíces e inflexiones."""
    if not word:
        return ""
    w = word.lower().strip(".,:;¿?¡!'\"()[]{}")
    irregulars = {
        "troubleshooting": "troubleshoot",
        "troubleshot": "troubleshoot",
        "troubleshooted": "troubleshoot",
        "built": "build",
        "building": "build",
        "wrote": "write",
        "writing": "write",
        "written": "write",
        "ran": "run",
        "running": "run",
        "resolví": "resolver",
        "resolvi": "resolver",
        "resolviendo": "resolver",
        "resuelto": "resolver",
    }
    if w in irregulars:
        return irregulars[w]
    # Quitar marcas diacríticas / acentos
    w = "".join(
        c for c in unicodedata.normalize("NFD", w)
        if unicodedata.category(c) != "Mn"
    )
    w = w.replace("ñ", "n")
    # Sufijos comunes en español
    for suffix in ("ando", "iendo", "amos", "aron", "ieron", "aran", "aria", "arian", "arias", "aste", "ar", "er", "ir"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            w = w[:-len(suffix)]
            break
    # Sufijos comunes en inglés
    for suffix in ("ing", "ed", "es", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            w = w[:-len(suffix)]
            break
    # Desinencias vocálicas finales cortas
    if len(w) > 4 and w.endswith(("e", "o", "a", "i")):
        w = w[:-1]
    return w


NON_VERB_WORDS: Set[str] = {
    # Artículos, determinantes y pronombres
    "el", "la", "los", "las", "un", "una", "unos", "unas", "the", "a", "an",
    "mi", "mis", "su", "sus", "nuestro", "nuestra", "nuestros", "nuestras", "my", "our", "their", "this", "that", "these", "those",
    # Preposiciones y conjunciones
    "de", "en", "para", "por", "con", "sin", "sobre", "of", "in", "for", "on", "at", "to", "with", "without", "from", "by", "and", "y",
    # Adjetivos y numerales
    "primera", "primero", "primer", "primeras", "primeros", "segunda", "segundo", "segundas", "segundos",
    "tercera", "tercero", "otra", "otro", "otras", "otros", "nuevo", "nueva", "nuevos", "nuevas",
    "first", "second", "third", "other", "another", "each", "every", "new",
    # Sustantivos comunes iniciales de viñetas (descripciones pasivas / nominales)
    "responsabilidad", "responsabilidades", "tarea", "tareas", "función", "funciones", "rol", "roles",
    "proyecto", "proyectos", "optimización", "optimizacion", "desarrollo", "mantenimiento", "soporte",
    "gestión", "gestion", "administración", "administracion", "análisis", "analisis", "diseño", "diseno",
    "implementación", "implementacion", "configuración", "configuracion", "revisión", "revision",
    "creación", "creacion", "automatización", "automatizacion", "documentación", "documentacion",
    "resolución", "resolucion", "atención", "atencion",
    "duty", "duties", "task", "tasks", "responsibility", "responsibilities", "project", "projects",
    "optimization", "maintenance", "support", "management", "administration", "analysis", "design",
    "implementation", "configuration", "review", "creation", "automation", "documentation", "resolution",
    # Verbos genéricos comodines pasivos (no son verbos de acción específicos ATS)
    "hacer", "do", "make"
}


def _is_likely_verb(word: str) -> bool:
    """Determina si una palabra inicial funciona como verbo (y no como sustantivo, artículo o adjetivo)."""
    if not word:
        return False
    w = word.lower().strip(".,:;¿?¡!'\"()[]{}")
    if w in VERB_LEVEL_MAP:
        return True
    if w in NON_VERB_WORDS:
        return False
    # Verbos irregulares o comunes en IT
    known_irregulars = {
        "troubleshot", "troubleshoot", "troubleshooting", "built", "build", "building",
        "wrote", "write", "writing", "ran", "run", "running", "held", "sent", "kept",
        "resuelto", "resolví", "resolvi", "resolviendo", "resolver", "diagnosticamos",
        "diagnosticó", "diagnostico", "diagnosticar", "diagnosticando", "configuré",
        "configure", "configurar", "configurando", "auditamos", "audité", "audite", "auditar"
    }
    if w in known_irregulars:
        return True
    # Terminaciones verbales explícitas en inglés
    if len(w) > 4 and w.endswith(("ed", "ing")):
        return True
    # Terminaciones verbales explícitas en español
    if len(w) > 4:
        if w.endswith(("ando", "iendo", "aron", "ieron", "amos", "aste", "iste")):
            return True
        if w.endswith(("ar", "er", "ir", "é", "í", "ó")):
            return True
    return False


def _get_verb_level_and_root(verb: str) -> Tuple[Optional[int], str]:
    """Retorna (nivel, raíz_canonica) para un verbo dado."""
    v = (verb or "").lower().strip(".,:;¿?¡!'\"()[]{}")
    if not v:
        return None, ""
    if v in VERB_LEVEL_MAP:
        return VERB_LEVEL_MAP[v], VERB_ROOT_MAP.get(v, v)
    return None, _normalize_stem(v)


def _extract_first_verb(text: str) -> str:
    """Extrae la primera palabra o verbo en minúsculas ignorando viñetas, puntuación y frases pasivas."""
    if not text:
        return ""
    cleaned = text.strip().lstrip("-*•·\t 0123456789.)").strip()
    cleaned_lower = cleaned.lower()
    for phrase in WEAK_PHRASES:
        if cleaned_lower.startswith(phrase):
            cleaned = cleaned[len(phrase):].strip().lstrip("-*•·\t :,").strip()
            break
    tokens = cleaned.split()
    if not tokens:
        return ""
    return tokens[0].lower().strip(".,:;¿?¡!'\"()[]{}")


def validate_verb_enhancement(
    orig_text: str,
    improved_text: str,
    action_verb: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Valida que la viñeta mejorada no aumente la autoridad ni el alcance del verbo original:
    - Nivel 1 (apoyo): helped, assisted, supported, collaborated, contributed, participated;
      ayudé, asistí, apoyé, colaboré, contribuí, participé.
    - Nivel 2 (ejecución/gestión operativa): managed, administered, maintained, operated, handled,
      monitored, supervised, performed, implemented, designed, developed, created, oversaw;
      gestioné, administré, mantuve, operé, manejé, monitoreé, supervisé, realicé,
      implementé, diseñé, desarrollé, creé, ejecuté.
    - Nivel 3 (liderazgo/dirección): led, directed, headed, spearheaded, orchestrated, championed;
      lideré, dirigí, encabecé, orquesté.

    Reglas:
    1. La viñeta mejorada nunca puede usar un verbo de nivel superior al del verbo original.
    2. Puede mantener el mismo verbo, o usar un sinónimo del MISMO nivel.
    3. Si el verbo original no está en ningún nivel, la viñeta mejorada debe conservar ese mismo verbo.
    """
    orig_verb = _extract_first_verb(orig_text)
    if not orig_verb:
        return True, "Sin verbo original identificable"

    improved_verb = _extract_first_verb(improved_text)
    action_v = (action_verb or "").lower().strip()

    orig_level, orig_root = _get_verb_level_and_root(orig_verb)
    improved_level, improved_root = _get_verb_level_and_root(improved_verb)

    if action_v:
        av_level, av_root = _get_verb_level_and_root(action_v)
    else:
        av_level, av_root = None, None

    cand_levels = [lvl for lvl in (improved_level, av_level) if lvl is not None]
    effective_improved_level = max(cand_levels) if cand_levels else None

    # Caso 1: El verbo original pertenece a un nivel catalogado (1, 2 o 3)
    if orig_level is not None:
        if effective_improved_level is not None and effective_improved_level > orig_level:
            return False, (
                f"Exageración detectada: verbo original '{orig_verb}' (Nivel {orig_level}) "
                f"escaló a '{improved_verb or action_v}' (Nivel {effective_improved_level})."
            )
        # Si el verbo mejorado no está en la taxonomía pero sustituyó al original
        if effective_improved_level is None and orig_root != improved_root and orig_root != av_root:
            return False, (
                f"Verbo original '{orig_verb}' (Nivel {orig_level}) fue sustituido por "
                f"verbo no homologado '{improved_verb or action_v}'."
            )
        return True, "Nivel de responsabilidad respetado"

    # Caso 2: El texto original no empezaba con un verbo catalogado.
    # Si era una frase nominal o pasiva (no verbo), se permite optimizar con verbo de ejecución (Nivel <= 2),
    # pero nunca atribuir liderazgo (Nivel 3).
    if not _is_likely_verb(orig_verb):
        if effective_improved_level is not None and effective_improved_level > 2:
            return False, (
                f"Exageración detectada: texto sin verbo de liderazgo escaló a "
                f"verbo de Nivel 3 '{improved_verb or action_v}'."
            )
        return True, "Texto nominal u operativo mejorado válidamente"

    # Caso 3: El verbo original es un verbo no catalogado (desconocido)
    # Regla: debe conservar exactamente ese mismo verbo
    if orig_root == improved_root or (av_root and orig_root == av_root):
        return True, "Mismo verbo original conservado"

    return False, (
        f"Verbo no catalogado '{orig_verb}' debe conservarse exactamente; "
        f"se intentó cambiar a '{improved_verb or action_v}'."
    )


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
1. CONSERVAR EL NIVEL DE RESPONSABILIDAD (REGLA FUNDAMENTAL ANTI-EXAGERACIÓN):
   - No aumentes la autoridad ni el alcance del verbo original; conserva el nivel de responsabilidad.
   - Nivel 1 (apoyo/colaboración: 'ayudé', 'asistí', 'apoyé', 'colaboré', 'contribuí', 'participé'):
     NUNCA subas ni exageres el nivel. NUNCA deben pasar a Nivel 2 ('gestioné', 'implementé', 'diseñé') ni a Nivel 3 ('lideré', 'dirigí').
   - Nivel 2 (ejecución/gestión operativa: 'gestioné', 'administré', 'mantuve', 'operé', 'manejé', 'monitoreé', 'supervisé', 'realicé', 'implementé', 'diseñé', 'desarrollé', 'creé'):
     Conserva el mismo verbo o usa un sinónimo del MISMO nivel. NUNCA subas a Nivel 3 ('lideré', 'dirigí', 'encabecé', 'orquesté').
   - Nivel 3 (liderazgo/dirección: 'lideré', 'dirigí', 'encabecé', 'orquesté').
   - Si el verbo original no pertenece a estos niveles, conserva obligatoriamente ese mismo verbo.

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
1. PRESERVE RESPONSIBILITY LEVEL (CRITICAL ANTI-EXAGGERATION RULE):
   - No aumentes la autoridad ni el alcance del verbo original; conserva el nivel de responsabilidad.
   - Do not elevate the authority or scope of the original verb; maintain the responsibility level.
   - Level 1 (support/collaboration: 'helped', 'assisted', 'supported', 'collaborated', 'contributed', 'participated'):
     NEVER elevate to Level 2 ('managed', 'implemented', 'designed') or Level 3 ('led', 'directed', 'spearheaded').
   - Level 2 (execution/operational management: 'managed', 'administered', 'maintained', 'operated', 'handled', 'monitored', 'supervised', 'performed', 'implemented', 'designed', 'developed', 'created', 'oversaw'):
     Keep the same verb or use a synonym of the SAME level (e.g., 'Managed' can become 'Administered' or 'Maintained', never 'Directed' or 'Led').
   - Level 3 (leadership/direction: 'led', 'directed', 'headed', 'spearheaded', 'orchestrated', 'championed').
   - If the original verb is not in these lists, strictly preserve the exact same verb.

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

BATCH_BULLET_ENHANCEMENT_SYSTEM_PROMPT_ES = """Eres un consultor de carrera y redactor experto en currículums de alto impacto (ATS).
Tu misión es optimizar una lista de viñetas o responsabilidades laborales haciéndolas concisas, profesionales y de alto impacto, respetando estrictamente la veracidad del contenido original.

REGLAS ESTRICTAS DE REDACCIÓN:
1. CONSERVAR EL NIVEL DE RESPONSABILIDAD (REGLA FUNDAMENTAL ANTI-EXAGERACIÓN):
   - No aumentes la autoridad ni el alcance del verbo original; conserva el nivel de responsabilidad.
   - Nivel 1 (apoyo/colaboración: 'ayudé', 'asistí', 'apoyé', 'colaboré', 'contribuí', 'participé'):
     NUNCA subas ni exageres el nivel. NUNCA deben pasar a Nivel 2 ('gestioné', 'implementé', 'diseñé') ni a Nivel 3 ('lideré', 'dirigí').
   - Nivel 2 (ejecución/gestión operativa: 'gestioné', 'administré', 'mantuve', 'operé', 'manejé', 'monitoreé', 'supervisé', 'realicé', 'implementé', 'diseñé', 'desarrollé', 'creé'):
     Conserva el mismo verbo o usa un sinónimo del MISMO nivel. NUNCA subas a Nivel 3 ('lideré', 'dirigí', 'encabecé', 'orquesté').
   - Nivel 3 (liderazgo/dirección: 'lideré', 'dirigí', 'encabecé', 'orquesté').
   - Si el verbo original no pertenece a estos niveles, conserva obligatoriamente ese mismo verbo.

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
     * Genera una pregunta concreta y puntual en el campo "suggestion" pidiéndole al candidato el resultado o métrica faltante.
   - Si la viñeta original ya contiene un resultado o métrica cuantitativa suficiente, el campo "suggestion" debe ser null.

5. PROHIBICIONES DE ESTILO:
   - Elimina frases pasivas o burocráticas como "responsable de", "encargado de", "encargada de", "mi rol era", "funciones incluían".

6. SIN REPETICIÓN: Evita repetir verbos de acción dentro de la misma experiencia.
7. IDIOMA: Redacta estrictamente en Español impecable y profesional.

8. ESQUEMA DE SALIDA:
   Devuelve ÚNICAMENTE un objeto JSON con la clave "bullets" que contenga una lista con exactamente el mismo número de viñetas que la entrada, en el mismo orden, respetando su identificador numérico "id":
{
  "bullets": [
    {
      "id": 1,
      "improved": "Texto del bullet mejorado en español",
      "action_verb": "verbo utilizado en pasado (en minúsculas)",
      "suggestion": "Pregunta sobre métrica faltante o null si ya tenía resultados suficientes"
    }
  ]
}"""

BATCH_BULLET_ENHANCEMENT_SYSTEM_PROMPT_EN = """You are an executive career advisor and expert ATS resume writer.
Your mission is to optimize a list of bullet points or job duties into concise, professional, high-impact achievements, strictly preserving truthfulness and factual accuracy.

STRICT WRITING RULES:
1. PRESERVE RESPONSIBILITY LEVEL (CRITICAL ANTI-EXAGGERATION RULE):
   - No aumentes la autoridad ni el alcance del verbo original; conserva el nivel de responsabilidad.
   - Do not elevate the authority or scope of the original verb; maintain the responsibility level.
   - Level 1 (support/collaboration: 'helped', 'assisted', 'supported', 'collaborated', 'contributed', 'participated'):
     NEVER elevate to Level 2 ('managed', 'implemented', 'designed') or Level 3 ('led', 'directed', 'spearheaded').
   - Level 2 (execution/operational management: 'managed', 'administered', 'maintained', 'operated', 'handled', 'monitored', 'supervised', 'performed', 'implemented', 'designed', 'developed', 'created', 'oversaw'):
     Keep the same verb or use a synonym of the SAME level (e.g., 'Managed' can become 'Administered' or 'Maintained', never 'Directed' or 'Led').
   - Level 3 (leadership/direction: 'led', 'directed', 'headed', 'spearheaded', 'orchestrated', 'championed').
   - If the original verb is not in these lists, strictly preserve the exact same verb.

2. DO NOT ADD FABRICATED RESULTS, BENEFITS, TECHNOLOGIES, OR DETAILS:
   - NEVER add technologies, tools, methodologies, client names, or duties not present in the original text.
   - NEVER invent results, metrics, percentages, business impact, or generic benefit phrases unless explicitly stated in the source text.
   - Stick with absolute fidelity to what the candidate wrote.

3. STRUCTURE FORMULA:
   - Action Verb + Factual Context + Result (only if the result is already present in the original text).
   - Maximum 1-2 lines (approx 100-180 characters).

4. ASK FOR MISSING RESULTS IN ATS SUGGESTION INSTEAD OF INVENTING THEM:
   - If the original bullet DOES NOT include a measurable result or quantitative metric:
     * DO NOT fabricate any outcome or result in the "improved" bullet.
     * Generate a targeted, clear question in the "suggestion" field asking the candidate for the missing metric or outcome.
   - If the original bullet already includes sufficient measurable results or metrics, "suggestion" must be null.

5. PHRASING PROHIBITIONS:
   - Eliminate passive or bureaucratic phrasing like "responsible for", "in charge of", "my duties included", "worked on".

6. NO REPETITION: Avoid repeating action verbs within the same company.
7. LANGUAGE: Write strictly in professional, flawless English.

8. MANDATORY OUTPUT SCHEMA:
   Return ONLY a valid JSON object with a "bullets" array matching the exact number and order of input bullets, preserving each bullet's "id":
{
  "bullets": [
    {
      "id": 1,
      "improved": "Enhanced bullet point text in English",
      "action_verb": "action verb used in past tense (lowercase)",
      "suggestion": "Targeted question asking for missing result/metric, or null if already quantified"
    }
  ]
}"""


def _format_batch_prompt(total_bullets: List[Dict[str, Any]], is_en: bool = False) -> str:
    """Construye el prompt en lote con identificadores claros para cada viñeta."""
    if is_en:
        lines = [
            "Please enhance the following bullet points following all strict ATS guidelines.",
            "Return a JSON object with a 'bullets' array preserving exact IDs and order:\n"
        ]
        for b in total_bullets:
            lines.append(
                f"- [id: {b['id']}] Company: {b['company']} | Position: {b['position']} | Original: \"{b['original'].strip()}\""
            )
        lines.append("\nGenerate the JSON output now.")
        return "\n".join(lines)
    else:
        lines = [
            "Optimiza la siguiente lista de viñetas siguiendo todas las reglas ATS.",
            "Devuelve un objeto JSON con la clave 'bullets' conservando exactamente los IDs y el orden:\n"
        ]
        for b in total_bullets:
            lines.append(
                f"- [id: {b['id']}] Empresa: {b['company']} | Cargo: {b['position']} | Viñeta original: \"{b['original'].strip()}\""
            )
        lines.append("\nGenera el JSON de salida ahora.")
        return "\n".join(lines)


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
        improved_raw = data.get("improved")
        if not improved_raw or not isinstance(improved_raw, str) or not improved_raw.strip():
            logger.warning(f"Respuesta de IA sin campo 'improved' válido para viñeta '{bullet_text}'. Aplicando fallback.")
            return _get_deterministic_bullet_fallback(bullet_text, is_en=is_en)
        improved_text = improved_raw.strip()
        suggestion = data.get("suggestion")
        action_verb = (data.get("action_verb") or "").lower().strip()

        # Validación posterior de nivel de responsabilidad (anti-exageración)
        is_valid, reason = validate_verb_enhancement(bullet_text, improved_text, action_verb)
        if not is_valid:
            logger.warning(
                f"Salida del modelo rechazada por validación de verbos para viñeta '{bullet_text}': {reason}. "
                f"Reintentando con instrucción estricta de conservar el verbo original..."
            )
            # Reintento estricto una vez si el deadline lo permite
            can_retry = (deadline is None or time.monotonic() < deadline)
            if can_retry:
                if is_en:
                    retry_prompt = f"""Company: {company}
Position: {position}
Original bullet point:
"{bullet_text.strip()}"

CRITICAL INSTRUCTION - STRICT VERB RETRY:
The previous attempt failed: {reason}.
No aumentes la autoridad ni el alcance del verbo original; conserva el nivel de responsabilidad.
Do not elevate the authority or scope of the original verb; maintain the responsibility level.
You MUST preserve the exact original verb or use a synonym of the same responsibility level.
Generate the JSON with the enhanced bullet point in English and the targeted metric suggestion if applicable."""
                else:
                    retry_prompt = f"""Empresa: {company}
Cargo: {position}
Viñeta original:
"{bullet_text.strip()}"

INSTRUCCIÓN CRÍTICA - REINTENTO DE VERBO ESTRICTO:
El intento anterior fue rechazado: {reason}.
No aumentes la autoridad ni el alcance del verbo original; conserva el nivel de responsabilidad.
Conserva OBLIGATORIAMENTE el verbo original o un sinónimo del mismo nivel de responsabilidad.
Genera el JSON con el bullet mejorado en español y la sugerencia de métrica si aplica."""

                try:
                    retry_data = provider.generate_json(
                        prompt=retry_prompt,
                        system_prompt=sys_prompt,
                        temperature=0.1,
                        deadline=deadline
                    )
                    retry_improved = (retry_data.get("improved") or "").strip()
                    retry_action = (retry_data.get("action_verb") or "").lower().strip()
                    retry_sug = retry_data.get("suggestion")

                    retry_valid, retry_reason = validate_verb_enhancement(bullet_text, retry_improved, retry_action)
                    if retry_valid:
                        improved_text = retry_improved
                        action_verb = retry_action
                        suggestion = retry_sug
                        is_valid = True
                    else:
                        logger.warning(
                            f"Reintento falló validación de verbos ({retry_reason}). "
                            f"Devolviendo viñeta original sin cambios."
                        )
                except Exception as retry_err:
                    logger.warning(f"Error en reintento de mejora de viñeta: {retry_err}")

            if not is_valid:
                # Si volvió a fallar o no hubo tiempo: devolver viñeta original sin cambios
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

    Reglas de procesamiento:
    (1) Procesa todas las viñetas en una sola llamada en lote con timeout_per_call=45 y el deadline de la operación.
    (2) Salida en JSON validado con esquema fijo: mismo número de viñetas que la entrada, mismo orden y un identificador por viñeta.
    (3) Si el JSON es inválido o falta alguna viñeta, usa el respaldo de una llamada por viñeta solo para las que falten, respetando el deadline.
    (4) Conserva las reglas del prompt: no inventar cifras, tecnologías ni beneficios, y no subir el nivel de participación.
    (5) Aplica a cada viñeta del lote la validación en código que descarta salidas que suben de verbo de apoyo a verbo de autoría, usando el respaldo determinista para esa viñeta.
    """
    is_en = (language == "en")

    # 1. Mejorar resumen profesional
    if resume.summary:
        if deadline is not None and time.monotonic() >= deadline:
            logger.warning("Tope de tiempo alcanzado antes de mejorar resumen; conservando original.")
        else:
            resume.summary_improved = enhance_summary(resume.summary, provider, language=language, deadline=deadline)

    # 2. Recopilar todas las viñetas de todas las experiencias para procesar en lote
    total_bullets: List[Dict[str, Any]] = []
    for exp_idx, exp in enumerate(resume.experience):
        for b_idx, b in enumerate(exp.bullets):
            total_bullets.append({
                "id": len(total_bullets) + 1,
                "exp_idx": exp_idx,
                "b_idx": b_idx,
                "company": exp.company,
                "position": exp.position,
                "original": b.original
            })

    if not total_bullets:
        return resume

    # Si el tiempo ya expiró antes de iniciar las viñetas, aplicar determinista directo
    if deadline is not None and time.monotonic() >= deadline:
        logger.warning("Tope de tiempo alcanzado antes de procesar viñetas; aplicando fallback determinista.")
        for exp in resume.experience:
            exp.bullets = [_get_deterministic_bullet_fallback(b.original, is_en=is_en) for b in exp.bullets]
        return resume

    # Regla (1): Una sola llamada en lote con timeout_per_call=45 y el deadline de la operación
    batch_data = None
    batch_prompt = _format_batch_prompt(total_bullets, is_en=is_en)
    batch_sys_prompt = BATCH_BULLET_ENHANCEMENT_SYSTEM_PROMPT_EN if is_en else BATCH_BULLET_ENHANCEMENT_SYSTEM_PROMPT_ES

    try:
        batch_data = provider.generate_json(
            prompt=batch_prompt,
            system_prompt=batch_sys_prompt,
            temperature=0.2,
            deadline=deadline,
            timeout_per_call=45.0
        )
    except AITimeBudgetExceeded:
        logger.warning("Tope de tiempo (deadline) agotado durante llamada por lote de viñetas.")
        batch_data = None
    except Exception as batch_err:
        logger.warning(f"Error en llamada por lote de viñetas: {batch_err}. Se recurrirá al respaldo para las viñetas.")
        batch_data = None

    # Regla (2): salida en JSON validado con esquema fijo: mismo número de viñetas que la entrada,
    # mismo orden y un identificador por viñeta.
    raw_bullets = None
    if isinstance(batch_data, dict):
        raw_bullets = batch_data.get("bullets")
    elif isinstance(batch_data, list):
        raw_bullets = batch_data

    validated_batch_by_id: Dict[int, Dict[str, Any]] = {}
    if isinstance(raw_bullets, list):
        # Mapeo por ID numérico explícito
        for entry in raw_bullets:
            if isinstance(entry, dict) and "id" in entry:
                try:
                    b_id = int(entry["id"])
                    if entry.get("improved"):
                        validated_batch_by_id[b_id] = entry
                except (ValueError, TypeError):
                    pass
        # Si no coincidieron por ID pero la longitud y orden corresponden exactamente a total_bullets:
        if not validated_batch_by_id and len(raw_bullets) == len(total_bullets):
            for idx, entry in enumerate(raw_bullets):
                if isinstance(entry, dict) and entry.get("improved"):
                    validated_batch_by_id[total_bullets[idx]["id"]] = entry

    # Procesar viñeta por viñeta aplicando reglas (3), (4) y (5)
    used_verbs_by_exp: Dict[int, Set[str]] = {idx: set() for idx in range(len(resume.experience))}
    processed_bullets: Dict[int, BulletItem] = {}

    for b_info in total_bullets:
        b_id = b_info["id"]
        exp_idx = b_info["exp_idx"]
        orig_text = b_info["original"]
        used_verbs = used_verbs_by_exp[exp_idx]

        if b_id in validated_batch_by_id:
            # (4) y (5) Viñeta presente en el lote validado
            item_dict = validated_batch_by_id[b_id]
            improved_text = (item_dict.get("improved") or orig_text).strip()
            sug = item_dict.get("suggestion")
            suggestion = sug.strip() if (isinstance(sug, str) and sug.strip()) else None
            action_verb = (item_dict.get("action_verb") or "").lower().strip() if isinstance(item_dict.get("action_verb"), str) else ""

            # Regla (5): validación compartida anti-exageración de nivel de responsabilidad
            is_valid, reason = validate_verb_enhancement(orig_text, improved_text, action_verb)
            if not is_valid:
                logger.warning(
                    f"Viñeta lote id {b_id} rechazada por validación de verbos: {reason}. "
                    f"Reintentando con instrucción estricta..."
                )
                if deadline is not None and time.monotonic() >= deadline:
                    logger.warning(f"Deadline alcanzado antes de reintentar viñeta id {b_id}; aplicando determinista.")
                    processed_bullets[b_id] = _get_deterministic_bullet_fallback(orig_text, is_en=is_en)
                else:
                    try:
                        single_item = improve_bullet_point(
                            bullet_text=orig_text,
                            company=b_info["company"],
                            position=b_info["position"],
                            used_verbs=used_verbs,
                            provider=provider,
                            language=language,
                            deadline=deadline
                        )
                        processed_bullets[b_id] = single_item
                    except Exception as err:
                        logger.error(f"Error en reintento individual para viñeta id {b_id}: {err}")
                        processed_bullets[b_id] = _get_deterministic_bullet_fallback(orig_text, is_en=is_en)
            else:
                if action_verb:
                    used_verbs.add(action_verb)
                else:
                    first_word = _extract_first_verb(improved_text)
                    if first_word:
                        used_verbs.add(first_word)

                processed_bullets[b_id] = BulletItem(
                    original=orig_text,
                    improved=improved_text,
                    suggestion=suggestion
                )
        else:
            # Regla (3): falta la viñeta o JSON inválido -> usar respaldo de una llamada por viñeta
            # solo para las que falten, respetando el deadline
            if deadline is not None and time.monotonic() >= deadline:
                logger.warning(f"Deadline alcanzado antes de respaldar viñeta id {b_id}; aplicando determinista.")
                processed_bullets[b_id] = _get_deterministic_bullet_fallback(orig_text, is_en=is_en)
            else:
                try:
                    single_item = improve_bullet_point(
                        bullet_text=orig_text,
                        company=b_info["company"],
                        position=b_info["position"],
                        used_verbs=used_verbs,
                        provider=provider,
                        language=language,
                        deadline=deadline
                    )
                    processed_bullets[b_id] = single_item
                except AITimeBudgetExceeded:
                    logger.warning(f"Tope de tiempo (deadline) superado al respaldar viñeta id {b_id}.")
                    processed_bullets[b_id] = _get_deterministic_bullet_fallback(orig_text, is_en=is_en)
                except Exception as err:
                    logger.error(f"Error en respaldo individual para viñeta id {b_id}: {err}")
                    processed_bullets[b_id] = _get_deterministic_bullet_fallback(orig_text, is_en=is_en)

    # Reconstruir las viñetas en la estructura original de experiencias
    for exp_idx, exp in enumerate(resume.experience):
        exp.bullets = [
            processed_bullets[b_info["id"]]
            for b_info in total_bullets
            if b_info["exp_idx"] == exp_idx
        ]

    return resume
