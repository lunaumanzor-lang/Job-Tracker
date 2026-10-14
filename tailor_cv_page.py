"""
Módulo de interfaz gráfica para la adaptación de currículums a vacantes laborales específicas.
Permite contrastar el CV actual contra los requerimientos de una oferta, generar propuestas
éticas de reformulación con IA en una sola llamada y gestionar versiones independientes
sin sobreescribir el perfil maestro ni el borrador de CV Improver.
"""

import time
import copy
from typing import Dict, Any, Optional, List
import importlib
import streamlit as st

import database
if not hasattr(database, "save_tailored_cv_version"):
    importlib.reload(database)

from database import (
    get_all_applications,
    get_application_by_id,
    save_tailored_cv_version,
    get_tailored_cv_versions,
    get_tailored_cv_version_by_id,
    delete_tailored_cv_version,
)
from job_scraper import extract_job_text_from_url
from ai_service import adapt_resume_to_job
from cv_improver.schema import (
    ResumeSchema,
    ExperienceItem,
    BulletItem
)
from cv_improver.ui import load_from_user_profile_database
from cv_improver.renderer import render_cv_to_pdf, render_cv_to_docx, render_cv_to_html


def get_base_resume() -> ResumeSchema:
    """
    Obtiene el currículum de partida para la adaptación:
    Prioriza el borrador activo en CV Improver si existe; de lo contrario,
    lo carga desde la base de datos de My Profile.
    """
    if "cv_improver_active_schema" in st.session_state and st.session_state["cv_improver_active_schema"]:
        active = st.session_state["cv_improver_active_schema"]
        if isinstance(active, ResumeSchema):
            return copy.deepcopy(active)
        elif isinstance(active, dict):
            try:
                return ResumeSchema(**active)
            except Exception:
                pass
    return load_from_user_profile_database()


def build_adapted_resume_from_choices(
    base_resume: ResumeSchema,
    adaptation_data: Dict[str, Any],
    accepted_summary: bool,
    accepted_bullets: Dict[str, bool]
) -> ResumeSchema:
    """
    Construye un nuevo ResumeSchema aplicando ÚNICAMENTE los cambios aceptados por el usuario.
    Nada entra al CV adaptado sin aceptación explícita.
    """
    new_cv = copy.deepcopy(base_resume)

    # 1. Resumen
    if accepted_summary and adaptation_data.get("summary_adapted"):
        new_cv.summary = adaptation_data["summary_adapted"]
        new_cv.summary_improved = adaptation_data["summary_adapted"]

    # 2. Experiencias y viñetas
    adapted_exps = adaptation_data.get("experiences", [])
    for exp_idx, exp in enumerate(new_cv.experience):
        # Buscar la experiencia adaptada correspondiente
        matching_adapted = None
        if exp_idx < len(adapted_exps):
            matching_adapted = adapted_exps[exp_idx]

        if matching_adapted and "bullets" in matching_adapted:
            ad_bullets = matching_adapted["bullets"]
            for b_idx, bullet in enumerate(exp.bullets):
                bullet_key = f"exp_{exp_idx}_b_{b_idx}"
                if accepted_bullets.get(bullet_key, False):
                    # El usuario aceptó el cambio adaptado
                    if b_idx < len(ad_bullets):
                        cand_adapted = ad_bullets[b_idx].get("adapted")
                        if cand_adapted:
                            bullet.original = cand_adapted
                            bullet.improved = cand_adapted

    return new_cv


