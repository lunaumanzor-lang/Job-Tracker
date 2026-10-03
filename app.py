# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 3: Application Tracker con Streamlit (app.py)
# ==============================================================================

import os
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
    get_skills_by_application
)

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
    generar_sugerencia_curso
)

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Job Application Tracker",
    page_icon="💼",
    layout="wide"  # 'wide' aprovecha mejor el ancho de la pantalla para tablas y formularios
)

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
    st.markdown(f"👤 **Usuario activo:** `{st.session_state.user.email}`")
with col_usr2:
    if st.button("🔑 Cambiar Contraseña", use_container_width=True):
        st.session_state.is_resetting_password = True
        st.rerun()
with col_usr3:
    if st.button("Cerrar Sesión", use_container_width=True):
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
st.caption("Fase 5.1: My Profile (Master Skill Profile) & Application Tracker")

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
# MENÚ DE NAVEGACIÓN LATERAL (Sidebar)
# ------------------------------------------------------------------------------
st.sidebar.title("🧭 Navegación")
st.sidebar.caption("Job Search & AI Intelligence")

menu_opcion = st.sidebar.radio(
    "Selecciona una sección:",
    [
        "📊 Dashboard",
        "📈 Statistics",
        "👤 My Profile",
        "🤖 AI Job Analyzer",
        "📋 Ver y Gestionar Aplicaciones",
        "➕ Agregar Nueva Aplicación"
    ],
    index=0
)


# ==============================================================================
# PÁGINA 0: DASHBOARD (Vista Rápida: Conteos Clave y Pipeline)
# ==============================================================================
if menu_opcion == "📊 Dashboard":
    st.subheader("📈 Resumen General de Postulaciones")
    st.caption("Vista rápida de métricas clave calculadas en tiempo real directamente desde Supabase.")

    try:
        # 1. Extraemos los datos de la nube (Supabase ya filtra por user_id automáticamente gracias al RLS)
        response = supabase.table("applications").select("*").execute()
        datos_dashboard = response.data
    except Exception as e:
        if "JWT expired" in str(e):
            st.warning("⏱️ Tu sesión ha expirado por seguridad. Por favor, haz clic en 'Cerrar Sesión' y vuelve a ingresar.")
            datos_dashboard = []
        else:
            st.error(f"Error al cargar datos del Dashboard: {e}")
            datos_dashboard = []

    if not datos_dashboard:
        st.info("No hay datos suficientes para mostrar estadísticas.")
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
                label="Total Applications",
                value=total_apps
            )

        with col_m2:
            st.metric(
                label="Interviews 🎯",
                value=entrevistas,
                help="Regla de negocio: incluye Recruiter Screen, Technical Interview y Final Interview"
            )

        with col_m3:
            st.metric(
                label="Offers 🎉",
                value=ofertas
            )

        with col_m4:
            st.metric(
                label="Rejections ❌",
                value=rechazos
            )

        with col_m5:
            st.metric(
                label="Follow-ups ⏰",
                value=follow_ups,
                help="Aplicaciones con fecha de seguimiento registrada próxima o vencida"
            )

        st.divider()

        # --------------------------------------------------------------------------
        # DESGLOSE COMPLETO POR ESTADO (Status Breakdown)
        # --------------------------------------------------------------------------
        st.markdown("### 📌 Estado del Pipeline (Status Breakdown)")
        st.caption("Cantidad exacta de postulaciones en cada etapa de tu proceso de búsqueda de empleo:")

        conteo_estados = df["status"].value_counts().to_dict()
        desglose_status = {opt: conteo_estados.get(opt, 0) for opt in STATUS_OPTIONS}

        # Fila 1: Etapas activas
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("📨 Applied", desglose_status.get("Applied", 0))
        with c2:
            st.metric("📞 Recruiter Screen", desglose_status.get("Recruiter Screen", 0))
        with c3:
            st.metric("💻 Technical Interview", desglose_status.get("Technical Interview", 0))
        with c4:
            st.metric("🤝 Final Interview", desglose_status.get("Final Interview", 0))

        # Fila 2: Resultados finales
        c5, c6, c7, _ = st.columns(4)
        with c5:
            st.metric("🎉 Offer", desglose_status.get("Offer", 0))
        with c6:
            st.metric("❌ Rejected", desglose_status.get("Rejected", 0))
        with c7:
            st.metric("👻 Ghosted", desglose_status.get("Ghosted", 0))

        # Gráfico interactivo de barras para ver la distribución visual
        st.markdown("#### 📊 Distribución Visual por Estado")
        df_status = pd.DataFrame(
            list(desglose_status.items()),
            columns=["Estado", "Cantidad"]
        ).set_index("Estado")
        st.bar_chart(df_status)

        st.divider()

        # Explicación técnica
        with st.expander("ℹ️ ¿Cómo se procesan estas estadísticas? (Conceptos Técnicos)"):
            st.markdown("""
            * **Extracción en Tiempo Real:** Los datos se leen directamente desde Supabase en la nube filtrados de forma segura por usuario gracias a **Row Level Security (RLS)**.
            * **Agregaciones con Pandas:** Las métricas, conteos y porcentajes son procesados dinámicamente en memoria mediante Pandas y visualizados con Streamlit.
            """)


