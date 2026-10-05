# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 3: Application Tracker con Streamlit (app.py)
# ==============================================================================

import os
import re
from datetime import datetime, date
import streamlit as st
import streamlit.components.v1 as components
import urllib.parse as urlparse
import pandas as pd
from supabase import create_client, Client

# Importamos las funciones de la base de datos de la Fase 2, 4, 5.1 y 7
from database import (
    create_tables,
    insert_application,
    get_all_applications,
    get_application_by_id,
    update_application,
    delete_application,
    get_dashboard_counts,
    get_status_breakdown,
    get_work_mode_breakdown,
    get_salary_statistics,
    get_monthly_applications,
    get_monthly_interviews,
    # Fase 5.1: My Profile & Skills
    SKILL_CATEGORIES,
    get_all_distinct_categories,
    PROFICIENCY_LEVELS,
    save_user_profile,
    get_user_profile,
    add_user_skill,
    add_user_skills_bulk,
    get_all_user_skills,
    update_user_skill_proficiency,
    update_user_skill_category,
    delete_user_skill,
    # Fase 5.3: Skills vinculadas a cada postulación
    insert_application_skills,
    get_skills_by_application,
    # Fase 6.1: i18n Language persistence & Currency options
    # Fase 6.1: i18n Language persistence & Currency options
    get_user_preferred_language,
    set_user_preferred_language,
    CURRENCY_OPTIONS,
    # Fase 5.6a & 5.7: CV Builder, Experiencia, Bullets y Educación
    get_all_experiences,
    add_experience_entry,
    update_experience_entry,
    delete_experience_entry,
    get_all_resume_bullets,
    get_bullets_by_experience,
    add_resume_bullet,
    update_resume_bullet,
    delete_resume_bullet,
    seed_default_resume_bullets,
    get_all_education,
    add_education_entry,
    update_education_entry,
    delete_education_entry,
    save_parsed_resume_data
)

# Fase 6.1 & 6.2: Sistema centralizado de traducción
from translations import t, t_status, t_work_mode, get_current_language

# Módulos de extracción de CV, Web Scraping e Inteligencia Artificial
from resume_parser import extract_resume_text
from job_scraper import extract_job_text_from_url
from ai_service import (
    extract_skills_and_profile_from_resume,
    analyze_job_description,
    generate_skill_gaps_study,
    generate_interview_questions,
    evaluate_interview_answer,
    get_api_key,
    generar_sugerencia_curso,
    rewrite_resume_bullet
)

# Fase 5.6c: Generador de PDF ATS-Friendly
from pdf_generator import generate_resume_pdf

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Job Application Tracker",
    page_icon="💼",
    layout="wide"  # 'wide' aprovecha mejor el ancho de la pantalla para tablas y formularios
)

# Inicialización de tablas de SQLite (incluyendo migración i18n si aplica)
create_tables()

# ------------------------------------------------------------------------------
# FASE 6.1: INTERNACIONALIZACIÓN (i18n) - RESOLUCIÓN DE IDIOMA
# ------------------------------------------------------------------------------
def resolve_initial_language() -> str:
    """
    Fase 6.1: Resuelve el idioma inicial según la prioridad requerida:
    1. Si user_profile.preferred_language tiene un valor guardado (no NULL), usar ese.
    2. Si es NULL, leer st.context.locale (si empieza con 'en' -> 'en', si empieza con 'es' -> 'es').
    3. Si no hay match o st.context.locale no está disponible, usar 'es' por defecto.
    """
    # 1. Preferencia explícita persistida en SQLite
    try:
        saved_lang = get_user_preferred_language()
        if saved_lang in ("es", "en"):
            return saved_lang
    except Exception:
        pass

    # 2. Detección automática en el navegador mediante st.context.locale
    try:
        browser_locale = getattr(st.context, "locale", None)
        if browser_locale and isinstance(browser_locale, str):
            loc = browser_locale.lower().strip()
            if loc.startswith("en"):
                return "en"
            elif loc.startswith("es"):
                return "es"
    except Exception:
        pass

    # 3. Fallback por defecto en caso de no coincidencia o falta de contexto
    return "es"

saved_pref = get_user_preferred_language()
if saved_pref in ("es", "en"):
    st.session_state["lang"] = saved_pref
    expected_radio_val = "🇪🇸 Español (ES)" if saved_pref == "es" else "🇺🇸 English (EN)"
    if "sidebar_lang_selector" in st.session_state and st.session_state["sidebar_lang_selector"] != expected_radio_val:
        st.session_state["sidebar_lang_selector"] = expected_radio_val
elif "lang" not in st.session_state:
    st.session_state["lang"] = resolve_initial_language()

# ------------------------------------------------------------------------------
# SUPABASE AUTHENTICATION & ACCESS CONTROL (Gated Content)
# ------------------------------------------------------------------------------
# 1. Conectar a Supabase usando los secretos guardados en .streamlit/secrets.toml
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Inyectar el token de autenticación del usuario en el cliente PostgREST
# para que todas las operaciones de base de datos viajen como usuario autenticado (RLS auth.uid())
if "access_token" in st.session_state and st.session_state.access_token:
    supabase.postgrest.auth(st.session_state.access_token)

# 2. Inicializar el usuario en el estado de la sesión
if 'user' not in st.session_state:
    st.session_state.user = None