def render_tailor_cv_page():
    """Renderiza la página completa de 'Adaptar a una vacante'."""
    lang = st.session_state.get("lang", "es")

    st.title("🎯 Adaptar a una vacante" if lang == "es" else "🎯 Tailor CV to a Job")
    st.subheader(
        "Adapta tu currículum a esa vacante, destacando la experiencia y las competencias que realmente posees."
        if lang == "es"
        else "Tailor your resume to that specific job, highlighting the experience and skills you truly possess."
    )
    st.divider()

    # --------------------------------------------------------------------------
    # 1. VALIDACIÓN DEL CV BASE (REQUISITO: RESUMEN Y AL MENOS 1 EXPERIENCIA)
    # --------------------------------------------------------------------------
    base_cv = get_base_resume()

    has_summary = bool(base_cv.summary and base_cv.summary.strip())
    has_experience = bool(base_cv.experience and len(base_cv.experience) > 0)
    has_bullets = any(len(e.bullets) > 0 for e in base_cv.experience) if has_experience else False

    is_cv_ready = has_summary and has_experience and has_bullets

    if not is_cv_ready:
        st.error(
            "⚠️ **Tu currículum base aún no está listo para ser adaptado.**"
            if lang == "es" else "⚠️ **Your base resume is not ready to be tailored yet.**"
        )
        missing_msgs = []
        if not has_summary:
            missing_msgs.append("• Falta el resumen profesional (Summary).")
        if not has_experience:
            missing_msgs.append("• Falta registrar al menos una experiencia laboral.")
        elif not has_bullets:
            missing_msgs.append("• Tus experiencias registradas no cuentan con viñetas o logros descritos.")

        for msg in missing_msgs:
            st.markdown(f"**{msg}**")

        st.info(
            "💡 Completa tu perfil en 'Mi Perfil' o utiliza 'Mejorar CV con IA' para cargar tu currículum antes de adaptarlo."
            if lang == "es" else "💡 Complete your profile in 'My Profile' or use 'CV Improver (AI)' to load your resume first."
        )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("👤 Ir a Mi Perfil" if lang == "es" else "👤 Go to My Profile", use_container_width=True):
                st.session_state["main_nav_radio"] = "profile"
                st.rerun()
        with col_b2:
            if st.button("✨ Ir a Mejorar CV con IA" if lang == "es" else "✨ Go to CV Improver", use_container_width=True):
                st.session_state["main_nav_radio"] = "cv_improver"
                st.rerun()

        st.divider()
        # Mostramos de todos modos las versiones ya guardadas previamente si existen
        _render_saved_versions_section(lang)
        return

    # Si está listo, mostrar pill informativo del CV detectado
    origen_cv = "Borrador activo en CV Improver" if "cv_improver_active_schema" in st.session_state else "Perfil maestro en My Profile"
    st.success(
        f"✅ **CV Base cargado:** {base_cv.contact.name or 'Candidato'} ({len(base_cv.experience)} experiencias, {sum(len(e.bullets) for e in base_cv.experience)} viñetas) — *Fuente: {origen_cv}*"
    )

    # --------------------------------------------------------------------------
    # 2. DEFINIR LA VACANTE CON TRES PESTAÑAS (URL, POSTULACIÓN O TEXTO)
    # --------------------------------------------------------------------------
    st.markdown("### 📋 1. Información de la Vacante Objetivo")

    # Si venimos con una postulación preseleccionada desde "Ver y Gestionar Aplicaciones"
    prefill_id = st.session_state.pop("tailor_prefill_app_id", None)
    if prefill_id:
        app_data = get_application_by_id(prefill_id)
        if app_data:
            st.session_state["tailor_company"] = app_data.get("company", "")
            st.session_state["tailor_position"] = app_data.get("position", "")
            st.session_state["tailor_input_url"] = app_data.get("job_url", "")
            st.session_state["tailor_job_text"] = app_data.get("notes", "") or ""
            st.session_state["tailor_selected_app_id"] = app_data.get("id")

    tab_url, tab_app, tab_text = st.tabs([
        "🔗 Pegar URL" if lang == "es" else "🔗 Paste URL",
        "📂 Postulación guardada" if lang == "es" else "📂 Saved Application",
        "✍️ Pegar texto" if lang == "es" else "✍️ Paste Text"
    ])

    with tab_url:
        st.caption("Ingresa la URL pública de la oferta de empleo para extraer su descripción:")
        col_u1, col_u2 = st.columns([3.5, 1.2])
        with col_u1:
            url_input = st.text_input(
                "URL de la vacante:",
                value=st.session_state.get("tailor_input_url", ""),
                key="input_tailor_url",
                placeholder="https://www.linkedin.com/jobs/view/... o portal de empleo"
            )
        with col_u2:
            st.write("")
            st.write("")
            if st.button("📥 Extraer texto", key="btn_scrape_job_url", use_container_width=True):
                if not url_input.strip():
                    st.warning("Ingresa una URL válida primero.")
                else:
                    with st.spinner("Descargando y analizando texto de la oferta..."):
                        ok, res_text = extract_job_text_from_url(url_input.strip())
                        if ok:
                            st.session_state["tailor_job_text"] = res_text
                            st.session_state["tailor_input_url"] = url_input.strip()
                            st.success(f"✅ Oferta extraída exitosamente ({len(res_text):,} caracteres).")
                        else:
                            st.warning(
                                f"⚠️ No se pudo extraer automáticamente el contenido: {res_text}"
                            )
                            st.info(
                                "💡 Puedes copiar el texto manualmente y pegarlo en la pestaña '✍️ Pegar texto' sin perder ningún dato."
                            )

        if st.session_state.get("tailor_job_text") and st.session_state.get("tailor_input_url"):
            st.caption(f"📄 Contenido de la oferta cargado ({len(st.session_state['tailor_job_text']):,} caracteres). Listo para adaptar.")

    with tab_app:
        st.caption("Selecciona una postulación que ya tengas registrada en tu seguimiento:")
        user_apps = get_all_applications()
        if not user_apps:
            st.info("No tienes postulaciones guardadas aún.")
        else:
            app_options = {
                a["id"]: f"#{a['id']} - {a.get('company', '')} ({a.get('position', '')})"
                for a in user_apps
            }
            default_idx = 0
            curr_sel = st.session_state.get("tailor_selected_app_id")
            if curr_sel in app_options:
                default_idx = list(app_options.keys()).index(curr_sel)

            selected_id = st.selectbox(
                "Seleccionar postulación:",
                options=list(app_options.keys()),
                format_func=lambda x: app_options[x],
                index=default_idx,
                key="select_tailor_app"
            )
            if selected_id:
                app_obj = next((a for a in user_apps if a["id"] == selected_id), None)
                if app_obj:
                    st.session_state["tailor_selected_app_id"] = selected_id
                    st.session_state["tailor_company"] = app_obj.get("company", "")
                    st.session_state["tailor_position"] = app_obj.get("position", "")
                    if app_obj.get("notes"):
                        st.session_state["tailor_job_text"] = app_obj.get("notes", "")
                    if app_obj.get("job_url"):
                        st.session_state["tailor_input_url"] = app_obj.get("job_url", "")
                    st.info(f"📍 **Empresa:** {app_obj.get('company')} | **Puesto:** {app_obj.get('position')}")

    with tab_text:
        st.caption("Pega directamente los requisitos, responsabilidades y descripción de la oferta laboral:")
        pasted_text = st.text_area(
            "Descripción completa de la vacante:",
            value=st.session_state.get("tailor_job_text", ""),
            height=200,
            key="area_tailor_job_desc",
            placeholder="Pega aquí el texto copiado de LinkedIn, Indeed, el sitio de carreras de la empresa, etc."
        )
        st.session_state["tailor_job_text"] = pasted_text

    company_val = st.session_state.get("tailor_company", "")
    position_val = st.session_state.get("tailor_position", "")

    # Validación de longitud (Tope estricto de 15.000 caracteres)
    job_text_current = st.session_state.get("tailor_job_text", "").strip()
    char_count = len(job_text_current)
    if char_count > 15000:
        st.warning(
            "⚠️ El texto supera el tope de 15.000 caracteres. Se recortará automáticamente a los primeros 15.000 caracteres."
        )
        job_text_current = job_text_current[:15000]

    # --------------------------------------------------------------------------
    # 3. LLAMADA A IA (CLIC EXPLÍCITO Y BANDERAS DE ESTADO)
    # --------------------------------------------------------------------------
    st.divider()
    st.markdown("### 🧠 2. Generar Adaptación con IA")
    st.caption(
        "La IA ejecutará **una sola llamada en lote** para adaptar el resumen y todas las viñetas, sin inventar jamás información inexistente."
    )

    # Control de tiempo de espera (cooldown de 5 segundos)
    last_call = st.session_state.get("tailor_last_ai_time", 0.0)
    time_diff = time.time() - last_call
    is_cooling_down = time_diff < 5.0
    cd_remaining = int(5.0 - time_diff) + 1 if is_cooling_down else 0

    btn_lbl = (
        f"⏳ Espera {cd_remaining}s..." if is_cooling_down
        else ("🚀 Adaptar mi CV a esta vacante con IA" if lang == "es" else "🚀 Tailor my CV to this job with AI")
    )

    can_trigger = bool(job_text_current) and not is_cooling_down

    if st.button(
        btn_lbl,
        key="btn_run_adaptation_ai",
        type="primary",
        disabled=not can_trigger,
        use_container_width=True
    ):
        st.session_state["tailor_adaptation_attempted"] = True
        st.session_state["tailor_last_ai_time"] = time.time()
        st.session_state["tailor_error"] = None

        with st.spinner("Analizando requerimientos de la oferta y adaptando currículum con Gemini..."):
            try:
                adapted_result = adapt_resume_to_job(
                    resume_data=base_cv,
                    job_text=job_text_current,
                    target_company=company_val,
                    target_position=position_val,
                    user_id=None,
                    language=lang
                )
                st.session_state["tailor_result"] = adapted_result
                st.session_state["tailor_accepted_summary"] = False
                st.session_state["tailor_accepted_bullets"] = {}
                st.rerun()
            except Exception as e:
                st.session_state["tailor_error"] = str(e)

    if st.session_state.get("tailor_error"):
        st.error(f"❌ Error al adaptar el CV: {st.session_state['tailor_error']}")

    # --------------------------------------------------------------------------
    # 4. COMPARADOR ANTES / DESPUÉS CON ACEPTACIÓN EXPLÍCITA
    # --------------------------------------------------------------------------
    tailor_result = st.session_state.get("tailor_result")
    if tailor_result:
        st.divider()
        st.markdown("### ⚖️ 3. Comparador Antes / Después")
        st.caption(
            "🛡️ **Regla de integridad:** Nada entra a tu versión adaptada sin que lo aceptes explícitamente. Revisa cada propuesta y marca las que deseas incorporar."
        )

        # Resumen Profesional
        st.markdown("#### 📝 Resumen Profesional")
        col_s_orig, col_s_adap = st.columns(2)
        with col_s_orig:
            st.info(f"**Original:**\n\n{base_cv.summary or 'Sin resumen registrado.'}")
        with col_s_adap:
            if tailor_result.get("summary_suspicious"):
                st.error(
                    f"⚠️ **Atención:** Se detectaron adiciones de cifras o herramientas ausentes en el original: "
                    f"{', '.join(tailor_result.get('summary_suspicious_reasons', []))}"
                )
            st.success(f"**Propuesta Adaptada:**\n\n{tailor_result.get('summary_adapted', '')}")

        acc_summary = st.checkbox(
            "✅ Aceptar este resumen adaptado para mi postulación",
            value=st.session_state.get("tailor_accepted_summary", False),
            key="chk_accept_summary"
        )
        st.session_state["tailor_accepted_summary"] = acc_summary

        # Habilidades destacadas por la IA
        if tailor_result.get("skills_highlighted"):
            st.markdown("#### 💡 Competencias Clave Resaltadas")
            skills_pills = " • ".join(f"`{s}`" for s in tailor_result.get("skills_highlighted", []))
            st.markdown(skills_pills)

        # Viñetas de Experiencias Laborales
        st.markdown("#### 💼 Experiencias y Logros")
        accepted_bullets_state = st.session_state.get("tailor_accepted_bullets", {})

        for exp_idx, exp_data in enumerate(tailor_result.get("experiences", [])):
            exp_company = exp_data.get("company") or f"Empresa #{exp_idx + 1}"
            exp_position = exp_data.get("position") or "Puesto"

            with st.expander(f"🏢 {exp_position} en {exp_company} ({len(exp_data.get('bullets', []))} viñetas)", expanded=True):
                for b_idx, bullet in enumerate(exp_data.get("bullets", [])):
                    orig_b = bullet.get("original", "")
                    adap_b = bullet.get("adapted", "")
                    expl_b = bullet.get("explanation", "")
                    is_susp = bullet.get("suspicious", False)
                    reasons = bullet.get("suspicious_reasons", [])

                    col_b_orig, col_b_adap = st.columns(2)
                    with col_b_orig:
                        st.markdown(f"**Original:**\n\n{orig_b}")
                    with col_b_adap:
                        if is_susp:
                            st.warning(
                                f"🚨 **Línea sospechosa:** {', '.join(reasons)}"
                            )
                        st.markdown(f"**Adaptada:**\n\n{adap_b}")
                        if expl_b:
                            st.caption(f"💡 *Motivo:* {expl_b}")

                    b_key = f"exp_{exp_idx}_b_{b_idx}"
                    curr_val = accepted_bullets_state.get(b_key, False)
                    chk_val = st.checkbox(
                        f"Aceptar cambio en viñeta #{b_idx + 1}",
                        value=curr_val,
                        key=f"chk_bullet_{exp_idx}_{b_idx}"
                    )
                    accepted_bullets_state[b_key] = chk_val

        st.session_state["tailor_accepted_bullets"] = accepted_bullets_state

        # ----------------------------------------------------------------------
        # 5. GUARDAR VERSIÓN ADAPTADA COMO COPIA INDEPENDIENTE
        # ----------------------------------------------------------------------
        st.divider()
        st.markdown("### 💾 4. Guardar como Versión de CV Independiente")
        st.caption(
            "Se guardará como una copia dedicada a esta vacante sin sobreescribir tu perfil maestro ni el borrador de CV Improver."
        )

        col_sv1, col_sv2 = st.columns(2)
        with col_sv1:
            save_company = st.text_input("Empresa (opcional):", value=company_val, key="input_save_company")
        with col_sv2:
            save_position = st.text_input("Puesto / Cargo (opcional):", value=position_val, key="input_save_position")

        default_name = f"CV para {save_company or 'Vacante'} - {save_position or 'Candidatura'}"
        version_name_input = st.text_input(
            "Nombre para identificar esta versión:",
            value=default_name,
            key="input_version_name"
        )

        # Construir el CV adaptado final con solo lo aceptado
        final_adapted_cv = build_adapted_resume_from_choices(
            base_resume=base_cv,
            adaptation_data=tailor_result,
            accepted_summary=st.session_state["tailor_accepted_summary"],
            accepted_bullets=st.session_state["tailor_accepted_bullets"]
        )

        num_accepted = sum(1 for v in accepted_bullets_state.values() if v)
        if st.session_state["tailor_accepted_summary"]:
            num_accepted += 1
        st.info(f"📊 Cambios aceptados a incorporar: **{num_accepted}** elementos.")

        if st.button("💾 Guardar versión adaptada", key="btn_save_tailored_version", type="primary", use_container_width=True):
            if not version_name_input.strip():
                st.warning("Por favor asigna un nombre a la versión.")
            else:
                try:
                    payload_cv = final_adapted_cv.model_dump() if hasattr(final_adapted_cv, "model_dump") else final_adapted_cv.dict()
                    save_tailored_cv_version(
                        version_name=version_name_input.strip(),
                        tailored_cv=payload_cv,
                        application_id=st.session_state.get("tailor_selected_app_id"),
                        target_company=save_company.strip() if save_company else None,
                        target_position=save_position.strip() if save_position else None,
                        job_url=st.session_state.get("tailor_input_url"),
                        job_description=job_text_current
                    )
                    st.success(f"🎉 ¡Versión '{version_name_input}' guardada exitosamente como copia independiente!")
                    # Limpiamos estado para evitar duplicados accidentales
                    st.session_state.pop("tailor_result", None)
                    st.session_state.pop("tailor_accepted_bullets", None)
                    st.rerun()
                except Exception as ex_save:
                    st.error(f"Error al guardar la versión: {ex_save}")

    # --------------------------------------------------------------------------
    # 6. HISTORIAL Y GESTOR DE VERSIONES GUARDADAS (VER, DESCARGAR, BORRAR)
    # --------------------------------------------------------------------------
    st.divider()
    _render_saved_versions_section(lang)