# ==============================================================================
# PÁGINA 1: STATISTICS (Fase 7: Página Dedicada de Estadísticas Avanzadas)
# ==============================================================================
elif menu_opcion == "📈 Statistics":
    st.header("📈 Job Search Statistics")
    st.caption("Página dedicada a estadísticas completas, tasas de conversión, métricas salariales y tendencias temporales.")

    # 1. Reutilización de métricas de la Fase 4 (sin duplicar queries)
    metricas = get_dashboard_counts()
    total_apps = metricas["total_applications"]
    interviews = metricas["interviews"]
    offers = metricas["offers"]
    rejections = metricas["rejections"]

    # Cálculo de Interview Rate
    # Regla de negocio: (Interviews / Total Applications) * 100
    interview_rate = (interviews / total_apps * 100) if total_apps > 0 else 0.0

    st.subheader("🎯 Métricas Principales del Proceso")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Applications", total_apps)
    with c2:
        st.metric("Interviews 🎯", interviews, help="Incluye Recruiter Screen, Technical Interview y Final Interview")
    with c3:
        st.metric("Offers 🎉", offers)
    with c4:
        st.metric("Rejected ❌", rejections)
    with c5:
        st.metric("Interview Rate 🚀", f"{interview_rate:.1f}%", help="% de aplicaciones que lograron pasar al menos a entrevista")

    st.divider()

    # 2. Modalidades de Trabajo (Work Mode Breakdown)
    st.subheader("🏢 Distribución por Modalidad de Trabajo")
    work_modes = get_work_mode_breakdown()

    col_wm1, col_wm2, col_wm3 = st.columns(3)
    with col_wm1:
        st.metric("Remote Applications 🏠", work_modes.get("Remote", 0))
    with col_wm2:
        st.metric("Hybrid Applications 🏢/🏠", work_modes.get("Hybrid", 0))
    with col_wm3:
        st.metric("On-site Applications 🏢", work_modes.get("On-site", 0))

    # Gráfico de barras de modalidades
    df_wm = pd.DataFrame(
        list(work_modes.items()),
        columns=["Modalidad", "Total"]
    ).set_index("Modalidad")
    st.bar_chart(df_wm)

    st.divider()

    # 3. Estadísticas Salariales (USD)
    st.subheader("💰 Estadísticas Salariales (USD)")
    st.caption("Métricas calculadas exclusivamente sobre vacantes con compensación en USD (se ignoran valores vacíos, rangos cualitativos o monedas locales como CRC).")
    
    salarios = get_salary_statistics()
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        st.metric("Salario Mínimo", f"${salarios['min']:,.2f} USD")
    with s_col2:
        st.metric("Salario Promedio", f"${salarios['avg']:,.2f} USD")
    with s_col3:
        st.metric("Salario Máximo", f"${salarios['max']:,.2f} USD")
    with s_col4:
        st.metric("Postulaciones con Salario", f"{salarios['count']} de {total_apps}")

    st.divider()

    # 4. Análisis Temporal Mes a Mes (Aplicaciones y Entrevistas por Mes)
    st.subheader("📅 Evolución Mensual: Postulaciones y Entrevistas")
    st.caption("Visualiza el volumen de postulaciones enviadas y entrevistas generadas a lo largo del tiempo.")

    monthly_apps = get_monthly_applications()
    monthly_ints = get_monthly_interviews()

    df_apps = pd.DataFrame(monthly_apps).rename(columns={"total": "Postulaciones"}) if monthly_apps else pd.DataFrame(columns=["mes", "Postulaciones"])
    df_ints = pd.DataFrame(monthly_ints).rename(columns={"total": "Entrevistas"}) if monthly_ints else pd.DataFrame(columns=["mes", "Entrevistas"])

    if not df_apps.empty:
        # Combinamos ambas series temporales usando un merge de pandas sobre la columna 'mes'
        df_evolucion = pd.merge(df_apps, df_ints, on="mes", how="left").fillna(0)
        df_evolucion["Entrevistas"] = df_evolucion["Entrevistas"].astype(int)
        df_evolucion = df_evolucion.rename(columns={"mes": "Mes"})

        col_tabla_mes, col_grafico_mes = st.columns([1, 2], gap="medium")
        with col_tabla_mes:
            st.markdown("##### 📋 Tabla Detallada por Mes")
            st.dataframe(df_evolucion, use_container_width=True, hide_index=True)

        with col_grafico_mes:
            st.markdown("##### 📈 Gráfico de Tendencia Mensual")
            st.line_chart(df_evolucion.set_index("Mes"))
    else:
        st.info("No hay suficientes datos con fecha para graficar la evolución mensual.")


