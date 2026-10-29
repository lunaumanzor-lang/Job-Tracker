"""
Orquestador de extracción de texto y conversión a ResumeSchema validado con LLM.
"""

import os
import re
import time
import logging
from typing import Optional, Dict, Any
from .base import validate_uploaded_file, UnsupportedFileTypeError
from .pdf_parser import extract_text_from_pdf
from .docx_parser import extract_text_from_docx
from .txt_parser import extract_text_from_txt
from ..schema import (
    ResumeSchema,
    ContactInfo,
    ExperienceItem,
    BulletItem,
    EducationItem,
    SkillCategory,
    LanguageItem,
    CertificationItem
)
from ..enhancer.provider_base import LLMProvider
from ai_client import AITimeBudgetExceeded

logger = logging.getLogger(__name__)


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    Valida el archivo y extrae el contenido de texto plano según su extensión.
    
    Formatos admitidos: .pdf, .docx, .txt
    """
    ext = validate_uploaded_file(file_bytes=file_bytes, filename=filename)

    if ext == "pdf":
        return extract_text_from_pdf(file_bytes=file_bytes, filename=filename)
    elif ext == "docx":
        return extract_text_from_docx(file_bytes=file_bytes, filename=filename)
    elif ext == "txt":
        return extract_text_from_txt(file_bytes=file_bytes, filename=filename)
    else:
        raise UnsupportedFileTypeError(f"Formato no soportado: .{ext}")


PARSE_RESUME_SYSTEM_PROMPT_ES = """Eres un asistente de reclutamiento y parseo experto en análisis de currículums vitae (ATS).
Tu tarea es convertir el texto sin formato de un CV en un objeto JSON estructurado y exhaustivo siguiendo estrictamente el esquema especificado.
Todo el contenido extraído (cargos, viñetas, resumen, habilidades y educación) debe presentarse en Español impecable.
REGLAS CRÍTICAS:
1. El campo "name" de "contact" NUNCA debe ser null. Si no está explícito al inicio, infiérelo del texto, correo o usa "Candidato".
2. DEBES capturar TODAS las experiencias laborales, empresas, cargos y viñetas (bullets). NUNCA dejes la lista "experience" vacía si el CV menciona historial de trabajo.
3. Conserva métricas numéricas, fechas, empresas y tecnologías intactas.
Responde ÚNICAMENTE con el objeto JSON válido, sin explicaciones ni markdown previo o posterior."""

PARSE_RESUME_USER_PROMPT_ES = """Analiza el siguiente texto de currículum vitae y genera un JSON con esta estructura exacta:

{{
  "contact": {{
    "name": "Nombre completo (NUNCA null)",
    "email": "correo@ejemplo.com o null",
    "phone": "+1 234 567 890 o null",
    "location": "Ciudad, País o null",
    "linkedin": "url de linkedin o null",
    "github": "url de github o null",
    "portfolio": "url personal o null"
  }},
  "summary": "Resumen o perfil profesional original o null",
  "experience": [
    {{
      "company": "Nombre de la empresa",
      "position": "Cargo desempeñado",
      "start_date": "Fecha inicio (ej. Ene 2021) o null",
      "end_date": "Fecha fin o Presente o null",
      "current": false,
      "location": "Ubicación o null",
      "bullets": [
        {{
          "original": "Texto exacto de la viñeta o responsabilidad",
          "improved": null,
          "suggestion": null
        }}
      ]
    }}
  ],
  "education": [
    {{
      "institution": "Universidad o escuela",
      "degree": "Título obtenido",
      "field_of_study": "Área de estudio o null",
      "start_date": "Año o fecha inicio o null",
      "end_date": "Año o fecha fin o null",
      "grade_or_details": "Detalles adicionales o null"
    }}
  ],
  "skills": [
    {{
      "category": "Nombre de la categoría (ej. Lenguajes de Programación, Frameworks, Herramientas, Habilidades Blandas)",
      "skills": ["Skill 1", "Skill 2"]
    }}
  ],
  "languages": [
    {{
      "language": "Idioma",
      "proficiency": "Nivel (ej. Nativo, B2, Intermedio) o null"
    }}
  ],
  "certifications": [
    {{
      "name": "Nombre de la certificación",
      "issuer": "Emisor (ej. AWS, Scrum Alliance) o null",
      "date": "Fecha o null",
      "credential_url": "URL o null"
    }}
  ]
}}