# 3. Crear la pantalla de Login y Registro
def login_screen():
    st.title("💼 AI Job Application Tracker")
    st.subheader("Acceso a la plataforma")

    tab1, tab2, tab3 = st.tabs(["Iniciar Sesión", "Crear Cuenta", "🔑 Recuperar Contraseña"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Correo electrónico")
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Entrar", use_container_width=True)

            if submit:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    if res.session:
                        st.session_state.access_token = res.session.access_token
                        st.session_state.refresh_token = res.session.refresh_token
                        supabase.postgrest.auth(res.session.access_token)
                    st.rerun()  # Refresca la pantalla para acceder a la aplicación
                except Exception as e:
                    st.error(f"Credenciales incorrectas: {e}")

        # Opción rápida de recuperación dentro de la pestaña de Iniciar Sesión
        with st.expander("¿Olvidaste tu contraseña?"):
            st.caption("Ingresa tu correo para recibir un enlace oficial de recuperación:")
            email_rec = st.text_input("Correo registrado", key="login_rec_email")
            if st.button("Enviar enlace de restablecimiento", key="btn_login_rec", use_container_width=True):
                if not email_rec.strip():
                    st.warning("Por favor ingresa tu correo electrónico.")
                else:
                    try:
                        supabase.auth.reset_password_for_email(
                            email_rec.strip(),
                            options={"redirect_to": "http://localhost:8501"}
                        )
                        st.success(f"📧 Se ha enviado un correo a **{email_rec.strip()}** con instrucciones para restablecer tu contraseña.")
                    except Exception as err:
                        st.error(f"Error al enviar recuperación: {err}")

    with tab2:
        with st.form("signup_form"):
            new_email = st.text_input("Correo electrónico")
            new_password = st.text_input("Contraseña", type="password")
            signup_submit = st.form_submit_button("Registrarse", use_container_width=True)

            if signup_submit:
                try:
                    res = supabase.auth.sign_up({"email": new_email, "password": new_password})
                    st.success("¡Cuenta creada exitosamente! Ya puedes iniciar sesión en la pestaña 'Iniciar Sesión'.")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")

    with tab3:
        st.markdown("### 🔑 Recuperar Contraseña con Código de Seguridad")
        st.caption("Recupera el acceso a tu cuenta fácilmente mediante un código de 6 dígitos enviado a tu correo.")
        st.markdown("---")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("#### 1️⃣ Solicitar código de seguridad")
            st.caption("Ingresa tu correo registrado y te enviaremos un código de seguridad:")
            with st.form("tab_request_code_form"):
                req_email = st.text_input(
                    "Correo electrónico", 
                    value=st.session_state.get("recovery_email", ""), 
                    key="tab_req_email"
                )
                btn_send_code = st.form_submit_button("Enviar código al correo", use_container_width=True)

                if btn_send_code:
                    if not req_email.strip():
                        st.warning("Por favor ingresa tu correo electrónico.")
                    else:
                        try:
                            supabase.auth.reset_password_for_email(
                                req_email.strip(),
                                options={"redirect_to": "http://localhost:8501"}
                            )
                            st.session_state.recovery_email = req_email.strip()
                            st.success(
                                f"📧 ¡Código enviado a **{req_email.strip()}**! "
                                "Revisa tu correo e ingresa el código de 6 dígitos en el paso 2."
                            )
                        except Exception as e:
                            if "rate limit" in str(e).lower():
                                st.warning("⏳ Has solicitado varios correos recientemente. Por seguridad de Supabase, por favor espera unos minutos.")
                            else:
                                st.error(f"Error al enviar código: {e}")

        with col_t2:
            st.markdown("#### 2️⃣ Ingresar código y nueva contraseña")
            st.caption("Escribe el código recibido y define tu nueva contraseña:")
            with st.form("tab_verify_code_form"):
                verify_email = st.text_input(
                    "Confirmar correo", 
                    value=st.session_state.get("recovery_email", ""), 
                    key="tab_verify_email"
                )
                otp_code = st.text_input("Código de seguridad (6 dígitos)", placeholder="Ej: 123456", max_chars=10, key="tab_otp_code")
                new_pass = st.text_input("Nueva contraseña (mínimo 6 caracteres)", type="password", key="tab_new_pass")
                confirm_pass = st.text_input("Confirmar nueva contraseña", type="password", key="tab_confirm_pass")
                btn_reset_with_code = st.form_submit_button("Actualizar Contraseña", use_container_width=True)

                if btn_reset_with_code:
                    if not verify_email.strip() or not otp_code.strip():
                        st.warning("Por favor ingresa tu correo y el código recibido.")
                    elif len(new_pass) < 6:
                        st.error("La contraseña debe tener al menos 6 caracteres.")
                    elif new_pass != confirm_pass:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        try:
                            # 1. Verificar OTP
                            res_otp = supabase.auth.verify_otp({
                                "email": verify_email.strip(),
                                "token": otp_code.strip(),
                                "type": "recovery"
                            })
                            # 2. Actualizar contraseña del usuario autenticado
                            supabase.auth.update_user({"password": new_pass})
                            st.session_state.user = res_otp.user
                            if res_otp.session:
                                st.session_state.access_token = res_otp.session.access_token
                                st.session_state.refresh_token = res_otp.session.refresh_token
                                supabase.postgrest.auth(res_otp.session.access_token)
                            st.session_state.is_resetting_password = False
                            st.success("🎉 ¡Tu contraseña ha sido actualizada con éxito! Ingresando a la plataforma...")
                            st.rerun()
                        except Exception as err_otp:
                            st.error(f"Error al verificar código: {err_otp}")

        st.divider()
        with st.expander("🔗 ¿Prefieres validar pegando el enlace completo del correo?"):
            pasted_url = st.text_input("Pega la dirección URL recibida:", key="input_pasted_reset_link")
            if st.button("Validar enlace y abrir formulario", key="btn_verify_pasted_link", use_container_width=True):
                if pasted_url.strip():
                    try:
                        parsed = urlparse.urlparse(pasted_url.strip())
                        params = urlparse.parse_qs(parsed.fragment) or urlparse.parse_qs(parsed.query)
                        if "access_token" in params and "refresh_token" in params:
                            res_sess = supabase.auth.set_session(params["access_token"][0], params["refresh_token"][0])
                            st.session_state.user = res_sess.user
                            if res_sess.session:
                                st.session_state.access_token = res_sess.session.access_token
                                st.session_state.refresh_token = res_sess.session.refresh_token
                                supabase.postgrest.auth(res_sess.session.access_token)
                            st.session_state.is_resetting_password = True
                            st.rerun()
                        elif "code" in params:
                            res_c = supabase.auth.exchange_code_for_session({"auth_code": params["code"][0]})
                            st.session_state.user = res_c.user
                            if res_c.session:
                                st.session_state.access_token = res_c.session.access_token
                                st.session_state.refresh_token = res_c.session.refresh_token
                                supabase.postgrest.auth(res_c.session.access_token)
                            st.session_state.is_resetting_password = True
                            st.rerun()
                        else:
                            st.warning("No se detectó un token en el enlace. Asegúrate de copiarlo completo.")
                    except Exception as e_paste:
                        st.error(f"Error al procesar el enlace: {e_paste}")
                else:
                    st.warning("Por favor pega la dirección URL que llegó a tu correo.")

# Detección y conversión en el navegador:
# 1. Mediante st.html (ejecución directa en la ventana principal, sin restricciones de sandbox iframe)
st.html(
    """
    <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" style="display:none;" onerror="
        try {
            if (window.location.hash && (window.location.hash.includes('access_token=') || window.location.hash.includes('type=recovery'))) {
                var clean = window.location.hash.replace(/^#/, '');
                window.location.href = window.location.origin + window.location.pathname + '?' + clean;
            }
        } catch(e) {}
    " onload="
        try {
            if (window.location.hash && (window.location.hash.includes('access_token=') || window.location.hash.includes('type=recovery'))) {
                var clean = window.location.hash.replace(/^#/, '');
                window.location.href = window.location.origin + window.location.pathname + '?' + clean;
            }
        } catch(e) {}
    ">
    """
)

# 2. Respaldo mediante iframe components
components.html(
    """
    <script>
        try {
            var p = window.parent;
            if (p && p.location && p.location.hash) {
                var hash = p.location.hash;
                if (hash.includes('access_token=') || hash.includes('type=recovery') || hash.includes('error=')) {
                    var cleanHash = hash.replace(/^#/, '');
                    p.location.href = p.location.origin + p.location.pathname + '?' + cleanHash;
                }
            }
        } catch (e) {}
    </script>
    """,
    height=0,
    width=0
)

# Captura de token de recuperación desde la URL de retorno (Implicit Flow / hash redirigido)
if "access_token" in st.query_params:
    try:
        acc_token = st.query_params.get("access_token")
        ref_token = st.query_params.get("refresh_token", "")
        res_session = supabase.auth.set_session(acc_token, ref_token)
        st.session_state.user = res_session.user
        if res_session.session:
            st.session_state.access_token = res_session.session.access_token
            st.session_state.refresh_token = res_session.session.refresh_token
            supabase.postgrest.auth(res_session.session.access_token)
        st.session_state.is_resetting_password = True
        st.query_params.clear()
        st.rerun()
    except Exception as err_token:
        st.warning(f"Error al validar token de recuperación: {err_token}")

# Captura de código de recuperación desde la URL de retorno (PKCE / Supabase Auth flow)
elif "code" in st.query_params:
    try:
        res_code = supabase.auth.exchange_code_for_session({"auth_code": st.query_params["code"]})
        st.session_state.user = res_code.user
        if res_code.session:
            st.session_state.access_token = res_code.session.access_token
            st.session_state.refresh_token = res_code.session.refresh_token
            supabase.postgrest.auth(res_code.session.access_token)
        st.session_state.is_resetting_password = True
        st.query_params.clear()
        st.rerun()
    except Exception as err_code:
        st.warning(f"El enlace de recuperación ya fue utilizado o expiró: {err_code}")

# Captura de posibles errores reportados por Supabase en la URL
elif "error_description" in st.query_params or "error" in st.query_params:
    err_msg = st.query_params.get("error_description") or st.query_params.get("error")
    st.error(f"Error en enlace de autenticación: {err_msg}")
    st.query_params.clear()

# Pantalla de creación de nueva contraseña tras el enlace de recuperación
def set_new_password_screen():
    st.title("💼 AI Job Application Tracker")
    st.subheader("🔑 Establecer nueva contraseña")
    st.caption("Ingresa tu nueva contraseña para actualizar tu acceso en Supabase.")

    if st.session_state.user is None:
        st.info("ℹ️ Para guardar la nueva contraseña, necesitamos validar tu enlace de correo.")
        pasted_inside = st.text_input("Pega aquí la URL completa del correo recibido:", key="pasted_url_inside_form")
        if st.button("Validar enlace de correo", key="btn_val_inside", use_container_width=True):
            if pasted_inside.strip():
                try:
                    parsed_in = urlparse.urlparse(pasted_inside.strip())
                    p_in = urlparse.parse_qs(parsed_in.fragment) or urlparse.parse_qs(parsed_in.query)
                    if "access_token" in p_in and "refresh_token" in p_in:
                        res_in = supabase.auth.set_session(p_in["access_token"][0], p_in["refresh_token"][0])
                        st.session_state.user = res_in.user
                        st.success("✅ Enlace validado con éxito. Ya puedes ingresar tu nueva contraseña abajo.")
                        st.rerun()
                    elif "code" in p_in:
                        res_cin = supabase.auth.exchange_code_for_session({"auth_code": p_in["code"][0]})
                        st.session_state.user = res_cin.user
                        st.success("✅ Enlace validado con éxito. Ya puedes ingresar tu nueva contraseña abajo.")
                        st.rerun()
                    else:
                        st.warning("No se detectó un token en el enlace. Asegúrate de copiarlo completo.")
                except Exception as ex_in:
                    st.error(f"Error al validar el enlace: {ex_in}")
            else:
                st.warning("Por favor pega la URL que llegó a tu correo.")

    with st.form("form_set_new_password"):
        new_pass = st.text_input("Nueva contraseña", type="password")
        confirm_pass = st.text_input("Confirmar nueva contraseña", type="password")
        submit_btn = st.form_submit_button("Guardar nueva contraseña", use_container_width=True)

        if submit_btn:
            if len(new_pass) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            elif new_pass != confirm_pass:
                st.error("Las contraseñas no coinciden.")
            else:
                try:
                    supabase.auth.update_user({"password": new_pass})
                    st.success("🎉 ¡Tu contraseña ha sido actualizada con éxito! Ya puedes usar la plataforma.")
                    st.session_state.is_resetting_password = False
                    st.rerun()
                except Exception as err:
                    st.error(f"Error al actualizar la contraseña: {err}")

    if st.button("⬅️ Cancelar / Volver", key="btn_cancel_reset"):
        st.session_state.is_resetting_password = False
        st.rerun()

# Si el usuario viene del enlace de reseteo, mostramos el formulario de cambio de clave
if st.session_state.get("is_resetting_password"):
    set_new_password_screen()
    st.stop()

# 4. Lógica de control de acceso: si no hay usuario, mostrar SOLO la pantalla de login
if st.session_state.user is None:
    login_screen()
    st.stop()  # Detiene la renderización del resto de la app (sidebar, dashboard, formularios)

# 5. Barra superior con el usuario activo y botón de Cerrar Sesión
col_usr1, col_usr2, col_usr3 = st.columns([0.6, 0.2, 0.2])
with col_usr1:
    user_label = "Active User" if st.session_state.get("lang") == "en" else "Usuario activo"
    st.markdown(f"👤 **{user_label}:** `{st.session_state.user.email}`")
with col_usr2:
    change_pwd_label = "🔑 Change Password" if st.session_state.get("lang") == "en" else "🔑 Cambiar Contraseña"
    if st.button(change_pwd_label, use_container_width=True):
        st.session_state.is_resetting_password = True
        st.rerun()
with col_usr3:
    if st.button(t("logout_button"), use_container_width=True):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.session_state.user = None
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.is_resetting_password = False
        st.rerun()

st.divider()

# Aseguramos la existencia de las tablas locales
create_tables()

# Título y encabezado principal
st.title("💼 AI Job Application Tracker")
st.caption(t("app_caption"))

# Valores exactos de Status requeridos por el proyecto
STATUS_OPTIONS = [
    "Applied",
    "Recruiter Screen",
    "Technical Interview",
    "Final Interview",
    "Offer",
    "Rejected",
    "Ghosted"
]

# Opciones de modalidad de trabajo
WORK_MODE_OPTIONS = ["Remote", "Hybrid", "On-site", "TBD"]


# ------------------------------------------------------------------------------
# COMPONENTE REUTILIZABLE: INTERVIEW COACH (Fase 5.3 & 5.5)
# ------------------------------------------------------------------------------
def render_interview_coach(app_actual: dict, show_close_button: bool = True):
    """
    Renderiza el Interview Coach para una postulación específica.
    Reutilizado tanto desde 'Application Details' como desde la opción independiente
    'Prepare me for this job' en el menú lateral.
    """
    st.divider()
    coach_head_title = t("coach_header_prefix", position=app_actual['position'], company=app_actual['company'])
    if show_close_button:
        col_c_head, col_c_close = st.columns([5, 1])
        with col_c_head:
            st.subheader(coach_head_title)
            st.caption(t("coach_subcaption"))
        with col_c_close:
            st.write("")
            if st.button(t("coach_btn_close"), key=f"close_coach_{app_actual['id']}", use_container_width=True):
                st.session_state["show_interview_coach"] = False
                st.session_state.pop("coach_session", None)
                st.rerun()
    else:
        st.subheader(coach_head_title)
        st.caption(t("coach_subcaption"))

    curr_lang = st.session_state.get("lang", "es")

    # Inicialización de la sesión del coach si es una postulación distinta o si cambió el idioma
    if ("coach_session" not in st.session_state or 
        st.session_state["coach_session"].get("app_id") != app_actual["id"] or
        st.session_state["coach_session"].get("lang") != curr_lang):
        st.session_state["coach_session"] = {
            "app_id": app_actual["id"],
            "lang": curr_lang,
            "study_guide": None,
            "questions": [],
            "current_index": 0,
            "current_feedback": None,
            "history": []
        }

    c_session = st.session_state["coach_session"]

    # Generación inicial con IA si aún no existen en la sesión
    if not c_session.get("questions") or c_session.get("study_guide") is None:
        spinner_msg = "🧠 Generando plan de entrenamiento, análisis de brechas y preguntas de entrevista con Gemini..." if curr_lang == "es" else "🧠 Generating tailored interview questions, study guide and practice plan with Gemini..."
        with st.spinner(spinner_msg):
            app_skills = get_skills_by_application(app_actual["id"])
            user_skills = get_all_user_skills()
            missing_list = [s["skill"] for s in app_skills if s.get("match_status") == "missing"]

            try:
                guia_estudio = generate_skill_gaps_study(
                    missing_skills=missing_list,
                    position=app_actual["position"],
                    company=app_actual["company"],
                    language=curr_lang
                )
                preguntas_gen = generate_interview_questions(
                    position=app_actual["position"],
                    company=app_actual["company"],
                    app_skills=app_skills,
                    user_skills=user_skills,
                    notes=app_actual.get("notes"),
                    language=curr_lang
                )
                c_session["study_guide"] = guia_estudio
                c_session["questions"] = preguntas_gen
                c_session["current_index"] = 0
                st.rerun()
            except Exception as e:
                st.error(t("coach_init_error", error=e))

    # Renderizado de las 3 secciones del Coach
    if c_session.get("questions") and (c_session.get("study_guide") is not None):
        tab_gaps, tab_bank, tab_sim = st.tabs([
            t("coach_tab_study"),
            f"{t('coach_tab_questions')} ({len(c_session['questions'])})",
            t("coach_tab_simulator")
        ])

        # PESTAÑA 1: GUÍA DE ESTUDIO DE BRECHAS
        with tab_gaps:
            st.markdown(f"### {t('coach_gaps_header')}")
            st.caption(t("coach_gaps_caption"))

            gaps_list = c_session.get("study_guide", [])
            if isinstance(gaps_list, list) and gaps_list:
                for g in gaps_list:
                    s_name = g.get("skill", "")
                    s_imp = g.get("importance", "Required").strip("[]")
                    s_ctx = g.get("context", "")
                    s_cat = g.get("category", "")
                    s_tips = g.get("key_concepts", "")
                    res = g.get("resource") or {}

                    with st.container(border=True):
                        col_g1, col_g2 = st.columns([3, 1])
                        with col_g1:
                            st.markdown(f"#### ❌ **{s_name}** `[{s_imp}]`")
                            cat_label = "Categoría" if st.session_state.get("lang") == "es" else "Category"
                            st.caption(f"{cat_label}: `{s_cat}`")
                        with col_g2:
                            if res.get("source") == "ms_learn_catalog_api":
                                st.caption("☁️ `MS Learn Oficial`")
                            elif res.get("source") == "curated_category" or res.get("source") == "skill_override":
                                st.caption("🛡️ `Plataforma Curada`")
                            else:
                                st.caption("🔍 `Búsqueda Externa`")

                        if s_ctx:
                            rel_label = "📌 Relevancia en el puesto" if st.session_state.get("lang") == "es" else "📌 Role relevance"
                            st.markdown(f"**{rel_label}:** {s_ctx}")
                        if s_tips:
                            tips_label = "🎯 Conceptos clave para la entrevista" if st.session_state.get("lang") == "es" else "🎯 Key interview concepts"
                            st.markdown(f"**{tips_label}:** {s_tips}")

                        if res and res.get("url"):
                            p_label = res.get("title") or res.get("platform", "Plataforma de estudio")
                            sug_label = "💡 Sugerencia de estudio" if st.session_state.get("lang") == "es" else "💡 Recommended resource"
                            st.markdown(f"**{sug_label}:** [{p_label}]({res['url']})")
            elif isinstance(gaps_list, str) and gaps_list.strip():
                st.markdown(gaps_list)
            else:
                msg_no_gaps = "🎉 ¡Excelente! No se detectaron brechas técnicas para esta postulación." if st.session_state.get("lang") == "es" else "🎉 Excellent! No technical skill gaps detected for this role."
                st.success(msg_no_gaps)

        # PESTAÑA 2: BANCO DE PREGUNTAS
        with tab_bank:
            st.markdown(f"### {t('coach_questions_header')}")
            st.caption(t("coach_questions_caption"))
            for q in c_session["questions"]:
                cat_display = q.get('category', 'Técnica')
                with st.expander(f"Q#{q.get('id', '')} - [{cat_display}] {q.get('focus_skill', '')}"):
                    q_lbl = "Pregunta" if st.session_state.get("lang") == "es" else "Question"
                    st.markdown(f"**{q_lbl}:**\n\n### {q.get('question')}")
                    st.info(f"{t('coach_tip_label')} {q.get('tip')}")

        # PESTAÑA 3: SIMULADOR DE PRÁCTICA
        with tab_sim:
            st.markdown(f"### {t('coach_simulator_header')}")
            st.caption(t("coach_simulator_caption"))

            cur_idx = c_session["current_index"]
            total_q = len(c_session["questions"])

            if cur_idx < total_q:
                q_actual = c_session["questions"][cur_idx]
                st.progress((cur_idx) / total_q)
                step_lbl = f"Pregunta {cur_idx + 1} de {total_q}" if st.session_state.get("lang") == "es" else f"Question {cur_idx + 1} of {total_q}"
                cat_lbl = "Categoría" if st.session_state.get("lang") == "es" else "Category"
                focus_lbl = "Enfoque" if st.session_state.get("lang") == "es" else "Focus"
                st.markdown(f"**{step_lbl}** | {cat_lbl}: `{q_actual.get('category')}`")
                st.info(f"**{focus_lbl}:** `{q_actual.get('focus_skill')}`\n\n#### {q_actual.get('question')}")

                with st.expander(t("coach_tip_eval")):
                    st.caption(q_actual.get("tip"))

                with st.form(key=f"form_practice_{app_actual['id']}_{cur_idx}"):
                    resp_usuario = st.text_area(
                        t("coach_your_answer_label"),
                        placeholder=t("coach_your_answer_placeholder"),
                        height=160,
                        key=f"txt_resp_{app_actual['id']}_{cur_idx}"
                    )
                    btn_enviar_resp = st.form_submit_button(t("coach_send_answer_btn"), use_container_width=True)

                if btn_enviar_resp:
                    if not resp_usuario.strip():
                        warn_empty = "⚠️ Por favor escribe tu respuesta antes de enviarla." if st.session_state.get("lang") == "es" else "⚠️ Please write your answer before submitting."
                        st.warning(warn_empty)
                    else:
                        eval_spinner_txt = "🧠 Evaluando tu respuesta con Gemini..." if st.session_state.get("lang") == "es" else "🧠 Evaluating your answer with Gemini..."
                        with st.spinner(eval_spinner_txt):
                            try:
                                evaluacion = evaluate_interview_answer(
                                    question=q_actual.get("question"),
                                    category=q_actual.get("category", ""),
                                    focus_skill=q_actual.get("focus_skill", ""),
                                    user_answer=resp_usuario.strip(),
                                    language=curr_lang
                                )
                                c_session["current_feedback"] = evaluacion
                                c_session["history"].append({
                                    "q_num": cur_idx + 1,
                                    "question": q_actual.get("question"),
                                    "answer": resp_usuario.strip(),
                                    "feedback": evaluacion
                                })
                                st.rerun()
                            except Exception as err:
                                st.error(f"Error: {err}")

                # Mostrar feedback si existe para la pregunta actual
                if c_session.get("current_feedback"):
                    fb = c_session["current_feedback"]
                    st.markdown("---")
                    st.markdown(f"#### {t('coach_ai_feedback_header')}")
                    st.metric(t("coach_rating_label"), fb.get("rating", "Evaluada"))

                    col_fb1, col_fb2 = st.columns(2)
                    with col_fb1:
                        st.markdown(f"**{t('coach_strengths_label')}**")
                        for st_item in fb.get("strengths", []):
                            st.markdown(f"✅ {st_item}")
                    with col_fb2:
                        st.markdown(f"**{t('coach_improvements_label')}**")
                        for imp_item in fb.get("areas_to_improve", []):
                            st.markdown(f"⚠️ {imp_item}")

                    if fb.get("suggested_framework"):
                        struct_lbl = "📐 Estructura recomendada" if st.session_state.get("lang") == "es" else "📐 Recommended Framework"
                        st.info(f"**{struct_lbl}:** {fb.get('suggested_framework')}")

                    if fb.get("model_answer"):
                        model_exp_lbl = "🌟 Ver respuesta modelo senior" if st.session_state.get("lang") == "es" else "🌟 View Model Senior Answer"
                        with st.expander(model_exp_lbl):
                            st.write(fb.get("model_answer"))

                    col_next1, col_next2 = st.columns([2, 1])
                    with col_next1:
                        if st.button(t("coach_sim_next_btn"), type="primary", use_container_width=True, key=f"btn_next_{app_actual['id']}_{cur_idx}"):
                            c_session["current_index"] += 1
                            c_session["current_feedback"] = None
                            st.rerun()
            else:
                # Todas las preguntas han sido completadas
                st.balloons()
                st.success(t("coach_sim_completed"))
                summary_lbl = "### 📜 Resumen de tu Sesión de Práctica:" if st.session_state.get("lang") == "es" else "### 📜 Practice Session Summary:"
                st.markdown(summary_lbl)

                for h in c_session.get("history", []):
                    q_header = f"Pregunta {h['q_num']}" if st.session_state.get("lang") == "es" else f"Question {h['q_num']}"
                    with st.expander(f"{q_header}: {h['question'][:70]}... — {h['feedback'].get('rating', '')}"):
                        ans_lbl = "Tu respuesta" if st.session_state.get("lang") == "es" else "Your answer"
                        struct_lbl = "Estructura sugerida" if st.session_state.get("lang") == "es" else "Suggested framework"
                        model_lbl = "Respuesta modelo" if st.session_state.get("lang") == "es" else "Model answer"
                        st.markdown(f"**{ans_lbl}:**\n\n_{h['answer']}_\n")
                        st.markdown(f"**{struct_lbl}:** {h['feedback'].get('suggested_framework', 'N/A')}")
                        st.markdown(f"**{model_lbl}:**\n\n{h['feedback'].get('model_answer', 'N/A')}")

                if st.button(t("coach_btn_reset"), key=f"btn_reset_coach_{app_actual['id']}", use_container_width=True):
                    c_session["current_index"] = 0
                    c_session["current_feedback"] = None
                    c_session["history"] = []
                    st.rerun()


# ------------------------------------------------------------------------------
# MENÚ DE NAVEGACIÓN LATERAL (Sidebar) CON INTERNACIONALIZACIÓN (Fase 6.1)
# ------------------------------------------------------------------------------
# 1. Selector manual de idioma persistente (visible en todas las pantallas)
st.sidebar.markdown(f"#### {t('lang_selector_label')}")
current_lang = st.session_state.get("lang", "es")
lang_index = 0 if current_lang == "es" else 1

def handle_language_change():
    selected_option = st.session_state.get("sidebar_lang_selector", "")
    if not selected_option:
        return
    new_lang = "en" if "EN" in selected_option else "es"
    if new_lang != st.session_state.get("lang"):
        st.session_state["lang"] = new_lang
        try:
            set_user_preferred_language(new_lang)
        except Exception:
            pass
        st.rerun()

st.sidebar.radio(
    t("lang_selector_label"),
    options=["🇪🇸 Español (ES)", "🇺🇸 English (EN)"],
    index=lang_index,
    key="sidebar_lang_selector",
    on_change=handle_language_change,
    horizontal=True,
    label_visibility="collapsed"
)
st.sidebar.divider()

# 2. Menú de navegación
st.sidebar.title(t("nav_title"))
st.sidebar.caption(t("nav_caption"))

MENU_KEYS = [
    "dashboard",
    "add_app",
    "view_apps",
    "analyzer",
    "coach",
    "cv_builder",
    "stats",
    "profile"
]

menu_label_map = {
    "dashboard": t("nav_dashboard"),
    "add_app": t("nav_add_app"),
    "view_apps": t("nav_view_apps"),
    "analyzer": t("nav_analyzer"),
    "coach": t("nav_coach"),
    "cv_builder": t("nav_cv_builder"),
    "stats": t("nav_stats"),
    "profile": t("nav_profile")
}

menu_opcion = st.sidebar.radio(
    t("nav_select_section"),
    MENU_KEYS,
    format_func=lambda k: menu_label_map[k],
    index=0
)


# ==============================================================================
# PÁGINA 0: DASHBOARD (Vista Rápida: Conteos Clave y Pipeline)
# ==============================================================================
if menu_opcion in ("dashboard", "📊 Dashboard"):
    st.subheader(t("dashboard_title"))
    st.caption(t("dashboard_caption"))

    try:
        # 1. Extraemos los datos de la nube (Supabase ya filtra por user_id automáticamente gracias al RLS)
        response = supabase.table("applications").select("*").execute()
        datos_dashboard = response.data
    except Exception as e:
        if "JWT expired" in str(e):
            st.warning(t("session_expired_warning"))
            datos_dashboard = []
        else:
            st.error(t("dashboard_load_error", error=e))
            datos_dashboard = []

    if not datos_dashboard:
        st.info(t("dashboard_empty"))
    else:
        # 2. Pasamos los datos a Pandas para que tus gráficos originales funcionen
        df = pd.DataFrame(datos_dashboard)

        # Calculamos las métricas clave directamente con Pandas
        total_apps = len(df)
        entrevistas = len(df[df["status"].isin(["Recruiter Screen", "Technical Interview", "Final Interview"])])
        ofertas = len(df[df["status"] == "Offer"])
        rechazos = len(df[df["status"] == "Rejected"])
        hoy_str = date.today().strftime("%Y-%m-%d")
        fup_col = "follow_up_date" if "follow_up_date" in df.columns else None
        follow_ups = len(df[df[fup_col].notna() & (df[fup_col] <= hoy_str)]) if fup_col else 0

        # Tarjetas destacadas de métricas
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

        with col_m1:
            st.metric(
                label=t("metric_total_apps"),
                value=total_apps,
                help=t("metric_total_apps_help")
            )

        with col_m2:
            st.metric(
                label=t("metric_interviews"),
                value=entrevistas,
                help=t("metric_interviews_help")
            )

        with col_m3:
            st.metric(
                label=t("metric_offers"),
                value=ofertas,
                help=t("metric_offers_help")
            )

        with col_m4:
            st.metric(
                label=t("metric_rejected"),
                value=rechazos,
                help=t("metric_rejected_help")
            )

        with col_m5:
            st.metric(
                label=t("metric_follow_ups"),
                value=follow_ups,
                help=t("metric_follow_ups_help")
            )

        st.divider()

        # --------------------------------------------------------------------------
        # DESGLOSE COMPLETO POR ESTADO (Status Breakdown)
        # --------------------------------------------------------------------------
        st.markdown(f"### 📌 {t('dashboard_chart_pipeline')}")
        st.caption(t("dashboard_caption_status_breakdown"))

        conteo_estados = df["status"].value_counts().to_dict()
        desglose_status = {opt: conteo_estados.get(opt, 0) for opt in STATUS_OPTIONS}

        # Fila 1: Etapas activas
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric(f"📨 {t_status('Applied')}", desglose_status.get("Applied", 0))
        with c2:
            st.metric(f"📞 {t_status('Recruiter Screen')}", desglose_status.get("Recruiter Screen", 0))
        with c3:
            st.metric(f"💻 {t_status('Technical Interview')}", desglose_status.get("Technical Interview", 0))
        with c4:
            st.metric(f"🤝 {t_status('Final Interview')}", desglose_status.get("Final Interview", 0))

        # Fila 2: Resultados finales
        c5, c6, c7, _ = st.columns(4)
        with c5:
            st.metric(f"🎉 {t_status('Offer')}", desglose_status.get("Offer", 0))
        with c6:
            st.metric(f"❌ {t_status('Rejected')}", desglose_status.get("Rejected", 0))
        with c7:
            st.metric(f"👻 {t_status('Ghosted')}", desglose_status.get("Ghosted", 0))

        # Gráfico interactivo de barras para ver la distribución visual
        chart_title = t("dashboard_visual_dist_title")
        st.markdown(f"#### 📊 {chart_title}")
        col_status_lbl = t("dashboard_col_status")
        col_count_lbl = t("dashboard_col_count")
        df_status = pd.DataFrame(
            [(t_status(opt), count) for opt, count in desglose_status.items()],
            columns=[col_status_lbl, col_count_lbl]
        ).set_index(col_status_lbl)
        st.bar_chart(df_status)

        st.divider()

        # Explicación técnica
        with st.expander(t("dashboard_technical_expander")):
            st.markdown(t("dashboard_technical_content"))


# ==============================================================================
# PÁGINA 1: STATISTICS (Fase 7: Página Dedicada de Estadísticas Avanzadas)
# ==============================================================================
elif menu_opcion in ("stats", "📈 Statistics", "📈 Estadísticas"):
    st.header(t("stats_title"))
    st.caption(t("stats_caption"))

    # 1. Reutilización de métricas de la Fase 4 (sin duplicar queries)
    metricas = get_dashboard_counts()
    total_apps = metricas["total_applications"]
    interviews = metricas["interviews"]
    offers = metricas["offers"]
    rejections = metricas["rejections"]

    # Cálculo de Interview Rate
    # Regla de negocio: (Interviews / Total Applications) * 100
    interview_rate = (interviews / total_apps * 100) if total_apps > 0 else 0.0

    st.subheader(f"🎯 {t('stats_kpi_conversion')}")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric(t("metric_total_apps"), total_apps)
    with c2:
        st.metric(t("metric_interviews"), interviews, help=t("metric_interviews_help"))
    with c3:
        st.metric(t("metric_offers"), offers)
    with c4:
        st.metric(t("metric_rejected"), rejections)
    with c5:
        st.metric(t("stats_kpi_conversion"), f"{interview_rate:.1f}%", help=t("stats_metric_conversion_help"))

    st.divider()

    # 2. Modalidades de Trabajo (Work Mode Breakdown)
    st.subheader(f"🏢 {t('dashboard_chart_work_mode')}")
    work_modes = get_work_mode_breakdown()

    col_wm1, col_wm2, col_wm3 = st.columns(3)
    with col_wm1:
        st.metric(t("stats_remote_apps"), work_modes.get("Remote", 0))
    with col_wm2:
        st.metric(t("stats_hybrid_apps"), work_modes.get("Hybrid", 0))
    with col_wm3:
        st.metric(t("stats_onsite_apps"), work_modes.get("On-site", 0))

    # Gráfico de barras de modalidades
    df_wm = pd.DataFrame(
        [(t_work_mode(k), v) for k, v in work_modes.items()],
        columns=[t("stats_col_modality"), t("stats_col_total")]
    ).set_index(t("stats_col_modality"))
    st.bar_chart(df_wm)

    st.divider()

    # 3. Estadísticas Salariales (USD)
    st.subheader(t("stats_salary_title"))
    st.caption(t("stats_salary_caption"))
    
    salarios = get_salary_statistics()
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        st.metric(t("stats_salary_min"), f"${salarios['min']:,.2f} USD")
    with s_col2:
        st.metric(t("stats_salary_avg"), f"${salarios['avg']:,.2f} USD")
    with s_col3:
        st.metric(t("stats_salary_max"), f"${salarios['max']:,.2f} USD")
    with s_col4:
        st.metric(t("stats_salary_count"), f"{salarios['count']} {t('stats_of')} {total_apps}")

    st.divider()

    # 4. Análisis Temporal Mes a Mes (Aplicaciones y Entrevistas por Mes)
    st.subheader(t("stats_monthly_title"))
    st.caption(t("stats_monthly_caption"))

    monthly_apps = get_monthly_applications()
    monthly_ints = get_monthly_interviews()

    col_app_lbl = t("stats_col_applications")
    col_int_lbl = t("stats_col_interviews")
    col_month_lbl = t("stats_col_month")

    df_apps = pd.DataFrame(monthly_apps).rename(columns={"total": col_app_lbl}) if monthly_apps else pd.DataFrame(columns=["mes", col_app_lbl])
    df_ints = pd.DataFrame(monthly_ints).rename(columns={"total": col_int_lbl}) if monthly_ints else pd.DataFrame(columns=["mes", col_int_lbl])

    if not df_apps.empty:
        # Combinamos ambas series temporales usando un merge de pandas sobre la columna 'mes'
        df_evolucion = pd.merge(df_apps, df_ints, on="mes", how="left").fillna(0)
        df_evolucion[col_int_lbl] = df_evolucion[col_int_lbl].astype(int)
        df_evolucion = df_evolucion.rename(columns={"mes": col_month_lbl})

        col_tabla_mes, col_grafico_mes = st.columns([1, 2], gap="medium")
        with col_tabla_mes:
            st.markdown(f"##### {t('stats_monthly_table_title')}")
            st.dataframe(df_evolucion, use_container_width=True, hide_index=True)

        with col_grafico_mes:
            st.markdown(f"##### {t('stats_monthly_chart_title')}")
            st.line_chart(df_evolucion.set_index(col_month_lbl))
    else:
        st.info(t("stats_monthly_no_data"))


# ==============================================================================
# PÁGINA 2: MY PROFILE (Fase 5.1: Master Skill Profile)
# ==============================================================================
elif menu_opcion in ("profile", "👤 My Profile", "👤 Mi Perfil"):
    st.header(t("profile_title"))
    st.caption(t("profile_caption"))

    # --------------------------------------------------------------------------
    # 1. PERFIL GENERAL DEL USUARIO (user_profile)
    # --------------------------------------------------------------------------
    perfil = get_user_profile()
    with st.expander(f"📝 {t('profile_tab_info')}", expanded=(perfil is not None)):
        if perfil:
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                st.markdown(f"**{t('profile_fullname')}:** {perfil.get('full_name') or t('not_specified')}")
                st.markdown(f"**{t('profile_current_title')}:** {perfil.get('current_title') or t('not_specified')}")
                st.markdown(f"**{t('profile_location')}:** {perfil.get('location') or t('not_specified')}")
            with p_col2:
                st.markdown(f"**{t('profile_email')}:** {perfil.get('email') or t('not_specified')}")
                st.markdown(f"**{t('profile_phone')}:** {perfil.get('phone') or t('not_specified')}")
                st.caption(t("profile_updated_at", date=perfil.get('updated_at') or 'N/A'))
            if perfil.get("summary"):
                st.info(f"**{t('profile_summary')}:**\n\n{perfil['summary']}")
        else:
            st.info(t("profile_no_profile_saved"))

        with st.popover(f"✏️ {t('profile_btn_save_info')}"):
            with st.form("form_editar_perfil"):
                ed_name = st.text_input(t("profile_fullname"), value=perfil.get("full_name") if perfil else "")
                ed_title = st.text_input(t("profile_current_title"), value=perfil.get("current_title") if perfil else "")
                ed_email = st.text_input(t("profile_email"), value=perfil.get("email") if perfil else "")
                ed_phone = st.text_input(t("profile_phone"), value=perfil.get("phone") if perfil else "")
                ed_loc = st.text_input(t("profile_location"), value=perfil.get("location") if perfil else "")
                ed_sum = st.text_area(t("profile_summary"), value=perfil.get("summary") if perfil else "", height=100)
                if st.form_submit_button(t("profile_btn_save_info")):
                    save_user_profile(ed_name, ed_title, ed_email, ed_phone, ed_loc, ed_sum)
                    st.success(t("profile_saved_toast"))
                    st.rerun()

    st.divider()

    # --------------------------------------------------------------------------
    # 2. SUBIDA DE RESUME Y EXTRACCIÓN AUTOMÁTICA CON IA
    # --------------------------------------------------------------------------
    st.subheader(t("profile_upload_header"))
    st.caption(t("profile_upload_caption"))

    archivo_subido = st.file_uploader(
        t("profile_upload_file_label"),
        type=["pdf", "docx", "txt"],
        help=t("profile_upload_file_help")
    )

    if archivo_subido is not None:
        try:
            texto_cv = extract_resume_text(archivo_subido)
            st.success(t("profile_upload_read_success", name=archivo_subido.name, chars=len(texto_cv)))
            with st.expander(t("profile_preview_expander")):
                st.text_area(t("profile_preview_content"), value=texto_cv, height=200, disabled=True)

            # Verificación de API Key
            api_key_activa = get_api_key()
            if not api_key_activa:
                st.warning(t("profile_no_api_key_warn"))
                key_input = st.text_input(t("profile_api_key_input"), type="password")
                if key_input:
                    api_key_activa = key_input.strip()
                    os.environ["GEMINI_API_KEY"] = api_key_activa
                    # Guardamos automáticamente en .env para que persista
                    try:
                        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                        with open(env_file, "w", encoding="utf-8") as f_env:
                            f_env.write(f"GEMINI_API_KEY={api_key_activa}\n")
                        st.info(t("profile_key_saved_env"))
                    except Exception:
                        pass

            col_btn, _ = st.columns([1, 2])
            with col_btn:
                btn_analizar = st.button(t("profile_btn_analyze_cv"), type="primary", disabled=not bool(api_key_activa))

            if btn_analizar:
                with st.spinner(t("profile_cv_analyzing_spinner")):
                    try:
                        resultado = extract_skills_and_profile_from_resume(texto_cv, api_key=api_key_activa)
                        st.session_state["pending_resume_review"] = resultado
                        st.rerun()
                    except Exception as err:
                        st.error(t("profile_ai_error", error=err))
        except Exception as err_lectura:
            st.error(t("profile_read_file_error", error=err_lectura))

    # --------------------------------------------------------------------------
    # PANTALLA DE REVISIÓN ANTES DE GUARDAR EN SQLITE (Fase 5.7)
    # --------------------------------------------------------------------------
    if "pending_resume_review" in st.session_state and st.session_state["pending_resume_review"]:
        review_data = st.session_state["pending_resume_review"]
        st.markdown(f"### {t('profile_review_title')}")
        st.caption(t("profile_review_caption"))

        with st.container(border=True):
            # A. Perfil General
            st.markdown(f"#### 👤 {t('profile_card_title')}")
            prof_rev = review_data.get("profile", {})
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                rev_name = st.text_input(t("profile_field_name"), value=prof_rev.get("full_name") or "", key="rev_input_name")
                rev_email = st.text_input(t("profile_field_email"), value=prof_rev.get("email") or "", key="rev_input_email")
                rev_loc = st.text_input(t("profile_field_location"), value=prof_rev.get("location") or "", key="rev_input_loc")
            with c_p2:
                rev_title = st.text_input(t("profile_field_title"), value=prof_rev.get("current_title") or "", key="rev_input_title")
                rev_phone = st.text_input(t("profile_field_phone"), value=prof_rev.get("phone") or "", key="rev_input_phone")
            rev_sum = st.text_area(t("profile_field_summary"), value=prof_rev.get("summary") or "", height=80, key="rev_input_sum")

            # B. Habilidades Extraídas
            skills_rev = review_data.get("skills", [])
            st.markdown(f"#### {t('profile_review_skills_header', count=len(skills_rev))}")
            if skills_rev:
                skills_tags = [f"**{s['skill_name']}** (`{s['category']}`)" for s in skills_rev]
                st.markdown(" • ".join(skills_tags))

            # C. Experiencia Laboral Extraída
            exp_rev = review_data.get("experience", [])
            st.markdown(f"#### {t('profile_review_exp_header')} ({len(exp_rev)})")
            
            reviewed_experiences = []
            for idx_e, exp_item in enumerate(exp_rev):
                with st.expander(f"💼 {exp_item.get('position', 'Puesto')} en {exp_item.get('company', 'Empresa')}", expanded=True):
                    col_ex1, col_ex2 = st.columns(2)
                    with col_ex1:
                        c_val = st.text_input(t("profile_review_company"), value=exp_item.get("company", ""), key=f"rev_comp_{idx_e}")
                        p_val = st.text_input(t("profile_review_position"), value=exp_item.get("position", ""), key=f"rev_pos_{idx_e}")
                    with col_ex2:
                        cur_val = st.checkbox(t("profile_review_current_job"), value=bool(exp_item.get("is_current")), key=f"rev_cur_{idx_e}")
                        col_dt1, col_dt2 = st.columns(2)
                        with col_dt1:
                            s_date_init = exp_item.get("start_date") or ""
                            s_val = st.text_input(t("profile_review_start_date"), value=s_date_init, key=f"rev_sdate_{idx_e}")
                            if not s_date_init and exp_item.get("start_date_raw"):
                                st.caption(f"{t('profile_review_date_warning')} (Original: '{exp_item.get('start_date_raw')}')")
                        with col_dt2:
                            e_date_init = exp_item.get("end_date") or ""
                            e_val = st.text_input(
                                t("profile_review_end_date"),
                                value=e_date_init,
                                placeholder="Trabajo actual (en curso)" if cur_val else "YYYY-MM",
                                help="Si marcas 'Trabajo actual', este campo se ignorará y se guardará como trabajo en curso.",
                                key=f"rev_edate_{idx_e}"
                            )
                            if not cur_val and not e_val and exp_item.get("end_date_raw"):
                                st.caption(f"{t('profile_review_date_warning')} (Original: '{exp_item.get('end_date_raw')}')")

                    raw_bullets_str = "\n".join(exp_item.get("bullets", []))
                    bullets_area = st.text_area(t("profile_review_bullets_label"), value=raw_bullets_str, height=100, key=f"rev_bullets_{idx_e}")
                    clean_bullets = [b.strip() for b in bullets_area.splitlines() if b.strip()]

                    reviewed_experiences.append({
                        "company": c_val.strip(),
                        "position": p_val.strip(),
                        "start_date": s_val.strip() if s_val.strip() else None,
                        "end_date": None if cur_val else (e_val.strip() if e_val.strip() else None),
                        "is_current": cur_val,
                        "bullets": clean_bullets,
                        "order_index": idx_e + 1
                    })

            # D. Educación Extraída
            edu_rev = review_data.get("education", [])
            st.markdown(f"#### {t('profile_review_edu_header')} ({len(edu_rev)})")
            reviewed_education = []
            for idx_ed, edu_item in enumerate(edu_rev):
                with st.expander(f"🎓 {edu_item.get('credential', 'Certificación')} — {edu_item.get('institution', 'Institución')}", expanded=True):
                    col_ed1, col_ed2 = st.columns(2)
                    with col_ed1:
                        inst_val = st.text_input(t("profile_review_institution"), value=edu_item.get("institution", ""), key=f"rev_inst_{idx_ed}")
                        cred_val = st.text_input(t("profile_review_credential"), value=edu_item.get("credential", ""), key=f"rev_cred_{idx_ed}")
                    with col_ed2:
                        col_edd1, col_edd2 = st.columns(2)
                        with col_edd1:
                            eds_init = edu_item.get("start_date") or ""
                            eds_val = st.text_input(t("profile_review_start_date"), value=eds_init, key=f"rev_eds_{idx_ed}")
                            if not eds_init and edu_item.get("start_date_raw"):
                                st.caption(f"{t('profile_review_date_warning')} (Original: '{edu_item.get('start_date_raw')}')")
                        with col_edd2:
                            ede_init = edu_item.get("end_date") or ""
                            ede_val = st.text_input(t("profile_review_end_date"), value=ede_init, key=f"rev_ede_{idx_ed}")
                            if not ede_init and edu_item.get("end_date_raw"):
                                st.caption(f"{t('profile_review_date_warning')} (Original: '{edu_item.get('end_date_raw')}')")

                    reviewed_education.append({
                        "institution": inst_val.strip(),
                        "credential": cred_val.strip(),
                        "start_date": eds_val.strip() if eds_val.strip() else None,
                        "end_date": ede_val.strip() if ede_val.strip() else None,
                        "order_index": idx_ed + 1
                    })

            # Botones de Acción
            st.divider()
            col_save_btn, col_disc_btn = st.columns([2, 1])
            with col_save_btn:
                if st.button(t("profile_review_btn_save"), type="primary", use_container_width=True, key="btn_confirm_review_save"):
                    save_user_profile(
                        full_name=rev_name.strip() or None,
                        current_title=rev_title.strip() or None,
                        email=rev_email.strip() or None,
                        phone=rev_phone.strip() or None,
                        location=rev_loc.strip() or None,
                        summary=rev_sum.strip() or None
                    )
                    if skills_rev:
                        add_user_skills_bulk(skills_rev, source="Resume")
                    save_parsed_resume_data(reviewed_experiences, reviewed_education, replace_existing=True)

                    del st.session_state["pending_resume_review"]
                    st.toast(t("profile_review_saved_toast"), icon="🎉")
                    st.rerun()

            with col_disc_btn:
                if st.button(t("profile_review_btn_discard"), use_container_width=True, key="btn_discard_review"):
                    del st.session_state["pending_resume_review"]
                    st.toast(t("profile_review_discarded_toast"), icon="ℹ️")
                    st.rerun()

    st.divider()

    # --------------------------------------------------------------------------
    # 3. GESTIÓN MANUAL DE SKILLS (CRUD DE TAGS)
    # --------------------------------------------------------------------------
    st.subheader(t("profile_skills_inventory_title"))
    todas_las_skills = get_all_user_skills()

    total_s = len(todas_las_skills)
    resume_s = len([s for s in todas_las_skills if s.get("source") == "Resume"])
    manual_s = len([s for s in todas_las_skills if s.get("source") == "Manual"])

    col_ms1, col_ms2, col_ms3 = st.columns(3)
    with col_ms1:
        st.metric(t("profile_metric_total_skills"), total_s)
    with col_ms2:
        st.metric(t("profile_metric_extracted_cv"), resume_s)
    with col_ms3:
        st.metric(t("profile_metric_added_manual"), manual_s)

    categorias_disponibles = get_all_distinct_categories()

    # Formulario para agregar una skill manualmente
    with st.expander(t("profile_add_skill_manually")):
        col_sk1, col_sk2, col_sk3 = st.columns([2, 1.4, 1])
        with col_sk1:
            input_skill = st.text_input(t("profile_skill_name_label"), placeholder=t("profile_skill_name_placeholder"), key="input_skill_manual")
        with col_sk2:
            opciones_cat_form = [t("profile_new_category_option")] + categorias_disponibles
            idx_cat_def = 1 if len(opciones_cat_form) > 1 else 0
            input_cat = st.selectbox(t("profile_category_label"), options=opciones_cat_form, index=idx_cat_def, key="input_cat_manual")
            nueva_cat_personalizada = None
            if input_cat == t("profile_new_category_option"):
                nueva_cat_personalizada = st.text_input(t("profile_new_category_label"), placeholder=t("profile_new_category_placeholder"), key="input_new_custom_cat")
        with col_sk3:
            input_prof = st.selectbox(t("profile_field_proficiency"), options=PROFICIENCY_LEVELS, index=1, key="input_prof_manual")
        
        btn_guardar_skill = st.button(t("profile_btn_save_skill_manual"), type="primary", use_container_width=True)

        if btn_guardar_skill:
            cat_final = nueva_cat_personalizada.strip() if (input_cat == t("profile_new_category_option") and nueva_cat_personalizada) else input_cat
            if not input_skill.strip():
                st.error(t("profile_err_empty_skill"))
            elif input_cat == t("profile_new_category_option") and not (nueva_cat_personalizada and nueva_cat_personalizada.strip()):
                st.error(t("profile_err_empty_category"))
            else:
                add_user_skill(
                    skill_name=input_skill.strip(),
                    category=cat_final,
                    source="Manual",
                    proficiency=input_prof
                )
                st.success(t("profile_msg_skill_saved", skill=input_skill.strip(), category=cat_final))
                st.rerun()

    # Despliegue de skills existentes
    if not todas_las_skills:
        st.info(t("profile_no_skills_registered"))
    else:
        st.markdown(t("profile_skills_grouped_by_cat"))
        
        # Agrupamos por categoría
        skills_por_cat = {}
        for s in todas_las_skills:
            skills_por_cat.setdefault(s["category"], []).append(s)

        # Iteramos sobre las categorías que tienen al menos una skill
        for cat_nombre, items_cat in sorted(skills_por_cat.items()):
            with st.container():
                st.markdown(t("profile_skills_count_category", category=cat_nombre, count=len(items_cat)))
                
                # Desplegamos cada skill en columnas compactas
                for item in items_cat:
                    c_badge, c_name, c_cat, c_prof, c_del = st.columns([1, 2.2, 1.8, 1.4, 0.6])
                    
                    with c_badge:
                        if item.get("source") == "Resume":
                            st.caption("📄 **Resume**")
                        else:
                            st.caption("✏️ **Manual**")
                    
                    with c_name:
                        st.markdown(f"**{item['skill_name']}**")

                    with c_cat:
                        # Dropdown para cambiar o reasignar la categoría
                        cat_actual = item.get("category", "DevOps")
                        opciones_fila = [t("profile_new_category_option")] + categorias_disponibles
                        idx_cat = opciones_fila.index(cat_actual) if cat_actual in opciones_fila else 1
                        nueva_cat = st.selectbox(
                            t("profile_category_label"),
                            options=opciones_fila,
                            index=idx_cat,
                            key=f"cat_{item['id']}",
                            label_visibility="collapsed"
                        )
                        if nueva_cat == t("profile_new_category_option"):
                            col_nc1, col_nc2 = st.columns([3, 1])
                            with col_nc1:
                                txt_cat_fila = st.text_input(
                                    "Nueva cat",
                                    placeholder=t("profile_category_label"),
                                    key=f"txt_nc_{item['id']}",
                                    label_visibility="collapsed"
                                )
                            with col_nc2:
                                if st.button("💾", key=f"btn_save_nc_{item['id']}", help=t("profile_help_save_new_cat")):
                                    if txt_cat_fila.strip():
                                        update_user_skill_category(item["id"], txt_cat_fila.strip())
                                        st.rerun()
                                    else:
                                        st.warning(t("profile_warn_type_name"))
                        elif nueva_cat != cat_actual:
                            update_user_skill_category(item["id"], nueva_cat)
                            st.rerun()
                    
                    with c_prof:
                        # Dropdown para cambiar el nivel de proficiency
                        prof_actual = item.get("proficiency", "Intermediate")
                        idx_prof = PROFICIENCY_LEVELS.index(prof_actual) if prof_actual in PROFICIENCY_LEVELS else 1
                        nuevo_nivel = st.selectbox(
                            t("profile_field_proficiency"),
                            options=PROFICIENCY_LEVELS,
                            index=idx_prof,
                            key=f"prof_{item['id']}",
                            label_visibility="collapsed"
                        )
                        if nuevo_nivel != prof_actual:
                            update_user_skill_proficiency(item["id"], nuevo_nivel)
                            st.rerun()

                    with c_del:
                        if st.button("🗑️", key=f"del_sk_{item['id']}", help=t("profile_help_delete_skill", skill=item['skill_name'])):
                            delete_user_skill(item["id"])
                            st.rerun()

                st.divider()


# ==============================================================================
# PÁGINA 2.5: AI JOB ANALYZER & MATCH EVALUATOR (Fase 5.2)
# ==============================================================================
elif menu_opcion in ("analyzer", "🤖 AI Job Analyzer"):
    st.subheader(t("analyzer_title"))
    st.caption(t("analyzer_caption"))

    # 1. Verificación del perfil y habilidades registradas en SQLite
    user_skills = get_all_user_skills()
    if not user_skills:
        st.warning(t("analyzer_no_user_skills_warning"))
    else:
        st.info(t("analyzer_active_profile_info", count=len(user_skills)))

    # 2. Verificación de API Key
    api_key_env = get_api_key()
    api_key_usuario = None
    if not api_key_env:
        with st.expander(t("analyzer_api_expander"), expanded=True):
            api_key_usuario = st.text_input(
                t("analyzer_api_key_label"),
                type="password",
                help=t("analyzer_api_key_help")
            )

    # 3. Ingreso de Datos (Selección desde aplicaciones existentes o manual)
    st.markdown(f"### {t('analyzer_section_input')}")

    # Obtenemos aplicaciones para el dropdown (de Supabase con fallback a SQLite)
    try:
        resp_apps = supabase.table("applications").select("id, company, position, job_url, notes").order("id", desc=False).execute()
        apps_para_dropdown = resp_apps.data or []
    except Exception:
        apps_para_dropdown = get_all_applications()

    metodo_origen = st.radio(
        t("analyzer_how_to_load"),
        options=[
            t("analyzer_opt_existing_apps"),
            t("analyzer_opt_manual_url")
        ],
        horizontal=True,
        key="metodo_origen_analyzer"
    )

    url_para_analizar = st.session_state.get("job_url_input", "")

    if metodo_origen == t("analyzer_opt_existing_apps"):
        if not apps_para_dropdown:
            st.info("ℹ️ No hay aplicaciones registradas todavía. Puedes ingresar una URL o texto manualmente." if st.session_state.get("lang") == "es" else "ℹ️ No registered applications yet. You can enter a URL or text manually.")
        else:
            # Mapeo de aplicaciones para el dropdown
            mapa_apps = {}
            for a in apps_para_dropdown:
                url_ind = ("🔗 Con enlace" if a.get("job_url") else "📄 Sin enlace") if st.session_state.get("lang") == "es" else ("🔗 With URL" if a.get("job_url") else "📄 Without URL")
                etiqueta = f"#{a['id']} - {a.get('company', 'Empresa')} | {a.get('position', 'Puesto')} ({url_ind})"
                mapa_apps[etiqueta] = a

            placeholder_app = t("analyzer_select_app_placeholder")
            opciones_apps = [placeholder_app] + list(mapa_apps.keys())
            
            idx_app_sel = 0
            if "last_selected_analyzer_app" in st.session_state and st.session_state["last_selected_analyzer_app"] in opciones_apps:
                idx_app_sel = opciones_apps.index(st.session_state["last_selected_analyzer_app"])

            seleccion_app = st.selectbox(
                t("analyzer_select_app_label"),
                options=opciones_apps,
                index=idx_app_sel,
                key="select_app_dropdown_analyzer"
            )

            if seleccion_app != placeholder_app:
                st.session_state["last_selected_analyzer_app"] = seleccion_app
                app_obj = mapa_apps[seleccion_app]
                app_url = (app_obj.get("job_url") or "").strip()
                url_para_analizar = app_url
                st.session_state["job_url_input"] = app_url

                col_det1, col_det2 = st.columns([3.5, 1.5])
                with col_det1:
                    st.text_input(t("analyzer_associated_url"), value=app_url or ("Sin URL registrada" if st.session_state.get("lang") == "es" else "No URL registered"), disabled=True, key="disp_app_url_field")
                with col_det2:
                    st.write("")
                    if app_url:
                        open_link_lbl = "🌐 Abrir enlace" if st.session_state.get("lang") == "es" else "🌐 Open link"
                        st.markdown(f"<div style='margin-top: 15px;'><a href='{app_url}' target='_blank' rel='noopener noreferrer'>{open_link_lbl}</a></div>", unsafe_allow_html=True)
                    else:
                        st.caption("ℹ️ Sin URL guardada" if st.session_state.get("lang") == "es" else "ℹ️ No URL saved")

                # Botones para jalar la información
                col_btn_j1, col_btn_j2 = st.columns(2)
                with col_btn_j1:
                    if app_url:
                        if st.button(t("analyzer_btn_extract_url"), use_container_width=True, key="btn_ext_url_app"):
                            with st.spinner("Descargando y extrayendo contenido de la página web..." if st.session_state.get("lang") == "es" else "Extracting webpage content..."):
                                exito_scrap, resultado_scrap = extract_job_text_from_url(app_url)
                                if exito_scrap:
                                    st.session_state["input_job_text_area"] = resultado_scrap
                                    st.session_state["job_text_input"] = resultado_scrap
                                    st.session_state["job_url_input"] = app_url
                                    st.success("✅ ¡Texto de la vacante extraído exitosamente desde la URL!" if st.session_state.get("lang") == "es" else "✅ Job posting text successfully extracted from URL!")
                                    st.rerun()
                                else:
                                    st.warning(f"⚠️ {resultado_scrap}")
                                    if app_obj.get("notes"):
                                        st.info("💡 Consejo: Esta postulación tiene notas guardadas. Puedes cargarlas con el botón contiguo." if st.session_state.get("lang") == "es" else "💡 Tip: This application has notes saved. You can load them with the adjacent button.")
                    else:
                        st.button(t("analyzer_btn_extract_url"), disabled=True, use_container_width=True, key="btn_ext_url_dis", help=t("analyzer_no_url_help"))

                with col_btn_j2:
                    if app_obj.get("notes"):
                        if st.button(t("analyzer_btn_load_notes"), use_container_width=True, key="btn_load_notes_app"):
                            st.session_state["input_job_text_area"] = app_obj["notes"]
                            st.session_state["job_text_input"] = app_obj["notes"]
                            st.session_state["job_url_input"] = app_url
                            st.success("✅ ¡Notas de la aplicación cargadas en el área de texto!" if st.session_state.get("lang") == "es" else "✅ Notes loaded into text area!")
                            st.rerun()
                    else:
                        st.button(t("analyzer_btn_load_notes"), disabled=True, use_container_width=True, key="btn_load_notes_dis", help=t("analyzer_no_notes_help"))

    else:
        # Modo manual
        col_url_m1, col_url_m2 = st.columns([3.5, 1.5])
        with col_url_m1:
            url_manual = st.text_input(
                t("analyzer_url_label"),
                value=st.session_state.get("job_url_input", ""),
                placeholder=t("analyzer_url_placeholder"),
                key="input_url_manual_field"
            )
            url_para_analizar = url_manual.strip()
            st.session_state["job_url_input"] = url_para_analizar
        with col_url_m2:
            st.write("")
            btn_extraer_manual = st.button("🌐 Extraer de URL" if st.session_state.get("lang") == "es" else "🌐 Extract URL", use_container_width=True, key="btn_ext_manual")

        if btn_extraer_manual:
            if not url_manual.strip():
                st.warning("⚠️ Por favor ingresa una URL válida antes de extraer." if st.session_state.get("lang") == "es" else "⚠️ Please enter a valid URL before extracting.")
            else:
                with st.spinner("Descargando y extrayendo contenido de la vacante..." if st.session_state.get("lang") == "es" else "Extracting job posting content..."):
                    exito_sc, texto_sc = extract_job_text_from_url(url_manual.strip())
                    if exito_sc:
                        st.session_state["input_job_text_area"] = texto_sc
                        st.session_state["job_text_input"] = texto_sc
                        st.session_state["job_url_input"] = url_manual.strip()
                        st.success("✅ ¡Texto extraído exitosamente de la URL!" if st.session_state.get("lang") == "es" else "✅ Text extracted successfully!")
                        st.rerun()
                    else:
                        st.warning(f"⚠️ {texto_sc}")

    # Área de texto para pegar o editar el Job Description
    job_text_val = st.text_area(
        t("analyzer_job_description_label"),
        value=st.session_state.get("job_text_input", ""),
        height=220,
        placeholder=t("analyzer_job_description_placeholder"),
        key="input_job_text_area"
    )

    # Botones de acción
    col_act1, col_act2 = st.columns([3, 1])
    with col_act1:
        btn_analizar_vacante = st.button(t("analyzer_btn_analyze"), type="primary", use_container_width=True)
    with col_act2:
        if st.button(t("analyzer_btn_clear"), use_container_width=True):
            st.session_state.pop("job_analysis_result", None)
            st.session_state.pop("job_text_input", None)
            st.session_state.pop("input_job_text_area", None)
            st.session_state.pop("job_url_input", None)
            st.session_state.pop("last_selected_analyzer_app", None)
            st.rerun()

    # Ejecución del análisis al presionar el botón
    if btn_analizar_vacante:
        if not job_text_val.strip():
            st.error(t("analyzer_err_empty_input"))
        else:
            api_key_activa = api_key_usuario or api_key_env
            if not api_key_activa:
                st.error(t("analyzer_err_no_api_key"))
            else:
                with st.spinner(t("analyzer_spinner_evaluating")):
                    try:
                        resultado_analisis = analyze_job_description(
                            job_text=job_text_val.strip(),
                            user_skills=user_skills,
                            api_key=api_key_activa
                        )
                        st.session_state["job_analysis_result"] = resultado_analisis
                        st.session_state["job_text_input"] = job_text_val
                        if url_para_analizar.strip():
                            st.session_state["job_url_input"] = url_para_analizar.strip()
                        st.success(t("analyzer_success_analysis"))
                        st.rerun()
                    except Exception as err:
                        st.error(t("analyzer_error_during_analysis", error=err))

    # 4. Visualización del Match y Resultados
    if "job_analysis_result" in st.session_state:
        analisis = st.session_state["job_analysis_result"]
        job_info = analisis.get("job_info", {})
        matching = analisis.get("skill_matching", {})

        strong_matches = matching.get("strong_matches", [])
        partial_matches = matching.get("partial_matches", [])
        missing_skills = matching.get("missing_skills", [])

        st.divider()
        st.markdown(t("analyzer_eval_section_title"))

        total_requisitos = len(strong_matches) + len(partial_matches) + len(missing_skills)
        if total_requisitos > 0:
            score_calculado = round(((len(strong_matches) + 0.5 * len(partial_matches)) / total_requisitos) * 100)
        else:
            score_calculado = 0

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric(t("analyzer_metric_estimated_score"), f"{score_calculado}%")
        with m_col2:
            st.metric(t("analyzer_metric_strong_matches"), f"{len(strong_matches)} {t('analyzer_unit_skills')}")
        with m_col3:
            st.metric(t("analyzer_metric_partial_matches"), f"{len(partial_matches)} {t('analyzer_unit_skills')}")
        with m_col4:
            st.metric(t("analyzer_metric_missing_skills"), f"{len(missing_skills)} {t('analyzer_unit_gaps')}")

        # Visualización en 2 Columnas: Fortalezas (Izquierda) vs Brechas (Derecha)
        col_match_left, col_match_right = st.columns(2)

        with col_match_left:
            st.markdown(t("analyzer_col_matches_title"))
            
            if strong_matches:
                st.markdown(t("analyzer_strong_subhead"))
                for s in strong_matches:
                    nombre = s.get("skill", "")
                    prof = s.get("proficiency", "Intermediate")
                    razon = s.get("reason", "")
                    razon_str = f" — _{razon}_" if razon else ""
                    st.markdown(f"✅ **{nombre}** `{prof}`{razon_str}")
            
            if partial_matches:
                st.markdown(t("analyzer_partial_subhead"))
                for s in partial_matches:
                    nombre = s.get("skill", "")
                    prof = s.get("proficiency", "Beginner")
                    razon = s.get("reason", "")
                    razon_str = f" — _{razon}_" if razon else ""
                    st.markdown(f"⚠️ **{nombre}** `{prof}`{razon_str}")

            if not strong_matches and not partial_matches:
                st.info(t("analyzer_no_matches_found"))

        with col_match_right:
            st.markdown(t("analyzer_col_gaps_title"))
            if missing_skills:
                for s in missing_skills:
                    nombre = s.get("skill", "")
                    importancia = s.get("importance", "Required").strip("[]")
                    razon = s.get("reason", "").strip()
                    if razon and not razon.endswith((".", "!", "?")):
                        razon += "."
                    razon_str = f" — _{razon}_" if razon else ""

                    res = s.get("resource")
                    if not res:
                        from skill_resources import recommend_resource, recommend_from_ms_learn_catalog
                        ms_kw = ["azure", "microsoft", ".net", "c#", "powershell", "windows server", "active directory", "sql server", "power bi", "office 365", "m365"]
                        if any(k in nombre.lower() for k in ms_kw):
                            res = recommend_from_ms_learn_catalog(nombre)
                        if not res:
                            res = recommend_resource(nombre, s.get("category", "CI/CD & DevOps"))

                    p_name = res.get("title") or res.get("platform", "Plataforma de estudio")
                    p_url = res.get("url", "#")
                    st.markdown(f"❌ **{nombre}** `[{importancia}]`{razon_str}\n\n&nbsp;&nbsp;&nbsp;&nbsp;{t('analyzer_learn_free_at')} [{p_name}]({p_url})")
            else:
                st.success(t("analyzer_no_gaps_success"))

        # 5. Formulario Autocompletado para Guardar la Aplicación
        st.divider()
        st.markdown(t("analyzer_preregister_title"))
        st.caption(t("analyzer_preregister_caption"))

        with st.form("form_ai_guardar_aplicacion"):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                company_val = st.text_input(t("field_company"), value=job_info.get("company", ""))
            with f_col2:
                position_val = st.text_input(t("field_position"), value=job_info.get("position", ""))

            f_col3, f_col4 = st.columns(2)
            with f_col3:
                status_default_idx = STATUS_OPTIONS.index("Applied") if "Applied" in STATUS_OPTIONS else 0
                status_val = st.selectbox(
                    t("field_status"),
                    options=STATUS_OPTIONS,
                    index=status_default_idx,
                    format_func=lambda s: t_status(s)
                )
            with f_col4:
                app_date_val = st.date_input(t("field_application_date"), value=date.today())

            f_col5, f_col6 = st.columns(2)
            with f_col5:
                wm_detectado = job_info.get("work_mode", "Remote")
                wm_idx = WORK_MODE_OPTIONS.index(wm_detectado) if wm_detectado in WORK_MODE_OPTIONS else 0
                work_mode_val = st.selectbox(
                    t("field_work_mode"),
                    options=WORK_MODE_OPTIONS,
                    index=wm_idx,
                    format_func=lambda m: t_work_mode(m)
                )
            with f_col6:
                salary_val = st.text_input(t("field_salary"), value=job_info.get("salary", ""))

            f_col7, f_col8 = st.columns(2)
            with f_col7:
                url_guardar_val = st.text_input(t("field_job_url"), value=st.session_state.get("job_url_input", ""))
            with f_col8:
                location_val = st.text_input(t("field_location"), value=job_info.get("location", ""))

            fortalezas_txt = ", ".join(s.get("skill", "") for s in strong_matches[:5])
            faltantes_txt = ", ".join(s.get("skill", "") for s in missing_skills[:5])
            notas_generadas = (
                f"{t('analyzer_notes_analyzed_with')}\n"
                f"{t('analyzer_notes_match_score', score=score_calculado)}\n"
                f"{t('analyzer_notes_strengths', strengths=fortalezas_txt or 'N/A')}\n"
                f"{t('analyzer_notes_gaps', gaps=faltantes_txt or 'N/A')}"
            )
            notes_val = st.text_area(t("field_notes"), value=notas_generadas, height=100)

            btn_guardar_app = st.form_submit_button(t("analyzer_btn_save_tracker"), use_container_width=True)

        if btn_guardar_app:
            if not company_val.strip():
                st.error(t("analyzer_err_company_req"))
            elif not position_val.strip():
                st.error(t("analyzer_err_position_req"))
            else:
                fecha_str = app_date_val.strftime("%Y-%m-%d")
                salario_limpio = salary_val.strip() if salary_val.strip() else None
                url_final = url_guardar_val.strip() if url_guardar_val.strip() else None
                notas_finales = notes_val.strip() if notes_val.strip() else None

                # 1. Calculamos ID consecutivo y guardamos en Supabase
                proximo_id = None
                try:
                    res_max = supabase.table("applications").select("id").order("id", desc=True).limit(1).execute()
                    if res_max.data and len(res_max.data) > 0:
                        proximo_id = int(res_max.data[0]["id"]) + 1
                    else:
                        proximo_id = 1
                except Exception:
                    proximo_id = None

                nueva_app_cloud = {
                    "user_id": st.session_state.user.id,
                    "company": company_val.strip(),
                    "position": position_val.strip(),
                    "status": status_val,
                    "application_date": fecha_str,
                    "salary": salario_limpio,
                    "work_mode": work_mode_val,
                    "location": location_val.strip() if location_val.strip() else None,
                    "job_url": url_final,
                    "notes": notas_finales
                }
                if proximo_id is not None:
                    nueva_app_cloud["id"] = proximo_id

                nuevo_id = None
                try:
                    try:
                        res_sb = supabase.table("applications").insert(nueva_app_cloud).execute()
                    except Exception:
                        nueva_app_cloud.pop("id", None)
                        res_sb = supabase.table("applications").insert(nueva_app_cloud).execute()
                    nuevo_id = res_sb.data[0]["id"]
                except Exception as ex_sb:
                    st.warning(f"Aviso al guardar en Supabase: {ex_sb}")

                # 2. Guardamos también en SQLite local por consistencia
                try:
                    from database import get_connection
                    with get_connection() as conn:
                        c_loc = conn.cursor()
                        if nuevo_id is not None:
                            c_loc.execute("""
                                INSERT INTO applications (id, company, position, status, application_date, salary, work_mode, location, job_url, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (nuevo_id, company_val.strip(), position_val.strip(), status_val, fecha_str, salario_limpio, work_mode_val, location_val.strip() if location_val.strip() else None, url_final, notas_finales))
                        else:
                            nuevo_id = insert_application(
                                company=company_val.strip(),
                                position=position_val.strip(),
                                status=status_val,
                                application_date=fecha_str,
                                salary=salario_limpio,
                                work_mode=work_mode_val,
                                location=location_val.strip() if location_val.strip() else None,
                                job_url=url_final,
                                notes=notas_finales
                            )
                        conn.commit()
                except Exception:
                    if nuevo_id is None:
                        nuevo_id = insert_application(
                            company=company_val.strip(),
                            position=position_val.strip(),
                            status=status_val,
                            application_date=fecha_str,
                            salary=salario_limpio,
                            work_mode=work_mode_val,
                            location=location_val.strip() if location_val.strip() else None,
                            job_url=url_final,
                            notes=notas_finales
                        )

                # PASO 0: Persistir las habilidades evaluadas en la tabla 'skills'
                skills_a_guardar = []
                for s in strong_matches:
                    skills_a_guardar.append({"skill": s.get("skill", ""), "match_status": "strong"})
                for s in partial_matches:
                    skills_a_guardar.append({"skill": s.get("skill", ""), "match_status": "partial"})
                for s in missing_skills:
                    skills_a_guardar.append({"skill": s.get("skill", ""), "match_status": "missing"})

                if skills_a_guardar and nuevo_id:
                    total_guardadas = insert_application_skills(nuevo_id, skills_a_guardar)
                    st.caption(t("analyzer_skills_linked", count=total_guardadas))

                st.success(t("analyzer_app_saved_success", company=company_val, id=nuevo_id))
                st.balloons()


# ==============================================================================
# PÁGINA 3: VER, BUSCAR, FILTRAR, EDITAR Y ELIMINAR APLICACIONES
# ==============================================================================
elif menu_opcion in ("view_apps", "📋 Ver y Gestionar Aplicaciones"):

    # 1. Obtenemos todas las aplicaciones desde Supabase
    try:
        # Supabase devuelve los datos directamente como una lista de diccionarios
        response = supabase.table("applications").select("*").order("id", desc=True).execute()
        todas_las_apps = response.data
    except Exception as e:
        if "JWT expired" in str(e):
            st.warning(t("session_expired_warning"))
            todas_las_apps = []
        else:
            st.error(f"Error al leer la base de datos en la nube: {e}")
            todas_las_apps = []

    if not todas_las_apps:
        st.info("No hay aplicaciones registradas todavía. Ve a la pestaña '➕ Agregar Nueva Aplicación' para crear la primera.")
    else:
        # Convertimos la lista de diccionarios a un DataFrame de pandas para facilitar búsquedas y filtros
        df = pd.DataFrame(todas_las_apps)

        # ----------------------------------------------------------------------
        # BÚSQUEDA Y FILTROS (Requisito 6)
        # ----------------------------------------------------------------------
        st.subheader(f"🔍 {t('btn_search')} & {t('btn_filter')}")
        col_busq, col_f_status, col_f_mode = st.columns([2, 1, 1])

        with col_busq:
            busqueda = st.text_input(t("filter_search_label"), placeholder="Ej. Citi, DevOps, AWS...")

        with col_f_status:
            filtro_status = st.selectbox(t("filter_status_label"), options=[t("filter_all")] + STATUS_OPTIONS)

        with col_f_mode:
            filtro_mode = st.selectbox(t("filter_work_mode_label"), options=[t("filter_all")] + WORK_MODE_OPTIONS)

        # Aplicamos los filtros al DataFrame en memoria
        df_filtrado = df.copy()

        # Filtro de texto (búsqueda insensible a mayúsculas/minúsculas)
        if busqueda.strip():
            patron = busqueda.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado["company"].str.lower().str.contains(patron, na=False) |
                df_filtrado["position"].str.lower().str.contains(patron, na=False)
            ]

        # Filtro por Status (ignora el filtro si se seleccionó 'Todos' o 'All')
        if filtro_status not in ("Todos", "All", t("filter_all")):
            df_filtrado = df_filtrado[df_filtrado["status"] == filtro_status]

        # Filtro por Work Mode (ignora el filtro si se seleccionó 'Todos' o 'All')
        if filtro_mode not in ("Todos", "All", t("filter_all")):
            df_filtrado = df_filtrado[df_filtrado["work_mode"] == filtro_mode]

        # Mostramos contador de resultados
        if st.session_state.get("lang") == "en":
            st.caption(f"Showing **{len(df_filtrado)}** of **{len(df)}** applications.")
        else:
            st.caption(f"Mostrando **{len(df_filtrado)}** de **{len(df)}** aplicaciones.")

        # ----------------------------------------------------------------------
        # TABLA DE APLICACIONES (Requisito 2)
        # ----------------------------------------------------------------------
        columnas_tabla = ["id", "company", "position", "status", "work_mode", "salary", "application_date"]
        # Filtramos solo columnas existentes por seguridad
        cols_mostrar = [c for c in columnas_tabla if c in df_filtrado.columns]

        st.dataframe(
            df_filtrado[cols_mostrar],
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # ----------------------------------------------------------------------
        # SELECCIONAR UNA APLICACIÓN PARA EDITAR, VER DETALLES O ELIMINAR (Requisitos 3, 4 y 5)
        # ----------------------------------------------------------------------
        st.subheader(t("view_apps_manage_section"))

        # Creamos una lista de opciones claras para el selectbox: "[ID] Empresa - Puesto"
        opciones_apps = {
            f"#{row['id']:02d} | {row['company']} — {row['position']} ({t_status(row['status'])})": row['id']
            for _, row in df_filtrado.iterrows()
        }

        if not opciones_apps:
            st.warning(t("view_apps_no_matches"))
        else:
            col_sel, _ = st.columns([2, 1])
            with col_sel:
                seleccion_texto = st.selectbox(
                    t("view_apps_select_label"),
                    options=list(opciones_apps.keys())
                )

            app_id_seleccionado = opciones_apps[seleccion_texto]
            app_actual = get_application_by_id(app_id_seleccionado)

            if app_actual:
                # Mostramos los detalles y el formulario de edición
                col_detalle, col_edicion = st.columns([1, 1], gap="large")

                # PANEL IZQUIERDO: DETALLE COMPLETO (Requisito 3)
                with col_detalle:
                    st.markdown(f"### 📄 {t('details_modal_title')}")
                    modalidad_txt = t_work_mode(app_actual.get('work_mode', '')) if app_actual.get('work_mode') else ("No especificada" if st.session_state.get("lang") == "es" else "Not specified")
                    salario_txt = app_actual['salary'] or ("No especificado" if st.session_state.get("lang") == "es" else "Not specified")
                    fecha_txt = app_actual['application_date'] or ("Sin fecha" if st.session_state.get("lang") == "es" else "No date")
                    fup_txt = app_actual.get('follow_up_date') or ("⏰ No asignada" if st.session_state.get("lang") == "es" else "⏰ Not scheduled")
                    loc_txt = app_actual.get('location') or "N/A"
                    lbl_empresa = t("field_company").replace("*", "").strip()
                    lbl_posicion = t("field_position").replace("*", "").strip()
                    st.info(f"**{lbl_empresa}:** {app_actual['company']}\n\n"
                            f"**{lbl_posicion}:** {app_actual['position']}\n\n"
                            f"**{t('field_status')}:** `{t_status(app_actual['status'])}`\n\n"
                            f"**{t('field_work_mode')}:** {modalidad_txt}\n\n"
                            f"**{t('table_col_salary')}:** {salario_txt}\n\n"
                            f"**{t('field_application_date')}:** {fecha_txt}\n\n"
                            f"**{t('field_follow_up_date')}:** {fup_txt}\n\n"
                            f"**{t('field_location')}:** {loc_txt}")

                    if app_actual.get("job_url"):
                        st.markdown(f"🔗 [{t('btn_open_job_url')}]({app_actual['job_url']})")

                    if app_actual.get("notes"):
                        with st.expander(t("app_detail_notes_expander")):
                            st.write(app_actual["notes"])

                    # ----------------------------------------------------------
                    # FASE 5.3: HABILIDADES ASOCIADAS Y BOTÓN INTERVIEW COACH
                    # ----------------------------------------------------------
                    st.markdown("---")
                    st.markdown(f"#### {t('app_detail_prep_title')}")
                    skills_vacante = get_skills_by_application(app_actual["id"])
                    if skills_vacante:
                        s_str = [s["skill"] for s in skills_vacante if s["match_status"] == "strong"]
                        s_part = [s["skill"] for s in skills_vacante if s["match_status"] == "partial"]
                        s_miss = [s["skill"] for s in skills_vacante if s["match_status"] == "missing"]
                        if s_str:
                            st.caption(f"{t('app_detail_strengths')}" + ", ".join(f"`{x}`" for x in s_str))
                        if s_part:
                            st.caption(f"{t('app_detail_partial')}" + ", ".join(f"`{x}`" for x in s_part))
                        if s_miss:
                            st.caption(f"{t('app_detail_gaps')}" + ", ".join(f"`{x}`" for x in s_miss))
                    else:
                        st.caption(t("app_detail_no_skills_analyzed"))

                    if st.button(t("app_detail_btn_prepare"), key=f"btn_prep_{app_actual['id']}", type="primary", use_container_width=True):
                        st.session_state["show_interview_coach"] = True
                        st.session_state["coach_app_id"] = app_actual["id"]
                        st.rerun()

                    # SECCIÓN DE ELIMINACIÓN CON CONFIRMACIÓN (Requisito 5)
                    st.markdown("---")
                    st.markdown(f"#### {t('app_detail_danger_zone')}")
                    with st.expander(t("app_detail_delete_expander")):
                        st.warning(t("app_detail_delete_warning", company=app_actual['company']))
                        confirmar_borrado = st.checkbox(t("app_detail_delete_checkbox"), key=f"conf_del_{app_actual['id']}")
                        
                        if st.button(t("app_detail_delete_btn"), type="primary", disabled=not confirmar_borrado):
                            id_a_borrar = app_actual["id"]
                            with st.spinner(t("app_detail_delete_spinner", id=id_a_borrar)):
                                error_supabase = None
                                try:
                                    # 1. Eliminar la fila seleccionada en Supabase
                                    supabase.table("applications").delete().eq("id", id_a_borrar).execute()
                                    
                                    # 2. Re-acomodar el orden en Supabase: desplazar hacia abajo (id = id - 1)
                                    # las aplicaciones posteriores en orden ascendente para evitar colisiones de clave primaria
                                    resp_posteriores = supabase.table("applications").select("id").gt("id", id_a_borrar).order("id", desc=False).execute()
                                    for fila in resp_posteriores.data or []:
                                        viejo_id = fila["id"]
                                        nuevo_id = viejo_id - 1
                                        supabase.table("applications").update({"id": nuevo_id}).eq("id", viejo_id).execute()
                                except Exception as ex_sup:
                                    error_supabase = ex_sup

                                # 3. Sincronizar el borrado y reajuste en SQLite local
                                try:
                                    delete_application(id_a_borrar)
                                except Exception as ex_sql:
                                    pass

                                if error_supabase:
                                    st.error(t("app_detail_delete_err_supabase", error=error_supabase))
                                else:
                                    st.success(t("app_detail_delete_success", id=id_a_borrar))
                                    st.rerun()

                # PANEL DERECHO: FORMULARIO DE EDICIÓN (Requisito 4)
                with col_edicion:
                    st.markdown(f"### {t('edit_section_title')}")
                    st.caption(t("edit_section_caption"))

                    with st.form(f"form_editar_{app_actual['id']}"):
                        edit_company = st.text_input(t("field_company"), value=app_actual["company"])
                        edit_position = st.text_input(t("field_position"), value=app_actual["position"])

                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            fecha_default = date.today()
                            if app_actual.get("application_date"):
                                try:
                                    fecha_default = datetime.strptime(app_actual["application_date"][:10], "%Y-%m-%d").date()
                                except Exception:
                                    pass
                            edit_date = st.date_input(t("field_application_date"), value=fecha_default)

                        with col_e2:
                            idx_status = STATUS_OPTIONS.index(app_actual["status"]) if app_actual["status"] in STATUS_OPTIONS else 0
                            edit_status = st.selectbox(
                                t("field_status"),
                                options=STATUS_OPTIONS,
                                index=idx_status,
                                format_func=lambda s: t_status(s)
                            )

                        col_e3, col_e4 = st.columns(2)
                        with col_e3:
                            mode_val = app_actual.get("work_mode") or "Remote"
                            idx_mode = WORK_MODE_OPTIONS.index(mode_val) if mode_val in WORK_MODE_OPTIONS else 0
                            edit_mode = st.selectbox(
                                t("field_work_mode"),
                                options=WORK_MODE_OPTIONS,
                                index=idx_mode,
                                format_func=lambda m: t_work_mode(m)
                            )
                        with col_e4:
                            edit_location = st.text_input(t("field_location"), value=app_actual.get("location") or "")

                        col_esal1, col_esal2 = st.columns(2)
                        sal_actual_str = (app_actual.get("salary") or "").strip()
                        idx_curr_edit = 0
                        edit_num_only = sal_actual_str
                        for ic, c_opt in enumerate(CURRENCY_OPTIONS):
                            c_code = c_opt.split()[0]
                            if c_code != "TBD" and c_code in sal_actual_str.upper():
                                idx_curr_edit = ic
                                edit_num_only = re.sub(rf"\b{c_code}\b", "", sal_actual_str, flags=re.IGNORECASE).strip()
                                break

                        with col_esal1:
                            edit_salary_val = st.text_input(t("field_salary_amount"), value=edit_num_only, key=f"edit_sal_{app_actual['id']}")
                        with col_esal2:
                            edit_currency_sel = st.selectbox(t("field_currency"), options=CURRENCY_OPTIONS, index=idx_curr_edit, key=f"edit_curr_{app_actual['id']}")

                        col_fup1, col_fup2 = st.columns(2)
                        with col_fup1:
                            asignar_fup = st.checkbox(t("field_follow_up"), value=bool(app_actual.get("follow_up_date")), key=f"chk_fup_{app_actual['id']}")
                        with col_fup2:
                            fup_val = date.today()
                            if app_actual.get("follow_up_date"):
                                try:
                                    fup_val = datetime.strptime(app_actual["follow_up_date"][:10], "%Y-%m-%d").date()
                                except Exception:
                                    pass
                            edit_fup = st.date_input(t("field_follow_up_date"), value=fup_val, key=f"date_fup_{app_actual['id']}") if asignar_fup else None

                        edit_job_url = st.text_input(t("field_job_url"), value=app_actual.get("job_url") or "")
                        edit_notes = st.text_area(t("field_notes"), value=app_actual.get("notes") or "", height=120)

                        btn_guardar_edicion = st.form_submit_button(t("edit_btn_save"), use_container_width=True)

                    if btn_guardar_edicion:
                        if not edit_company.strip() or not edit_position.strip():
                            st.error(t("edit_error_empty"))
                        else:
                            fecha_str = edit_date.strftime("%Y-%m-%d")
                            fup_str = edit_fup.strftime("%Y-%m-%d") if edit_fup else None

                            # Formatear salario editado con moneda
                            salary_edit_final = None
                            if edit_salary_val.strip():
                                raw_es = edit_salary_val.strip()
                                code_e = edit_currency_sel.split()[0] if edit_currency_sel and not edit_currency_sel.startswith("TBD") else ""
                                if code_e and code_e not in raw_es.upper():
                                    salary_edit_final = f"{raw_es} {code_e}"
                                else:
                                    salary_edit_final = raw_es

                            # 1. Actualizamos en Supabase (en la nube)
                            try:
                                datos_actualizados = {
                                    "company": edit_company.strip(),
                                    "position": edit_position.strip(),
                                    "status": edit_status,
                                    "application_date": fecha_str,
                                    "salary": salary_edit_final,
                                    "work_mode": edit_mode,
                                    "location": edit_location.strip() if edit_location else None,
                                    "job_url": edit_job_url.strip() if edit_job_url else None,
                                    "notes": edit_notes.strip() if edit_notes else None,
                                    "follow_up_date": fup_str
                                }
                                supabase.table("applications").update(datos_actualizados).eq("id", app_actual["id"]).execute()

                                # 2. Sincronizamos también en SQLite local por consistencia
                                try:
                                    update_application(
                                        app_id=app_actual["id"],
                                        company=edit_company.strip(),
                                        position=edit_position.strip(),
                                        status=edit_status,
                                        application_date=fecha_str,
                                        salary=salary_edit_final,
                                        work_mode=edit_mode,
                                        location=edit_location.strip() if edit_location else None,
                                        job_url=edit_job_url.strip() if edit_job_url else None,
                                        notes=edit_notes.strip() if edit_notes else None,
                                        follow_up_date=fup_str
                                    )
                                except Exception:
                                    pass

                                st.success(t("msg_app_updated_cloud_success"))
                                st.rerun()
                            except Exception as e:
                                st.error(t("msg_app_update_cloud_error", error=e))

                # --------------------------------------------------------------
                # FASE 5.3: INTERVIEW COACH INTEGRADO
                # --------------------------------------------------------------
                # --------------------------------------------------------------
                # FASE 5.3: INTERVIEW COACH INTEGRADO
                # --------------------------------------------------------------
                if st.session_state.get("show_interview_coach") and st.session_state.get("coach_app_id") == app_actual["id"]:
                    render_interview_coach(app_actual=app_actual, show_close_button=True)


# ==============================================================================
# PÁGINA 3: AGREGAR NUEVA APLICACIÓN (Requisito 1)
# ==============================================================================
elif menu_opcion in ("add_app", "➕ Agregar Nueva Aplicación"):
    st.subheader(t("add_app_title"))
    st.caption(t("add_app_caption"))

    with st.form("form_nueva_aplicacion", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input(t("field_company"), placeholder="Ej. Microsoft, Akamai...")
        with col2:
            position = st.text_input(t("field_position"), placeholder="Ej. DevOps Engineer, SRE...")

        col3, col4 = st.columns(2)
        with col3:
            app_date = st.date_input(t("field_application_date"), value=date.today(), key="new_app_date")
        with col4:
            status = st.selectbox(t("field_status"), options=STATUS_OPTIONS, index=0, key="new_status")

        col5, col6 = st.columns(2)
        with col5:
            work_mode = st.radio(t("field_work_mode"), options=["Remote", "Hybrid", "On-site"], horizontal=True, key="new_work_mode")
        with col6:
            location = st.text_input(t("field_location"), placeholder="Ej. San José, Costa Rica / Remote US", key="new_location")

        col_sal1, col_sal2 = st.columns(2)
        with col_sal1:
            salary_input = st.text_input(
                t("field_salary_amount"),
                placeholder="Ej. 5000 o 4000 - 5000",
                key="new_salary"
            )
        with col_sal2:
            selected_curr = st.selectbox(
                t("field_currency"),
                options=CURRENCY_OPTIONS,
                index=0,  # USD por defecto
                key="new_salary_curr"
            )

        col7, col8 = st.columns(2)
        with col7:
            job_url = st.text_input(t("field_job_url"), placeholder="https://linkedin.com/jobs/...", key="new_url")
        with col8:
            asignar_fup_nuevo = st.checkbox("Programar Follow-up", value=False, key="new_fup_chk")
            fup_date_nuevo = st.date_input(t("field_follow_up_date"), value=date.today(), key="new_fup_date") if asignar_fup_nuevo else None

        notes = st.text_area(t("field_notes"), placeholder="Pega aquí requisitos clave o notas...", key="new_notes")

        btn_crear = st.form_submit_button(t("btn_save_application"), use_container_width=True)

    if btn_crear:
        errores = []
        if not company.strip():
            errores.append("El campo **Company** es obligatorio.")
        if not position.strip():
            errores.append("El campo **Position** es obligatorio.")

        salary_limpio = None
        if salary_input.strip():
            salario_raw = salary_input.strip()
            codigo_moneda = selected_curr.split()[0] if selected_curr and not selected_curr.startswith("TBD") else ""

            # Limpiamos caracteres no numéricos salvo guion y punto para formatear si es un valor simple
            salario_solo_digitos = re.sub(r"[^\d.]", "", salario_raw.replace(",", ""))
            try:
                if salario_solo_digitos and re.match(r"^\d+(?:\.\d+)?$", salario_solo_digitos) and "-" not in salario_raw:
                    val_float = float(salario_solo_digitos)
                    formatted_num = f"{int(val_float):,}"
                    salary_limpio = f"{formatted_num} {codigo_moneda}".strip() if codigo_moneda else formatted_num
                else:
                    # Es un rango (ej: 4000 - 5000) o texto (ej: TBD, Negociable)
                    if codigo_moneda and codigo_moneda not in salario_raw.upper():
                        salary_limpio = f"{salario_raw} {codigo_moneda}"
                    else:
                        salary_limpio = salario_raw
            except Exception:
                salary_limpio = salario_raw

        if errores:
            for err in errores:
                st.error(f"⚠️ {err}")
        else:
            fecha_str = app_date.strftime("%Y-%m-%d")
            fup_nuevo_str = fup_date_nuevo.strftime("%Y-%m-%d") if (asignar_fup_nuevo and fup_date_nuevo) else None
            
            # Calculamos el próximo ID consecutivo para mantener la secuencia continua
            proximo_id = None
            try:
                res_max = supabase.table("applications").select("id").order("id", desc=True).limit(1).execute()
                if res_max.data and len(res_max.data) > 0:
                    proximo_id = int(res_max.data[0]["id"]) + 1
                else:
                    proximo_id = 1
            except Exception:
                proximo_id = None

            # 1. Empaquetar los datos para Supabase
            nueva_aplicacion = {
                "user_id": st.session_state.user.id,  # Vincula el registro al usuario logueado
                "company": company.strip(),
                "position": position.strip(),
                "status": status,
                "application_date": fecha_str,
                "salary": salary_limpio,
                "work_mode": work_mode,
                "location": location.strip() if location else None,
                "job_url": job_url.strip() if job_url else None,
                "notes": notes.strip() if notes else None,
                "follow_up_date": fup_nuevo_str
            }
            if proximo_id is not None:
                nueva_aplicacion["id"] = proximo_id

            try:
                # 2. Enviar a Supabase
                try:
                    response = supabase.table("applications").insert(nueva_aplicacion).execute()
                except Exception:
                    # En caso de restricción con ID explícito, insertar con auto-secuencia
                    nueva_aplicacion.pop("id", None)
                    response = supabase.table("applications").insert(nueva_aplicacion).execute()
                
                # 3. Extraer el nuevo ID de la respuesta de la nube
                nuevo_id = response.data[0]['id']

                # 4. Sincronizar en la base SQLite local por consistencia
                try:
                    from database import get_connection
                    with get_connection() as conn:
                        c_loc = conn.cursor()
                        c_loc.execute("""
                            INSERT INTO applications (id, company, position, status, application_date, salary, work_mode, location, job_url, notes, follow_up_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            nuevo_id,
                            company.strip(),
                            position.strip(),
                            status,
                            fecha_str,
                            salary_limpio,
                            work_mode,
                            location.strip() if location else None,
                            job_url.strip() if job_url else None,
                            notes.strip() if notes else None,
                            fup_nuevo_str
                        ))
                        conn.commit()
                except Exception:
                    pass
                
                st.success(f"🎉 ¡Aplicación a **{company}** guardada con éxito en la nube con ID #{nuevo_id}!")
            except Exception as e:
                if "row-level security" in str(e).lower() and ("access_token" not in st.session_state or not st.session_state.access_token):
                    st.error("⚠️ Tu sesión actual no tiene el token de base de datos activado. Por favor haz clic en **Cerrar Sesión** (arriba a la derecha) e inicia sesión nuevamente para sincronizar los permisos RLS.")
                else:
                    st.error(f"⚠️ Error al guardar en Supabase: {e}")


# ==============================================================================
# PÁGINA 5: PREPARE ME FOR THIS JOB (OPCIÓN INDEPENDIENTE DEL MENÚ)
# ==============================================================================
elif menu_opcion in ("coach", "🎯 Prepare me for this job"):
    st.subheader(t("coach_title"))
    st.caption(t("coach_caption"))

    # 1. Obtenemos todas las aplicaciones desde Supabase o SQLite
    todas_las_apps = []
    try:
        response = supabase.table("applications").select("*").order("id", desc=True).execute()
        todas_las_apps = response.data or []
    except Exception:
        try:
            todas_las_apps = get_all_applications()
        except Exception:
            todas_las_apps = []

    if not todas_las_apps:
        st.info(t("coach_no_apps_available"))
    else:
        # Selector de aplicación: dropdown que muestra "Company - Position"
        opciones_etiquetas = [
            f"#{app_item['id']} — {app_item['company']} ({app_item['position']})"
            for app_item in todas_las_apps
        ]

        # Recuperar índice previo si existe
        idx_default = 0
        if "coach_menu_selected_id" in st.session_state:
            for i, a in enumerate(todas_las_apps):
                if a["id"] == st.session_state["coach_menu_selected_id"]:
                    idx_default = i
                    break

        seleccion_str = st.selectbox(
            t("coach_select_app_label"),
            options=opciones_etiquetas,
            index=idx_default,
            key="sb_coach_app_selector"
        )

        app_elegida = todas_las_apps[opciones_etiquetas.index(seleccion_str)]
        st.session_state["coach_menu_selected_id"] = app_elegida["id"]

        # Renderizamos el coach reutilizando la función compartida sin duplicar código
        render_interview_coach(app_actual=app_elegida, show_close_button=False)


# ==============================================================================
# PÁGINA 6: CV BUILDER & AI OPTIMIZER (Fase 5.6a: Editor Híbrido de Bullets)
# ==============================================================================
elif menu_opcion in ("cv_builder", "📄 CV Builder", "📄 CV Builder & AI Optimizer"):
    st.subheader(t("cv_builder_title"))
    st.caption(t("cv_builder_caption"))

    # 1. Entrada opcional de la vacante (Job Description)
    job_description = st.text_area(
        t("cv_job_desc_label"),
        placeholder=t("cv_job_desc_placeholder"),
        height=110,
        key="cv_job_desc_input"
    )

    # Obtenemos las experiencias, bullets y educación persistidos en SQLite
    experiences = get_all_experiences()
    bullets = get_all_resume_bullets()
    education = get_all_education()

    # Mapeamos bullets por experience_id y por sección para compatibilidad
    bullets_by_exp = {}
    sections_dict = {}
    for b in bullets:
        bullets_by_exp.setdefault(b["experience_id"], []).append(b)
        sections_dict.setdefault(b.get("section", "Experiencia"), []).append(b)

    # Fila de modo y botón de Match Score completo (Fase 5.6b)
    col_mode_info, col_calc_match = st.columns([3, 2])
    with col_mode_info:
        if job_description.strip():
            st.info(f"🎯 **Modo Activo: {t('cv_mode_tailored')}** — La IA adaptará tus bullets incorporando requerimientos y palabras clave de la vacante pegada.")
        else:
            st.info(f"⚡ **Modo Activo: {t('cv_mode_general')}** — La IA optimizará tus bullets aplicando la Fórmula de Impacto de Google (Acción + Tecnología + Métricas de resultado).")

    with col_calc_match:
        # El botón de Match Score solo se muestra si hay una vacante pegada
        if job_description.strip():
            if st.button(t("cv_btn_calculate_match"), type="primary", use_container_width=True, key="btn_cv_calculate_match"):
                # Construimos el texto completo del resume concatenando perfil, experiencias y educación
                user_prof = get_user_profile()
                resume_lines = []
                if user_prof:
                    candidato_titulo = f"Candidato: {user_prof.get('full_name') or ''} - {user_prof.get('current_title') or ''}"
                    resume_lines.append(candidato_titulo)
                    if user_prof.get("summary"):
                        resume_lines.append(f"Resumen Profesional: {user_prof['summary']}")

                for exp in experiences:
                    fechas_exp = f"({exp['start_date'] or ''} - {'Presente' if exp['is_current'] else (exp['end_date'] or '')})"
                    resume_lines.append(f"\nExperiencia: {exp['position']} en {exp['company']} {fechas_exp}:")
                    for b_item in bullets_by_exp.get(exp["id"], []):
                        resume_lines.append(f"- {b_item['current_text']}")

                if education:
                    resume_lines.append("\nEducación y Certificaciones:")
                    for edu in education:
                        fechas_edu = f"({edu['start_date'] or ''} - {edu['end_date'] or ''})"
                        resume_lines.append(f"- {edu['credential']} en {edu['institution']} {fechas_edu}")

                full_resume_text = "\n".join(resume_lines)

                with st.spinner(t("cv_spinner_evaluating")):
                    try:
                        # Reutilizamos exactamente el mismo motor y mega-prompt de la Fase 5.2
                        resultado_match = analyze_job_description(
                            job_text=job_description.strip(),
                            candidate_text=full_resume_text,
                            api_key=get_api_key()
                        )
                        st.session_state["cv_match_result"] = resultado_match
                        st.toast(t("cv_match_success_toast"), icon="🎯")
                        st.rerun()
                    except Exception as err:
                        st.error(f"❌ Error al calcular match con la vacante: {err}")

    st.divider()

    # 2. Pantalla Dividida: Editor Interactivo (Izquierda) vs Vista Previa / Match (Derecha)
    col_editor, col_preview = st.columns([1, 1], gap="large")

    # --------------------------------------------------------------------------
    # COLUMNA IZQUIERDA: EDITOR INTERACTIVO DE EXPERIENCIA Y BULLETS
    # --------------------------------------------------------------------------
    with col_editor:
        st.markdown(f"### {t('cv_editor_col_title')}")

        # Formulario para agregar una nueva experiencia laboral estructurada
        with st.expander("➕ Agregar nueva experiencia laboral", expanded=False):
            with st.form("form_add_new_experience"):
                c_ne1, c_ne2 = st.columns(2)
                with c_ne1:
                    ne_comp = st.text_input("Empresa *", placeholder="Ej. Amazon, Google, StartUp...")
                    ne_pos = st.text_input("Puesto / Cargo *", placeholder="Ej. Senior Cloud Engineer...")
                with c_ne2:
                    ne_cur = st.checkbox("¿Es tu trabajo actual?", value=False)
                    c_ned1, c_ned2 = st.columns(2)
                    with c_ned1:
                        ne_sdate = st.text_input("Inicio (YYYY-MM)", placeholder="2022-01")
                    with c_ned2:
                        ne_edate = st.text_input("Fin (YYYY-MM)", placeholder="2024-05", help="Ignorado si marcas '¿Es tu trabajo actual?'")
                
                ne_first_bullet = st.text_area("Primer logro / bullet (opcional)", placeholder="Logro o responsabilidad inicial...", height=70)
                btn_submit_exp = st.form_submit_button("💾 Guardar Nueva Experiencia", type="primary")

                if btn_submit_exp:
                    if ne_comp.strip() and ne_pos.strip():
                        new_eid = add_experience_entry(
                            company=ne_comp.strip(),
                            position=ne_pos.strip(),
                            start_date=ne_sdate.strip() if ne_sdate.strip() else None,
                            end_date=None if ne_cur else (ne_edate.strip() if ne_edate.strip() else None),
                            is_current=ne_cur
                        )
                        if ne_first_bullet.strip():
                            add_resume_bullet(new_eid, ne_first_bullet.strip())
                        st.toast("✅ Experiencia agregada exitosamente", icon="💼")
                        st.rerun()
                    else:
                        st.error("Por favor completa al menos la empresa y el cargo.")

        if not experiences:
            st.warning(t("cv_no_bullets"))
            if st.button(t("cv_btn_reset_defaults")):
                seed_default_resume_bullets()
                st.rerun()
        else:
            for exp in experiences:
                exp_id = exp["id"]
                exp_bullets = bullets_by_exp.get(exp_id, [])
                dates_badge = f"{exp['start_date'] or ''} — {'Presente' if exp['is_current'] else (exp['end_date'] or '')}"

                with st.container(border=True):
                    # Cabecera de la Experiencia
                    st.markdown(f"#### 🏢 {exp['position']} — **{exp['company']}**")
                    st.caption(f"📅 **Período:** `{dates_badge}`")

                    # Expander para editar la empresa, puesto y fechas
                    with st.expander("✏️ Editar datos de este puesto / empresa", expanded=False):
                        with st.form(f"form_edit_exp_{exp_id}"):
                            ced_1, ced_2 = st.columns(2)
                            with ced_1:
                                upd_comp = st.text_input("Empresa", value=exp["company"], key=f"upd_c_{exp_id}")
                                upd_pos = st.text_input("Puesto", value=exp["position"], key=f"upd_p_{exp_id}")
                            with ced_2:
                                upd_cur = st.checkbox("Trabajo actual", value=bool(exp["is_current"]), key=f"upd_cur_{exp_id}")
                                c_updd1, c_updd2 = st.columns(2)
                                with c_updd1:
                                    upd_s = st.text_input("Inicio (YYYY-MM)", value=exp["start_date"] or "", key=f"upd_s_{exp_id}")
                                with c_updd2:
                                    upd_e = st.text_input("Fin (YYYY-MM)", value=exp["end_date"] or "", placeholder="YYYY-MM", help="Ignorado si marcas 'Trabajo actual'", key=f"upd_e_{exp_id}")

                            if st.form_submit_button("💾 Guardar Cambios de Puesto"):
                                update_experience_entry(
                                    exp_id,
                                    upd_comp,
                                    upd_pos,
                                    upd_s.strip() if upd_s.strip() else None,
                                    None if upd_cur else (upd_e.strip() if upd_e.strip() else None),
                                    upd_cur
                                )
                                st.toast("Datos actualizados", icon="💾")
                                st.rerun()

                    # Bullets pertenecientes a esta experiencia
                    if not exp_bullets:
                        st.info("Aún no hay viñetas/bullets para este puesto.")
                    else:
                        for b in exp_bullets:
                            b_id = b["id"]
                            with st.container(border=True):
                                pending_prop_key = f"cv_pending_improvement_{b_id}"
                                pending_mode_key = f"cv_pending_mode_{b_id}"

                                if pending_prop_key in st.session_state:
                                    st.caption(f"📌 {t('cv_current_label')}")
                                    st.write(b["current_text"])

                                    active_mode = t("cv_mode_tailored") if st.session_state.get(pending_mode_key) == "tailored" else t("cv_mode_general")
                                    st.success(f"**{t('cv_improvement_pending', mode=active_mode)}**\n\n{st.session_state[pending_prop_key]}")

                                    c_acc, c_disc = st.columns(2)
                                    with c_acc:
                                        if st.button(t("cv_btn_accept"), key=f"btn_accept_{b_id}", type="primary"):
                                            # Persistencia real en SQLite tras confirmación explícita
                                            update_resume_bullet(b_id, st.session_state[pending_prop_key])
                                            del st.session_state[pending_prop_key]
                                            if pending_mode_key in st.session_state:
                                                del st.session_state[pending_mode_key]
                                            st.toast(t("cv_bullet_saved_toast"), icon="💾")
                                            st.rerun()
                                    with c_disc:
                                        if st.button(t("cv_btn_discard"), key=f"btn_discard_{b_id}"):
                                            # Descartar propuesta en session_state sin alterar SQLite
                                            del st.session_state[pending_prop_key]
                                            if pending_mode_key in st.session_state:
                                                del st.session_state[pending_mode_key]
                                            st.info(t("cv_improvement_discarded"))
                                            st.rerun()
                                else:
                                    # Vista normal de edición manual
                                    edited_text = st.text_area(
                                        t("cv_bullet_text_label"),
                                        value=b["current_text"],
                                        key=f"txt_bullet_val_{b_id}",
                                        height=80,
                                        label_visibility="collapsed"
                                    )

                                    b_c1, b_c2, b_c3 = st.columns([3, 1, 1])
                                    with b_c1:
                                        if st.button(f"⚡ {t('cv_btn_improve_ai')}", key=f"btn_ai_improve_{b_id}"):
                                            with st.spinner("🤖 Generando propuesta de redacción..."):
                                                improved = rewrite_resume_bullet(
                                                    current_bullet=edited_text,
                                                    job_description=job_description
                                                )
                                                # Guardamos la propuesta en memoria (session_state) antes de persistir
                                                st.session_state[pending_prop_key] = improved
                                                st.session_state[pending_mode_key] = "tailored" if bool(job_description and job_description.strip()) else "general"
                                                st.rerun()
                                    with b_c2:
                                        if edited_text != b["current_text"]:
                                            if st.button("💾", key=f"btn_save_txt_{b_id}", help=t("btn_save")):
                                                update_resume_bullet(b_id, edited_text)
                                                st.toast(t("cv_bullet_saved_toast"), icon="💾")
                                                st.rerun()
                                    with b_c3:
                                        if st.button("🗑️", key=f"btn_del_b_{b_id}", help=t("btn_delete")):
                                            delete_resume_bullet(b_id)
                                            st.toast(t("cv_bullet_deleted_toast"), icon="🗑️")
                                            st.rerun()

                    # Formulario para agregar un nuevo bullet a esta experiencia
                    with st.expander(f"➕ Agregar viñeta / bullet a este puesto", expanded=False):
                        with st.form(f"form_add_b_{exp_id}"):
                            new_b_text = st.text_area("Texto del logro o responsabilidad:", placeholder="Ej. Lideré la migración de...", height=75)
                            if st.form_submit_button("➕ Agregar viñeta", type="primary"):
                                if new_b_text.strip():
                                    add_resume_bullet(exp_id, new_b_text.strip())
                                    st.toast("Bullet agregado con éxito", icon="✅")
                                    st.rerun()
                                else:
                                    st.error("El texto del bullet no puede estar vacío.")

                    # Botón para eliminar la experiencia completa
                    with st.expander("🗑️ Eliminar este puesto completo", expanded=False):
                        st.caption("Esta acción eliminará el puesto y todos sus bullets asociados.")
                        if st.button(f"Eliminar {exp['position']} permanentemente", key=f"btn_del_exp_{exp_id}", type="secondary"):
                            delete_experience_entry(exp_id)
                            st.toast("Experiencia eliminada", icon="🗑️")
                            st.rerun()

    # --------------------------------------------------------------------------
    # COLUMNA DERECHA: PESTAÑAS DE MATCH SCORE Y VISTA PREVIA DEL PDF
    # --------------------------------------------------------------------------
    with col_preview:
        tab_match, tab_preview = st.tabs([
            f"{t('cv_tab_match_analysis')}",
            f"{t('cv_tab_pdf_preview')}"
        ])

        with tab_match:
            if "cv_match_result" not in st.session_state:
                if job_description.strip():
                    st.info(f"💡 Haz clic en el botón superior **'{t('cv_btn_calculate_match')}'** para evaluar tu CV completo contra los requisitos de la vacante.")
                else:
                    st.info(f"ℹ️ Pega una descripción de puesto en el campo superior y presiona **'{t('cv_btn_calculate_match')}'** para calcular el Match Score.")
            else:
                analisis_match = st.session_state["cv_match_result"]
                match_data = analisis_match.get("skill_matching", {})
                strong_m = match_data.get("strong_matches", [])
                partial_m = match_data.get("partial_matches", [])
                missing_m = match_data.get("missing_skills", [])

                total_reqs = len(strong_m) + len(partial_m) + len(missing_m)
                match_score = round(((len(strong_m) + 0.5 * len(partial_m)) / total_reqs) * 100) if total_reqs > 0 else 0

                st.markdown(f"### {t('cv_match_results_title')}")

                # Fila de métricas clave (consistente con Fase 5.2)
                sc1, sc2, sc3, sc4 = st.columns(4)
                with sc1:
                    st.metric(t("cv_metric_estimated_score"), f"{match_score}%")
                with sc2:
                    st.metric(t("cv_metric_strong_matches"), f"{len(strong_m)} {t('cv_unit_skills')}")
                with sc3:
                    st.metric(t("cv_metric_partial_matches"), f"{len(partial_m)} {t('cv_unit_skills')}")
                with sc4:
                    st.metric(t("cv_metric_missing_skills"), f"{len(missing_m)} {t('cv_unit_gaps')}")

                st.markdown("---")

                # Fortalezas y Coincidencias Parciales
                with st.expander(f"✅ {t('cv_col_matches_title')} ({len(strong_m) + len(partial_m)})", expanded=True):
                    if strong_m:
                        st.markdown(t("cv_strong_subhead"))
                        for sm in strong_m:
                            n_sk = sm.get("skill", "")
                            p_sk = sm.get("proficiency", "Intermediate")
                            r_sk = sm.get("reason", "")
                            r_str = f" — _{r_sk}_" if r_sk else ""
                            st.markdown(f"✅ **{n_sk}** `{p_sk}`{r_str}")

                    if partial_m:
                        st.markdown(t("cv_partial_subhead"))
                        for pm in partial_m:
                            n_sk = pm.get("skill", "")
                            p_sk = pm.get("proficiency", "Beginner")
                            r_sk = pm.get("reason", "")
                            r_str = f" — _{r_sk}_" if r_sk else ""
                            st.markdown(f"⚠️ **{n_sk}** `{p_sk}`{r_str}")

                    if not strong_m and not partial_m:
                        st.info(t("cv_no_matches_found"))

                # Requisitos Faltantes con sugerencia gratuita de cursos (skill_resources.py)
                with st.expander(f"❌ {t('cv_col_gaps_title')} ({len(missing_m)})", expanded=True):
                    if missing_m:
                        from skill_resources import recommend_resource, recommend_from_ms_learn_catalog
                        ms_keywords = [
                            "azure", "microsoft", ".net", "c#", "c sharp", "powershell",
                            "windows server", "active directory", "sql server", "power bi",
                            "office 365", "m365", "sharepoint"
                        ]
                        for ms in missing_m:
                            nom = ms.get("skill", "")
                            imp = ms.get("importance", "Required").strip("[]")
                            raz = ms.get("reason", "").strip()
                            if raz and not raz.endswith((".", "!", "?")):
                                raz += "."
                            raz_str = f" — _{raz}_" if raz else ""

                            res = ms.get("resource")
                            if not res:
                                if any(k in nom.lower() for k in ms_keywords):
                                    res = recommend_from_ms_learn_catalog(nom)
                                if not res:
                                    res = recommend_resource(nom, ms.get("category", "CI/CD & DevOps"))

                            p_title = res.get("title") or res.get("name") or res.get("platform", "Plataforma de estudio")
                            p_url = res.get("url", "#")
                            st.markdown(f"❌ **{nom}** `[{imp}]`{raz_str}\n\n&nbsp;&nbsp;&nbsp;&nbsp;{t('cv_learn_free_at')} [{p_title}]({p_url})")
                    else:
                        st.success(t("cv_no_gaps_success"))

        with tab_preview:
            st.markdown(f"### {t('cv_preview_col_title')}")

            # ------------------------------------------------------------------
            # FASE 5.6c: PANEL DE CONFIGURACIÓN Y EXPORTACIÓN A PDF ATS-FRIENDLY
            # ------------------------------------------------------------------
            with st.container(border=True):
                st.markdown(f"#### {t('cv_pdf_export_title')}")

                col_sel_tmpl, col_color = st.columns([3, 2])
                with col_sel_tmpl:
                    template_opciones = {
                        "moderno": t("cv_template_moderno"),
                        "ejecutivo": t("cv_template_ejecutivo")
                    }
                    tmpl_choice = st.selectbox(
                        t("cv_template_selector_label"),
                        options=list(template_opciones.keys()),
                        format_func=lambda k: template_opciones[k],
                        key="sb_cv_template_choice"
                    )
                with col_color:
                    color_acento = st.color_picker(
                        t("cv_color_picker_label"),
                        value="#1B365D",
                        key="cp_cv_accent_color"
                    )

                btn_generate_pdf = st.button(
                    t("cv_btn_generate_pdf"),
                    type="primary",
                    use_container_width=True,
                    key="btn_trigger_generate_pdf"
                )

                if btn_generate_pdf:
                    with st.spinner(t("cv_pdf_generating_spinner")):
                        p_usuario = get_user_profile()
                        u_skills = get_all_user_skills()
                        r_bullets = get_all_resume_bullets()
                        lang_act = get_current_language()

                        pdf_bytes, txt_verif, err_gen = generate_resume_pdf(
                            template_name=tmpl_choice,
                            accent_color=color_acento,
                            user_profile=p_usuario,
                            user_skills=u_skills,
                            resume_bullets=r_bullets,
                            language=lang_act
                        )

                        if err_gen:
                            st.error(t("cv_pdf_err_generation", error=err_gen))
                        elif not txt_verif or len(txt_verif.strip()) < 50:
                            st.warning(t("cv_pdf_err_unreadable"))
                        else:
                            st.session_state["generated_cv_pdf"] = pdf_bytes
                            st.session_state["generated_cv_chars"] = len(txt_verif)
                            st.session_state["generated_cv_tmpl"] = tmpl_choice
                            st.rerun()

                if "generated_cv_pdf" in st.session_state:
                    st.success(t("cv_pdf_verified_success", chars=st.session_state.get("generated_cv_chars", 0)))
                    p_info = get_user_profile() or {}
                    nombre_descarga = p_info.get("full_name") or "Curriculum"
                    nombre_limpio = re.sub(r'[^a-zA-Z0-9_-]', '_', nombre_descarga).strip('_')
                    file_pdf_name = f"CV_{nombre_limpio}_{st.session_state.get('generated_cv_tmpl', 'ats')}.pdf"

                    st.download_button(
                        label=t("cv_btn_download_pdf"),
                        data=st.session_state["generated_cv_pdf"],
                        file_name=file_pdf_name,
                        mime="application/pdf",
                        use_container_width=True,
                        key="btn_download_resume_pdf"
                    )

            st.markdown(f"##### {t('cv_preview_live_summary')}")
            with st.container(border=True):
                perfil_usuario = get_user_profile()
                if perfil_usuario:
                    st.markdown(f"### **{perfil_usuario.get('full_name') or 'Candidato'}**")
                    sub_meta = [p for p in [perfil_usuario.get('current_title'), perfil_usuario.get('location')] if p]
                    if sub_meta:
                        st.markdown(f"*{' | '.join(sub_meta)}*")
                    contactos = [
                        f"📧 {perfil_usuario.get('email')}" if perfil_usuario.get('email') else "",
                        f"📱 {perfil_usuario.get('phone')}" if perfil_usuario.get('phone') else ""
                    ]
                    linea_contacto = " &nbsp;|&nbsp; ".join([c for c in contactos if c])
                    if linea_contacto:
                        st.caption(linea_contacto)
                    if perfil_usuario.get('summary'):
                        st.markdown(f"> *{perfil_usuario['summary']}*")
                    st.divider()

                st.markdown("#### **Experiencia Profesional**")
                if not experiences:
                    st.caption(t("no_data"))
                else:
                    for exp in experiences:
                        exp_id = exp["id"]
                        exp_bullets = bullets_by_exp.get(exp_id, [])
                        dates_badge = f"{exp['start_date'] or ''} — {'Presente' if exp['is_current'] else (exp['end_date'] or '')}"
                        st.markdown(f"**{exp['position']}** — {exp['company']} *({dates_badge})*")
                        for b_item in exp_bullets:
                            st.markdown(f"- {b_item['current_text']}")
                        st.write("")

                if education:
                    st.markdown("#### **Educación y Certificaciones**")
                    for edu in education:
                        ed_f = f"({edu['start_date'] or ''} — {edu['end_date'] or ''})" if edu.get("start_date") or edu.get("end_date") else ""
                        st.markdown(f"**{edu['credential']}** — {edu['institution']} *{ed_f}*")
