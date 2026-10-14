"""
Interfaz gráfica de usuario interactiva y enriquecida para el módulo CV Improver en Streamlit.
Presenta panel gráfico de mejoras sección por sección, comparación visual interactiva,
escaparate de plantillas llamativas con personalización en vivo y exportación completa
(fechas, nombres de empresas, puestos, descripciones y educación).
"""

import os
import copy
from typing import Dict
from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components

# Cargar variables de entorno de .env (para GEMINI_API_KEY)
load_dotenv()

from .parsers import (
    validate_uploaded_file,
    extract_text_from_file,
    parse_resume_to_schema,
    detect_resume_language,
    FileValidationError
)
from .enhancer import (
    get_active_llm_provider,
    AnthropicProvider,
    GeminiProvider,
    enhance_resume_content
)
from .renderer import render_cv_to_pdf, render_cv_to_html, render_cv_to_docx
from .schema import (
    ResumeSchema,
    ContactInfo,
    ExperienceItem,
    BulletItem,
    EducationItem,
    SkillCategory
)
from .examples import SECTOR_EXAMPLES, load_example_schema



def load_from_user_profile_database() -> ResumeSchema:
    """
    Construye un ResumeSchema a partir de los datos guardados en My Profile (SQLite)
    en modo solo lectura para trabajarlos en CV Improver sin mutar la base de datos.
    """
    from database import (
        get_user_profile,
        get_all_experiences,
        get_bullets_by_experience,
        get_all_education,
        get_all_user_skills
    )

    p = get_user_profile() or {}
    contact = ContactInfo(
        name=p.get("full_name") or "Candidato",
        email=p.get("email"),
        phone=p.get("phone"),
        location=p.get("location"),
        linkedin=None,
        github=None,
        portfolio=None
    )

    exps = []
    for exp_row in get_all_experiences():
        exp_id = exp_row["id"]
        bullet_rows = get_bullets_by_experience(exp_id)
        bullets = [
            BulletItem(original=b.get("bullet_text") or "", improved=None, suggestion=None)
            for b in bullet_rows
        ]
        exps.append(ExperienceItem(
            company=exp_row.get("company") or "Empresa",
            position=exp_row.get("position") or "Cargo",
            start_date=exp_row.get("start_date"),
            end_date=exp_row.get("end_date"),
            current=bool(exp_row.get("is_current")),
            bullets=bullets
        ))

    edus = []
    for edu_row in get_all_education():
        edus.append(EducationItem(
            institution=edu_row.get("institution") or "Institución",
            degree=edu_row.get("credential") or "Título",
            start_date=edu_row.get("start_date"),
            end_date=edu_row.get("end_date")
        ))

    skills_dict = {}
    for s_row in get_all_user_skills():
        cat = s_row.get("category") or "General"
        skills_dict.setdefault(cat, []).append(s_row.get("skill_name"))

    skill_cats = [
        SkillCategory(category=cat, skills=items)
        for cat, items in skills_dict.items()
    ]

    return ResumeSchema(
        contact=contact,
        summary=p.get("summary"),
        summary_improved=None,
        experience=exps,
        education=edus,
        skills=skill_cats
    )


def prepare_export_ready_resume(resume: ResumeSchema, bullets_status: Dict[str, str]) -> ResumeSchema:
    """
    Genera una copia profunda del ResumeSchema sincronizada con el estado de cada viñeta
    (aprobada vs rechazada/original) para que PDF y DOCX exporten exactamente lo seleccionado.
    """
    clean_resume = copy.deepcopy(resume)
    for exp_idx, exp in enumerate(clean_resume.experience):
        for b_idx, bullet in enumerate(exp.bullets):
            b_key = f"cv_imp_b_{exp_idx}_{b_idx}"
            status = bullets_status.get(b_key, "improved" if bullet.improved else "original")
            if status == "original":
                bullet.improved = bullet.original
            else:
                bullet.improved = bullet.improved or bullet.original
    return clean_resume


def process_and_enhance_cv(raw_text: str, target_language: str = "auto"):
    """
    Orquesta el análisis estructural y la mejora de viñetas en el idioma especificado ('es', 'en' o 'auto').
    """
    if not target_language or target_language == "auto":
        resolved_lang = detect_resume_language(raw_text)
    else:
        resolved_lang = target_language.lower()

    provider, p_name = get_active_llm_provider(
        anthropic_key=st.session_state.get("cv_improver_anthropic_key"),
        gemini_key=st.session_state.get("cv_improver_gemini_key")
    )
    lang_label = "Inglés" if resolved_lang == "en" else "Español"
    with st.spinner(f"🧠 Analizando estructura con {p_name} y optimizando viñetas en {lang_label}..."):
        try:
            parsed_resume = parse_resume_to_schema(
                raw_text=raw_text,
                provider=provider,
                language=resolved_lang
            )
            if provider:
                enhanced_resume = enhance_resume_content(parsed_resume, provider=provider, language=resolved_lang)
            else:
                from .enhancer.bullet_enhancer import enhance_resume_content as fallback_enhance
                from .enhancer.provider_base import LLMProvider
                class HeuristicDummy(LLMProvider):
                    def generate_text(self, p, s=None, temperature=0.2, max_tokens=4096):
                        raise RuntimeError("Sin API activa")
                enhanced_resume = fallback_enhance(parsed_resume, provider=HeuristicDummy(), language=resolved_lang)

            st.session_state["cv_improver_active_schema"] = enhanced_resume
            st.session_state["cv_improver_language"] = resolved_lang
            st.session_state["cv_improver_bullets_status"] = {}
            st.session_state["cv_improver_is_example"] = False
            st.session_state.pop("cv_improver_draft_discarded", None)
            persist_active_cv_draft()
            st.toast(f"¡CV analizado y optimizado en {lang_label} con éxito!", icon="🎉")
            st.rerun()
        except Exception as parse_err:
            st.error(f"Error procesando el currículum en {lang_label}: {parse_err}")


def persist_active_cv_draft():
    """Guarda en Supabase el borrador activo para garantizar continuidad permanente."""
    schema = st.session_state.get("cv_improver_active_schema")
    if schema is not None:
        try:
            from database import save_cv_improver_draft
            schema_data = schema.model_dump() if hasattr(schema, "model_dump") else schema.dict()
            draft = {
                "schema": schema_data,
                "bullets_status": st.session_state.get("cv_improver_bullets_status", {}),
                "language": st.session_state.get("cv_improver_language", "es"),
                "filename": st.session_state.get("cv_improver_filename", "CV_Optimizado"),
                "raw_text": st.session_state.get("cv_improver_raw_text", ""),
                "selected_cv_template": st.session_state.get("selected_cv_template", "moderna"),
                "is_example": st.session_state.get("cv_improver_is_example", False)
            }
            save_cv_improver_draft(draft)
        except Exception as e:
            print(f"Aviso al persistir borrador de CV: {e}")


def is_resume_example_unedited(resume: ResumeSchema) -> bool:
    """
    Verifica si el currículum activo proviene de un ejemplo del sector y aún
    no ha sido editado con la información real del usuario.
    """
    if resume is None:
        return False

    is_marked = st.session_state.get("cv_improver_is_example", False)
    filename = st.session_state.get("cv_improver_filename", "")
    is_example_file = bool(filename and filename.startswith("Ejemplo_"))

    if not is_marked and not is_example_file:
        return False

    # 1. Si el nombre de contacto sigue vacío
    has_contact_name = bool(resume.contact and resume.contact.name and resume.contact.name.strip())
    # 2. Si todavía contiene la marca '[ejemplo]' en resumen, empresa o cargo
    has_example_tags = (
        (resume.summary and "[ejemplo]" in resume.summary.lower())
        or any("[ejemplo]" in (exp.company or "").lower() for exp in resume.experience)
        or any("[ejemplo]" in (exp.position or "").lower() for exp in resume.experience)
    )
    if not has_contact_name or has_example_tags:
        return True

    # El usuario ya ingresó su nombre y reemplazó las etiquetas de ejemplo
    st.session_state["cv_improver_is_example"] = False
    return False


