"""
Esquema Pydantic para la representación estructurada y validación de CVs.
Diseñado con validadores defensivos para aceptar de forma robusta cualquier variación de formato o valores nulos producidos por modelos LLM.
"""

from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ContactInfo(BaseModel):
    """Información de contacto del candidato."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Nombre completo del candidato")
    email: Optional[str] = Field(None, description="Correo electrónico de contacto")
    phone: Optional[str] = Field(None, description="Número de teléfono")
    location: Optional[str] = Field(None, description="Ciudad, país o modalidad de residencia")
    linkedin: Optional[str] = Field(None, description="Enlace al perfil de LinkedIn")
    github: Optional[str] = Field(None, description="Enlace al perfil de GitHub")
    portfolio: Optional[str] = Field(None, description="Sitio web personal o portafolio")

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: Any) -> str:
        if v is None or str(v).lower() in ("none", "null"):
            return ""
        return str(v).strip()


class BulletItem(BaseModel):
    """Logro o responsabilidad individual en una experiencia laboral."""
    model_config = ConfigDict(extra="ignore")

    original: str = Field(default="", description="Texto original extraído del CV")
    improved: Optional[str] = Field(None, description="Versión mejorada siguiendo reglas de acción, contexto y resultado")
    suggestion: Optional[str] = Field(None, description="Sugerencia o pregunta pidiendo datos faltantes si carece de métricas")

    @field_validator("original", mode="before")
    @classmethod
    def sanitize_original(cls, v: Any) -> str:
        if not v or str(v).lower() in ("none", "null"):
            return ""
        return str(v).strip()


class ExperienceItem(BaseModel):
    """Entrada de experiencia laboral o profesional."""
    model_config = ConfigDict(extra="ignore")

    company: str = Field(default="Empresa", description="Nombre de la empresa o cliente")
    position: str = Field(default="Puesto", description="Título o cargo desempeñado")
    start_date: Optional[str] = Field(None, description="Fecha de inicio (ej. 'Ene 2022' o '2022-01')")
    end_date: Optional[str] = Field(None, description="Fecha de fin o 'Presente' / 'Actual'")
    current: bool = Field(False, description="True si es el empleo actual")
    location: Optional[str] = Field(None, description="Ubicación o 'Remoto'")
    bullets: List[BulletItem] = Field(default_factory=list, description="Lista de logros o responsabilidades")

    @field_validator("company", mode="before")
    @classmethod
    def sanitize_company(cls, v: Any) -> str:
        if not v or not str(v).strip() or str(v).lower() in ("none", "null"):
            return "Empresa"
        return str(v).strip()

    @field_validator("position", mode="before")
    @classmethod
    def sanitize_position(cls, v: Any) -> str:
        if not v or not str(v).strip() or str(v).lower() in ("none", "null"):
            return "Puesto"
        return str(v).strip()

    @field_validator("bullets", mode="before")
    @classmethod
    def sanitize_bullets(cls, v: Any) -> List[Any]:
        if not v:
            return []
        if isinstance(v, list):
            cleaned = []
            for item in v:
                if isinstance(item, str) and item.strip():
                    cleaned.append({"original": item.strip()})
                elif isinstance(item, dict):
                    orig = item.get("original") or item.get("text") or item.get("bullet") or item.get("description") or ""
                    if str(orig).strip():
                        cleaned.append({
                            "original": str(orig).strip(),
                            "improved": item.get("improved"),
                            "suggestion": item.get("suggestion")
                        })
                elif isinstance(item, BulletItem):
                    cleaned.append(item)
            return cleaned
        elif isinstance(v, str) and v.strip():
            return [{"original": b.strip()} for b in v.split("\n") if b.strip()]
        return []


class EducationItem(BaseModel):
    """Entrada académica o de formación formal."""
    model_config = ConfigDict(extra="ignore")

    institution: str = Field(default="Institución", description="Nombre de la universidad o institución educativa")
    degree: str = Field(default="Título", description="Grado o título obtenido (ej. 'Licenciatura en Computación')")
    field_of_study: Optional[str] = Field(None, description="Campo de estudio o especialidad")
    start_date: Optional[str] = Field(None, description="Fecha de inicio")
    end_date: Optional[str] = Field(None, description="Fecha de graduación o fin")
    grade_or_details: Optional[str] = Field(None, description="Honores, promedio o detalles adicionales")

    @field_validator("institution", mode="before")
    @classmethod
    def sanitize_institution(cls, v: Any) -> str:
        if not v or not str(v).strip() or str(v).lower() in ("none", "null"):
            return "Institución"
        return str(v).strip()

    @field_validator("degree", mode="before")
    @classmethod
    def sanitize_degree(cls, v: Any) -> str:
        if not v or not str(v).strip() or str(v).lower() in ("none", "null"):
            return "Título"
        return str(v).strip()


class SkillCategory(BaseModel):
    """Categoría o grupo de habilidades técnicas o blandas."""
    model_config = ConfigDict(extra="ignore")

    category: str = Field(default="Habilidades", description="Nombre del grupo (ej. 'Lenguajes', 'Cloud & DevOps', 'Bases de Datos')")
    skills: List[str] = Field(default_factory=list, description="Lista de habilidades o tecnologías")

    @field_validator("category", mode="before")
    @classmethod
    def sanitize_category(cls, v: Any) -> str:
        if not v or not str(v).strip() or str(v).lower() in ("none", "null"):
            return "Habilidades"
        return str(v).strip()

    @field_validator("skills", mode="before")
    @classmethod
    def sanitize_skills(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return [str(s).strip() for s in v if s and str(s).strip()]
        elif isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return []


class LanguageItem(BaseModel):
    """Dominio de idiomas."""
    model_config = ConfigDict(extra="ignore")

    language: str = Field(default="Idioma", description="Nombre del idioma (ej. 'Inglés', 'Español')")
    proficiency: Optional[str] = Field(None, description="Nivel de dominio (ej. 'Nativo', 'B2', 'C1 Avanzado')")

    @field_validator("language", mode="before")
    @classmethod
    def sanitize_language(cls, v: Any) -> str:
        if not v or not str(v).strip() or str(v).lower() in ("none", "null"):
            return "Idioma"
        return str(v).strip()


class CertificationItem(BaseModel):
    """Certificación profesional o licencia técnica."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="Certificación", description="Nombre oficial de la certificación")
    issuer: Optional[str] = Field(None, description="Organización emisora (ej. 'AWS', 'Google Cloud')")
    date: Optional[str] = Field(None, description="Fecha de expedición")
    credential_url: Optional[str] = Field(None, description="URL de verificación de credencial")

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: Any) -> str:
        if not v or not str(v).strip() or str(v).lower() in ("none", "null"):
            return "Certificación"
        return str(v).strip()


class ResumeSchema(BaseModel):
    """Esquema raíz completo del currículum vitae."""
    model_config = ConfigDict(extra="ignore")

    contact: ContactInfo = Field(default_factory=ContactInfo, description="Datos de contacto")
    summary: Optional[str] = Field(None, description="Resumen profesional original")
    summary_improved: Optional[str] = Field(None, description="Resumen profesional mejorado orientado a impacto")
    experience: List[ExperienceItem] = Field(default_factory=list, description="Historial laboral")
    education: List[EducationItem] = Field(default_factory=list, description="Educación y títulos")
    skills: List[SkillCategory] = Field(default_factory=list, description="Habilidades clasificadas")
    languages: List[LanguageItem] = Field(default_factory=list, description="Idiomas conocidos")
    certifications: List[CertificationItem] = Field(default_factory=list, description="Certificaciones y credenciales")
    raw_text: Optional[str] = Field(None, description="Texto original extraído del archivo")

    @field_validator("contact", mode="before")
    @classmethod
    def sanitize_contact(cls, v: Any) -> Any:
        if isinstance(v, ContactInfo):
            return v
        if not v or not isinstance(v, dict):
            return {"name": ""}
        return v
