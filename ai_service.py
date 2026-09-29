# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 5: Servicio de Inteligencia Artificial con Gemini LLM (ai_service.py)
# ==============================================================================

import os
import re
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import google.generativeai as genai

from database import SKILL_CATEGORIES

# Cargar variables de entorno desde el archivo .env en el directorio actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

logger = logging.getLogger(__name__)


def get_api_key() -> Optional[str]:
    """
    Obtiene la API key de Gemini buscando en orden:
    1. Variable de entorno GEMINI_API_KEY
    2. Variable de entorno GOOGLE_API_KEY
    """
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def get_generative_model(api_key: str) -> genai.GenerativeModel:
    """
    Selecciona el mejor modelo disponible para la API Key dada,
    consultando genai.list_models() para evitar errores 404 por incompatibilidad de versión.
    """
    genai.configure(api_key=api_key)

    candidatos_preferidos = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-pro"
    ]

    try:
        # Consultamos qué modelos soporta esta API Key en particular
        modelos_disponibles = []
        for m in genai.list_models():
            metodos = getattr(m, "supported_generation_methods", [])
            if "generateContent" in metodos:
                modelos_disponibles.append(m.name)

        if modelos_disponibles:
            # Buscamos si alguno de nuestros preferidos está en los disponibles
            for cand in candidatos_preferidos:
                for disp in modelos_disponibles:
                    # m.name suele venir como "models/gemini-1.5-flash"
                    if cand == disp or f"models/{cand}" == disp:
                        return genai.GenerativeModel(disp, generation_config={"temperature": 0.2})
            
            # Si no coincide ninguno preferido, usamos el primero que soporte generateContent
            return genai.GenerativeModel(modelos_disponibles[0], generation_config={"temperature": 0.2})
    except Exception as err:
        logger.warning(f"No se pudo consultar list_models(): {err}")

    # Fallback predeterminado si list_models falla por permisos
    return genai.GenerativeModel("gemini-1.5-flash-latest", generation_config={"temperature": 0.2})