def _handle_cv_file_uploaded(uploaded_file, origin_badge: str = "upload"):
    """
    Procesa un archivo de CV subido (PDF, Word o TXT) ya sea desde carga manual o desde LinkedIn.
    Ejecuta validación, extracción de texto (OCR si aplica), detección de idioma y botones de optimización.
    """
    if uploaded_file is None:
        return

    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name

    try:
        validate_uploaded_file(file_bytes=file_bytes, filename=file_name)

        import hashlib
        file_hash = hashlib.md5(file_bytes).hexdigest()
        current_cached_hash = st.session_state.get("cv_improver_file_hash")

        cached_text = st.session_state.get("cv_improver_raw_text", "")
        is_suspiciously_short = len(cached_text) < 800 and len(file_bytes) > 20000

        if current_cached_hash != file_hash or not cached_text or is_suspiciously_short:
            with st.spinner("📄 Leyendo y extrayendo texto del documento (con soporte OCR)..."):
                raw_text = extract_text_from_file(file_bytes=file_bytes, filename=file_name)
                st.session_state["cv_improver_filename"] = file_name
                st.session_state["cv_improver_file_hash"] = file_hash
                st.session_state["cv_improver_raw_text"] = raw_text
                st.session_state["cv_improver_is_example"] = False
                st.session_state.pop("cv_improver_active_schema", None)
                st.session_state.pop("cv_improver_bullets_status", None)

        raw_cv_text = st.session_state.get("cv_improver_raw_text", "")
        c_info1, c_info2 = st.columns([3, 1])
        with c_info1:
            st.success(f"Archivo **{file_name}** listo para análisis ({len(file_bytes)/1024:.1f} KB · {len(raw_cv_text)} caracteres detectados).")
        with c_info2:
            if st.button("🔄 Re-extraer", help="Forzar nueva extracción y OCR si deseas refrescar la lectura", key=f"btn_force_reextract_{origin_badge}", use_container_width=True):
                st.session_state.pop("cv_improver_file_hash", None)
                st.session_state.pop("cv_improver_raw_text", None)
                st.session_state.pop("cv_improver_active_schema", None)
                st.rerun()

        with st.expander("👁️ Ver texto original detectado en el archivo"):
            st.text_area("Contenido sin procesar:", value=raw_cv_text, height=130, disabled=True, key=f"raw_text_view_{origin_badge}")

    except FileValidationError as ve:
        st.error(f"⚠️ Error de validación: {ve}")
        return
    except Exception as ex:
        st.error(f"⚠️ Error al leer el archivo: {ex}")
        return

    raw_cv_text = st.session_state.get("cv_improver_raw_text", "")
    detected_cv_lang = detect_resume_language(raw_cv_text) if raw_cv_text else "es"

    if detected_cv_lang == "en":
        st.info("🌐 **Idioma detectado en tu currículum:** 🇺🇸 **Inglés**. Por defecto optimizaremos tu CV en inglés respetando el idioma nativo de tu documento.")
    else:
        st.info("🌐 **Idioma detectado en tu currículum:** 🇪🇸 **Español**.")

    st.caption("Selecciona el idioma en el que deseas analizar y redactar las mejoras:")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        is_es = (detected_cv_lang == "es")
        lbl_es = "🇪🇸 Mejorar y Analizar este CV con IA en Español (Detectado)" if is_es else "🇪🇸 Traducir y Analizar este CV en Español"
        if st.button(lbl_es, type="primary" if is_es else "secondary", use_container_width=True, key=f"btn_run_improver_{origin_badge}_es"):
            process_and_enhance_cv(st.session_state["cv_improver_raw_text"], target_language="es")
    with col_btn2:
        is_en = (detected_cv_lang == "en")
        lbl_en = "🇺🇸 Mejorar y Analizar este CV con IA en Inglés (Detectado)" if is_en else "🇺🇸 Mejorar y Analizar este CV con IA en Inglés"
        if st.button(lbl_en, type="primary" if is_en else "secondary", use_container_width=True, key=f"btn_run_improver_{origin_badge}_en"):
            process_and_enhance_cv(st.session_state["cv_improver_raw_text"], target_language="en")