def _render_saved_versions_section(lang: str):
    """Renderiza el listado de versiones adaptadas guardadas con opciones de descarga y borrado."""
    st.markdown("### 📂 Versiones de CV Adaptadas Guardadas")
    st.caption("Consulta, descarga en PDF/Word o elimina las copias que has preparado para cada oferta laboral:")

    try:
        saved_versions = get_tailored_cv_versions()
    except Exception as ex:
        st.error(f"No se pudieron cargar las versiones guardadas: {ex}")
        return

    if not saved_versions:
        st.info("Aún no tienes versiones adaptadas guardadas.")
        return

    for ver in saved_versions:
        v_id = ver["id"]
        v_name = ver.get("version_name") or f"Versión #{v_id}"
        v_company = ver.get("target_company") or "Empresa no especificada"
        v_position = ver.get("target_position") or "Puesto no especificado"
        v_created = str(ver.get("created_at", ""))[:16].replace("T", " ")

        with st.expander(f"📄 {v_name} — {v_company} ({v_position}) [{v_created}]"):
            col_info, col_actions = st.columns([2.5, 1.5])
            with col_info:
                st.markdown(f"**Empresa:** {v_company}")
                st.markdown(f"**Puesto:** {v_position}")
                if ver.get("job_url"):
                    st.markdown(f"**Enlace a la oferta:** [{ver.get('job_url')}]({ver.get('job_url')})")
                if ver.get("job_description"):
                    with st.expander("Ver descripción de la oferta guardada"):
                        st.text(ver.get("job_description"))

            with col_actions:
                st.markdown("##### 📥 Opciones de Exportación")
                plantilla_sel = st.selectbox(
                    "Plantilla visual:",
                    options=["moderna", "clasica", "minimalista", "vanguardia", "zafiro"],
                    key=f"sel_tpl_{v_id}"
                )

                try:
                    cv_dict = ver.get("tailored_cv") or {}
                    resume_to_render = ResumeSchema(**cv_dict)

                    # Descarga PDF
                    pdf_bytes, pages, engine = render_cv_to_pdf(resume_to_render, template_name=plantilla_sel)
                    st.download_button(
                        label=f"📕 Descargar PDF ({pages} pág)",
                        data=pdf_bytes,
                        file_name=f"{v_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_{v_id}",
                        use_container_width=True
                    )

                    # Descarga DOCX
                    docx_bytes = render_cv_to_docx(resume_to_render)
                    st.download_button(
                        label="📘 Descargar Word (.docx)",
                        data=docx_bytes,
                        file_name=f"{v_name.replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_docx_{v_id}",
                        use_container_width=True
                    )
                except Exception as ex_rend:
                    st.error(f"Error al preparar archivos para descarga: {ex_rend}")

                st.write("")
                # Borrado seguro
                with st.popover(f"🗑️ Eliminar versión"):
                    st.warning("¿Estás seguro de que deseas eliminar esta versión de CV adaptada?")
                    if st.button("Sí, eliminar definitivamente", key=f"btn_confirm_del_{v_id}", type="primary"):
                        try:
                            delete_tailored_cv_version(v_id)
                            st.success("Versión eliminada.")
                            st.rerun()
                        except Exception as ex_del:
                            st.error(f"Error al eliminar: {ex_del}")