TEXTO DEL CURRÍCULUM:
---
{raw_text}
---
"""

PARSE_RESUME_SYSTEM_PROMPT_EN = """You are an expert executive technical recruiter and ATS resume parsing specialist.
Your mission is to parse the unformatted resume text into a comprehensive, highly accurate structured JSON object following strictly the schema.
ALL content (job titles, professional summary, bullet points, skills categories, and education details) MUST be output strictly in professional English.
CRITICAL RULES:
1. The "name" field in "contact" MUST NEVER be null. If not explicitly stated, infer it from the top lines, email or use "Candidate".
2. You MUST extract ALL work experience items, companies, job titles, and bullet points. NEVER return an empty "experience" array if the resume contains any employment history.
3. Preserve all factual metrics, dates, and technologies completely intact.
Respond ONLY with the valid JSON object, without explanations, markdown wrapping, or commentary."""

PARSE_RESUME_USER_PROMPT_EN = """Analyze the following resume text and generate a structured JSON strictly in English with this exact structure:

{{
  "contact": {{
    "name": "Full Name (NEVER null)",
    "email": "email@example.com or null",
    "phone": "+1 234 567 890 or null",
    "location": "City, Country or null",
    "linkedin": "url or null",
    "github": "url or null",
    "portfolio": "url or null"
  }},
  "summary": "Professional summary in English or null",
  "experience": [
    {{
      "company": "Company Name",
      "position": "Job Title in English",
      "start_date": "Start Date (e.g. Jan 2021) or null",
      "end_date": "End Date or Present or null",
      "current": false,
      "location": "Location or null",
      "bullets": [
        {{
          "original": "Original or translated bullet point text in English",
          "improved": null,
          "suggestion": null
        }}
      ]
    }}
  ],
  "education": [
    {{
      "institution": "University or School",
      "degree": "Degree in English",
      "field_of_study": "Field of Study in English or null",
      "start_date": "Year or date or null",
      "end_date": "Year or date or null",
      "grade_or_details": null
    }}
  ],
  "skills": [
    {{
      "category": "Category name in English (e.g. Programming Languages, Cloud & DevOps, Frameworks, Core Tools)",
      "skills": ["Skill 1", "Skill 2"]
    }}
  ],
  "languages": [
    {{
      "language": "Language name in English",
      "proficiency": "Proficiency level in English or null"
    }}
  ],
  "certifications": [
    {{
      "name": "Certification Name",
      "issuer": "Issuer or null",
      "date": "Date or null",
      "credential_url": "URL or null"
    }}
  ]
}}