def render_cv_improver_page():
    """Renderiza la sección completa, gráfica y de alto impacto de CV Improver."""
    st.title("✨ CV Improver: Diseños de Alto Impacto y Optimización con IA")
    st.caption("Crea un currículum moderno, limpio y espaciado que destaque ante reclutadores y sistemas ATS con plantillas contemporáneas.")

    # --------------------------------------------------------------------------
    # RESTAURACIÓN AUTOMÁTICA DEL BORRADOR GUARDADO EN SUPABASE
    # --------------------------------------------------------------------------
    if "cv_improver_active_schema" not in st.session_state and not st.session_state.get("cv_improver_draft_discarded"):
        try:
            from database import get_cv_improver_draft
            saved_draft = get_cv_improver_draft()
            if saved_draft and isinstance(saved_draft, dict) and "schema" in saved_draft:
                st.session_state["cv_improver_active_schema"] = ResumeSchema(**saved_draft["schema"])
                st.session_state["cv_improver_bullets_status"] = saved_draft.get("bullets_status", {})
                st.session_state["cv_improver_language"] = saved_draft.get("language", "es")
                st.session_state["cv_improver_filename"] = saved_draft.get("filename", "CV_Optimizado")
                st.session_state["cv_improver_raw_text"] = saved_draft.get("raw_text", "")
                st.session_state["cv_improver_is_example"] = saved_draft.get("is_example", False)
                if "selected_cv_template" in saved_draft:
                    st.session_state["selected_cv_template"] = saved_draft["selected_cv_template"]
        except Exception as e:
            print(f"Aviso al restaurar borrador previo: {e}")

    # AVISO DE PRIVACIDAD Y SEGURIDAD
    st.info(
        "🔒 **Entorno de Trabajo Seguro:** Tu borrador se guarda en la nube para que continúes cuando quieras. "
        "Tus datos maestros en My Profile permanecen intactos."
    )


    # --------------------------------------------------------------------------
    # PASO 1: ¿CÓMO QUIERES EMPEZAR A CREAR TU CV?
    # --------------------------------------------------------------------------
    st.markdown("### 1️⃣ ¿Cómo quieres empezar a crear tu CV?")
    st.caption("Selecciona cómo deseas comenzar tu currículum: cargando un documento propio, explorando un ejemplo profesional de tu sector o importando tu perfil desde LinkedIn:")

    tab_cargar, tab_ejemplos, tab_linkedin = st.tabs([
        "📤 Cargar un CV existente",
        "📚 Empezar con un ejemplo del sector",
        "💼 Importar desde LinkedIn (PDF)"
    ])

    with tab_cargar:
        sub_tab_file, sub_tab_profile = st.tabs([
            "📄 Subir archivo nuevo (PDF, DOCX, TXT)",
            "📋 Cargar copia desde My Profile"
        ])

        with sub_tab_file:
            uploaded_file = st.file_uploader(
                "Arrastra o selecciona tu archivo (máx. 5 MB)",
                type=["pdf", "docx", "txt"],
                key="cv_improver_file_uploader",
                help="Formatos admitidos: PDF con texto seleccionable, Word (.docx) o texto plano (.txt)."
            )
            if uploaded_file is not None:
                _handle_cv_file_uploaded(uploaded_file, origin_badge="upload")

        with sub_tab_profile:
            st.caption("Importa una copia en memoria de tus datos actuales de My Profile para visualizarlos y rediseñarlos con las nuevas plantillas:")
            schema_preview = load_from_user_profile_database()
            profile_sample = (schema_preview.summary or "") + " " + " ".join([b.original for exp in schema_preview.experience for b in exp.bullets])
            detected_prof_lang = detect_resume_language(profile_sample) if profile_sample.strip() else "es"

            if detected_prof_lang == "en":
                st.info("🌐 **Idioma detectado en los datos de My Profile:** 🇺🇸 **Inglés**.")
            else:
                st.info("🌐 **Idioma detectado en los datos de My Profile:** 🇪🇸 **Español**.")

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                is_prof_es = (detected_prof_lang == "es")
                lbl_p_es = "📥 🇪🇸 Importar y Mejorar en Español (Detectado)" if is_prof_es else "📥 🇪🇸 Importar y Mejorar en Español"
                if st.button(lbl_p_es, type="primary" if is_prof_es else "secondary", key="btn_import_from_profile_copy_es", use_container_width=True):
                    try:
                        schema_copy = load_from_user_profile_database()
                        if not schema_copy.experience and not schema_copy.contact.name:
                            st.warning("No tienes datos guardados en My Profile. Sube un archivo en la pestaña anterior.")
                        else:
                            provider, _ = get_active_llm_provider(
                                anthropic_key=st.session_state.get("cv_improver_anthropic_key"),
                                gemini_key=st.session_state.get("cv_improver_gemini_key")
                            )
                            if provider:
                                schema_copy = enhance_resume_content(schema_copy, provider=provider, language="es")
                            st.session_state["cv_improver_filename"] = "Perfil_Importado_MyProfile"
                            st.session_state["cv_improver_active_schema"] = schema_copy
                            st.session_state["cv_improver_language"] = "es"
                            st.session_state["cv_improver_bullets_status"] = {}
                            st.session_state["cv_improver_is_example"] = False
                            st.session_state.pop("cv_improver_draft_discarded", None)
                            persist_active_cv_draft()
                            st.toast("Copia importada y optimizada en Español.", icon="✅")
                            st.rerun()
                    except Exception as imp_err:
                        st.error(f"Error al cargar copia de perfil: {imp_err}")

            with col_p2:
                is_prof_en = (detected_prof_lang == "en")
                lbl_p_en = "📥 🇺🇸 Importar y Mejorar en Inglés (Detectado)" if is_prof_en else "📥 🇺🇸 Importar y Mejorar en Inglés"
                if st.button(lbl_p_en, type="primary" if is_prof_en else "secondary", key="btn_import_from_profile_copy_en", use_container_width=True):
                    try:
                        schema_copy = load_from_user_profile_database()
                        if not schema_copy.experience and not schema_copy.contact.name:
                            st.warning("No tienes datos guardados en My Profile. Sube un archivo en la pestaña anterior.")
                        else:
                            provider, _ = get_active_llm_provider(
                                anthropic_key=st.session_state.get("cv_improver_anthropic_key"),
                                gemini_key=st.session_state.get("cv_improver_gemini_key")
                            )
                            if provider:
                                schema_copy = enhance_resume_content(schema_copy, provider=provider, language="en")
                            st.session_state["cv_improver_filename"] = "Perfil_Importado_MyProfile"
                            st.session_state["cv_improver_active_schema"] = schema_copy
                            st.session_state["cv_improver_language"] = "en"
                            st.session_state["cv_improver_bullets_status"] = {}
                            st.session_state["cv_improver_is_example"] = False
                            st.session_state.pop("cv_improver_draft_discarded", None)
                            persist_active_cv_draft()
                            st.toast("Copia importada y optimizada en Inglés.", icon="✅")
                            st.rerun()
                    except Exception as imp_err:
                        st.error(f"Error al cargar copia de perfil: {imp_err}")

    with tab_ejemplos:
        st.markdown("#### 📚 Plantillas de Ejemplo Fijas por Sector (Sin llamadas a IA)")
        st.caption(
            "Selecciona un currículum modelo prediseñado con las mejores prácticas del sector. "
            "**No consume llamadas a IA** y carga datos genéricos de ejemplo listos para editar y personalizar de inmediato."
        )

        col_sec_sel, col_sec_btn = st.columns([3, 2])
        sector_keys = list(SECTOR_EXAMPLES.keys())
        with col_sec_sel:
            selected_key = st.selectbox(
                "Elige un sector o especialidad:",
                options=sector_keys,
                format_func=lambda k: f"{SECTOR_EXAMPLES[k]['icon']} {SECTOR_EXAMPLES[k]['title']} — {SECTOR_EXAMPLES[k]['role']}",
                key="cv_improver_sector_select"
            )

        info = SECTOR_EXAMPLES[selected_key]
        example_preview = load_example_schema(selected_key)

        with col_sec_btn:
            st.write("")
            st.write("")
            if st.button(
                f"🚀 Cargar ejemplo de {info['title']}",
                key="btn_load_sector_example",
                type="primary",
                use_container_width=True
            ):
                schema_ex = load_example_schema(selected_key)
                st.session_state["cv_improver_filename"] = f"Ejemplo_{selected_key.title()}"
                st.session_state["cv_improver_active_schema"] = schema_ex
                st.session_state["cv_improver_language"] = "es"
                st.session_state["cv_improver_bullets_status"] = {}
                st.session_state["cv_improver_raw_text"] = schema_ex.raw_text or ""
                st.session_state["cv_improver_is_example"] = True
                st.session_state.pop("cv_improver_draft_discarded", None)
                persist_active_cv_draft()
                st.toast(f"¡Plantilla de '{info['title']}' cargada con éxito en el editor!", icon="✨")
                st.rerun()

        with st.container(border=True):
            st.markdown(f"**{info['icon']} {info['title']}** — *{info['role']}*")
            st.write(info["description"])

            with st.expander("👁️ Ver contenido y estructura del ejemplo", expanded=False):
                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    st.markdown("**Resumen Profesional:**")
                    st.write(example_preview.summary)
                    st.markdown("**Experiencias Laborales:**")
                    for exp in example_preview.experience:
                        st.markdown(f"- **{exp.position}** en *{exp.company}* ({exp.start_date} - {exp.end_date})")
                        for b in exp.bullets[:2]:
                            st.caption(f"  • {b.original}")
                with c_p2:
                    st.markdown("**Habilidades Principales:**")
                    for cat in example_preview.skills:
                        st.markdown(f"- **{cat.category}:** {', '.join(cat.skills[:5])}")
                    st.markdown("**Educación:**")
                    for edu in example_preview.education:
                        st.markdown(f"- {edu.degree} · *{edu.institution}*")
                    if example_preview.languages:
                        st.markdown("**Idiomas:**")
                        for lang in example_preview.languages:
                            st.caption(f"• {lang.language}: {lang.proficiency}")

    with tab_linkedin:
        st.markdown("#### 💼 Importar Perfil desde LinkedIn (PDF)")
        st.caption(
            "Dado que LinkedIn no ofrece una integración API pública para perfiles de usuario, "
            "puedes descargar tu perfil oficial en PDF y subirlo aquí. "
            "Entrará exactamente por el mismo motor de parseo y optimización que cualquier otro CV."
        )

        with st.container(border=True):
            st.markdown(
                """
                **📌 Guía rápida para descargar tu CV desde LinkedIn:**
                1. Inicia sesión en **LinkedIn** y ve a tu **Perfil** (haz clic en tu foto o nombre).
                2. En la tarjeta principal debajo de tu foto de portada, haz clic en el botón **Más** (`More...`) situado junto a *"Añadir sección"*.
                3. En el menú desplegable, haz clic en **Guardar como PDF** (`Save to PDF`).
                4. LinkedIn generará y descargará inmediatamente tu currículum oficial en formato `.pdf`.
                5. **Sube ese archivo PDF** en el recuadro inferior para procesarlo:
                """
            )

        linkedin_file = st.file_uploader(
            "Arrastra o selecciona el archivo PDF descargado de tu perfil de LinkedIn",
            type=["pdf"],
            key="cv_improver_linkedin_uploader",
            help="Sube el archivo PDF obtenido desde 'Más → Guardar como PDF' en tu perfil de LinkedIn."
        )
        if linkedin_file is not None:
            _handle_cv_file_uploaded(linkedin_file, origin_badge="linkedin")

    # --------------------------------------------------------------------------
    # PASO 2: PANEL DE MEJORAS Y GALERÍA DE PLANTILLAS
    # --------------------------------------------------------------------------
    resume: ResumeSchema = st.session_state.get("cv_improver_active_schema")
    if resume is not None:
        if "cv_improver_bullets_status" not in st.session_state:
            st.session_state["cv_improver_bullets_status"] = {}

        st.divider()

        col_draft_hdr1, col_draft_hdr2 = st.columns([3.5, 1.5])
        with col_draft_hdr1:
            st.markdown("### 2️⃣ Panel de Mejoras y Plantillas")
            st.caption("💾 **Borrador sincronizado en la nube:** Tu progreso se guarda automáticamente y puedes continuar en cualquier momento.")
        with col_draft_hdr2:
            st.write("")
            if st.button("🗑️ Descartar borrador y reiniciar", key="btn_clear_cv_improver_draft", use_container_width=True, help="Elimina el borrador de trabajo actual en Supabase para empezar desde cero"):
                from database import delete_cv_improver_draft
                delete_cv_improver_draft()
                for k in ["cv_improver_active_schema", "cv_improver_bullets_status", "cv_improver_language", "cv_improver_filename", "cv_improver_raw_text", "cv_improver_file_hash", "cv_improver_is_example"]:
                    st.session_state.pop(k, None)
                st.session_state["cv_improver_draft_discarded"] = True
                st.toast("Borrador descartado con éxito.", icon="ℹ️")
                st.rerun()

        # AVISO VISIBLE CUANDO EL CV ES UN EJEMPLO CON DATOS FICTICIOS
        if is_resume_example_unedited(resume):
            st.warning("⚠️ **Este es un ejemplo con datos ficticios. Reemplázalo con tu información antes de descargar o guardar**")

        # BARRA DE IDIOMA ACTIVO Y CAMBIO RÁPIDO
        active_lang = st.session_state.get("cv_improver_language", "es")
        c_lang_bar1, c_lang_bar2, c_lang_bar3 = st.columns([1.5, 1, 1])
        with c_lang_bar1:
            lang_label_badge = "🇺🇸 Inglés (English)" if active_lang == "en" else "🇪🇸 Español"
            st.markdown(f"🌐 **Idioma de optimización activo:** `{lang_label_badge}`")
        with c_lang_bar2:
            if st.button("🇪🇸 Re-analizar en Español", key="btn_reanalyze_es", use_container_width=True, disabled=(active_lang == "es")):
                if st.session_state.get("cv_improver_raw_text"):
                    process_and_enhance_cv(st.session_state["cv_improver_raw_text"], target_language="es")
                else:
                    provider, _ = get_active_llm_provider(
                        anthropic_key=st.session_state.get("cv_improver_anthropic_key"),
                        gemini_key=st.session_state.get("cv_improver_gemini_key")
                    )
                    if provider:
                        enhanced = enhance_resume_content(resume, provider=provider, language="es")
                        st.session_state["cv_improver_active_schema"] = enhanced
                    st.session_state["cv_improver_language"] = "es"
                    st.rerun()
        with c_lang_bar3:
            if st.button("🇺🇸 Re-analizar en Inglés", key="btn_reanalyze_en", use_container_width=True, disabled=(active_lang == "en")):
                if st.session_state.get("cv_improver_raw_text"):
                    process_and_enhance_cv(st.session_state["cv_improver_raw_text"], target_language="en")
                else:
                    provider, _ = get_active_llm_provider(
                        anthropic_key=st.session_state.get("cv_improver_anthropic_key"),
                        gemini_key=st.session_state.get("cv_improver_gemini_key")
                    )
                    if provider:
                        enhanced = enhance_resume_content(resume, provider=provider, language="en")
                        st.session_state["cv_improver_active_schema"] = enhanced
                    st.session_state["cv_improver_language"] = "en"
                    st.rerun()

        st.divider()

        total_bullets = sum(len(exp.bullets) for exp in resume.experience)
        improved_count = sum(sum(1 for b in exp.bullets if b.improved and b.improved != b.original) for exp in resume.experience)
        suggestions_count = sum(sum(1 for b in exp.bullets if b.suggestion) for exp in resume.experience)

        # ----------------------------------------------------------------------
        # SCORECARD EJECUTIVO DE MEJORAS GRÁFICAS
        # ----------------------------------------------------------------------
        st.markdown("### 📊 Tablero de Impacto y Optimización")
        
        # Tarjetas estilizadas de métricas
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        with m_c1:
            st.metric(
                label="🎯 Score ATS Estimado",
                value="96%",
                delta="+42% de optimización",
                help="Legibilidad de entidades y palabras clave evaluadas por sistemas ATS."
            )
        with m_c2:
            st.metric(
                label="⚡ Verbos de Acción Activos",
                value=f"{improved_count} de {total_bullets}",
                delta="100% dinámicos",
                help="Viñetas reescritas iniciando con verbos en pasado eliminando frases pasivas."
            )
        with m_c3:
            st.metric(
                label="💡 Sugerencias de Cuantificación",
                value=suggestions_count,
                help="Preguntas clave para enriquecer logros con cifras concretas."
            )
        with m_c4:
            st.metric(
                label="🏢 Empleos con Fechas y Cargos",
                value=len(resume.experience),
                help="Cargos y empresas estructurados cronológicamente con fechas de inicio y fin."
            )

        # ----------------------------------------------------------------------
        # NAVEGACIÓN PRINCIPAL: PLANTILLAS / COMPARATIVA / EDICIÓN
        # ----------------------------------------------------------------------
        tab_plantillas, tab_comparativa, tab_edicion = st.tabs([
            "🎨 Galería de Plantillas y Descarga",
            "🔍 Comparativa Visual de Mejoras",
            "✏️ Editor y Ajuste de Datos"
        ])

        # ======================================================================
        # PESTAÑA 1: GALERÍA DE PLANTILLAS LLAMATIVAS CON MINI-MOCKUPS
        # ======================================================================
        with tab_plantillas:
            st.markdown("#### 🌟 Elige una Plantilla de Alto Impacto")
            st.caption("Cada plantilla acomoda la información de forma diferente según tu área profesional, con diseños modernos, limpios y optimizados:")

            current_template = st.session_state.get("selected_cv_template", "moderna")

            # WIREFRAME MOCKUPS EN CSS PARA CADA PLANTILLA
            col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)

            # Plantilla 1: Neo-Executive
            with col_t1:
                with st.container(border=True):
                    # Mockup Wireframe
                    st.markdown("""
                    <div style="height: 90px; background: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 6px; display: flex; overflow: hidden; margin-bottom: 8px;">
                      <div style="width: 35%; background: #0F172A; padding: 8px 4px; text-align: center;">
                        <div style="width: 18px; height: 18px; border-radius: 50%; background: #3B82F6; margin: 0 auto 6px auto;"></div>
                        <div style="height: 3px; background: #64748B; border-radius: 2px; margin-bottom: 3px;"></div>
                        <div style="height: 3px; background: #475569; border-radius: 2px; width: 70%; margin: 0 auto 5px auto;"></div>
                        <div style="height: 2px; background: #334155; margin-bottom: 2px;"></div>
                        <div style="height: 2px; background: #334155;"></div>
                      </div>
                      <div style="width: 65%; padding: 8px 6px;">
                        <div style="height: 5px; background: #3B82F6; width: 60%; border-radius: 2px; margin-bottom: 6px;"></div>
                        <div style="height: 3px; background: #CBD5E1; border-radius: 2px; margin-bottom: 4px;"></div>
                        <div style="height: 3px; background: #E2E8F0; border-radius: 2px; margin-bottom: 8px;"></div>
                        <div style="height: 4px; background: #0F172A; width: 50%; border-radius: 2px; margin-bottom: 3px;"></div>
                        <div style="height: 2px; background: #94A3B8; width: 90%; margin-bottom: 2px;"></div>
                        <div style="height: 2px; background: #CBD5E1; width: 85%;"></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("**🌟 Neo-Ejecutiva**")
                    st.markdown(
                        "<div style='min-height: 56px; background: rgba(59, 130, 246, 0.10); border-left: 3px solid #3B82F6; padding: 5px 7px; border-radius: 4px; font-size: 0.73rem; line-height: 1.3; margin: 4px 0 6px 0;'>"
                        "<strong style='color: #60A5FA; display: block; font-size: 0.72rem; margin-bottom: 2px;'>🎯 Área recomendada:</strong>"
                        "<span style='opacity: 0.95;'>Gerencia, Ventas B2B, RRHH, Negocios y Consultoría</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )
                    st.caption("📌 **Ideal:** Gerencia, Ventas B2B, RRHH y Negocios.\n\n*Sidebar de contraste, monograma y timeline ejecutiva.*")
                    if st.button("Elegir Neo-Ejecutiva", key="btn_pick_mod", use_container_width=True, type="primary" if current_template == "moderna" else "secondary"):
                        st.session_state["selected_cv_template"] = "moderna"
                        st.rerun()

            # Plantilla 2: Zafiro Tech
            with col_t2:
                with st.container(border=True):
                    # Mockup Wireframe
                    st.markdown("""
                    <div style="height: 90px; background: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 6px; overflow: hidden; margin-bottom: 8px;">
                      <div style="height: 26px; background: #1E40AF; padding: 4px 6px;">
                        <div style="height: 5px; background: #FFFFFF; width: 50%; border-radius: 2px; margin-bottom: 3px;"></div>
                        <div style="height: 3px; background: rgba(255,255,255,0.7); width: 30%; border-radius: 2px;"></div>
                      </div>
                      <div style="display: flex; padding: 6px 4px; gap: 4px;">
                        <div style="width: 65%;">
                          <div style="height: 4px; background: #1E40AF; width: 45%; margin-bottom: 4px;"></div>
                          <div style="height: 2px; background: #64748B; margin-bottom: 2px;"></div>
                          <div style="height: 2px; background: #94A3B8; margin-bottom: 2px;"></div>
                          <div style="height: 2px; background: #CBD5E1;"></div>
                        </div>
                        <div style="width: 35%; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 3px; padding: 3px;">
                          <div style="height: 3px; background: #475569; margin-bottom: 3px;"></div>
                          <div style="height: 2px; background: #94A3B8; margin-bottom: 2px;"></div>
                          <div style="height: 2px; background: #CBD5E1;"></div>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("**💎 Zafiro Tech**")
                    st.markdown(
                        "<div style='min-height: 56px; background: rgba(37, 99, 235, 0.10); border-left: 3px solid #2563EB; padding: 5px 7px; border-radius: 4px; font-size: 0.73rem; line-height: 1.3; margin: 4px 0 6px 0;'>"
                        "<strong style='color: #60A5FA; display: block; font-size: 0.72rem; margin-bottom: 2px;'>🎯 Área recomendada:</strong>"
                        "<span style='opacity: 0.95;'>Informática, Developers, Soporte Técnico, Cloud y TI</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )
                    st.caption("📌 **Ideal:** Informática, Developers, Soporte Técnico y TI.\n\n*Hero banner superior, 2 columnas y tarjetas Bento.*")
                    if st.button("Elegir Zafiro", key="btn_pick_zaf", use_container_width=True, type="primary" if current_template == "zafiro" else "secondary"):
                        st.session_state["selected_cv_template"] = "zafiro"
                        st.rerun()

            # Plantilla 3: Vanguardia
            with col_t3:
                with st.container(border=True):
                    # Mockup Wireframe
                    st.markdown("""
                    <div style="height: 90px; background: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 6px; overflow: hidden; margin-bottom: 8px;">
                      <div style="height: 4px; background: #0284C7; margin-bottom: 4px;"></div>
                      <div style="padding: 4px 6px;">
                        <div style="height: 6px; background: #0F172A; width: 40%; border-radius: 2px; margin-bottom: 2px;"></div>
                        <div style="height: 3px; background: #0284C7; width: 25%; margin-bottom: 5px;"></div>
                        <div style="display: flex; gap: 4px;">
                          <div style="width: 65%;">
                            <div style="height: 3px; background: #0284C7; width: 40%; margin-bottom: 3px;"></div>
                            <div style="height: 2px; background: #64748B; margin-bottom: 2px;"></div>
                            <div style="height: 2px; background: #94A3B8; margin-bottom: 2px;"></div>
                            <div style="height: 2px; background: #CBD5E1;"></div>
                          </div>
                          <div style="width: 35%; border-left: 1px solid #E2E8F0; padding-left: 3px;">
                            <div style="height: 3px; background: #475569; margin-bottom: 3px;"></div>
                            <div style="height: 2px; background: #CBD5E1; margin-bottom: 2px;"></div>
                            <div style="height: 2px; background: #CBD5E1;"></div>
                          </div>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("**🚀 Vanguardia**")
                    st.markdown(
                        "<div style='min-height: 56px; background: rgba(2, 132, 199, 0.10); border-left: 3px solid #0284C7; padding: 5px 7px; border-radius: 4px; font-size: 0.73rem; line-height: 1.3; margin: 4px 0 6px 0;'>"
                        "<strong style='color: #38BDF8; display: block; font-size: 0.72rem; margin-bottom: 2px;'>🎯 Área recomendada:</strong>"
                        "<span style='opacity: 0.95;'>Marketing, Diseño UI/UX, Producto, Creativos y Growth</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )
                    st.caption("📌 **Ideal:** Marketing, Diseño UI/UX, Producto y Creativos.\n\n*Acento superior, timeline de hitos y badges modernos.*")
                    if st.button("Elegir Vanguardia", key="btn_pick_vg", use_container_width=True, type="primary" if current_template == "vanguardia" else "secondary"):
                        st.session_state["selected_cv_template"] = "vanguardia"
                        st.rerun()

            # Plantilla 4: Nórdica Editorial
            with col_t4:
                with st.container(border=True):
                    # Mockup Wireframe
                    st.markdown("""
                    <div style="height: 90px; background: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 6px; padding: 8px 8px; margin-bottom: 8px;">
                      <div style="height: 6px; background: #0F172A; width: 45%; margin-bottom: 3px;"></div>
                      <div style="height: 3px; background: #64748B; width: 30%; margin-bottom: 6px;"></div>
                      <div style="height: 1px; background: #E2E8F0; margin-bottom: 5px;"></div>
                      <div style="height: 3px; background: #475569; width: 25%; margin-bottom: 4px;"></div>
                      <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                        <div style="height: 2.5px; background: #0F172A; width: 40%;"></div>
                        <div style="height: 2px; background: #94A3B8; width: 20%;"></div>
                      </div>
                      <div style="height: 2px; background: #64748B; width: 85%; margin-bottom: 2px;"></div>
                      <div style="height: 2px; background: #CBD5E1; width: 75%;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("**🌿 Nórdica**")
                    st.markdown(
                        "<div style='min-height: 56px; background: rgba(16, 185, 129, 0.10); border-left: 3px solid #10B981; padding: 5px 7px; border-radius: 4px; font-size: 0.73rem; line-height: 1.3; margin: 4px 0 6px 0;'>"
                        "<strong style='color: #34D399; display: block; font-size: 0.72rem; margin-bottom: 2px;'>🎯 Área recomendada:</strong>"
                        "<span style='opacity: 0.95;'>Finanzas, Contabilidad, Legal, Consultoría y Redacción</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )
                    st.caption("📌 **Ideal:** Finanzas, Contabilidad, Legal y Consultoría.\n\n*Mucho aire blanco, tipografía ligera y alta legibilidad.*")
                    if st.button("Elegir Nórdica", key="btn_pick_nord", use_container_width=True, type="primary" if current_template == "minimalista" else "secondary"):
                        st.session_state["selected_cv_template"] = "minimalista"
                        st.rerun()

            # Plantilla 5: Clásica ATS
            with col_t5:
                with st.container(border=True):
                    # Mockup Wireframe
                    st.markdown("""
                    <div style="height: 90px; background: #FFFFFF; border: 1.5px solid #CBD5E1; border-radius: 6px; padding: 6px 8px; text-align: center; margin-bottom: 8px;">
                      <div style="height: 5px; background: #1E3A8A; width: 50%; margin: 0 auto 3px auto;"></div>
                      <div style="height: 2.5px; background: #64748B; width: 35%; margin: 0 auto 4px auto;"></div>
                      <div style="height: 1.5px; background: #1E3A8A; margin-bottom: 5px;"></div>
                      <div style="height: 3px; background: #1E3A8A; width: 30%; margin-bottom: 3px; text-align: left;"></div>
                      <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                        <div style="height: 2.5px; background: #0F172A; width: 45%;"></div>
                        <div style="height: 2px; background: #64748B; width: 25%;"></div>
                      </div>
                      <div style="height: 2px; background: #64748B; width: 90%; margin-bottom: 2px; text-align: left;"></div>
                      <div style="height: 2px; background: #CBD5E1; width: 80%; text-align: left;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("**🏛️ Clásica ATS**")
                    st.markdown(
                        "<div style='min-height: 56px; background: rgba(148, 163, 184, 0.10); border-left: 3px solid #94A3B8; padding: 5px 7px; border-radius: 4px; font-size: 0.73rem; line-height: 1.3; margin: 4px 0 6px 0;'>"
                        "<strong style='color: #CBD5E1; display: block; font-size: 0.72rem; margin-bottom: 2px;'>🎯 Área recomendada:</strong>"
                        "<span style='opacity: 0.95;'>Ingeniería Tradicional, Banca, Sector Público y Operaciones</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )
                    st.caption("📌 **Ideal:** Ingeniería Tradicional, Banca, Sector Público y Operaciones.\n\n*1 columna tradicional suiza, 100% compatible ATS estricto.*")
                    if st.button("Elegir Clásica", key="btn_pick_clas", use_container_width=True, type="primary" if current_template == "clasica" else "secondary"):
                        st.session_state["selected_cv_template"] = "clasica"
                        st.rerun()

            st.divider()

            # PALETAS Y PERSONALIZACIÓN DE COLOR
            color_presets = {
                # Azules Corporativos y Tecnológicos
                "🏛️ Azul Marino Ejecutivo (Navy)": "#1E3A8A",
                "💎 Azul Zafiro Real (Sapphire)": "#1D4ED8",
                "⚡ Azul Acero Tech (Steel Blue)": "#2563EB",
                "🌌 Azul Noche Profundo (Midnight)": "#0F172A",
                # Escala de Grises y Neutros Sobrios
                "💼 Gris Carbón Slate (Charcoal)": "#334155",
                "🏢 Gris Grafito Neutro (Graphite)": "#1F2937",
                "📐 Gris Pizarra Oscuro (Dark Slate)": "#475569",
                "🖤 Negro Ébano Minimalista (Obsidian)": "#111827",
                # Verdes y Petróleos Ejecutivos
                "🌲 Verde Esmeralda Ejecutivo (Emerald)": "#065F46",
                "🌿 Verde Bosque Sobrio (Forest Green)": "#166534",
                "🌊 Verde Petróleo / Deep Teal": "#0F766E",
                "🍃 Ciprés / Eucalipto Oscuro": "#115E59",
                # Burdeos, Vinos y Terracotas Distinguidos
                "🍷 Burdeos / Borgoña Real (Burgundy)": "#881337",
                "🌹 Rojo Vino Ejecutivo (Cabernet)": "#991B1B",
                "🏺 Terracota / Bronce Cálido (Warm Bronze)": "#9A3412",
                "☕ Café Moca / Espresso Ejecutivo": "#78350F",
                # Púrpuras e Índigos de Liderazgo
                "🔮 Índigo Real Profundo (Royal Indigo)": "#4338CA",
                "🍇 Ciruela Oscuro Ejecutivo (Deep Plum)": "#581C87"
            }

            if "preset_color_select" not in st.session_state or st.session_state["preset_color_select"] not in color_presets:
                st.session_state["preset_color_select"] = "🏛️ Azul Marino Ejecutivo (Navy)"

            if "custom_color_picker" not in st.session_state:
                st.session_state["custom_color_picker"] = color_presets[st.session_state["preset_color_select"]]

            def on_preset_color_change():
                sel = st.session_state.get("preset_color_select")
                if sel and sel in color_presets:
                    st.session_state["custom_color_picker"] = color_presets[sel]

            col_p1, col_p2 = st.columns([2, 1])
            with col_p1:
                preset_choice = st.selectbox(
                    "🎨 Paleta de Acento Recomendada:",
                    options=list(color_presets.keys()),
                    key="preset_color_select",
                    on_change=on_preset_color_change,
                    help="Colores ejecutivos de alto contraste y legibilidad seleccionados especialmente para currículums profesionales."
                )

            with col_p2:
                selected_color = st.color_picker(
                    "Color personalizado / Ajuste fino:",
                    key="custom_color_picker"
                )

            # SINCRONIZAR Y RENDERIZAR
            export_resume = prepare_export_ready_resume(resume, st.session_state["cv_improver_bullets_status"])
            active_lang = st.session_state.get("cv_improver_language", "es")
            html_preview = render_cv_to_html(
                resume=export_resume,
                template_name=current_template,
                accent_color=selected_color,
                language=active_lang
            )

            # VISTA PREVIA EN VIVO
            st.markdown(f"##### 👁️ Previsualización en Vivo: *Plantilla {current_template.capitalize()}*")
            components.html(html_preview, height=780, scrolling=True)

            # BOTÓN PRINCIPAL DE DESCARGA EN PDF CON DISEÑO IDÉNTICO
            st.markdown("##### 📥 Descargar tu Currículum en PDF")

            is_example_active = is_resume_example_unedited(export_resume)
            can_download = True

            if is_example_active:
                st.warning("⚠️ **Este es un ejemplo con datos ficticios. Reemplázalo con tu información antes de descargar o guardar**")
                confirm_download = st.checkbox(
                    "Confirmo explícitamente que este currículum contiene datos ficticios de ejemplo y deseo descargarlo de todas formas.",
                    key="chk_confirm_download_fictitious_example"
                )
                can_download = confirm_download
                if not can_download:
                    st.info("💡 Para descargar tu currículum en PDF, completa tus datos reales en la pestaña **✏️ Ajuste y Edición** o confirma arriba que contiene datos ficticios marcando la casilla.")

            if can_download:
                st.success(f"✨ **Descarga en PDF Lista:** El documento se descargará directamente en **archivo .pdf** con el **100% de la fidelidad visual de la plantilla {current_template.capitalize()}** (mismos colores, cuadros de habilidades y stack, divisiones y tipografía idéntica a la previsualización).")

                try:
                    pdf_bytes, pages, engine = render_cv_to_pdf(
                        resume=export_resume,
                        template_name=current_template,
                        accent_color=selected_color,
                        language=active_lang
                    )
                    raw_slug = (export_resume.contact.name or "").strip().replace(' ', '_')
                    name_slug = raw_slug if raw_slug else "Ejemplo_CV"
                    clean_name = f"CV_{name_slug}_{current_template.capitalize()}.pdf"
                    st.download_button(
                        label=f"📥 DESCARGAR CV EN PDF ({current_template.capitalize()} · {pages} pág{'s' if pages > 1 else ''})",
                        data=pdf_bytes,
                        file_name=clean_name,
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                        key="btn_download_cv_pdf_main_action"
                    )
                    st.caption(f"🔒 Archivo: **`{clean_name}`** (Formato PDF oficial) | Motor: `{engine}`.")
                except Exception as e:
                    st.error(f"Error generando PDF: {e}")

                # Exportación opcional alternativa en Word
                with st.expander("📄 ¿Deseas también una copia en Microsoft Word (.docx)?", expanded=False):
                    st.caption("Nota: El archivo de Word es un documento de texto editable estándar (.docx). Para conservar el diseño visual idéntico con cuadros, colores y columnas, utiliza el botón principal de PDF arriba.")
                    try:
                        docx_bytes = render_cv_to_docx(
                            resume=export_resume,
                            accent_hex=selected_color,
                            language=active_lang
                        )
                        clean_name_docx = f"CV_{name_slug}.docx"
                        st.download_button(
                            label="📄 Descargar copia en Word (.docx)",
                            data=docx_bytes,
                            file_name=clean_name_docx,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="btn_download_docx_optional"
                        )
                    except Exception as e:
                        st.error(f"Error generando DOCX: {e}")

        # ======================================================================
        # PESTAÑA 2: COMPARATIVA VISUAL DE MEJORAS
        # ======================================================================
        with tab_comparativa:
            st.markdown("#### 🔍 Comparativa Visual Antes vs Después")
            st.caption("Revisa cómo la IA optimizó cada viñeta bajo la fórmula Acción + Contexto + Resultado, eliminando lenguaje pasivo:")

            # COMPARATIVA PERFIL PROFESIONAL
            if resume.summary:
                with st.container(border=True):
                    st.markdown("##### 📝 Perfil Profesional")
                    c_s1, c_s2 = st.columns(2)
                    with c_s1:
                        st.markdown("**🔴 Perfil Inicial:**")
                        st.info(resume.summary)
                    with c_s2:
                        st.markdown("**🟢 Perfil Optimizado con IA (Enfoque en Valor):**")
                        st.success(resume.summary_improved or resume.summary)

            # COMPARATIVA EXPERIENCIAS LABORALES
            if not resume.experience:
                st.info("No se detectaron experiencias laborales en el texto.")
            else:
                for exp_idx, exp in enumerate(resume.experience):
                    present_str = "Present" if active_lang == "en" else "Presente"
                    na_str = "N/A" if active_lang == "en" else "S/F"
                    date_badge = f"{exp.start_date or na_str} – {present_str if exp.current else (exp.end_date or na_str)}"
                    
                    st.markdown(f"##### 💼 **{exp.position}** en **{exp.company}** · `{date_badge}`")

                    for b_idx, bullet in enumerate(exp.bullets):
                        b_key = f"cv_imp_b_{exp_idx}_{b_idx}"
                        if b_key not in st.session_state["cv_improver_bullets_status"]:
                            st.session_state["cv_improver_bullets_status"][b_key] = "improved" if bullet.improved else "original"

                        current_status = st.session_state["cv_improver_bullets_status"][b_key]

                        with st.container(border=True):
                            c_b1, c_b2 = st.columns(2)
                            with c_b1:
                                st.markdown("**🔴 Viñeta Original:**")
                                st.info(bullet.original)
                            
                            with c_b2:
                                st.markdown("**🟢 Viñeta Optimizada con IA (Enfoque en Valor):**")
                                st.success(bullet.improved or bullet.original)

                            if bullet.suggestion:
                                st.warning(f"💡 **Pregunta del Reclutador para Cuantificar:** {bullet.suggestion}")

                            # Control de estado de un clic
                            c_act1, c_act2 = st.columns(2)
                            with c_act1:
                                if current_status == "improved":
                                    st.success("✅ Versión optimizada activa para exportar.")
                                else:
                                    if st.button(f"✨ Usar versión optimizada", key=f"btn_apply_{b_key}", use_container_width=True):
                                        st.session_state["cv_improver_bullets_status"][b_key] = "improved"
                                        st.rerun()
                            with c_act2:
                                if current_status == "original":
                                    st.info("↩️ Versión original activa para exportar.")
                                else:
                                    if st.button(f"↩️ Mantener original", key=f"btn_keep_{b_key}", use_container_width=True):
                                        st.session_state["cv_improver_bullets_status"][b_key] = "original"
                                        st.rerun()

        # ======================================================================
        # PESTAÑA 3: EDITOR Y AJUSTE DE DATOS
        # ======================================================================
        with tab_edicion:
            st.markdown("#### ✏️ Ajuste y Edición de Entidades")
            st.caption("Verifica o modifica directamente los nombres de empresas, puestos, fechas, educación y habilidades:")

            is_example_active = is_resume_example_unedited(resume)
            if is_example_active:
                st.warning("⚠️ **Este es un ejemplo con datos ficticios. Reemplázalo con tu información antes de descargar o guardar**")

            # EDITAR DATOS DE CONTACTO Y ENLACES
            with st.expander("👤 Datos de Contacto (Nombre, Correo, Teléfono, Ubicación, Enlaces)", expanded=True):
                c_c1, c_c2 = st.columns(2)
                with c_c1:
                    resume.contact.name = st.text_input("Nombre Completo *:", value=resume.contact.name or "", key="edit_contact_name")
                    resume.contact.email = st.text_input("Correo Electrónico:", value=resume.contact.email or "", key="edit_contact_email")
                    resume.contact.phone = st.text_input("Teléfono / WhatsApp:", value=resume.contact.phone or "", key="edit_contact_phone")
                with c_c2:
                    resume.contact.location = st.text_input("Ubicación (Ciudad, País):", value=resume.contact.location or "", key="edit_contact_location")
                    resume.contact.linkedin = st.text_input("LinkedIn (URL):", value=resume.contact.linkedin or "", key="edit_contact_linkedin")
                    resume.contact.github = st.text_input("GitHub / Portafolio (URL):", value=resume.contact.github or resume.contact.portfolio or "", key="edit_contact_github")

            # EDITAR EXPERIENCIAS
            with st.expander("💼 Experiencias Laborales (Fechas, Empresas, Puestos)", expanded=True):
                for exp_idx, exp in enumerate(resume.experience):
                    st.markdown(f"**Puesto #{exp_idx + 1}:**")
                    c_e1, c_e2, c_e3 = st.columns([2, 2, 1])
                    with c_e1:
                        exp.position = st.text_input("Cargo / Puesto:", value=exp.position, key=f"edit_pos_{exp_idx}")
                    with c_e2:
                        exp.company = st.text_input("Empresa:", value=exp.company, key=f"edit_comp_{exp_idx}")
                    with c_e3:
                        exp.start_date = st.text_input("Fecha Inicio:", value=exp.start_date or "", key=f"edit_sd_{exp_idx}")

                    c_e4, c_e5, c_e6 = st.columns([1, 1.5, 1.5])
                    with c_e4:
                        exp.end_date = st.text_input("Fecha Fin:", value=exp.end_date or "", key=f"edit_ed_{exp_idx}")
                    with c_e5:
                        exp.current = st.checkbox("Trabajo actual en curso", value=exp.current, key=f"edit_cur_{exp_idx}")
                    with c_e6:
                        exp.location = st.text_input("Ubicación / Modalidad:", value=exp.location or "", key=f"edit_loc_{exp_idx}")

                    # Editar texto activo de los bullets de esta experiencia
                    for b_idx, bullet in enumerate(exp.bullets):
                        b_key = f"cv_imp_b_{exp_idx}_{b_idx}"
                        cur_status = st.session_state["cv_improver_bullets_status"].get(b_key, "improved")
                        val = bullet.improved if cur_status == "improved" else bullet.original
                        edited_txt = st.text_area(f"Viñeta {b_idx + 1}:", value=val or "", key=f"edit_bullet_txt_{b_key}", height=70)
                        if cur_status == "improved":
                            bullet.improved = edited_txt
                        else:
                            bullet.original = edited_txt

            # EDITAR RESUMEN
            with st.expander("📝 Perfil Profesional", expanded=False):
                resume.summary_improved = st.text_area(
                    "Texto activo del resumen:",
                    value=resume.summary_improved or resume.summary or "",
                    key="edit_sum_final",
                    height=100
                )

            # EDITAR EDUCACIÓN
            with st.expander(f"🎓 Educación y Títulos ({len(resume.education)})", expanded=False):
                for edu_idx, edu in enumerate(resume.education):
                    c_ed1, c_ed2, c_ed3 = st.columns([2, 2, 1])
                    with c_ed1:
                        edu.degree = st.text_input("Título:", value=edu.degree, key=f"ed_d_{edu_idx}")
                    with c_ed2:
                        edu.institution = st.text_input("Institución:", value=edu.institution, key=f"ed_i_{edu_idx}")
                    with c_ed3:
                        edu.start_date = st.text_input("Inicio:", value=edu.start_date or "", key=f"ed_s_{edu_idx}")

                    c_ed4, c_ed5 = st.columns([1, 2])
                    with c_ed4:
                        edu.end_date = st.text_input("Fin / Graduación:", value=edu.end_date or "", key=f"ed_e_{edu_idx}")
                    with c_ed5:
                        edu.field_of_study = st.text_input("Especialidad:", value=edu.field_of_study or "", key=f"ed_f_{edu_idx}")

            # EDITAR HABILIDADES
            with st.expander(f"🛠️ Habilidades Técnicas ({len(resume.skills)})", expanded=False):
                for sc_idx, sc in enumerate(resume.skills):
                    st.markdown(f"**Categoría:** `{sc.category}`")
                    s_str = ", ".join(sc.skills)
                    ed_s = st.text_input("Habilidades (separadas por coma):", value=s_str, key=f"ed_sk_{sc_idx}")
                    sc.skills = [s.strip() for s in ed_s.split(",") if s.strip()]

            # GUARDAR EN EL PERFIL MAESTRO CON PROTECCIÓN ESTRICTA
            st.divider()
            with st.expander("💾 Guardar datos en My Profile", expanded=False):
                st.caption("Actualiza los datos maestros de tu cuenta en My Profile a partir de este currículum.")
                from database import get_user_profile, save_user_profile, get_all_experiences
                existing_profile = get_user_profile() or {}
                has_real_profile = bool(
                    existing_profile.get("full_name")
                    or existing_profile.get("email")
                    or existing_profile.get("summary")
                    or get_all_experiences()
                )

                can_save_profile = True
                confirm_save_profile = False

                if is_example_active:
                    st.warning("⚠️ **Este es un ejemplo con datos ficticios. Reemplázalo con tu información antes de descargar o guardar**")
                    if has_real_profile:
                        st.error("🛡️ **Operación Bloqueada:** Tu cuenta ya cuenta con un perfil real guardado. Para proteger tus datos, nunca se sobrescribe el perfil real del usuario con datos de un ejemplo.")
                        can_save_profile = False
                    else:
                        confirm_save_profile = st.checkbox(
                            "Confirmo explícitamente que este currículum contiene datos ficticios y deseo guardarlo en mi perfil de todas formas.",
                            key="chk_confirm_profile_fictitious_save"
                        )
                        can_save_profile = confirm_save_profile
                        if not can_save_profile:
                            st.info("💡 Completa tus datos reales en el formulario superior o marca la confirmación para habilitar el guardado.")

                first_exp = resume.experience[0].position if resume.experience else None
                if st.button("💾 Guardar en My Profile", disabled=not can_save_profile, key="btn_save_active_to_profile"):
                    if is_example_active and has_real_profile:
                        st.error("Operación bloqueada: Nunca se sobrescribe el perfil real del usuario con datos del ejemplo.")
                    elif is_example_active and not confirm_save_profile:
                        st.error("No se puede guardar en el perfil sin una confirmación explícita de que contiene datos ficticios.")
                    else:
                        save_user_profile(
                            full_name=resume.contact.name or None,
                            current_title=first_exp,
                            email=resume.contact.email or None,
                            phone=resume.contact.phone or None,
                            location=resume.contact.location or None,
                            summary=resume.summary_improved or resume.summary or None
                        )
                        st.success("✅ Perfil maestro actualizado con éxito en My Profile.")
                        st.rerun()

        # Auto-guardado en Supabase del progreso actual
        persist_active_cv_draft()

        # Enlace a Adaptar a una vacante
        st.divider()
        st.markdown("### 🎯 ¿Deseas postularte a una vacante específica?")
        st.caption("Adapta este currículum a los requisitos de una oferta concreta, destacando tus competencias más relevantes.")
        if st.button("🚀 Adaptar mi CV a una vacante específica", key="btn_goto_tailor_cv_from_improver", use_container_width=True):
            st.session_state["main_nav_radio"] = "tailor_cv"
            st.rerun()