def extract_skills_and_profile_from_resume(resume_text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Envía el texto del currículum al LLM con un prompt estrictamente formateado
    para extraer información del perfil y clasificar las habilidades en un JSON estructurado.
    
    Técnicas aplicadas:
    - Zero-shot / Structured schema instruction
    - Lista blanca forzada de 14 categorías estándar
    - Cascada de modelos (gemini-3.5-flash -> 3.6 -> 3.8 -> latest)
    - Parseo defensivo de JSON con manejo de excepciones
    """
    key = api_key or get_api_key()
    if not key:
        raise ValueError(
            "No se encontró la clave de API de Gemini (GEMINI_API_KEY). "
            "Por favor ingrésala en la pantalla o agrégala en tu archivo .env."
        )

    genai.configure(api_key=key)

    categorias_permitidas_str = ", ".join(f'"{cat}"' for cat in SKILL_CATEGORIES)

    prompt = f"""
Eres un reclutador técnico senior y experto en análisis de perfiles de tecnología.
Tu tarea es analizar el siguiente texto extraído de un currículum vitae (Resume/CV) y extraer:
1. Datos generales del profesional (Nombre completo, título actual, email, teléfono, ubicación y un breve resumen).
2. Todas las tecnologías, herramientas, metodologías, certificaciones y habilidades blandas identificadas.

CATEGORÍAS PERMITIDAS PARA CADA HABILIDAD:
Debes clasificar OBLIGATORIAMENTE cada habilidad en exactamente una de estas categorías:
[{categorias_permitidas_str}]

NIVELES DE PROFICIENCY PERMITIDOS:
- "Beginner": mencionado brevemente o en cursos iniciales.
- "Intermediate": uso regular profesional comprobable en proyectos.
- "Advanced": 4+ años de experiencia, roles de liderazgo, arquitectura o especialidad principal.
Si no puedes determinar con certeza el nivel, asigna "Intermediate".

REGLAS ESTRICTAS DE RESPUESTA:
- Responde ÚNICAMENTE con un objeto JSON válido.
- NO agregues texto conversacional, ni explicaciones, ni bloques de código markdown como ```json ... ```.
- Sigue exactamente esta estructura:

{{
  "profile": {{
    "full_name": "Nombre completo o null",
    "current_title": "Puesto actual o más reciente o null",
    "email": "Email o null",
    "phone": "Teléfono o null",
    "location": "Ubicación geográfica o null",
    "summary": "Resumen profesional sintético de 2 o 3 oraciones"
  }},
  "skills": [
    {{
      "skill_name": "Nombre de la tecnología/herramienta (ej. Linux, AWS, Docker, Python)",
      "category": "Una de las categorías permitidas arriba",
      "proficiency": "Beginner, Intermediate o Advanced"
    }}
  ]
}}

TEXTO DEL CURRÍCULUM A ANALIZAR:
\"\"\"
{resume_text}
\"\"\"
"""

    # Cascada de modelos activos para evitar 404 de modelos retirados y 503 por picos de demanda
    modelos_a_probar = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
        "gemini-flash-latest"
    ]

    raw_text = None
    ultimo_error = None

    for nombre_modelo in modelos_a_probar:
        try:
            logger.info(f"Intentando llamar a Gemini con modelo: {nombre_modelo}...")
            model = genai.GenerativeModel(
                model_name=nombre_modelo,
                generation_config={"temperature": 0.2}
            )
            response = model.generate_content(prompt)
            if response and response.text:
                raw_text = response.text.strip()
                logger.info(f"Respuesta exitosa con modelo: {nombre_modelo}")
                break
        except Exception as e:
            logger.warning(f"Error con modelo {nombre_modelo}: {e}")
            ultimo_error = e
            continue

    if not raw_text:
        err_str = str(ultimo_error)
        if "429" in err_str or "quota" in err_str.lower():
            raise RuntimeError(
                "⏳ Se alcanzó el límite temporal de 5 peticiones por minuto de la capa gratuita de Gemini. "
                "Por favor espera 30 segundos y vuelve a presionar el botón."
            )
        raise RuntimeError(f"Error al comunicarse con el modelo de IA: {err_str}")

    # --------------------------------------------------------------------------
    # PARSEO DEFENSIVO DE JSON
    # --------------------------------------------------------------------------
    # Eliminamos posibles backticks de markdown que el modelo pudiera añadir
    texto_limpio = raw_text
    if texto_limpio.startswith("```"):
        # Eliminamos primera línea (ej. ```json) y última línea (```)
        lineas = texto_limpio.splitlines()
        if len(lineas) >= 2:
            texto_limpio = "\n".join(lineas[1:-1])

    # Intentamos encontrar el primer '{' y el último '}'
    inicio_json = texto_limpio.find("{")
    fin_json = texto_limpio.rfind("}")
    if inicio_json != -1 and fin_json != -1:
        texto_limpio = texto_limpio[inicio_json : fin_json + 1]

    try:
        data = json.loads(texto_limpio)
    except json.JSONDecodeError as err:
        logger.error(f"Error decodificando JSON del LLM: {err}\nTexto recibido:\n{raw_text}")
        raise ValueError(f"La IA no devolvió un JSON válido. Error: {str(err)}")

    # Validamos estructura mínima esperada
    if not isinstance(data, dict):
        raise ValueError("El resultado de la IA no es un diccionario JSON.")

    if "profile" not in data:
        data["profile"] = {}
    if "skills" not in data or not isinstance(data["skills"], list):
        data["skills"] = []

    # Validamos que cada skill tenga su categoría dentro de las permitidas
    skills_validas = []
    for s in data["skills"]:
        if isinstance(s, dict) and s.get("skill_name"):
            cat = s.get("category", "")
            if cat not in SKILL_CATEGORIES:
                # Si el LLM inventó una categoría parecida, fallback a una razonable
                cat = "DevOps"
            prof = s.get("proficiency", "Intermediate")
            if prof not in ["Beginner", "Intermediate", "Advanced"]:
                prof = "Intermediate"
            skills_validas.append({
                "skill_name": s["skill_name"].strip(),
                "category": cat,
                "proficiency": prof
            })

    data["skills"] = skills_validas
    return data


def analyze_job_description(
    job_text: str,
    user_skills: list,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analiza una descripción de puesto (Job Description) y la compara contra
    el Master Skill Profile del usuario en SQLite.
    
    Extrae:
    1. Metadatos de la vacante (empresa, posición, modalidad, ubicación, salario).
    2. Clasificación de habilidades en 3 categorías consensuadas:
       - strong_matches: Habilidades que el usuario domina (Intermediate / Advanced).
       - partial_matches: Habilidades que el usuario tiene pero a nivel inicial (Beginner).
       - missing_skills: Tecnologías y requisitos demandados que el usuario no tiene registrados.
    
    Implementa:
    - Cascada de modelos Gemini para evitar errores 404/503.
    - Parseo defensivo y saneamiento de claves para prevenir KeyError en la UI.
    """
    key = api_key or get_api_key()
    if not key:
        raise ValueError(
            "No se encontró la clave de API de Gemini (GEMINI_API_KEY). "
            "Por favor ingrésala o agrégala en tu archivo .env."
        )

    genai.configure(api_key=key)

    # Formatear el Master Skill Profile del usuario para el prompt
    skills_formateadas = []
    for s in user_skills:
        nombre = s.get("skill_name", "")
        categoria = s.get("category", "General")
        nivel = s.get("proficiency", "Intermediate")
        skills_formateadas.append(f"- {nombre} ({categoria}) | Nivel: {nivel}")

    texto_skills_perfil = "\n".join(skills_formateadas) if skills_formateadas else "No hay habilidades registradas en el perfil aún."

    prompt = f"""
Eres un reclutador técnico senior y experto en evaluación de talento tech.
Tu tarea es analizar la siguiente descripción de vacante laboral (Job Description) y compararla minuciosamente contra el perfil de habilidades del candidato (Master Skill Profile).

PERFIL DE HABILIDADES DEL CANDIDATO (Master Skill Profile):
\"\"\"
{texto_skills_perfil}
\"\"\"

DESCRIPCIÓN DE LA VACANTE A ANALIZAR:
\"\"\"
{job_text}
\"\"\"

CRITERIOS DE CLASIFICACIÓN (ESTRICTOS):
1. 'strong_matches': Habilidades y tecnologías solicitadas o valoradas por la vacante que el candidato TIENE registradas con nivel "Intermediate" o "Advanced".
2. 'partial_matches': Habilidades y tecnologías solicitadas o valoradas por la vacante que el candidato TIENE registradas pero con nivel "Beginner" (fundamentos o nivel inicial).
3. 'missing_skills': Habilidades, tecnologías, herramientas, certificaciones o conocimientos requeridos o deseables en la vacante que el candidato NO TIENE en su perfil.

EXTRACCIÓN DE INFORMACIÓN DEL PUESTO:
- company: Nombre de la empresa empleadora (si no se especifica claramente, escribe "No especificada").
- position: Título del puesto / rol (ej. "Senior DevOps Engineer", "Site Reliability Engineer", "Cloud Architect").
- work_mode: Clasifica OBLIGATORIAMENTE en uno de: "Remote", "Hybrid", "On-site" o "TBD" (si no está claro).
- location: Ubicación geográfica o "Remote".
- salary: Rango o cifra salarial si se menciona explícitamente (ej. "$90,000 - $110,000 USD"), o cadena vacía "" si no se menciona.

REGLAS DE RESPUESTA:
- Responde ÚNICAMENTE con un objeto JSON válido.
- NO agregues explicaciones fuera del bloque JSON.
- Sigue exactamente esta estructura:

{{
  "job_info": {{
    "company": "Nombre de la empresa",
    "position": "Título de la vacante",
    "work_mode": "Remote",
    "location": "Ubicación o Remote",
    "salary": ""
  }},
  "skill_matching": {{
    "strong_matches": [
      {{
        "skill": "Nombre de la tecnología",
        "proficiency": "Advanced o Intermediate",
        "reason": "Breve explicación de coincidencia"
      }}
    ],
    "partial_matches": [
      {{
        "skill": "Nombre de la tecnología",
        "proficiency": "Beginner",
        "reason": "Por qué es parcial (nivel inicial)"
      }}
    ],
    "missing_skills": [
      {{
        "skill": "Nombre de la tecnología faltante",
        "importance": "Required o Nice-to-have",
        "reason": "Rol en la vacante"
      }}
    ]
  }}
}}
"""

    modelos_a_probar = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
        "gemini-flash-latest"
    ]

    raw_text = None
    ultimo_error = None

    for nombre_modelo in modelos_a_probar:
        try:
            logger.info(f"Analizando vacante con modelo Gemini: {nombre_modelo}...")
            model = genai.GenerativeModel(
                model_name=nombre_modelo,
                generation_config={"temperature": 0.2}
            )
            response = model.generate_content(prompt)
            if response and response.text:
                raw_text = response.text.strip()
                logger.info(f"Análisis exitoso con modelo: {nombre_modelo}")
                break
        except Exception as e:
            logger.warning(f"Error con modelo {nombre_modelo}: {e}")
            ultimo_error = e
            continue

    if not raw_text:
        err_str = str(ultimo_error)
        if "429" in err_str or "quota" in err_str.lower():
            raise RuntimeError(
                "⏳ Se alcanzó el límite de peticiones por minuto de Gemini. "
                "Espera 30 segundos y vuelve a presionar el botón de análisis."
            )
        raise RuntimeError(f"Error al comunicarse con Gemini: {err_str}")

    # Parseo defensivo
    texto_limpio = raw_text
    if texto_limpio.startswith("```"):
        lineas = texto_limpio.splitlines()
        if len(lineas) >= 2:
            texto_limpio = "\n".join(lineas[1:-1])

    inicio_json = texto_limpio.find("{")
    fin_json = texto_limpio.rfind("}")
    if inicio_json != -1 and fin_json != -1:
        texto_limpio = texto_limpio[inicio_json : fin_json + 1]

    try:
        data = json.loads(texto_limpio)
    except json.JSONDecodeError as err:
        logger.error(f"Error decodificando JSON de vacante: {err}\nTexto recibido:\n{raw_text}")
        raise ValueError(f"La IA no devolvió un formato JSON válido: {err}")

    # Normalización y validación defensiva de la estructura
    if not isinstance(data, dict):
        raise ValueError("El resultado de la IA no es un diccionario.")

    # 1. job_info
    job_info = data.get("job_info", {})
    if not isinstance(job_info, dict):
        job_info = {}

    work_mode_raw = str(job_info.get("work_mode", "TBD")).capitalize()
    if work_mode_raw not in ["Remote", "Hybrid", "On-site", "TBD"]:
        work_mode_raw = "TBD"

    data["job_info"] = {
        "company": str(job_info.get("company") or "No especificada").strip(),
        "position": str(job_info.get("position") or "Puesto no especificado").strip(),
        "work_mode": work_mode_raw,
        "location": str(job_info.get("location") or "No especificada").strip(),
        "salary": str(job_info.get("salary") or "").strip()
    }

    # 2. skill_matching
    skill_matching = data.get("skill_matching", {})
    if not isinstance(skill_matching, dict):
        skill_matching = {}

    def normalizar_items(lista, default_key, default_val):
        items_limpios = []
        if isinstance(lista, list):
            for item in lista:
                if isinstance(item, dict) and item.get("skill"):
                    items_limpios.append({
                        "skill": str(item["skill"]).strip(),
                        default_key: str(item.get(default_key, default_val)).strip(),
                        "reason": str(item.get("reason", "")).strip()
                    })
                elif isinstance(item, str) and item.strip():
                    items_limpios.append({
                        "skill": item.strip(),
                        default_key: default_val,
                        "reason": ""
                    })
        return items_limpios

    data["skill_matching"] = {
        "strong_matches": normalizar_items(skill_matching.get("strong_matches"), "proficiency", "Intermediate"),
        "partial_matches": normalizar_items(skill_matching.get("partial_matches"), "proficiency", "Beginner"),
        "missing_skills": normalizar_items(skill_matching.get("missing_skills"), "importance", "Required")
    }

    return data