RESUME TEXT:
---
{raw_text}
---
"""

# Compatibilidad hacia atrás
PARSE_RESUME_SYSTEM_PROMPT = PARSE_RESUME_SYSTEM_PROMPT_ES
PARSE_RESUME_USER_PROMPT = PARSE_RESUME_USER_PROMPT_ES


def detect_resume_language(text: str) -> str:
    """
    Detecta automáticamente si el texto del currículum está predominantemente en inglés ('en') o español ('es').
    """
    if not text or not text.strip():
        return "es"

    text_lower = text.lower()
    en_words = [
        " the ", " and ", " of ", " to ", " in ", " with ", " for ", " at ", " from ", " on ",
        "experience", "education", "skills", "summary", "present", "responsibilities",
        "work experience", "professional experience", "developed", "managed", "designed",
        "implemented", "engineer", "software", "university", "bachelor", "degree"
    ]
    es_words = [
        " de ", " la ", " el ", " en ", " y ", " con ", " para ", " por ", " del ", " los ", " las ",
        "experiencia", "educación", "educacion", "habilidades", "resumen", "presente", "actual",
        "experiencia laboral", "experiencia profesional", "desarrollo", "desarrollé", "lideré",
        "puesto", "empresa", "licenciatura", "título", "titulo", "ingeniería", "ingenieria"
    ]

    en_score = sum(text_lower.count(w) for w in en_words)
    es_score = sum(text_lower.count(w) for w in es_words)

    return "en" if en_score > es_score else "es"


def _sanitize_and_repair_json(json_data: Any, raw_text: str, is_en: bool) -> Dict[str, Any]:
    """
    Normaliza y repara estructuras JSON generadas por LLMs para asegurar que cumplan
    estrictamente con ResumeSchema sin lanzar ValidationError.
    """
    if not isinstance(json_data, dict):
        if isinstance(json_data, list) and len(json_data) > 0 and isinstance(json_data[0], dict):
            json_data = json_data[0]
        else:
            return {}

    # Desempaquetar si el modelo envolvió en {"resume": ...}, {"cv": ...}, {"data": ...}
    for wrapper in ["resume", "cv", "data", "result", "candidate"]:
        if wrapper in json_data and isinstance(json_data[wrapper], dict) and ("experience" in json_data[wrapper] or "work_experience" in json_data[wrapper]):
            json_data = json_data[wrapper]
            break

    # 1. Contacto
    contact = json_data.get("contact")
    if not isinstance(contact, dict):
        contact = {}
        json_data["contact"] = contact

    name_val = contact.get("name")
    if not name_val or not str(name_val).strip() or str(name_val).lower() in ("none", "null", "undefined"):
        inferred_name = None
        for line in raw_text.splitlines()[:6]:
            clean_l = line.strip()
            if not clean_l:
                continue
            if any(term in clean_l.lower() for term in ["curriculum", "resume", "cv", "@", "http", "www."]):
                continue
            if len(clean_l.split()) <= 5:
                inferred_name = clean_l
                break
        contact["name"] = inferred_name or ("Candidate" if is_en else "Candidato")

    # 2. Experiencia
    alt_exp_keys = ["work_experience", "workExperience", "experiences", "employment", "historial_laboral", "trayectoria", "jobs", "career"]
    if "experience" not in json_data or not isinstance(json_data["experience"], list):
        for alt in alt_exp_keys:
            if alt in json_data and isinstance(json_data[alt], list):
                json_data["experience"] = json_data[alt]
                break
        if "experience" not in json_data or not isinstance(json_data["experience"], list):
            json_data["experience"] = []

    cleaned_exp = []
    for exp in json_data["experience"]:
        if not isinstance(exp, dict):
            continue
        company = exp.get("company") or ("Company" if is_en else "Empresa")
        position = exp.get("position") or exp.get("role") or exp.get("title") or ("Role" if is_en else "Puesto")
        bullets = exp.get("bullets") or exp.get("responsibilities") or exp.get("achievements") or exp.get("tasks") or []

        cleaned_bullets = []
        if isinstance(bullets, list):
            for b in bullets:
                if isinstance(b, str) and b.strip():
                    cleaned_bullets.append({"original": b.strip()})
                elif isinstance(b, dict):
                    orig = b.get("original") or b.get("text") or b.get("bullet") or b.get("description") or ""
                    if str(orig).strip():
                        cleaned_bullets.append({
                            "original": str(orig).strip(),
                            "improved": b.get("improved"),
                            "suggestion": b.get("suggestion")
                        })
        elif isinstance(bullets, str) and bullets.strip():
            cleaned_bullets = [{"original": s.strip()} for s in bullets.split("\n") if s.strip()]

        cleaned_exp.append({
            "company": str(company).strip(),
            "position": str(position).strip(),
            "start_date": exp.get("start_date") or exp.get("startDate"),
            "end_date": exp.get("end_date") or exp.get("endDate"),
            "current": bool(exp.get("current", False)),
            "location": exp.get("location"),
            "bullets": cleaned_bullets
        })
    json_data["experience"] = cleaned_exp

    # 3. Educación
    alt_edu_keys = ["educacion", "academics", "academic_background", "studies", "formacion", "education_history"]
    if "education" not in json_data or not isinstance(json_data["education"], list):
        for alt in alt_edu_keys:
            if alt in json_data and isinstance(json_data[alt], list):
                json_data["education"] = json_data[alt]
                break
        if "education" not in json_data or not isinstance(json_data["education"], list):
            json_data["education"] = []

    cleaned_edu = []
    for edu in json_data["education"]:
        if not isinstance(edu, dict):
            continue
        cleaned_edu.append({
            "institution": str(edu.get("institution") or edu.get("school") or edu.get("university") or ("Institution" if is_en else "Institución")).strip(),
            "degree": str(edu.get("degree") or edu.get("title") or ("Degree" if is_en else "Título")).strip(),
            "field_of_study": edu.get("field_of_study") or edu.get("fieldOfStudy"),
            "start_date": edu.get("start_date"),
            "end_date": edu.get("end_date"),
            "grade_or_details": edu.get("grade_or_details") or edu.get("details")
        })
    json_data["education"] = cleaned_edu

    # 4. Habilidades
    alt_skills_keys = ["habilidades", "technical_skills", "technologies", "competencies"]
    if "skills" not in json_data:
        for alt in alt_skills_keys:
            if alt in json_data:
                json_data["skills"] = json_data[alt]
                break

    skills_val = json_data.get("skills")
    if isinstance(skills_val, list):
        if all(isinstance(x, str) for x in skills_val):
            json_data["skills"] = [{"category": "Skills" if is_en else "Habilidades", "skills": skills_val}]
    elif isinstance(skills_val, dict):
        json_data["skills"] = [{"category": k, "skills": v if isinstance(v, list) else [str(v)]} for k, v in skills_val.items()]
    else:
        json_data["skills"] = []

    # 5. Idiomas y Certificaciones
    if not isinstance(json_data.get("languages"), list):
        json_data["languages"] = []
    if not isinstance(json_data.get("certifications"), list):
        json_data["certifications"] = []

    return json_data


def parse_resume_to_schema(
    raw_text: str,
    provider: Optional[LLMProvider] = None,
    language: str = "auto",
    deadline: Optional[float] = None
) -> ResumeSchema:
    """
    Convierte el texto extraído de un CV en un objeto ResumeSchema validado.
    Detecta automáticamente el idioma si se especifica 'auto' o respeta el idioma solicitado ('es' o 'en').
    Si no se suministra proveedor ni API key, recurre a un parser heurístico bilingüe.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("El texto proporcionado para parsear el CV está vacío.")

    if not language or language.lower() == "auto":
        resolved_lang = detect_resume_language(raw_text)
    else:
        resolved_lang = language.lower()

    is_en = (resolved_lang == "en")
    user_prompt_tpl = PARSE_RESUME_USER_PROMPT_EN if is_en else PARSE_RESUME_USER_PROMPT_ES
    sys_prompt = PARSE_RESUME_SYSTEM_PROMPT_EN if is_en else PARSE_RESUME_SYSTEM_PROMPT_ES

    # 1. Intentar con LLM si se proporciona o si existe API key configurada
    if provider is None:
        from ..enhancer import get_active_llm_provider
        provider, _ = get_active_llm_provider()

    if provider is not None:
        if deadline is not None and time.monotonic() >= deadline:
            logger.warning("Tope de tiempo (deadline monotónico) alcanzado antes de parsear CV con LLM.")
            raise AITimeBudgetExceeded("⏱️ El tiempo límite asignado para la extracción de CV ha sido superado.")
        try:
            prompt = user_prompt_tpl.format(raw_text=raw_text)
            json_data = provider.generate_json(
                prompt=prompt,
                system_prompt=sys_prompt,
                temperature=0.0,
                deadline=deadline
            )
            # Reparar y sanear de forma preventiva antes de validar el esquema
            repaired_json = _sanitize_and_repair_json(json_data, raw_text=raw_text, is_en=is_en)
            resume = ResumeSchema.model_validate(repaired_json)
            resume.raw_text = raw_text

            # Si el LLM no detectó experiencias pero sí hay texto, verificar contingencia
            if not resume.experience and len(raw_text.splitlines()) > 5:
                heuristic_fallback = _fallback_heuristic_parse(raw_text, language=resolved_lang)
                if heuristic_fallback.experience:
                    resume.experience = heuristic_fallback.experience
                    if not resume.education and heuristic_fallback.education:
                        resume.education = heuristic_fallback.education
                    if not resume.skills and heuristic_fallback.skills:
                        resume.skills = heuristic_fallback.skills

            return resume
        except AITimeBudgetExceeded:
            logger.warning("Tope de tiempo alcanzado en parse_resume_to_schema con LLM. Propagando AITimeBudgetExceeded...")
            raise
        except Exception as e:
            logger.error(f"Error procesando CV con LLMProvider: {e}", exc_info=True)
            logger.info("Recurriendo al parser heurístico de contingencia...")

    # 2. Parser heurístico de contingencia (sin API o cuando falla el LLM)
    resume = _fallback_heuristic_parse(raw_text, language=resolved_lang)
    resume.raw_text = raw_text
    return resume