# ==============================================================================
# PÁGINA 2: MY PROFILE (Fase 5.1: Master Skill Profile)
# ==============================================================================
elif menu_opcion == "👤 My Profile":
    st.header("👤 Mi Perfil y Master Skill Profile")
    st.caption("Administra tu perfil profesional y tu inventario maestro de habilidades para comparar con futuras vacantes.")

    # --------------------------------------------------------------------------
    # 1. PERFIL GENERAL DEL USUARIO (user_profile)
    # --------------------------------------------------------------------------
    perfil = get_user_profile()
    with st.expander("📝 Datos Generales del Perfil", expanded=(perfil is not None)):
        if perfil:
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                st.markdown(f"**Nombre:** {perfil.get('full_name') or 'No especificado'}")
                st.markdown(f"**Título:** {perfil.get('current_title') or 'No especificado'}")
                st.markdown(f"**Ubicación:** {perfil.get('location') or 'No especificada'}")
            with p_col2:
                st.markdown(f"**Email:** {perfil.get('email') or 'No especificado'}")
                st.markdown(f"**Teléfono:** {perfil.get('phone') or 'No especificado'}")
                st.caption(f"Última actualización: {perfil.get('updated_at') or 'N/A'}")
            if perfil.get("summary"):
                st.info(f"**Resumen Profesional:**\n\n{perfil['summary']}")
        else:
            st.info("Aún no tienes un perfil guardado. Puedes subir tu currículum abajo para que la IA lo extraiga automáticamente, o ingresar tus datos manualmente.")

        with st.popover("✏️ Editar datos de perfil"):
            with st.form("form_editar_perfil"):
                ed_name = st.text_input("Nombre Completo", value=perfil.get("full_name") if perfil else "")
                ed_title = st.text_input("Título Profesional / Rol", value=perfil.get("current_title") if perfil else "")
                ed_email = st.text_input("Email", value=perfil.get("email") if perfil else "")
                ed_phone = st.text_input("Teléfono", value=perfil.get("phone") if perfil else "")
                ed_loc = st.text_input("Ubicación", value=perfil.get("location") if perfil else "")
                ed_sum = st.text_area("Resumen Profesional", value=perfil.get("summary") if perfil else "", height=100)
                if st.form_submit_button("Guardar Perfil"):
                    save_user_profile(ed_name, ed_title, ed_email, ed_phone, ed_loc, ed_sum)
                    st.success("¡Perfil actualizado con éxito!")
                    st.rerun()

    st.divider()

    # --------------------------------------------------------------------------
    # 2. SUBIDA DE RESUME Y EXTRACCIÓN AUTOMÁTICA CON IA
    # --------------------------------------------------------------------------
    st.subheader("📄 Subir Currículum y Extraer Skills con IA")
    st.caption("Sube tu CV en formato PDF, Word (.docx) o Texto (.txt) para que Gemini extraiga tus habilidades automáticamente.")

    archivo_subido = st.file_uploader(
        "Selecciona tu archivo de CV:",
        type=["pdf", "docx", "txt"],
        help="Formatos permitidos: .pdf (con pypdf), .docx (con python-docx), .txt"
    )

    if archivo_subido is not None:
        try:
            texto_cv = extract_resume_text(archivo_subido)
            st.success(f"✅ Archivo '{archivo_subido.name}' leído exitosamente ({len(texto_cv):,} caracteres extraídos).")
            with st.expander("👁️ Previsualizar texto extraído del documento"):
                st.text_area("Contenido extraído", value=texto_cv, height=200, disabled=True)

            # Verificación de API Key
            api_key_activa = get_api_key()
            if not api_key_activa:
                st.warning("⚠️ No se detectó GEMINI_API_KEY en el entorno ni en archivo .env.")
                key_input = st.text_input("Ingresa tu clave de API de Gemini para este análisis:", type="password")
                if key_input:
                    api_key_activa = key_input.strip()
                    os.environ["GEMINI_API_KEY"] = api_key_activa
                    # Guardamos automáticamente en .env para que persista
                    try:
                        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
                        with open(env_file, "w", encoding="utf-8") as f_env:
                            f_env.write(f"GEMINI_API_KEY={api_key_activa}\n")
                        st.info("💡 Tu clave ha sido guardada en .env para futuros análisis.")
                    except Exception:
                        pass

            col_btn, _ = st.columns([1, 2])
            with col_btn:
                btn_analizar = st.button("🚀 Analizar CV con IA (Gemini)", type="primary", disabled=not bool(api_key_activa))

            if btn_analizar:
                with st.spinner("🤖 La IA está leyendo tu currículum, identificando tus skills y clasificándolas en categorías estándar..."):
                    try:
                        resultado = extract_skills_and_profile_from_resume(texto_cv, api_key=api_key_activa)
                        
                        # Guardamos perfil detectado si no existe
                        prof_data = resultado.get("profile", {})
                        if prof_data:
                            save_user_profile(
                                full_name=prof_data.get("full_name"),
                                current_title=prof_data.get("current_title"),
                                email=prof_data.get("email"),
                                phone=prof_data.get("phone"),
                                location=prof_data.get("location"),
                                summary=prof_data.get("summary")
                            )

                        # Guardamos skills en bulk
                        skills_extraidas = resultado.get("skills", [])
                        total_insertadas = add_user_skills_bulk(skills_extraidas, source="Resume")
                        
                        st.success(f"🎉 ¡Análisis finalizado! Se extrajeron e indexaron {total_insertadas} habilidades técnicas en tu base de datos.")
                        st.rerun()
                    except Exception as err:
                        st.error(f"❌ Ocurrió un error al procesar con IA: {err}")
        except Exception as err_lectura:
            st.error(f"❌ Error al leer el archivo: {err_lectura}")

    st.divider()

    # --------------------------------------------------------------------------
    # 3. GESTIÓN MANUAL DE SKILLS (CRUD DE TAGS)
    # --------------------------------------------------------------------------
    st.subheader("🏷️ Master Skill Inventory (Inventario de Habilidades)")
    todas_las_skills = get_all_user_skills()

    total_s = len(todas_las_skills)
    resume_s = len([s for s in todas_las_skills if s.get("source") == "Resume"])
    manual_s = len([s for s in todas_las_skills if s.get("source") == "Manual"])

    col_ms1, col_ms2, col_ms3 = st.columns(3)
    with col_ms1:
        st.metric("Total de Skills Dominadas", total_s)
    with col_ms2:
        st.metric("Extraídas de CV 📄", resume_s)
    with col_ms3:
        st.metric("Agregadas Manualmente ✏️", manual_s)

    categorias_disponibles = get_all_distinct_categories()

    # Formulario para agregar una skill manualmente
    with st.expander("➕ Agregar una nueva tecnología / habilidad manualmente"):
        col_sk1, col_sk2, col_sk3 = st.columns([2, 1.4, 1])
        with col_sk1:
            input_skill = st.text_input("Nombre de la Tecnología / Skill *", placeholder="Ej. Terraform, Kubernetes, GraphQL...", key="input_skill_manual")
        with col_sk2:
            opciones_cat_form = ["➕ Nueva Categoría..."] + categorias_disponibles
            idx_cat_def = 1 if len(opciones_cat_form) > 1 else 0
            input_cat = st.selectbox("Categoría *", options=opciones_cat_form, index=idx_cat_def, key="input_cat_manual")
            nueva_cat_personalizada = None
            if input_cat == "➕ Nueva Categoría...":
                nueva_cat_personalizada = st.text_input("Nombre de la nueva categoría *", placeholder="Ej. AI & Machine Learning...", key="input_new_custom_cat")
        with col_sk3:
            input_prof = st.selectbox("Nivel de Dominio", options=PROFICIENCY_LEVELS, index=1, key="input_prof_manual")
        
        btn_guardar_skill = st.button("💾 Guardar Skill Manual", type="primary", use_container_width=True)

        if btn_guardar_skill:
            cat_final = nueva_cat_personalizada.strip() if (input_cat == "➕ Nueva Categoría..." and nueva_cat_personalizada) else input_cat
            if not input_skill.strip():
                st.error("El nombre de la habilidad no puede estar vacío.")
            elif input_cat == "➕ Nueva Categoría..." and not (nueva_cat_personalizada and nueva_cat_personalizada.strip()):
                st.error("Por favor escribe el nombre de la nueva categoría.")
            else:
                add_user_skill(
                    skill_name=input_skill.strip(),
                    category=cat_final,
                    source="Manual",
                    proficiency=input_prof
                )
                st.success(f"✅ ¡Habilidad '{input_skill.strip()}' guardada con éxito en '{cat_final}'!")
                st.rerun()

    # Despliegue de skills existentes
    if not todas_las_skills:
        st.info("Aún no tienes habilidades registradas. Sube tu currículum arriba o agrega tus tecnologías dominadas con el formulario.")
    else:
        st.markdown("##### 📌 Habilidades agrupadas por Categoría:")
        
        # Agrupamos por categoría
        skills_por_cat = {}
        for s in todas_las_skills:
            skills_por_cat.setdefault(s["category"], []).append(s)

        # Iteramos sobre las categorías que tienen al menos una skill
        for cat_nombre, items_cat in sorted(skills_por_cat.items()):
            with st.container():
                st.markdown(f"**{cat_nombre}** ({len(items_cat)} habilidades)")
                
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
                        opciones_fila = ["➕ Nueva Categoría..."] + categorias_disponibles
                        idx_cat = opciones_fila.index(cat_actual) if cat_actual in opciones_fila else 1
                        nueva_cat = st.selectbox(
                            "Categoría",
                            options=opciones_fila,
                            index=idx_cat,
                            key=f"cat_{item['id']}",
                            label_visibility="collapsed"
                        )
                        if nueva_cat == "➕ Nueva Categoría...":
                            col_nc1, col_nc2 = st.columns([3, 1])
                            with col_nc1:
                                txt_cat_fila = st.text_input(
                                    "Nueva cat",
                                    placeholder="Nombre categoría...",
                                    key=f"txt_nc_{item['id']}",
                                    label_visibility="collapsed"
                                )
                            with col_nc2:
                                if st.button("💾", key=f"btn_save_nc_{item['id']}", help="Guardar nueva categoría"):
                                    if txt_cat_fila.strip():
                                        update_user_skill_category(item["id"], txt_cat_fila.strip())
                                        st.rerun()
                                    else:
                                        st.warning("Escribe un nombre.")
                        elif nueva_cat != cat_actual:
                            update_user_skill_category(item["id"], nueva_cat)
                            st.rerun()
                    
                    with c_prof:
                        # Dropdown para cambiar el nivel de proficiency
                        prof_actual = item.get("proficiency", "Intermediate")
                        idx_prof = PROFICIENCY_LEVELS.index(prof_actual) if prof_actual in PROFICIENCY_LEVELS else 1
                        nuevo_nivel = st.selectbox(
                            "Nivel",
                            options=PROFICIENCY_LEVELS,
                            index=idx_prof,
                            key=f"prof_{item['id']}",
                            label_visibility="collapsed"
                        )
                        if nuevo_nivel != prof_actual:
                            update_user_skill_proficiency(item["id"], nuevo_nivel)
                            st.rerun()

                    with c_del:
                        if st.button("🗑️", key=f"del_sk_{item['id']}", help=f"Eliminar {item['skill_name']}"):
                            delete_user_skill(item["id"])
                            st.rerun()

                st.divider()