def _fallback_heuristic_parse(text: str, language: str = "es") -> ResumeSchema:
    """
    Parser heurístico avanzado para estructurar completamente un CV
    (contacto, resumen, experiencias con fechas y puestos, educación, habilidades,
    idiomas y certificaciones) de forma determinista y sin depender de conexión externa.
    """
    is_en = (language == "en")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ResumeSchema(contact=ContactInfo(name="Candidate" if is_en else "Candidato"), experience=[])

    # 1. Contacto
    first_line = lines[0]
    name = first_line
    if any(term in name.lower() for term in ["curriculum", "resume", "cv", "hoja de vida"]) and len(lines) > 1:
        name = lines[1]

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    phone_match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
    linkedin_match = re.search(r"(https?://[^\s]*linkedin\.com/[^\s]+)", text, re.IGNORECASE)
    github_match = re.search(r"(https?://[^\s]*github\.com/[^\s]+)", text, re.IGNORECASE)

    location = None
    for l in lines[:8]:
        if any(c in l.lower() for c in ["méxico", "mexico", "costa rica", "madrid", "bogotá", "remoto", "remote", "colombia", "argentina", "chile", "perú", "spain", "usa", "united states", "panamá"]):
            for part in re.split(r"[\|\•\-\–]", l):
                p_clean = part.strip()
                if any(c in p_clean.lower() for c in ["méxico", "mexico", "costa rica", "madrid", "bogotá", "remoto", "remote", "colombia", "argentina", "chile", "perú", "panamá"]):
                    location = p_clean
                    break

    contact = ContactInfo(
        name=name,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0) if phone_match else None,
        location=location,
        linkedin=linkedin_match.group(0) if linkedin_match else None,
        github=github_match.group(0) if github_match else None
    )

    # 2. Segmentación de Secciones Ampliada con Normalización Unicode y Prefijos
    sec_stems = {
        "summary": ["RESUMEN", "SUMMAR", "PERFIL", "PROFILE", "ABOUT", "SOBRE MI", "ACERCA DE", "BIOGRAF"],
        "experience": [
            "EXPERIENC", "HISTORIAL LABORAL", "HISTORIAL PROFESIONAL", "WORK EXPERIENC",
            "WORK HISTOR", "EMPLOYMENT", "PROFESSIONAL EXPERIENC", "RELEVANT EXPERIENC",
            "TRAYECTORIA", "CARGOS DESEMP", "CAREER", "LABORAL", "ANTECEDENTES", "HISTORIAL DE EMPLEO"
        ],
        "education": [
            "EDUCAC", "FORMACION", "ESTUDIO", "ACADEMIC", "TITULACION", "UNIVERSITAR", "PREPARACION ACADEMIC"
        ],
        "skills": [
            "HABILIDAD", "SKILL", "TECNOLOGI", "COMPETENC", "HERRAMIENT", "HARD SKILL",
            "CORE SKILL", "APTITUD", "CONOCIMIENTO", "STACK"
        ],
        "languages": ["IDIOMA", "LANGUAG"],
        "certifications": ["CERTIFIC", "CURSO", "LICENCIA", "ACREDITA", "CREDENTIAL"]
    }

    import unicodedata, html

    def _norm_sec(text_val: str) -> str:
        t = html.unescape(text_val)
        t = unicodedata.normalize('NFKD', t)
        t = re.sub(r'[\u0300-\u036f]', '', t)
        t = re.sub(r'[^a-zA-Z0-9\s]', ' ', t)
        return ' '.join(t.upper().split())

    current_section = "header"
    section_lines = {k: [] for k in sec_stems}
    section_lines["header"] = []

    for line in lines[1:]:
        # Si la línea tiene dos puntos con contenido descriptivo extenso (ej. "Lenguajes: Python, SQL"),
        # no es una cabecera de sección, pertenece a la sección activa.
        if ":" in line and len(line.split(":", 1)[1].strip()) > 3:
            if current_section in section_lines:
                section_lines[current_section].append(line)
            continue

        n_line = _norm_sec(line)
        # Una cabecera de sección suele tener pocas palabras
        if len(n_line.split()) <= 6:
            matched_sec = None
            for sec_name, stems in sec_stems.items():
                if any(n_line == s or n_line.startswith(s + " ") or n_line.startswith(s) for s in stems):
                    matched_sec = sec_name
                    break
            if matched_sec:
                current_section = matched_sec
                continue

        if current_section in section_lines:
            section_lines[current_section].append(line)

    # Si la sección de experiencia no fue detectada por cabecera, buscar en las líneas del header previas a educación
    if not section_lines["experience"] and section_lines["header"]:
        candidate_exp_lines = []
        date_probe = re.compile(r"(\b(?:19|20)\d\d\b|presente|actual|present|current)", re.IGNORECASE)
        for hl in section_lines["header"]:
            if date_probe.search(hl) or any(hl.startswith(b) for b in ["-", "•", "*", "–"]):
                candidate_exp_lines.append(hl)
        if candidate_exp_lines:
            section_lines["experience"] = section_lines["header"]
            section_lines["header"] = []

    # A. Resumen
    summary = " ".join(section_lines["summary"]) if section_lines["summary"] else None

    # B. Experiencias
    experiences = []
    exp_lines = section_lines["experience"]
    current_exp = None
    date_pattern = re.compile(r"(\b(?:19|20)\d\d\b.*(?:\b(?:19|20)\d\d\b|presente|actual|present|current))", re.IGNORECASE)

    for l in exp_lines:
        is_bullet = bool(re.match(r"^[\-\•\*\–\d\.]\s+", l))
        has_date = bool(date_pattern.search(l) or re.search(r"\b(19\d\d|20\d\d)\b", l))
        has_separator = any(sep in l for sep in ["|", "—", "–", " - "])

        if not is_bullet and (has_date or has_separator or len(l.split()) <= 8):
            parts = [p.strip() for p in re.split(r"[\|\—\–]|\s+-\s+", l) if p.strip()]
            company = parts[0] if len(parts) > 0 else ("Company" if is_en else "Empresa")
            position = parts[1] if len(parts) > 1 else ("Role" if is_en else "Especialista")
            date_str = parts[2] if len(parts) > 2 else ""

            d_match = date_pattern.search(l)
            if d_match:
                date_str = d_match.group(1).strip()

            start_d, end_d = None, None
            is_curr = False
            if date_str:
                d_parts = re.split(r"[-–—a]\s*|to\s*", date_str, flags=re.IGNORECASE)
                if len(d_parts) >= 2:
                    start_d = d_parts[0].strip()
                    end_d = d_parts[1].strip()
                    if any(w in end_d.lower() for w in ["presente", "actual", "present", "current"]):
                        is_curr = True
                        end_d = "Present" if is_en else "Presente"
                else:
                    start_d = date_str.strip()

            current_exp = ExperienceItem(
                company=company,
                position=position,
                start_date=start_d,
                end_date=end_d,
                current=is_curr,
                bullets=[]
            )
            experiences.append(current_exp)
        else:
            clean_b = re.sub(r"^[\-\•\*\–\d\.]\s+", "", l).strip()
            if clean_b:
                if current_exp is None:
                    current_exp = ExperienceItem(
                        company="Professional Experience" if is_en else "Experiencia Profesional",
                        position="Main Role" if is_en else "Puesto Principal",
                        bullets=[]
                    )
                    experiences.append(current_exp)
                current_exp.bullets.append(BulletItem(original=clean_b))

    # C. Educación
    education = []
    for l in section_lines["education"]:
        parts = [p.strip() for p in re.split(r"[\|\—\–]|\s+-\s+", l) if p.strip()]
        inst = parts[0] if len(parts) > 0 else ("University" if is_en else "Universidad")
        deg = parts[1] if len(parts) > 1 else ("Degree / Credential" if is_en else "Licenciatura / Grado")
        d_str = parts[2] if len(parts) > 2 else None
        s_d, e_d = None, None
        if d_str:
            d_parts = re.split(r"[-–—]", d_str)
            if len(d_parts) >= 2:
                s_d, e_d = d_parts[0].strip(), d_parts[1].strip()
            else:
                s_d = d_str
        education.append(EducationItem(
            institution=inst,
            degree=deg,
            start_date=s_d,
            end_date=e_d
        ))

    # D. Habilidades
    skills = []
    for l in section_lines["skills"]:
        if ":" in l:
            cat_name, items = l.split(":", 1)
            skill_list = [s.strip() for s in items.split(",") if s.strip()]
            if skill_list:
                skills.append(SkillCategory(category=cat_name.strip(), skills=skill_list))
        else:
            items = [s.strip() for s in l.split(",") if s.strip()]
            if items:
                skills.append(SkillCategory(category="Skills" if is_en else "Competencias", skills=items))

    # E. Idiomas
    languages = []
    for l in section_lines["languages"]:
        if ":" in l:
            lang, prof = l.split(":", 1)
            languages.append(LanguageItem(language=lang.strip(), proficiency=prof.strip()))
        else:
            languages.append(LanguageItem(language=l.strip()))

    # F. Certificaciones
    certifications = []
    for l in section_lines["certifications"]:
        parts = [p.strip() for p in re.split(r"[\|\—\–]", l) if p.strip()]
        c_name = parts[0] if len(parts) > 0 else l
        issuer = parts[1] if len(parts) > 1 else None
        date_c = parts[2] if len(parts) > 2 else None
        certifications.append(CertificationItem(name=c_name, issuer=issuer, date=date_c))

    return ResumeSchema(
        contact=contact,
        summary=summary,
        experience=experiences,
        education=education,
        skills=skills,
        languages=languages,
        certifications=certifications,
        raw_text=text
    )