# ==============================================================================
# PÁGINA 2.5: AI JOB ANALYZER & MATCH EVALUATOR (Fase 5.2)
# ==============================================================================
elif menu_opcion == "🤖 AI Job Analyzer":
    st.subheader("🤖 AI Job Analyzer & Match Evaluator")
    st.caption(
        "Evalúa cualquier vacante laboral asistido por IA, compara sus requerimientos en tiempo real "
        "contra tu Master Skill Profile y precarga la postulación en tu Tracker con un solo clic."
    )

    # 1. Verificación del perfil y habilidades registradas en SQLite
    user_skills = get_all_user_skills()
    if not user_skills:
        st.warning(
            "⚠️ Tu Master Skill Profile no contiene habilidades registradas aún. "
            "Para obtener un análisis comparativo preciso, te recomendamos ir primero a la sección "
            "**'👤 My Profile'** y subir tu currículum o ingresar tus habilidades clave."
        )
    else:
        st.info(f"💡 Comparando vacantes contra tu perfil activo de **{len(user_skills)} habilidades** registradas.")

    # 2. Verificación de API Key
    api_key_env = get_api_key()
    api_key_usuario = None
    if not api_key_env:
        with st.expander("🔑 Configuración de API Key de Gemini", expanded=True):
            api_key_usuario = st.text_input(
                "Ingresa tu clave de API de Gemini:",
                type="password",
                help="Obtén tu clave gratuita en https://aistudio.google.com/app/apikey"
            )

    # 3. Ingreso de Datos (Selección desde aplicaciones existentes o manual)
    st.markdown("### 📥 1. Ingreso de la Vacante")

    # Obtenemos aplicaciones para el dropdown (de Supabase con fallback a SQLite)
    try:
        resp_apps = supabase.table("applications").select("id, company, position, job_url, notes").order("id", desc=False).execute()
        apps_para_dropdown = resp_apps.data or []
    except Exception:
        apps_para_dropdown = get_all_applications()

    metodo_origen = st.radio(
        "¿Cómo deseas cargar la vacante?",
        options=[
            "📋 Seleccionar de aplicaciones existentes",
            "✏️ Ingresar enlace web (URL) manualmente"
        ],
        horizontal=True,
        key="metodo_origen_analyzer"
    )

    url_para_analizar = st.session_state.get("job_url_input", "")

    if metodo_origen == "📋 Seleccionar de aplicaciones existentes":
        if not apps_para_dropdown:
            st.info("ℹ️ No hay aplicaciones registradas todavía. Puedes ingresar una URL o texto manualmente.")
        else:
            # Mapeo de aplicaciones para el dropdown
            mapa_apps = {}
            for a in apps_para_dropdown:
                url_ind = "🔗 Con enlace" if a.get("job_url") else "📄 Sin enlace"
                etiqueta = f"#{a['id']} - {a.get('company', 'Empresa')} | {a.get('position', 'Puesto')} ({url_ind})"
                mapa_apps[etiqueta] = a

            opciones_apps = ["-- Selecciona una aplicación registrada --"] + list(mapa_apps.keys())
            
            idx_app_sel = 0
            if "last_selected_analyzer_app" in st.session_state and st.session_state["last_selected_analyzer_app"] in opciones_apps:
                idx_app_sel = opciones_apps.index(st.session_state["last_selected_analyzer_app"])

            seleccion_app = st.selectbox(
                "Selecciona una postulación para obtener su vacante:",
                options=opciones_apps,
                index=idx_app_sel,
                key="select_app_dropdown_analyzer"
            )

            if seleccion_app != "-- Selecciona una aplicación registrada --":
                st.session_state["last_selected_analyzer_app"] = seleccion_app
                app_obj = mapa_apps[seleccion_app]
                app_url = (app_obj.get("job_url") or "").strip()
                url_para_analizar = app_url
                st.session_state["job_url_input"] = app_url

                col_det1, col_det2 = st.columns([3.5, 1.5])
                with col_det1:
                    st.text_input("Enlace web asociado:", value=app_url or "Sin URL registrada", disabled=True, key="disp_app_url_field")
                with col_det2:
                    st.write("")
                    if app_url:
                        st.markdown(f"<div style='margin-top: 15px;'><a href='{app_url}' target='_blank' rel='noopener noreferrer'>🌐 Abrir enlace</a></div>", unsafe_allow_html=True)
                    else:
                        st.caption("ℹ️ Sin URL guardada")

                # Botones para jalar la información
                col_btn_j1, col_btn_j2 = st.columns(2)
                with col_btn_j1:
                    if app_url:
                        if st.button("🌐 Extraer texto desde la URL", use_container_width=True, key="btn_ext_url_app"):
                            with st.spinner("Descargando y extrayendo contenido de la página web..."):
                                exito_scrap, resultado_scrap = extract_job_text_from_url(app_url)
                                if exito_scrap:
                                    st.session_state["input_job_text_area"] = resultado_scrap
                                    st.session_state["job_text_input"] = resultado_scrap
                                    st.session_state["job_url_input"] = app_url
                                    st.success("✅ ¡Texto de la vacante extraído exitosamente desde la URL!")
                                    st.rerun()
                                else:
                                    st.warning(f"⚠️ {resultado_scrap}")
                                    if app_obj.get("notes"):
                                        st.info("💡 Consejo: Esta postulación tiene notas guardadas. Puedes cargarlas con el botón contiguo.")
                    else:
                        st.button("🌐 Extraer texto desde la URL", disabled=True, use_container_width=True, key="btn_ext_url_dis", help="Esta postulación no tiene URL guardada")

                with col_btn_j2:
                    if app_obj.get("notes"):
                        if st.button("📝 Cargar notas/descripción guardada", use_container_width=True, key="btn_load_notes_app"):
                            st.session_state["input_job_text_area"] = app_obj["notes"]
                            st.session_state["job_text_input"] = app_obj["notes"]
                            st.session_state["job_url_input"] = app_url
                            st.success("✅ ¡Notas de la aplicación cargadas en el área de texto!")
                            st.rerun()
                    else:
                        st.button("📝 Cargar notas/descripción guardada", disabled=True, use_container_width=True, key="btn_load_notes_dis", help="Esta postulación no tiene notas guardadas")

    else:
        # Modo manual
        col_url_m1, col_url_m2 = st.columns([3.5, 1.5])
        with col_url_m1:
            url_manual = st.text_input(
                "Enlace web de la vacante (URL):",
                value=st.session_state.get("job_url_input", ""),
                placeholder="https://www.linkedin.com/jobs/view/... o portal de empleo",
                key="input_url_manual_field"
            )
            url_para_analizar = url_manual.strip()
            st.session_state["job_url_input"] = url_para_analizar
        with col_url_m2:
            st.write("")
            btn_extraer_manual = st.button("🌐 Extraer de URL", use_container_width=True, key="btn_ext_manual")

        if btn_extraer_manual:
            if not url_manual.strip():
                st.warning("⚠️ Por favor ingresa una URL válida antes de extraer.")
            else:
                with st.spinner("Descargando y extrayendo contenido de la vacante..."):
                    exito_sc, texto_sc = extract_job_text_from_url(url_manual.strip())
                    if exito_sc:
                        st.session_state["input_job_text_area"] = texto_sc
                        st.session_state["job_text_input"] = texto_sc
                        st.session_state["job_url_input"] = url_manual.strip()
                        st.success("✅ ¡Texto extraído exitosamente de la URL!")
                        st.rerun()
                    else:
                        st.warning(f"⚠️ {texto_sc}")

    # Área de texto para pegar o editar el Job Description
    job_text_val = st.text_area(
        "Texto de la Descripción de la Vacante (Job Description): *",
        value=st.session_state.get("job_text_input", ""),
        height=220,
        placeholder="Pega aquí el texto completo de la vacante (título, responsabilidades, requisitos técnicos, etc.) o extráelo usando los botones superiores...",
        key="input_job_text_area"
    )

    # Botones de acción
    col_act1, col_act2 = st.columns([3, 1])
    with col_act1:
        btn_analizar_vacante = st.button("⚡ Analizar y Evaluar Match con IA", type="primary", use_container_width=True)
    with col_act2:
        if st.button("🧹 Limpiar Análisis", use_container_width=True):
            st.session_state.pop("job_analysis_result", None)
            st.session_state.pop("job_text_input", None)
            st.session_state.pop("input_job_text_area", None)
            st.session_state.pop("job_url_input", None)
            st.session_state.pop("last_selected_analyzer_app", None)
            st.rerun()

    # Ejecución del análisis al presionar el botón
    if btn_analizar_vacante:
        if not job_text_val.strip():
            st.error("⚠️ Por favor pega el texto de la vacante o extrae una URL antes de analizar.")
        else:
            api_key_activa = api_key_usuario or api_key_env
            if not api_key_activa:
                st.error("⚠️ Debes proporcionar tu clave de API de Gemini para realizar el análisis.")
            else:
                with st.spinner("🧠 Analizando vacante y comparando contra tu Master Skill Profile con Gemini..."):
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
                        st.success("🎉 ¡Análisis y cálculo de match completados exitosamente!")
                        st.rerun()
                    except Exception as err:
                        st.error(f"❌ Error durante el análisis: {err}")

    # 4. Visualización del Match y Resultados
    if "job_analysis_result" in st.session_state:
        analisis = st.session_state["job_analysis_result"]
        job_info = analisis.get("job_info", {})
        matching = analisis.get("skill_matching", {})

        strong_matches = matching.get("strong_matches", [])
        partial_matches = matching.get("partial_matches", [])
        missing_skills = matching.get("missing_skills", [])

        st.divider()
        st.markdown("### 📊 2. Evaluación de Compatibilidad (Match Score)")

        total_requisitos = len(strong_matches) + len(partial_matches) + len(missing_skills)
        if total_requisitos > 0:
            score_calculado = round(((len(strong_matches) + 0.5 * len(partial_matches)) / total_requisitos) * 100)
        else:
            score_calculado = 0

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric("🎯 Match Score Estimado", f"{score_calculado}%")
        with m_col2:
            st.metric("🟢 Strong Matches", f"{len(strong_matches)} skills")
        with m_col3:
            st.metric("🟡 Partial Matches", f"{len(partial_matches)} skills")
        with m_col4:
            st.metric("🔴 Missing Skills", f"{len(missing_skills)} brechas")

        # Visualización en 2 Columnas: Fortalezas (Izquierda) vs Brechas (Derecha)
        col_match_left, col_match_right = st.columns(2)

        with col_match_left:
            st.markdown("#### 🟢 Habilidades que Posees (Matches)")
            
            if strong_matches:
                st.markdown("**Fortalezas Principales (Intermediate / Advanced):**")
                for s in strong_matches:
                    nombre = s.get("skill", "")
                    prof = s.get("proficiency", "Intermediate")
                    razon = s.get("reason", "")
                    razon_str = f" — _{razon}_" if razon else ""
                    st.markdown(f"✅ **{nombre}** `{prof}`{razon_str}")
            
            if partial_matches:
                st.markdown("**Coincidencias en Desarrollo (Beginner):**")
                for s in partial_matches:
                    nombre = s.get("skill", "")
                    prof = s.get("proficiency", "Beginner")
                    razon = s.get("reason", "")
                    razon_str = f" — _{razon}_" if razon else ""
                    st.markdown(f"⚠️ **{nombre}** `{prof}`{razon_str}")

            if not strong_matches and not partial_matches:
                st.info("No se encontraron coincidencias directas con tus habilidades registradas.")

        with col_match_right:
            st.markdown("#### 🔴 Requerimientos Faltantes (Gaps)")
            if missing_skills:
                for s in missing_skills:
                    nombre = s.get("skill", "")
                    importancia = s.get("importance", "Required").strip("[]")
                    razon = s.get("reason", "").strip()
                    if razon and not razon.endswith((".", "!", "?")):
                        razon += "."
                    razon_str = f" — _{razon}_" if razon else ""

                    texto_curso, url_curso = generar_sugerencia_curso(
                        skill=nombre,
                        position=job_info.get("position", ""),
                        reason=razon
                    )
                    st.markdown(f"❌ **{nombre}** `[{importancia}]`{razon_str} 💡 Sugerencia: [{texto_curso}]({url_curso})")
            else:
                st.success("🎉 ¡Excelente! No se detectaron tecnologías o requisitos faltantes para esta vacante.")

        # 5. Formulario Autocompletado para Guardar la Aplicación
        st.divider()
        st.markdown("### 📝 3. Pre-registro en Aplicaciones")
        st.caption(
            "Revisa y modifica los campos extraídos por la IA antes de guardarlos en tu base de datos SQLite."
        )

        with st.form("form_ai_guardar_aplicacion"):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                company_val = st.text_input("Company *", value=job_info.get("company", ""))
            with f_col2:
                position_val = st.text_input("Position *", value=job_info.get("position", ""))

            f_col3, f_col4 = st.columns(2)
            with f_col3:
                status_default_idx = STATUS_OPTIONS.index("Applied") if "Applied" in STATUS_OPTIONS else 0
                status_val = st.selectbox("Status", options=STATUS_OPTIONS, index=status_default_idx)
            with f_col4:
                app_date_val = st.date_input("Application Date", value=date.today())

            f_col5, f_col6 = st.columns(2)
            with f_col5:
                wm_detectado = job_info.get("work_mode", "Remote")
                wm_idx = WORK_MODE_OPTIONS.index(wm_detectado) if wm_detectado in WORK_MODE_OPTIONS else 0
                work_mode_val = st.selectbox("Work Mode", options=WORK_MODE_OPTIONS, index=wm_idx)
            with f_col6:
                salary_val = st.text_input("Salary (USD)", value=job_info.get("salary", ""))

            f_col7, f_col8 = st.columns(2)
            with f_col7:
                url_guardar_val = st.text_input("Job URL", value=st.session_state.get("job_url_input", ""))
            with f_col8:
                location_val = st.text_input("Location", value=job_info.get("location", ""))

            fortalezas_txt = ", ".join(s.get("skill", "") for s in strong_matches[:5])
            faltantes_txt = ", ".join(s.get("skill", "") for s in missing_skills[:5])
            notas_generadas = (
                f"Analizado con AI Job Analyzer.\n"
                f"Match Score: {score_calculado}%\n"
                f"Fortalezas: {fortalezas_txt or 'N/A'}\n"
                f"Faltantes: {faltantes_txt or 'N/A'}"
            )
            notes_val = st.text_area("Notes", value=notas_generadas, height=100)

            btn_guardar_app = st.form_submit_button("💾 GUARDAR POSTULACIÓN EN TRACKER", use_container_width=True)

        if btn_guardar_app:
            if not company_val.strip():
                st.error("⚠️ El campo Company es obligatorio.")
            elif not position_val.strip():
                st.error("⚠️ El campo Position es obligatorio.")
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
                    st.caption(f"💾 Se vincularon **{total_guardadas} habilidades** evaluadas a esta postulación.")

                st.success(f"🎉 ¡Aplicación a **{company_val}** (#{nuevo_id}) guardada exitosamente en la nube y en tu base de datos!")
                st.balloons()


# ==============================================================================
# PÁGINA 3: VER, BUSCAR, FILTRAR, EDITAR Y ELIMINAR APLICACIONES
# ==============================================================================
elif menu_opcion == "📋 Ver y Gestionar Aplicaciones":

    # 1. Obtenemos todas las aplicaciones desde Supabase
    try:
        # Supabase devuelve los datos directamente como una lista de diccionarios
        response = supabase.table("applications").select("*").order("id", desc=True).execute()
        todas_las_apps = response.data
    except Exception as e:
        if "JWT expired" in str(e):
            st.warning("⏱️ Tu sesión ha expirado por seguridad. Por favor, haz clic en 'Cerrar Sesión' y vuelve a ingresar.")
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
        st.subheader("🔍 Buscar y Filtrar")
        col_busq, col_f_status, col_f_mode = st.columns([2, 1, 1])

        with col_busq:
            busqueda = st.text_input("Buscar por Empresa o Puesto:", placeholder="Ej. Citi, DevOps, AWS...")

        with col_f_status:
            filtro_status = st.selectbox("Filtrar por Status:", options=["Todos"] + STATUS_OPTIONS)

        with col_f_mode:
            filtro_mode = st.selectbox("Filtrar por Modalidad:", options=["Todos"] + WORK_MODE_OPTIONS)

        # Aplicamos los filtros al DataFrame en memoria
        df_filtrado = df.copy()

        # Filtro de texto (búsqueda insensible a mayúsculas/minúsculas)
        if busqueda.strip():
            patron = busqueda.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado["company"].str.lower().str.contains(patron, na=False) |
                df_filtrado["position"].str.lower().str.contains(patron, na=False)
            ]

        # Filtro por Status
        if filtro_status != "Todos":
            df_filtrado = df_filtrado[df_filtrado["status"] == filtro_status]

        # Filtro por Work Mode
        if filtro_mode != "Todos":
            df_filtrado = df_filtrado[df_filtrado["work_mode"] == filtro_mode]

        # Mostramos contador de resultados
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
        st.subheader("⚙️ Gestionar una Aplicación (Editar / Detalles / Eliminar)")

        # Creamos una lista de opciones claras para el selectbox: "[ID] Empresa - Puesto"
        opciones_apps = {
            f"#{row['id']:02d} | {row['company']} — {row['position']} ({row['status']})": row['id']
            for _, row in df_filtrado.iterrows()
        }

        if not opciones_apps:
            st.warning("No hay aplicaciones que coincidan con los filtros seleccionados.")
        else:
            col_sel, _ = st.columns([2, 1])
            with col_sel:
                seleccion_texto = st.selectbox(
                    "Selecciona una aplicación de la lista para verla o modificarla:",
                    options=list(opciones_apps.keys())
                )

            app_id_seleccionado = opciones_apps[seleccion_texto]
            app_actual = get_application_by_id(app_id_seleccionado)

            if app_actual:
                # Mostramos los detalles y el formulario de edición
                col_detalle, col_edicion = st.columns([1, 1], gap="large")

                # PANEL IZQUIERDO: DETALLE COMPLETO (Requisito 3)
                with col_detalle:
                    st.markdown("### 📄 Detalles de la Postulación")
                    st.info(f"**Empresa:** {app_actual['company']}\n\n"
                            f"**Puesto:** {app_actual['position']}\n\n"
                            f"**Estado actual:** `{app_actual['status']}`\n\n"
                            f"**Modalidad:** {app_actual['work_mode'] or 'No especificada'}\n\n"
                            f"**Salario registrado:** {app_actual['salary'] or 'No especificado'}\n\n"
                            f"**Fecha de postulación:** {app_actual['application_date'] or 'Sin fecha'}\n\n"
                            f"**Fecha de Follow-up:** {app_actual.get('follow_up_date') or '⏰ No asignada'}\n\n"
                            f"**Ubicación:** {app_actual['location'] or 'N/A'}")

                    if app_actual.get("job_url"):
                        st.markdown(f"🔗 [Abrir enlace de la vacante]({app_actual['job_url']})")

                    if app_actual.get("notes"):
                        with st.expander("📝 Ver Notas / Descripción completa"):
                            st.write(app_actual["notes"])

                    # ----------------------------------------------------------
                    # FASE 5.3: HABILIDADES ASOCIADAS Y BOTÓN INTERVIEW COACH
                    # ----------------------------------------------------------
                    st.markdown("---")
                    st.markdown("#### 🎯 Preparación de Entrevista")
                    skills_vacante = get_skills_by_application(app_actual["id"])
                    if skills_vacante:
                        s_str = [s["skill"] for s in skills_vacante if s["match_status"] == "strong"]
                        s_part = [s["skill"] for s in skills_vacante if s["match_status"] == "partial"]
                        s_miss = [s["skill"] for s in skills_vacante if s["match_status"] == "missing"]
                        if s_str:
                            st.caption("🟢 **Fortalezas:** " + ", ".join(f"`{x}`" for x in s_str))
                        if s_part:
                            st.caption("🟡 **Match Parcial:** " + ", ".join(f"`{x}`" for x in s_part))
                        if s_miss:
                            st.caption("🔴 **Brechas:** " + ", ".join(f"`{x}`" for x in s_miss))
                    else:
                        st.caption("ℹ️ Sin habilidades analizadas previamente. El Coach utilizará los datos del puesto y notas.")

                    if st.button("🎯 PREPARE ME FOR THIS JOB", key=f"btn_prep_{app_actual['id']}", type="primary", use_container_width=True):
                        st.session_state["show_interview_coach"] = True
                        st.session_state["coach_app_id"] = app_actual["id"]
                        st.rerun()

                    # SECCIÓN DE ELIMINACIÓN CON CONFIRMACIÓN (Requisito 5)
                    st.markdown("---")
                    st.markdown("#### 🗑️ Zona de peligro")
                    with st.expander("Eliminar esta postulación"):
                        st.warning(f"¿Estás seguro de que deseas eliminar permanentemente la postulación a **{app_actual['company']}**?")
                        confirmar_borrado = st.checkbox("Sí, confirmo que deseo eliminar este registro.", key=f"conf_del_{app_actual['id']}")
                        
                        if st.button("🚨 Eliminar Definitivamente", type="primary", disabled=not confirmar_borrado):
                            id_a_borrar = app_actual["id"]
                            with st.spinner(f"Eliminando postulación #{id_a_borrar} y reordenando las aplicaciones posteriores..."):
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
                                    st.error(f"Error al sincronizar con Supabase: {error_supabase}")
                                else:
                                    st.success(f"✅ Postulación #{id_a_borrar} eliminada con éxito y el orden de todas las aplicaciones posteriores fue reajustado automáticamente.")
                                    st.rerun()

                # PANEL DERECHO: FORMULARIO DE EDICIÓN (Requisito 4)
                with col_edicion:
                    st.markdown("### ✏️ Editar Datos")
                    st.caption("Modifica los campos necesarios (por ejemplo cambiar 'TBD' por la empresa real o agregar fecha de Follow-up).")

                    with st.form(f"form_editar_{app_actual['id']}"):
                        edit_company = st.text_input("Company *", value=app_actual["company"])
                        edit_position = st.text_input("Position *", value=app_actual["position"])

                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            fecha_default = date.today()
                            if app_actual.get("application_date"):
                                try:
                                    fecha_default = datetime.strptime(app_actual["application_date"][:10], "%Y-%m-%d").date()
                                except Exception:
                                    pass
                            edit_date = st.date_input("Application Date", value=fecha_default)

                        with col_e2:
                            idx_status = STATUS_OPTIONS.index(app_actual["status"]) if app_actual["status"] in STATUS_OPTIONS else 0
                            edit_status = st.selectbox("Status", options=STATUS_OPTIONS, index=idx_status)

                        col_e3, col_e4 = st.columns(2)
                        with col_e3:
                            mode_val = app_actual.get("work_mode") or "Remote"
                            idx_mode = WORK_MODE_OPTIONS.index(mode_val) if mode_val in WORK_MODE_OPTIONS else 0
                            edit_mode = st.selectbox("Work Mode", options=WORK_MODE_OPTIONS, index=idx_mode)
                        with col_e4:
                            edit_salary = st.text_input("Salary", value=app_actual.get("salary") or "")

                        col_e5, col_e6 = st.columns(2)
                        with col_e5:
                            edit_location = st.text_input("Location", value=app_actual.get("location") or "")
                        with col_e6:
                            # Campo de fecha de seguimiento (Follow-up)
                            fup_val = date.today()
                            if app_actual.get("follow_up_date"):
                                try:
                                    fup_val = datetime.strptime(app_actual["follow_up_date"][:10], "%Y-%m-%d").date()
                                except Exception:
                                    pass
                            asignar_fup = st.checkbox("Asignar Follow-up", value=bool(app_actual.get("follow_up_date")), key=f"chk_fup_{app_actual['id']}")
                            edit_fup = st.date_input("Fecha Follow-up", value=fup_val, key=f"date_fup_{app_actual['id']}") if asignar_fup else None

                        edit_job_url = st.text_input("Job URL", value=app_actual.get("job_url") or "")
                        edit_notes = st.text_area("Notes", value=app_actual.get("notes") or "", height=120)

                        btn_guardar_edicion = st.form_submit_button("💾 GUARDAR CAMBIOS", use_container_width=True)

                    if btn_guardar_edicion:
                        if not edit_company.strip() or not edit_position.strip():
                            st.error("Company y Position no pueden estar vacíos.")
                        else:
                            fecha_str = edit_date.strftime("%Y-%m-%d")
                            fup_str = edit_fup.strftime("%Y-%m-%d") if edit_fup else None
                            
                            # 1. Actualizamos en Supabase (en la nube)
                            try:
                                datos_actualizados = {
                                    "company": edit_company.strip(),
                                    "position": edit_position.strip(),
                                    "status": edit_status,
                                    "application_date": fecha_str,
                                    "salary": edit_salary.strip() if edit_salary else None,
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
                                        salary=edit_salary.strip() if edit_salary else None,
                                        work_mode=edit_mode,
                                        location=edit_location.strip() if edit_location else None,
                                        job_url=edit_job_url.strip() if edit_job_url else None,
                                        notes=edit_notes.strip() if edit_notes else None,
                                        follow_up_date=fup_str
                                    )
                                except Exception:
                                    pass

                                st.success("¡Aplicación actualizada con éxito en la nube!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar en Supabase: {e}")

                # --------------------------------------------------------------
                # FASE 5.3: INTERVIEW COACH INTEGRADO
                # --------------------------------------------------------------
                if st.session_state.get("show_interview_coach") and st.session_state.get("coach_app_id") == app_actual["id"]:
                    st.divider()
                    col_c_head, col_c_close = st.columns([5, 1])
                    with col_c_head:
                        st.subheader(f"🎯 Interview Coach: {app_actual['position']} @ {app_actual['company']}")
                        st.caption("Preparación técnica y situacional adaptada a los requerimientos de esta vacante y a tu Master Skill Profile.")
                    with col_c_close:
                        st.write("")
                        if st.button("✖️ Cerrar Coach", key=f"close_coach_{app_actual['id']}", use_container_width=True):
                            st.session_state["show_interview_coach"] = False
                            st.session_state.pop("coach_session", None)
                            st.rerun()

                    # Inicialización de la sesión del coach si es una postulación distinta
                    if ("coach_session" not in st.session_state or 
                        st.session_state["coach_session"].get("app_id") != app_actual["id"]):
                        st.session_state["coach_session"] = {
                            "app_id": app_actual["id"],
                            "study_guide": None,
                            "questions": [],
                            "current_index": 0,
                            "current_feedback": None,
                            "history": []
                        }

                    c_session = st.session_state["coach_session"]

                    # Generación inicial con IA si aún no existen en la sesión
                    if not c_session.get("questions") or c_session.get("study_guide") is None:
                        with st.spinner("🧠 Generando plan de entrenamiento, análisis de brechas y preguntas de entrevista con Gemini..."):
                            app_skills = get_skills_by_application(app_actual["id"])
                            user_skills = get_all_user_skills()
                            missing_list = [s["skill"] for s in app_skills if s.get("match_status") == "missing"]

                            try:
                                guia_estudio = generate_skill_gaps_study(
                                    missing_skills=missing_list,
                                    position=app_actual["position"],
                                    company=app_actual["company"]
                                )
                                preguntas_gen = generate_interview_questions(
                                    position=app_actual["position"],
                                    company=app_actual["company"],
                                    app_skills=app_skills,
                                    user_skills=user_skills,
                                    notes=app_actual.get("notes")
                                )
                                c_session["study_guide"] = guia_estudio
                                c_session["questions"] = preguntas_gen
                                c_session["current_index"] = 0
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error al inicializar el Interview Coach: {e}")

                    # Renderizado de las 3 secciones del Coach
                    if c_session.get("questions") and (c_session.get("study_guide") is not None):
                        tab_gaps, tab_bank, tab_sim = st.tabs([
                            "📚 Skill Gaps Study (Guía Rápida)",
                            f"❓ Banco de Preguntas ({len(c_session['questions'])})",
                            "🎙️ Simulador de Entrevista (Practice)"
                        ])

                        # PESTAÑA 1: GUÍA DE ESTUDIO DE BRECHAS
                        with tab_gaps:
                            st.markdown("### 📚 Guía de Estudio de Brechas Técnicas")
                            st.caption("Conceptos esenciales, vocabulario indispensable y recursos oficiales recomendados para cada habilidad faltante.")

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
                                            st.caption(f"Categoría: `{s_cat}`")
                                        with col_g2:
                                            if res.get("source") == "ms_learn_catalog_api":
                                                st.caption("☁️ `MS Learn Oficial`")
                                            elif res.get("source") == "curated":
                                                st.caption("🛡️ `Plataforma Curada`")
                                            else:
                                                st.caption("🔍 `Búsqueda Externa`")

                                        if s_ctx:
                                            st.markdown(f"**📌 Relevancia en el puesto:** {s_ctx}")
                                        if s_tips:
                                            st.markdown(f"**🎯 Conceptos clave para la entrevista:** {s_tips}")

                                        if res and res.get("url"):
                                            p_label = res.get("title") or res.get("platform", "Plataforma de estudio")
                                            st.markdown(f"💡 **Sugerencia de estudio:** [{p_label}]({res['url']})")
                            elif isinstance(gaps_list, str) and gaps_list.strip():
                                st.markdown(gaps_list)
                            else:
                                st.success("🎉 ¡Excelente! No se detectaron brechas técnicas para esta postulación.")

                        # PESTAÑA 2: BANCO DE PREGUNTAS
                        with tab_bank:
                            st.markdown("### ❓ Preguntas de Entrevista Personalizadas")
                            st.caption("Preguntas técnicas y situacionales cruzando los requisitos del puesto con tu perfil real.")
                            for q in c_session["questions"]:
                                with st.expander(f"Q#{q.get('id', '')} - [{q.get('category', 'Técnica')}] {q.get('focus_skill', '')}"):
                                    st.markdown(f"**Pregunta:**\n\n### {q.get('question')}")
                                    st.info(f"💡 **Tip del entrevistador:** {q.get('tip')}")

                        # PESTAÑA 3: SIMULADOR DE PRÁCTICA
                        with tab_sim:
                            st.markdown("### 🎙️ Simulador de Práctica Interactivo")
                            st.caption("Escribe tus respuestas y recibe retroalimentación constructiva de la IA en tiempo real.")

                            cur_idx = c_session["current_index"]
                            total_q = len(c_session["questions"])

                            if cur_idx < total_q:
                                q_actual = c_session["questions"][cur_idx]
                                st.progress((cur_idx) / total_q)
                                st.markdown(f"**Pregunta {cur_idx + 1} de {total_q}** | Categoría: `{q_actual.get('category')}`")
                                st.info(f"**Enfoque:** `{q_actual.get('focus_skill')}`\n\n#### {q_actual.get('question')}")

                                with st.expander("💡 Tip del entrevistador (¿Qué buscan evaluar?)"):
                                    st.caption(q_actual.get("tip"))

                                with st.form(key=f"form_practice_{app_actual['id']}_{cur_idx}"):
                                    resp_usuario = st.text_area(
                                        "Tu respuesta:",
                                        placeholder="Escribe tu respuesta como si estuvieras hablando con el entrevistador...",
                                        height=160,
                                        key=f"txt_resp_{app_actual['id']}_{cur_idx}"
                                    )
                                    btn_enviar_resp = st.form_submit_button("🚀 Enviar respuesta para evaluación", use_container_width=True)

                                if btn_enviar_resp:
                                    if not resp_usuario.strip():
                                        st.warning("⚠️ Por favor escribe tu respuesta antes de enviarla.")
                                    else:
                                        with st.spinner("🧠 Evaluando tu respuesta con Gemini..."):
                                            try:
                                                evaluacion = evaluate_interview_answer(
                                                    question=q_actual.get("question"),
                                                    category=q_actual.get("category", ""),
                                                    focus_skill=q_actual.get("focus_skill", ""),
                                                    user_answer=resp_usuario.strip()
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
                                                st.error(f"Error al evaluar: {err}")

                                # Mostrar feedback si existe para la pregunta actual
                                if c_session.get("current_feedback"):
                                    fb = c_session["current_feedback"]
                                    st.markdown("---")
                                    st.markdown("#### 📋 Feedback de la IA:")
                                    st.metric("Calificación", fb.get("rating", "Evaluada"))

                                    col_fb1, col_fb2 = st.columns(2)
                                    with col_fb1:
                                        st.markdown("**🟢 Fortalezas identificadas:**")
                                        for st_item in fb.get("strengths", []):
                                            st.markdown(f"✅ {st_item}")
                                    with col_fb2:
                                        st.markdown("**🟡 Oportunidades de mejora:**")
                                        for imp_item in fb.get("areas_to_improve", []):
                                            st.markdown(f"⚠️ {imp_item}")

                                    if fb.get("suggested_framework"):
                                        st.info(f"📐 **Estructura recomendada:** {fb.get('suggested_framework')}")

                                    if fb.get("model_answer"):
                                        with st.expander("🌟 Ver respuesta modelo senior"):
                                            st.write(fb.get("model_answer"))

                                    col_next1, col_next2 = st.columns([2, 1])
                                    with col_next1:
                                        if st.button("➡️ Siguiente Pregunta", type="primary", use_container_width=True, key=f"btn_next_{cur_idx}"):
                                            c_session["current_index"] += 1
                                            c_session["current_feedback"] = None
                                            st.rerun()
                            else:
                                # Todas las preguntas han sido completadas
                                st.balloons()
                                st.success("🎉 ¡Excelente trabajo! Has completado todas las preguntas de preparación para esta vacante.")
                                st.markdown("### 📜 Resumen de tu Sesión de Práctica:")

                                for h in c_session.get("history", []):
                                    with st.expander(f"Pregunta {h['q_num']}: {h['question'][:70]}... — {h['feedback'].get('rating', '')}"):
                                        st.markdown(f"**Tu respuesta:**\n\n_{h['answer']}_\n")
                                        st.markdown(f"**Estructura sugerida:** {h['feedback'].get('suggested_framework', 'N/A')}")
                                        st.markdown(f"**Respuesta modelo:**\n\n{h['feedback'].get('model_answer', 'N/A')}")

                                if st.button("🔄 Reiniciar Práctica", key=f"btn_reset_coach_{app_actual['id']}", use_container_width=True):
                                    c_session["current_index"] = 0
                                    c_session["current_feedback"] = None
                                    c_session["history"] = []
                                    st.rerun()


# ==============================================================================
# PÁGINA 3: AGREGAR NUEVA APLICACIÓN (Requisito 1)
# ==============================================================================
elif menu_opcion == "➕ Agregar Nueva Aplicación":
    st.subheader("➕ Formulario de Nueva Aplicación")
    st.caption("Ingresa los datos de una nueva vacante para registrarla en la base de datos.")

    with st.form("form_nueva_aplicacion", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("Company *", placeholder="Ej. Microsoft, Akamai...")
        with col2:
            position = st.text_input("Position *", placeholder="Ej. DevOps Engineer, SRE...")

        col3, col4 = st.columns(2)
        with col3:
            app_date = st.date_input("Application Date", value=date.today(), key="new_app_date")
        with col4:
            status = st.selectbox("Status", options=STATUS_OPTIONS, index=0, key="new_status")

        col5, col6 = st.columns(2)
        with col5:
            work_mode = st.radio("Work Mode", options=["Remote", "Hybrid", "On-site"], horizontal=True, key="new_work_mode")
        with col6:
            salary_input = st.text_input("Salary", placeholder="Ej. 5000 USD, TBD, Por confirmar...", key="new_salary")

        col7, col8 = st.columns(2)
        with col7:
            job_url = st.text_input("Job URL", placeholder="https://linkedin.com/jobs/...", key="new_url")
        with col8:
            location = st.text_input("Location", placeholder="Ej. San José, Costa Rica / Remote US", key="new_location")

        # Campo opcional para programar un Follow-up desde la creación
        col_fup1, col_fup2 = st.columns(2)
        with col_fup1:
            asignar_fup_nuevo = st.checkbox("Programar Follow-up", value=False, key="new_fup_chk")
        with col_fup2:
            fup_date_nuevo = st.date_input("Fecha de Follow-up", value=date.today(), key="new_fup_date") if asignar_fup_nuevo else None

        notes = st.text_area("Notes / Job Description", placeholder="Pega aquí requisitos clave o notas...", key="new_notes")

        btn_crear = st.form_submit_button("💾 SAVE APPLICATION", use_container_width=True)

    if btn_crear:
        errores = []
        if not company.strip():
            errores.append("El campo **Company** es obligatorio.")
        if not position.strip():
            errores.append("El campo **Position** es obligatorio.")

        salary_limpio = None
        if salary_input.strip():
            salario_txt = salary_input.replace("$", "").replace(",", "").strip()
            try:
                salario_num = float(salario_txt)
                salary_limpio = f"{int(salario_num)} USD"
            except ValueError:
                # Permite ingresar texto libre como TBD, Por confirmar, aún no lo sé, etc.
                salary_limpio = salary_input.strip()

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
