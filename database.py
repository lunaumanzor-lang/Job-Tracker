# ==============================================================================
# PROYECTO: SmartCV
# FASE 2: Base de Datos Relacional con SQLite (database.py)
# ==============================================================================

import os
import re
import hashlib
from datetime import datetime, timezone, timedelta, date
from typing import List, Dict, Optional, Any
import logging
import pandas as pd
from cryptography.fernet import Fernet
from supabase import Client

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# 1. ESQUEMA DE BASE DE DATOS MIGRADO A SUPABASE
# ------------------------------------------------------------------------------
# Las tablas residen en Supabase (PostgreSQL). Ver supabase_schema.sql.


# ------------------------------------------------------------------------------
# CONSTANTES DE DOMINIO
# ------------------------------------------------------------------------------
# Monedas de América y Europa (Fase 6.1)
CURRENCY_OPTIONS = [
    # Principales / América del Norte y Centroamérica
    "USD ($) — Dólar estadounidense (EE. UU.)",
    "CRC (₡) — Colón costarricense (Costa Rica)",
    "EUR (€) — Euro (Unión Europea)",
    "GBP (£) — Libra esterlina (Reino Unido)",
    "CAD (CA$) — Dólar canadiense (Canadá)",
    "MXN ($) — Peso mexicano (México)",
    "GTQ (Q) — Quetzal (Guatemala)",
    "HNL (L) — Lempira (Honduras)",
    "NIO (C$) — Córdoba (Nicaragua)",
    "PAB (B/.) — Balboa (Panamá)",
    "DOP (RD$) — Peso dominicano (Rep. Dominicana)",
    "JMD (J$) — Dólar jamaiquino (Jamaica)",
    "TTD (TT$) — Dólar trinitense (Trinidad y Tobago)",
    "BSD (B$) — Dólar bahameño (Bahamas)",
    "BZD (BZ$) — Dólar beliceño (Belice)",
    # América del Sur
    "BRL (R$) — Real brasileño (Brasil)",
    "COP ($) — Peso colombiano (Colombia)",
    "ARS ($) — Peso argentino (Argentina)",
    "CLP ($) — Peso chileno (Chile)",
    "PEN (S/) — Sol peruano (Perú)",
    "UYU ($) — Peso uruguayo (Uruguay)",
    "BOB (Bs.) — Boliviano (Bolivia)",
    "PYG (₲) — Guaraní (Paraguay)",
    "VES (Bs.) — Bolívar digital (Venezuela)",
    "GYD (G$) — Dólar guyanés (Guyana)",
    "SRD (Sr$) — Dólar surinamés (Surinam)",
    # Europa
    "CHF (Fr.) — Franco suizo (Suiza)",
    "SEK (kr) — Corona sueca (Suecia)",
    "NOK (kr) — Corona noruega (Noruega)",
    "DKK (kr) — Corona danesa (Dinamarca)",
    "PLN (zł) — Złoty polaco (Polonia)",
    "CZK (Kč) — Corona checa (Rep. Checa)",
    "HUF (Ft) — Forinto húngaro (Hungría)",
    "RON (lei) — Leu rumano (Rumania)",
    "BGN (лв) — Lev búlgaro (Bulgaria)",
    "ISK (kr) — Corona islandesa (Islandia)",
    "TRY (₺) — Lira turca (Turquía)",
    # Sin especificar
    "TBD / Sin especificar"
]

SKILL_CATEGORIES = [
    "Operating Systems",
    "Cloud",
    "Automation",
    "Programming",
    "DevOps",
    "Web Servers",
    "Security",
    "Monitoring",
    "Networking",
    "Databases",
    "ITSM",
    "CI/CD",
    "Virtualization",
    "Certifications",
    "Soft Skills"
]

PROFICIENCY_LEVELS = [
    "Beginner",
    "Intermediate",
    "Advanced"
]


def get_all_distinct_categories(user_id: Optional[str] = None, client: Any = None) -> List[str]:
    """
    Retorna la lista unificada y ordenada de categorías:
    las predeterminadas en SKILL_CATEGORIES más cualquier categoría personalizada
    creada o registrada por el usuario en Supabase.
    Aplica filtro explícito .eq("user_id", user_id) además de RLS.
    """
    categorias = set(SKILL_CATEGORIES)
    uid = user_id or get_current_user_id()
    if not uid:
        return sorted(list(categorias))
    sb = client or get_supabase_client()
    if not sb:
        return sorted(list(categorias))
    try:
        response = (
            sb.table("user_skills")
            .select("category")
            .eq("user_id", uid)
            .execute()
        )
        if response and response.data:
            for row in response.data:
                cat = row.get("category")
                if cat and str(cat).strip():
                    categorias.add(str(cat).strip())
    except Exception:
        pass
    return sorted(list(categorias))


# ------------------------------------------------------------------------------
# 2. OPERACIONES CRUD: APPLICATIONS (Módulo 4 - Migración Supabase)
# ------------------------------------------------------------------------------
def insert_application(
    company: str,
    position: str,
    status: str = "Applied",
    application_date: Optional[str] = None,
    salary: Optional[str] = None,
    work_mode: Optional[str] = None,
    location: Optional[str] = None,
    job_url: Optional[str] = None,
    recruiter: Optional[str] = None,
    notes: Optional[str] = None,
    follow_up_date: Optional[str] = None,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> int:
    """
    Inserta una nueva postulación en Supabase vinculada al usuario autenticado.
    Retorna el ID numérico generado.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en insert_application: no hay cliente de sesión o usuario autenticado")
        return 0

    clean_app_date = application_date.strip() if application_date and application_date.strip() else None
    clean_fup_date = follow_up_date.strip() if follow_up_date and follow_up_date.strip() else None

    payload = {
        "user_id": uid,
        "company": company.strip() if company else "",
        "position": position.strip() if position else "",
        "status": status.strip() if status else "Applied",
        "application_date": clean_app_date,
        "salary": salary.strip() if salary and salary.strip() else None,
        "work_mode": work_mode.strip() if work_mode and work_mode.strip() else None,
        "location": location.strip() if location and location.strip() else None,
        "job_url": job_url.strip() if job_url and job_url.strip() else None,
        "recruiter": recruiter.strip() if recruiter and recruiter.strip() else None,
        "notes": notes.strip() if notes and notes.strip() else None,
        "follow_up_date": clean_fup_date
    }

    try:
        res = client.table("applications").insert(payload).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("id", 0)
        return 0
    except Exception as e:
        err_msg = str(e)
        if "applications_pkey" in err_msg or "duplicate key" in err_msg or "23505" in err_msg:
            try:
                admin = _get_service_role_client()
                target_client = admin if admin else client
                res_max = target_client.table("applications").select("id").order("id", desc=True).limit(1).execute()
                max_id = int(res_max.data[0]["id"]) if (res_max.data and len(res_max.data) > 0) else 0
                payload_fallback = dict(payload)
                payload_fallback["id"] = max_id + 1
                res_fb = client.table("applications").insert(payload_fallback).execute()
                if res_fb.data and len(res_fb.data) > 0:
                    return res_fb.data[0].get("id", 0)
            except Exception as e_fb:
                print(f"Error en fallback de ID para applications: {e_fb}")
        print(f"Error al insertar aplicación en Supabase: {e}")
        return 0


def insert_application_skills(
    application_id: int,
    skills: List[Dict[str, str]],
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> int:
    """
    Inserta las habilidades asociadas a una postulación con su match_status en Supabase,
    vinculadas tanto a application_id como a user_id.
    Retorna la cantidad de habilidades insertadas.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en insert_application_skills: no hay cliente de sesión o usuario autenticado")
        return 0

    filas = []
    for item in skills:
        nombre = item.get("skill", "").strip()
        st_match = item.get("match_status", "strong").strip()
        if nombre:
            filas.append({
                "user_id": uid,
                "application_id": application_id,
                "skill": nombre,
                "match_status": st_match
            })

    if not filas:
        return 0

    try:
        res = client.table("skills").insert(filas).execute()
        return len(res.data) if res.data else 0
    except Exception as e:
        err_msg = str(e)
        if "skills_pkey" in err_msg or "duplicate key" in err_msg or "23505" in err_msg:
            try:
                admin = _get_service_role_client()
                target_client = admin if admin else client
                res_max = target_client.table("skills").select("id").order("id", desc=True).limit(1).execute()
                max_id = int(res_max.data[0]["id"]) if (res_max.data and len(res_max.data) > 0) else 0
                filas_fallback = []
                for idx, f in enumerate(filas, start=1):
                    f_copy = dict(f)
                    f_copy["id"] = max_id + idx
                    filas_fallback.append(f_copy)
                res_fb = client.table("skills").insert(filas_fallback).execute()
                return len(res_fb.data) if res_fb.data else 0
            except Exception as e_fb:
                print(f"Error en fallback de ID para skills: {e_fb}")
        print(f"Error al insertar habilidades de aplicación en Supabase: {e}")
        return 0


def get_skills_by_application(
    application_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> List[Dict[str, Any]]:
    """
    Recupera todas las habilidades de una postulación específica para el usuario autenticado.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en get_skills_by_application: no hay cliente de sesión o usuario autenticado")
        return []

    try:
        res = (
            client.table("skills")
            .select("*")
            .eq("application_id", application_id)
            .eq("user_id", uid)
            .order("id", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Error al obtener habilidades de la postulación {application_id} en Supabase: {e}")
        return []


def get_all_applications(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> List[Dict[str, Any]]:
    """
    Obtiene todas las postulaciones del usuario autenticado ordenadas por ID descendente.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en get_all_applications: no hay cliente de sesión o usuario autenticado")
        return []

    try:
        res = (
            client.table("applications")
            .select("*")
            .eq("user_id", uid)
            .order("id", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Error al obtener postulaciones en Supabase: {e}")
        return []


def get_application_by_id(
    app_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Optional[Dict[str, Any]]:
    """
    Busca una postulación específica por ID para el usuario autenticado.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en get_application_by_id: no hay cliente de sesión o usuario autenticado")
        return None

    try:
        res = (
            client.table("applications")
            .select("*")
            .eq("id", app_id)
            .eq("user_id", uid)
            .execute()
        )
        if res.data and len(res.data) > 0:
            return res.data[0]
        return None
    except Exception as e:
        print(f"Error al obtener aplicación {app_id} en Supabase: {e}")
        return None


def update_application_status(
    app_id: int,
    new_status: str,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Actualiza el estado de una postulación en Supabase, acotado al usuario autenticado.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en update_application_status: no hay cliente de sesión o usuario autenticado")
        return False

    try:
        res = (
            client.table("applications")
            .update({"status": new_status.strip()})
            .eq("id", app_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al actualizar estado de la aplicación {app_id} en Supabase: {e}")
        return False


def update_application(
    app_id: int,
    company: str,
    position: str,
    status: str,
    application_date: Optional[str] = None,
    salary: Optional[str] = None,
    work_mode: Optional[str] = None,
    location: Optional[str] = None,
    job_url: Optional[str] = None,
    notes: Optional[str] = None,
    follow_up_date: Optional[str] = None,
    recruiter: Optional[str] = None,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Actualiza los campos editables de una postulación en Supabase, acotado al usuario autenticado.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en update_application: no hay cliente de sesión o usuario autenticado")
        return False

    clean_app_date = application_date.strip() if application_date and application_date.strip() else None
    clean_fup_date = follow_up_date.strip() if follow_up_date and follow_up_date.strip() else None

    payload = {
        "company": company.strip() if company else "",
        "position": position.strip() if position else "",
        "status": status.strip() if status else "Applied",
        "application_date": clean_app_date,
        "salary": salary.strip() if salary and salary.strip() else None,
        "work_mode": work_mode.strip() if work_mode and work_mode.strip() else None,
        "location": location.strip() if location and location.strip() else None,
        "job_url": job_url.strip() if job_url and job_url.strip() else None,
        "notes": notes.strip() if notes and notes.strip() else None,
        "follow_up_date": clean_fup_date
    }
    if recruiter is not None:
        payload["recruiter"] = recruiter.strip() if recruiter and recruiter.strip() else None

    try:
        res = (
            client.table("applications")
            .update(payload)
            .eq("id", app_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al actualizar aplicación {app_id} en Supabase: {e}")
        return False


def delete_application(
    app_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Elimina una postulación de Supabase, acotado al usuario autenticado.
    NO renumera IDs (mantiene la integridad referencial y secuencias de PostgreSQL).
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en delete_application: no hay cliente de sesión o usuario autenticado")
        return False

    try:
        client.table("skills").delete().eq("application_id", app_id).eq("user_id", uid).execute()
        client.table("interviews").delete().eq("application_id", app_id).eq("user_id", uid).execute()
        res = (
            client.table("applications")
            .delete()
            .eq("id", app_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al eliminar aplicación {app_id} en Supabase: {e}")
        return False


# ------------------------------------------------------------------------------
# 6. MÉTRICAS Y AGREGACIONES DEL DASHBOARD CON PANDAS (Módulo 4)
# ------------------------------------------------------------------------------
def get_dashboard_counts(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Dict[str, int]:
    """
    Calcula las 5 métricas clave para el usuario autenticado usando Pandas en memoria:
    - total_applications
    - interviews ('Recruiter Screen', 'Technical Interview', 'Final Interview')
    - offers ('Offer')
    - rejections ('Rejected')
    - follow_ups (follow_up_date <= hoy)
    """
    default = {
        "total_applications": 0,
        "interviews": 0,
        "offers": 0,
        "rejections": 0,
        "follow_ups": 0
    }
    apps = get_all_applications(user_id=user_id, client=client)
    if not apps:
        return default

    try:
        df = pd.DataFrame(apps)
        total_apps = len(df)
        interviews = len(df[df["status"].isin(["Recruiter Screen", "Technical Interview", "Final Interview"])]) if "status" in df.columns else 0
        offers = len(df[df["status"] == "Offer"]) if "status" in df.columns else 0
        rejections = len(df[df["status"] == "Rejected"]) if "status" in df.columns else 0

        today_str = date.today().isoformat()
        if "follow_up_date" in df.columns:
            valid_fu = df["follow_up_date"].dropna().astype(str).str.strip()
            follow_ups = int(((valid_fu != "") & (valid_fu <= today_str)).sum())
        else:
            follow_ups = 0

        return {
            "total_applications": total_apps,
            "interviews": interviews,
            "offers": offers,
            "rejections": rejections,
            "follow_ups": follow_ups
        }
    except Exception as e:
        print(f"Error al calcular get_dashboard_counts con pandas: {e}")
        return default


def get_status_breakdown(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Dict[str, int]:
    """
    Calcula la distribución de postulaciones por estado para el usuario autenticado usando Pandas.
    """
    estados_base = [
        "Applied",
        "Recruiter Screen",
        "Technical Interview",
        "Final Interview",
        "Offer",
        "Rejected",
        "Ghosted"
    ]
    breakdown = {estado: 0 for estado in estados_base}
    apps = get_all_applications(user_id=user_id, client=client)
    if not apps:
        return breakdown

    try:
        df = pd.DataFrame(apps)
        if "status" in df.columns:
            counts = df["status"].value_counts().to_dict()
            for st_name, cnt in counts.items():
                if st_name:
                    breakdown[st_name] = int(cnt)
        return breakdown
    except Exception as e:
        print(f"Error al calcular get_status_breakdown con pandas: {e}")
        return breakdown


def get_work_mode_breakdown(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Dict[str, int]:
    """
    Calcula la distribución por modalidad de trabajo usando Pandas.
    """
    modalidades = {"Remote": 0, "Hybrid": 0, "On-site": 0}
    apps = get_all_applications(user_id=user_id, client=client)
    if not apps:
        return modalidades

    try:
        df = pd.DataFrame(apps)
        if "work_mode" in df.columns:
            valid_wm = df["work_mode"].dropna().astype(str).str.strip()
            valid_wm = valid_wm[valid_wm != ""]
            counts = valid_wm.value_counts().to_dict()
            for mode, cnt in counts.items():
                if mode in modalidades:
                    modalidades[mode] = int(cnt)
                else:
                    modalidades[mode or "Otro"] = int(cnt)
        return modalidades
    except Exception as e:
        print(f"Error al calcular get_work_mode_breakdown con pandas: {e}")
        return modalidades


def get_salary_statistics(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Dict[str, Any]:
    """
    Calcula estadísticas salariales en USD (min, avg, max, count) usando Pandas.
    """
    default = {"min": 0.0, "avg": 0.0, "max": 0.0, "count": 0}
    apps = get_all_applications(user_id=user_id, client=client)
    if not apps:
        return default

    try:
        df = pd.DataFrame(apps)
        if "salary" not in df.columns:
            return default

        valid_salaries = df["salary"].dropna().astype(str).str.strip()
        valid_salaries = valid_salaries[valid_salaries != ""]
        if valid_salaries.empty:
            return default

        salarios_validos = []
        non_usd_codes = ["CRC", "EUR", "GBP", "CAD", "MXN", "GTQ", "HNL", "NIO", "PAB", "DOP", "BRL", "COP", "ARS", "CLP", "PEN", "UYU", "BOB", "PYG", "VES", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "BGN", "ISK", "TRY"]

        for val in valid_salaries:
            val_upper = val.upper()
            if any(c in val_upper for c in non_usd_codes):
                continue
            nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", val.replace(",", "")) if float(n) >= 500]
            if nums:
                salarios_validos.append(sum(nums) / len(nums))

        if not salarios_validos:
            return default

        sal_series = pd.Series(salarios_validos)
        return {
            "min": round(float(sal_series.min()), 2),
            "avg": round(float(sal_series.mean()), 2),
            "max": round(float(sal_series.max()), 2),
            "count": int(sal_series.count())
        }
    except Exception as e:
        print(f"Error al calcular get_salary_statistics con pandas: {e}")
        return default


def get_monthly_applications(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> List[Dict[str, Any]]:
    """
    Calcula la cantidad de postulaciones agrupadas cronológicamente por mes (YYYY-MM) usando Pandas.
    """
    apps = get_all_applications(user_id=user_id, client=client)
    if not apps:
        return []

    try:
        df = pd.DataFrame(apps)
        if "application_date" not in df.columns:
            return []

        valid_dates = df["application_date"].dropna().astype(str).str.strip()
        valid_dates = valid_dates[valid_dates != ""]
        if valid_dates.empty:
            return []

        months = valid_dates.str.slice(0, 7)
        months = months[months.str.len() == 7]
        if months.empty:
            return []

        monthly_counts = months.value_counts().sort_index()
        return [{"mes": str(m), "total": int(cnt)} for m, cnt in monthly_counts.items()]
    except Exception as e:
        print(f"Error al calcular get_monthly_applications con pandas: {e}")
        return []


def get_monthly_interviews(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> List[Dict[str, Any]]:
    """
    Calcula la cantidad de entrevistas agrupadas por mes usando Pandas.
    """
    apps = get_all_applications(user_id=user_id, client=client)
    if not apps:
        return []

    try:
        df = pd.DataFrame(apps)
        if "application_date" not in df.columns or "status" not in df.columns:
            return []

        interview_statuses = ["Recruiter Screen", "Technical Interview", "Final Interview"]
        df_interviews = df[df["status"].isin(interview_statuses)]
        if df_interviews.empty:
            return []

        valid_dates = df_interviews["application_date"].dropna().astype(str).str.strip()
        valid_dates = valid_dates[valid_dates != ""]
        if valid_dates.empty:
            return []

        months = valid_dates.str.slice(0, 7)
        months = months[months.str.len() == 7]
        if months.empty:
            return []

        monthly_counts = months.value_counts().sort_index()
        return [{"mes": str(m), "total": int(cnt)} for m, cnt in monthly_counts.items()]
    except Exception as e:
        print(f"Error al calcular get_monthly_interviews con pandas: {e}")
        return []


# ------------------------------------------------------------------------------
# 8. OPERACIONES CRUD: USER PROFILE (Fase 5.1 & Migración Supabase)
# ------------------------------------------------------------------------------
def get_supabase_client():
    """
    Obtiene o inicializa el cliente de Supabase guardado en st.session_state
    para la sesión del usuario actual, asegurando que no sea un cliente global compartido.
    """
    try:
        import streamlit as st
        from supabase import create_client
        if "supabase_client" not in st.session_state:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
            st.session_state.supabase_client = create_client(url, key)
        client = st.session_state.supabase_client
        if "access_token" in st.session_state and st.session_state.access_token:
            try:
                client.postgrest.auth(st.session_state.access_token)
            except Exception:
                pass
        return client
    except Exception:
        return None


def get_current_user_id(client: Optional[Client] = None) -> Optional[str]:
    """
    Obtiene el user_id del usuario autenticado en la sesión actual de Streamlit o del cliente Supabase.
    """
    try:
        import streamlit as st
        user = getattr(st.session_state, "user", None)
        if user:
            u_id = getattr(user, "id", None)
            if not u_id and isinstance(user, dict):
                u_id = user.get("id")
            if u_id:
                return str(u_id)
        if client:
            try:
                res = client.auth.get_user()
                if res and res.user:
                    return str(res.user.id)
            except Exception:
                pass
    except Exception:
        pass
    return None


def save_user_profile(
    full_name: Optional[str] = None,
    current_title: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    location: Optional[str] = None,
    summary: Optional[str] = None,
    user_id: Optional[str] = None,
    client: Any = None
) -> bool:
    """
    Inserta o actualiza el perfil del usuario autenticado en Supabase.
    Aplica filtro explícito por user_id además de RLS.
    """
    from datetime import datetime, timezone
    uid = user_id or get_current_user_id()
    if not uid:
        return False
    sb = client or get_supabase_client()
    if not sb:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "user_id": uid,
        "full_name": full_name,
        "current_title": current_title,
        "email": email,
        "phone": phone,
        "location": location,
        "summary": summary,
        "updated_at": now_iso
    }
    try:
        existing = (
            sb.table("user_profile")
            .select("id")
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        if existing and existing.data:
            response = (
                sb.table("user_profile")
                .update(payload)
                .eq("user_id", uid)
                .execute()
            )
        else:
            response = (
                sb.table("user_profile")
                .insert(payload)
                .execute()
            )
        return bool(response and response.data)
    except Exception:
        return False


def get_user_profile(user_id: Optional[str] = None, client: Any = None) -> Optional[Dict[str, Any]]:
    """
    Obtiene la información del perfil del usuario autenticado desde Supabase.
    Aplica filtro explícito .eq("user_id", user_id) además de RLS.
    """
    uid = user_id or get_current_user_id()
    if not uid:
        return None
    sb = client or get_supabase_client()
    if not sb:
        return None
    try:
        response = (
            sb.table("user_profile")
            .select("*")
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        if response and response.data:
            return dict(response.data)
        return None
    except Exception:
        return None


def get_user_preferred_language(user_id: Optional[str] = None, client: Any = None) -> Optional[str]:
    """
    Obtiene la preferencia de idioma guardada ('es' o 'en') del usuario autenticado en Supabase.
    Aplica filtro explícito .eq("user_id", user_id) además de RLS.
    """
    uid = user_id or get_current_user_id()
    if not uid:
        return None
    sb = client or get_supabase_client()
    if not sb:
        return None
    try:
        response = (
            sb.table("user_profile")
            .select("preferred_language")
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        if response and response.data and response.data.get("preferred_language"):
            return str(response.data["preferred_language"]).strip().lower()
        return None
    except Exception:
        return None


def set_user_preferred_language(lang: str, user_id: Optional[str] = None, client: Any = None) -> bool:
    """
    Guarda o actualiza la preferencia de idioma ('es' o 'en') del usuario autenticado en Supabase.
    Aplica filtro explícito por user_id además de RLS.
    """
    lang_clean = lang.strip().lower() if lang else "es"
    from datetime import datetime, timezone
    uid = user_id or get_current_user_id()
    if not uid:
        return False
    sb = client or get_supabase_client()
    if not sb:
        return False
    try:
        existing = (
            sb.table("user_profile")
            .select("id")
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        if existing and existing.data:
            response = (
                sb.table("user_profile")
                .update({"preferred_language": lang_clean, "updated_at": now_iso})
                .eq("user_id", uid)
                .execute()
            )
        else:
            response = (
                sb.table("user_profile")
                .insert({"user_id": uid, "preferred_language": lang_clean, "updated_at": now_iso})
                .execute()
            )
        return bool(response and response.data)
    except Exception:
        return False


def add_user_skill(
    skill_name: str,
    category: str,
    source: str = "Manual",
    proficiency: str = "Intermediate",
    user_id: Optional[str] = None,
    client: Any = None
) -> bool:
    """
    Agrega o actualiza una habilidad en el inventario del usuario en Supabase.
    Compara en Python con .strip().lower() para evitar duplicados y actualizar
    el nivel sin importar mayúsculas o minúsculas.
    """
    clean_name = skill_name.strip()
    if not clean_name:
        return False
    uid = user_id or get_current_user_id()
    if not uid:
        return False
    sb = client or get_supabase_client()
    if not sb:
        return False

    try:
        existing_skills = get_all_user_skills(user_id=uid, client=sb)
        target_skill = None
        for s in existing_skills:
            if str(s.get("skill_name", "")).strip().lower() == clean_name.lower():
                target_skill = s
                break

        if target_skill:
            skill_id = target_skill["id"]
            cat_to_save = category.strip() if category else target_skill.get("category", "General")
            response = (
                sb.table("user_skills")
                .update({
                    "proficiency": proficiency,
                    "category": cat_to_save,
                    "source": source
                })
                .eq("id", skill_id)
                .eq("user_id", uid)
                .execute()
            )
            try:
                import streamlit as st
                st.session_state[f"prof_{skill_id}"] = proficiency
                st.session_state[f"cat_{skill_id}"] = cat_to_save
            except Exception:
                pass
            return bool(response and response.data)
        else:
            payload = {
                "user_id": uid,
                "skill_name": clean_name,
                "category": category.strip() if category else "General",
                "source": source,
                "proficiency": proficiency
            }
            response = (
                sb.table("user_skills")
                .insert(payload)
                .execute()
            )
            return bool(response and response.data)
    except Exception:
        return False


def add_user_skills_bulk(
    skills: List[Dict[str, str]],
    source: str = "Resume",
    user_id: Optional[str] = None,
    client: Any = None
) -> int:
    """
    Inserta o actualiza múltiples habilidades en Supabase en una sola operación upsert.
    Usa on_conflict="user_id,skill_name" y retorna la cantidad de habilidades procesadas.
    """
    if not skills:
        return 0
    uid = user_id or get_current_user_id()
    if not uid:
        return 0
    sb = client or get_supabase_client()
    if not sb:
        return 0

    skills_map = {}
    for item in skills:
        name = item.get("skill_name", "").strip()
        if name:
            skills_map[name.lower()] = {
                "user_id": uid,
                "skill_name": name,
                "category": item.get("category", "General").strip() or "General",
                "source": source,
                "proficiency": item.get("proficiency", "Intermediate")
            }

    if not skills_map:
        return 0

    records = list(skills_map.values())
    try:
        response = (
            sb.table("user_skills")
            .upsert(records, on_conflict="user_id,skill_name")
            .execute()
        )
        if response and response.data:
            return len(response.data)
        return len(records)
    except Exception:
        return 0


def get_all_user_skills(user_id: Optional[str] = None, client: Any = None) -> List[Dict[str, Any]]:
    """
    Obtiene todas las habilidades del usuario desde Supabase ordenadas por categoría y nombre.
    Aplica filtro explícito .eq("user_id", user_id) además de RLS.
    """
    uid = user_id or get_current_user_id()
    if not uid:
        return []
    sb = client or get_supabase_client()
    if not sb:
        return []
    try:
        response = (
            sb.table("user_skills")
            .select("*")
            .eq("user_id", uid)
            .order("category", desc=False)
            .order("skill_name", desc=False)
            .execute()
        )
        if response and response.data:
            return response.data
        return []
    except Exception:
        return []


def update_user_skill_proficiency(
    skill_id: int,
    new_proficiency: str,
    user_id: Optional[str] = None,
    client: Any = None
) -> bool:
    """
    Modifica el nivel de dominio (proficiency) de una habilidad existente en Supabase.
    Aplica filtro explícito por user_id e id además de RLS.
    """
    uid = user_id or get_current_user_id()
    if not uid:
        return False
    sb = client or get_supabase_client()
    if not sb:
        return False
    try:
        response = (
            sb.table("user_skills")
            .update({"proficiency": new_proficiency})
            .eq("id", skill_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(response and response.data)
    except Exception:
        return False


def update_user_skill_category(
    skill_id: int,
    new_category: str,
    user_id: Optional[str] = None,
    client: Any = None
) -> bool:
    """
    Modifica la categoría asignada a una habilidad existente en Supabase.
    Aplica filtro explícito por user_id e id además de RLS.
    """
    uid = user_id or get_current_user_id()
    if not uid:
        return False
    sb = client or get_supabase_client()
    if not sb:
        return False
    try:
        response = (
            sb.table("user_skills")
            .update({"category": new_category.strip()})
            .eq("id", skill_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(response and response.data)
    except Exception:
        return False


def delete_user_skill(
    skill_id: int,
    user_id: Optional[str] = None,
    client: Any = None
) -> bool:
    """
    Elimina una habilidad del perfil del usuario por su ID en Supabase.
    Aplica filtro explícito por user_id e id además de RLS.
    """
    uid = user_id or get_current_user_id()
    if not uid:
        return False
    sb = client or get_supabase_client()
    if not sb:
        return False
    try:
        response = (
            sb.table("user_skills")
            .delete()
            .eq("id", skill_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(response and response.data)
    except Exception:
        return False


# ==============================================================================
# FASE 5.6a & 5.7: FUNCIONES PARA EXPERIENCIA, BULLETS Y EDUCACIÓN (CV BUILDER & RESUME PARSER)
# ==============================================================================

def get_all_experiences(user_id: Optional[str] = None, client: Optional[Client] = None) -> List[Dict[str, Any]]:
    """
    Retorna todas las experiencias laborales registradas del usuario en Supabase,
    ordenadas por order_index ascendente e id ascendente.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return []

    try:
        res = (
            client.table("experience_entries")
            .select("*")
            .eq("user_id", uid)
            .order("order_index", desc=False)
            .order("id", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Error al obtener experiencias en Supabase: {e}")
        return []


def add_experience_entry(
    company: str,
    position: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_current: bool = False,
    order_index: int = 0,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> int:
    """
    Inserta una nueva experiencia laboral estructurada en Supabase y retorna su ID generado.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en add_experience_entry: no hay cliente o usuario autenticado")
        return 0

    payload = {
        "user_id": uid,
        "company": company.strip(),
        "position": position.strip(),
        "start_date": start_date,
        "end_date": end_date,
        "is_current": bool(is_current),
        "order_index": order_index
    }
    try:
        res = client.table("experience_entries").insert(payload).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("id", 0)
        return 0
    except Exception as e:
        print(f"Error al agregar experiencia laboral en Supabase: {e}")
        return 0


def update_experience_entry(
    experience_id: int,
    company: str,
    position: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_current: bool = False,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Actualiza los datos de una experiencia laboral en Supabase, acotado al usuario activo.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en update_experience_entry: no hay cliente o usuario autenticado")
        return False

    payload = {
        "company": company.strip(),
        "position": position.strip(),
        "start_date": start_date,
        "end_date": end_date,
        "is_current": bool(is_current)
    }
    try:
        res = (
            client.table("experience_entries")
            .update(payload)
            .eq("id", experience_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al actualizar experiencia laboral en Supabase: {e}")
        return False


def delete_experience_entry(
    experience_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Elimina una experiencia laboral y en cascada todos sus bullets asociados en Supabase,
    acotado al usuario activo.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en delete_experience_entry: no hay cliente o usuario autenticado")
        return False

    try:
        client.table("resume_bullets").delete().eq("experience_id", experience_id).eq("user_id", uid).execute()
        res = client.table("experience_entries").delete().eq("id", experience_id).eq("user_id", uid).execute()
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al eliminar experiencia laboral en Supabase: {e}")
        return False


# ------------------------------------------------------------------------------
# BULLETS DE LOGROS (resume_bullets)
# ------------------------------------------------------------------------------

def get_all_resume_bullets(user_id: Optional[str] = None, client: Optional[Client] = None) -> List[Dict[str, Any]]:
    """
    Obtiene todos los bullets del CV en Supabase ordenados por la experiencia correspondiente y order_index.
    Para compatibilidad hacia atrás y soporte del CV Builder, sintetiza el campo 'section'
    como 'position - company' e incluye company, position y fechas.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return []

    try:
        exps = (
            client.table("experience_entries")
            .select("*")
            .eq("user_id", uid)
            .order("order_index", desc=False)
            .order("id", desc=False)
            .execute()
            .data or []
        )
        if not exps:
            return []

        bullets = (
            client.table("resume_bullets")
            .select("*")
            .eq("user_id", uid)
            .order("order_index", desc=False)
            .order("id", desc=False)
            .execute()
            .data or []
        )

        exp_map = {e["id"]: e for e in exps}
        joined_results = []
        for b in bullets:
            exp = exp_map.get(b.get("experience_id"))
            if exp:
                pos = exp.get("position") or ""
                comp = exp.get("company") or ""
                joined_results.append({
                    "id": b.get("id"),
                    "experience_id": b.get("experience_id"),
                    "section": f"{pos} - {comp}".strip(" -"),
                    "company": comp,
                    "position": pos,
                    "start_date": exp.get("start_date"),
                    "end_date": exp.get("end_date"),
                    "is_current": exp.get("is_current"),
                    "bullet_text": b.get("bullet_text"),
                    "original_text": b.get("original_text"),
                    "current_text": b.get("current_text"),
                    "order_index": b.get("order_index", 0),
                    "_exp_order": exp.get("order_index", 0),
                    "_exp_id": exp.get("id", 0)
                })

        joined_results.sort(key=lambda x: (x["_exp_order"], x["_exp_id"], x["order_index"], x["id"]))
        for r in joined_results:
            r.pop("_exp_order", None)
            r.pop("_exp_id", None)
        return joined_results
    except Exception as e:
        print(f"Error al obtener todos los resume bullets en Supabase: {e}")
        return []


def get_bullets_by_experience(
    experience_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> List[Dict[str, Any]]:
    """
    Obtiene los bullets de una experiencia específica en Supabase, acotado al usuario activo.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return []

    try:
        res = (
            client.table("resume_bullets")
            .select("*")
            .eq("experience_id", experience_id)
            .eq("user_id", uid)
            .order("order_index", desc=False)
            .order("id", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Error al obtener bullets de experiencia en Supabase: {e}")
        return []


def add_resume_bullet(
    experience_id: int,
    bullet_text: str,
    original_text: Optional[str] = None,
    current_text: Optional[str] = None,
    order_index: int = 0,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> int:
    """
    Inserta un nuevo bullet asociado a una experiencia laboral en Supabase y retorna su ID.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en add_resume_bullet: no hay cliente o usuario autenticado")
        return 0

    b_txt = bullet_text.strip()
    orig = (original_text or b_txt).strip()
    curr = (current_text or b_txt).strip()
    payload = {
        "user_id": uid,
        "experience_id": experience_id,
        "bullet_text": b_txt,
        "original_text": orig,
        "current_text": curr,
        "order_index": order_index
    }
    try:
        res = client.table("resume_bullets").insert(payload).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("id", 0)
        return 0
    except Exception as e:
        print(f"Error al agregar resume bullet en Supabase: {e}")
        return 0


def update_resume_bullet(
    bullet_id: int,
    current_text: str,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Actualiza el texto actual (current_text y bullet_text) de un bullet en Supabase, acotado al usuario.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en update_resume_bullet: no hay cliente o usuario autenticado")
        return False

    clean_text = current_text.strip()
    payload = {
        "current_text": clean_text,
        "bullet_text": clean_text
    }
    try:
        res = (
            client.table("resume_bullets")
            .update(payload)
            .eq("id", bullet_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al actualizar resume bullet en Supabase: {e}")
        return False


def delete_resume_bullet(
    bullet_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Elimina un bullet del CV por su ID en Supabase, acotado al usuario.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en delete_resume_bullet: no hay cliente o usuario autenticado")
        return False

    try:
        res = (
            client.table("resume_bullets")
            .delete()
            .eq("id", bullet_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al eliminar resume bullet en Supabase: {e}")
        return False


# ------------------------------------------------------------------------------
# EDUCACIÓN Y CERTIFICACIONES (education_entries)
# ------------------------------------------------------------------------------

def get_all_education(user_id: Optional[str] = None, client: Optional[Client] = None) -> List[Dict[str, Any]]:
    """
    Obtiene todos los registros de educación y certificaciones en Supabase para el usuario activo.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return []

    try:
        res = (
            client.table("education_entries")
            .select("*")
            .eq("user_id", uid)
            .order("order_index", desc=False)
            .order("id", desc=False)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Error al obtener educación en Supabase: {e}")
        return []


def add_education_entry(
    institution: str,
    credential: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    order_index: int = 0,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> int:
    """
    Inserta un registro de educación o certificación en Supabase para el usuario activo y retorna su ID.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en add_education_entry: no hay cliente o usuario autenticado")
        return 0

    payload = {
        "user_id": uid,
        "institution": institution.strip(),
        "credential": credential.strip(),
        "start_date": start_date,
        "end_date": end_date,
        "order_index": order_index
    }
    try:
        res = client.table("education_entries").insert(payload).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("id", 0)
        return 0
    except Exception as e:
        print(f"Error al agregar educación en Supabase: {e}")
        return 0


def update_education_entry(
    education_id: int,
    institution: str,
    credential: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Actualiza un registro de educación en Supabase acotado al usuario activo.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en update_education_entry: no hay cliente o usuario autenticado")
        return False

    payload = {
        "institution": institution.strip(),
        "credential": credential.strip(),
        "start_date": start_date,
        "end_date": end_date
    }
    try:
        res = (
            client.table("education_entries")
            .update(payload)
            .eq("id", education_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al actualizar educación en Supabase: {e}")
        return False


def delete_education_entry(
    education_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Elimina un registro de educación en Supabase por su ID, acotado al usuario activo.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en delete_education_entry: no hay cliente o usuario autenticado")
        return False

    try:
        res = (
            client.table("education_entries")
            .delete()
            .eq("id", education_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al eliminar educación en Supabase: {e}")
        return False


# ------------------------------------------------------------------------------
# GUARDADO EN BULK TRAS REVISIÓN DE RESUME PARSER (Fase 5.7)
# ------------------------------------------------------------------------------

def save_parsed_resume_data(
    experience_list: List[Dict[str, Any]],
    education_list: List[Dict[str, Any]],
    replace_existing: bool = True,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Persiste en Supabase los datos de experiencia laboral, sus bullets asociados y la
    educación extraída y confirmada por el usuario.
    Regla: Inserta primero lo nuevo y borra lo viejo solo si todas las inserciones
    fueron exitosas, siempre acotado al user_id activo. Si falla, hace rollback de lo
    recién insertado y conserva lo viejo.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en save_parsed_resume_data: no hay cliente o usuario autenticado")
        return False

    inserted_exp_ids: List[int] = []
    inserted_bullet_ids: List[int] = []
    inserted_edu_ids: List[int] = []

    try:
        # 1. Si se va a reemplazar lo existente, identificamos los IDs anteriores para borrarlos al final
        old_exp_ids: List[int] = []
        old_edu_ids: List[int] = []
        if replace_existing:
            old_exp_res = client.table("experience_entries").select("id").eq("user_id", uid).execute()
            old_exp_ids = [row["id"] for row in (old_exp_res.data or []) if "id" in row]

            old_edu_res = client.table("education_entries").select("id").eq("user_id", uid).execute()
            old_edu_ids = [row["id"] for row in (old_edu_res.data or []) if "id" in row]

        # 2. Inserción de nuevas experiencias y sus viñetas
        for idx_exp, exp in enumerate(experience_list, start=1):
            comp = str(exp.get("company", "Empresa")).strip()
            pos = str(exp.get("position", "Puesto")).strip()
            s_date = exp.get("start_date")
            e_date = exp.get("end_date")
            is_cur = bool(exp.get("is_current"))
            order_idx = exp.get("order_index", idx_exp)

            exp_payload = {
                "user_id": uid,
                "company": comp,
                "position": pos,
                "start_date": s_date,
                "end_date": e_date,
                "is_current": is_cur,
                "order_index": order_idx
            }
            exp_res = client.table("experience_entries").insert(exp_payload).execute()
            if not exp_res.data or len(exp_res.data) == 0:
                raise RuntimeError(f"Fallo al insertar experiencia: {comp} - {pos}")

            new_exp_id = exp_res.data[0]["id"]
            inserted_exp_ids.append(new_exp_id)

            bullets = exp.get("bullets", [])
            for idx_b, b_text in enumerate(bullets, start=1):
                clean_b = str(b_text).strip()
                if clean_b:
                    b_payload = {
                        "user_id": uid,
                        "experience_id": new_exp_id,
                        "bullet_text": clean_b,
                        "original_text": clean_b,
                        "current_text": clean_b,
                        "order_index": idx_b
                    }
                    b_res = client.table("resume_bullets").insert(b_payload).execute()
                    if b_res.data and len(b_res.data) > 0:
                        inserted_bullet_ids.append(b_res.data[0]["id"])

        # 3. Inserción de nueva educación
        for idx_edu, edu in enumerate(education_list, start=1):
            inst = str(edu.get("institution", "Institución")).strip()
            cred = str(edu.get("credential", "Título / Certificación")).strip()
            s_date = edu.get("start_date")
            e_date = edu.get("end_date")
            order_idx = edu.get("order_index", idx_edu)

            if inst or cred:
                edu_payload = {
                    "user_id": uid,
                    "institution": inst,
                    "credential": cred,
                    "start_date": s_date,
                    "end_date": e_date,
                    "order_index": order_idx
                }
                edu_res = client.table("education_entries").insert(edu_payload).execute()
                if not edu_res.data or len(edu_res.data) == 0:
                    raise RuntimeError(f"Fallo al insertar educación: {inst} - {cred}")
                inserted_edu_ids.append(edu_res.data[0]["id"])

        # 4. Todo salió bien: si replace_existing es True, borramos lo viejo acotado a user_id
        if replace_existing:
            if old_exp_ids:
                client.table("resume_bullets").delete().eq("user_id", uid).in_("experience_id", old_exp_ids).execute()
                client.table("experience_entries").delete().eq("user_id", uid).in_("id", old_exp_ids).execute()
            if old_edu_ids:
                client.table("education_entries").delete().eq("user_id", uid).in_("id", old_edu_ids).execute()

        return True

    except Exception as e:
        print(f"Error en save_parsed_resume_data: {e}")
        # Rollback de lo recién insertado para no dejar datos corruptos o duplicados
        try:
            if inserted_bullet_ids:
                client.table("resume_bullets").delete().eq("user_id", uid).in_("id", inserted_bullet_ids).execute()
            if inserted_exp_ids:
                client.table("experience_entries").delete().eq("user_id", uid).in_("id", inserted_exp_ids).execute()
            if inserted_edu_ids:
                client.table("education_entries").delete().eq("user_id", uid).in_("id", inserted_edu_ids).execute()
        except Exception as rb_err:
            print(f"Error durante rollback de inserción: {rb_err}")
        return False


# ------------------------------------------------------------------------------
# BORRADOR DE TRABAJO DE CV IMPROVER (cv_improver_drafts)
# ------------------------------------------------------------------------------

def save_cv_improver_draft(
    draft_data: Dict[str, Any],
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Guarda o actualiza el borrador de trabajo en curso del usuario para Mejorar CV en Supabase.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        print("Error en save_cv_improver_draft: no hay cliente o usuario autenticado")
        return False

    payload = {
        "user_id": uid,
        "draft_data": draft_data
    }
    try:
        res = (
            client.table("cv_improver_drafts")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error al guardar borrador de CV Improver en Supabase: {e}")
        return False


def get_cv_improver_draft(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Optional[Dict[str, Any]]:
    """
    Obtiene el borrador de trabajo en curso del usuario para Mejorar CV desde Supabase.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return None

    try:
        res = (
            client.table("cv_improver_drafts")
            .select("draft_data")
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        if res.data and "draft_data" in res.data:
            return res.data["draft_data"]
        return None
    except Exception as e:
        print(f"Error al obtener borrador de CV Improver en Supabase: {e}")
        return None


def delete_cv_improver_draft(
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Elimina el borrador de trabajo de Mejorar CV del usuario en Supabase.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return False

    try:
        client.table("cv_improver_drafts").delete().eq("user_id", uid).execute()
        return True
    except Exception as e:
        print(f"Error al eliminar borrador de CV Improver en Supabase: {e}")
        return False




# ------------------------------------------------------------------------------
# GESTIÓN DE SESIONES PERSISTENTES SEGURA (auth_sessions en Supabase vía service_role)
# ------------------------------------------------------------------------------
def _get_service_role_client() -> Optional[Client]:
    """
    Crea un cliente de Supabase usando SUPABASE_SERVICE_ROLE_KEY exclusivamente
    para la gestión de la tabla auth_sessions en el servidor.
    NUNCA se guarda en st.session_state ni se usa para sign_in ni operaciones de usuario.
    """
    try:
        import streamlit as st
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL")
        service_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not service_key:
            return None
        return create_client(url, service_key)
    except Exception as e:
        print(f"Error al inicializar cliente service_role de Supabase: {e}")
        return None


def _hash_session_id(session_id: str) -> str:
    """
    Calcula el hash SHA-256 del session_id.
    El session_id en texto claro jamás se almacena en la base de datos.
    """
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _get_fernet_cipher() -> Optional[Fernet]:
    """
    Obtiene la instancia de cifrado Fernet usando SESSION_ENCRYPTION_KEY de secrets.
    """
    try:
        import streamlit as st
        enc_key = st.secrets.get("SESSION_ENCRYPTION_KEY")
        if not enc_key:
            return None
        return Fernet(enc_key.encode("utf-8") if isinstance(enc_key, str) else enc_key)
    except Exception as e:
        print(f"Error al inicializar cifrador Fernet: {e}")
        return None


def _encrypt_refresh_token(refresh_token: str) -> Optional[str]:
    """
    Cifra simétricamente el refresh_token con Fernet.
    """
    cipher = _get_fernet_cipher()
    if not cipher or not refresh_token:
        return None
    try:
        return cipher.encrypt(refresh_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        print(f"Error al cifrar refresh token: {e}")
        return None


def _decrypt_refresh_token(encrypted_token: str) -> Optional[str]:
    """
    Descifra el refresh_token con Fernet.
    """
    cipher = _get_fernet_cipher()
    if not cipher or not encrypted_token:
        return None
    try:
        return cipher.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        print(f"Error al descifrar refresh token: {e}")
        return None


def save_auth_session(
    session_id: str,
    user_id: str,
    user_email: str,
    refresh_token: str,
    access_token: Optional[str] = None,
    hours: int = 4
) -> bool:
    """
    Guarda la sesión persistente en Supabase (auth_sessions) usando service_role.
    - session_id se almacena como hash SHA-256.
    - refresh_token se almacena cifrado con Fernet.
    - No se guarda el access_token en la base de datos.
    """
    client = _get_service_role_client()
    if not client:
        return False

    enc_rt = _encrypt_refresh_token(refresh_token)
    if not enc_rt:
        return False

    sid_hash = _hash_session_id(session_id)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)

    try:
        client.table("auth_sessions").upsert({
            "session_id_hash": sid_hash,
            "user_id": str(user_id),
            "user_email": str(user_email),
            "encrypted_refresh_token": enc_rt,
            "expires_at": expires_at.isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Error en save_auth_session (service_role): {e}")
        return False


def get_auth_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Recupera una sesión activa por el session_id usando service_role.
    Valida la expiración de 4 horas y descifra el refresh_token con Fernet.
    """
    client = _get_service_role_client()
    if not client:
        return None

    sid_hash = _hash_session_id(session_id)
    try:
        res = (
            client.table("auth_sessions")
            .select("*")
            .eq("session_id_hash", sid_hash)
            .limit(1)
            .execute()
        )
        if not res.data or len(res.data) == 0:
            return None

        record = res.data[0]
        exp_str = record.get("expires_at")
        if exp_str:
            exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) >= exp_dt:
                delete_auth_session(session_id)
                return None

        raw_rt = _decrypt_refresh_token(record.get("encrypted_refresh_token", ""))
        if not raw_rt:
            return None

        return {
            "session_id": session_id,
            "user_id": record.get("user_id"),
            "user_email": record.get("user_email"),
            "refresh_token": raw_rt,
            "expires_at": exp_str
        }
    except Exception as e:
        print(f"Error en get_auth_session (service_role): {e}")
        return None


def update_auth_session_tokens(
    session_id: str,
    token_or_access: str,
    refresh_token: Optional[str] = None
) -> bool:
    """
    Actualiza el refresh_token cifrado tras la rotación de Supabase.
    Acepta update_auth_session_tokens(session_id, refresh_token)
    y update_auth_session_tokens(session_id, access_token, refresh_token) por compatibilidad.
    """
    actual_rt = refresh_token if refresh_token is not None else token_or_access
    client = _get_service_role_client()
    if not client or not actual_rt:
        return False

    enc_rt = _encrypt_refresh_token(actual_rt)
    if not enc_rt:
        return False

    sid_hash = _hash_session_id(session_id)
    try:
        client.table("auth_sessions").update({
            "encrypted_refresh_token": enc_rt
        }).eq("session_id_hash", sid_hash).execute()
        return True
    except Exception as e:
        print(f"Error en update_auth_session_tokens (service_role): {e}")
        return False


def delete_auth_session(session_id: str) -> bool:
    """
    Elimina una sesión activa de auth_sessions mediante el hash del session_id.
    """
    client = _get_service_role_client()
    if not client:
        return False

    sid_hash = _hash_session_id(session_id)
    try:
        client.table("auth_sessions").delete().eq("session_id_hash", sid_hash).execute()
        return True
    except Exception as e:
        print(f"Error en delete_auth_session (service_role): {e}")
        return False


def cleanup_expired_sessions() -> None:
    """
    Limpia todas las sesiones expiradas en auth_sessions usando service_role.
    """
    client = _get_service_role_client()
    if not client:
        return
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        client.table("auth_sessions").delete().lt("expires_at", now_iso).execute()
    except Exception as e:
        print(f"Error en cleanup_expired_sessions (service_role): {e}")


# ==============================================================================
# FASE: VERSIONES DE CV ADAPTADAS A VACANTES (cv_tailored_versions)
# ==============================================================================

def save_tailored_cv_version(
    version_name: str,
    tailored_cv: Dict[str, Any],
    application_id: Optional[int] = None,
    target_company: Optional[str] = None,
    target_position: Optional[str] = None,
    job_url: Optional[str] = None,
    job_description: Optional[str] = None,
    version_id: Optional[int] = None,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Dict[str, Any]:
    """
    Guarda o actualiza una versión de CV adaptada a una vacante específica en Supabase.
    Actualiza explícitamente el timestamp 'updated_at' en cada guardado.
    Garantiza aislamiento multi-tenant verificando .eq('user_id', uid).
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        raise PermissionError("No hay cliente de base de datos o usuario autenticado disponible.")

    now_iso = datetime.now(timezone.utc).isoformat()

    if version_id:
        payload = {
            "version_name": version_name.strip(),
            "tailored_cv": tailored_cv,
            "target_company": target_company.strip() if target_company else None,
            "target_position": target_position.strip() if target_position else None,
            "job_url": job_url.strip() if job_url else None,
            "job_description": job_description,
            "updated_at": now_iso
        }
        if application_id is not None:
            payload["application_id"] = application_id

        try:
            res = (
                client.table("cv_tailored_versions")
                .update(payload)
                .eq("id", version_id)
                .eq("user_id", uid)
                .execute()
            )
            if not res.data:
                raise RuntimeError(f"No se encontró la versión {version_id} para el usuario o no se pudo actualizar.")
            return res.data[0]
        except Exception as e:
            logger.error(f"Error al actualizar versión adaptada de CV en Supabase: {e}")
            raise RuntimeError(f"Error al actualizar versión adaptada de CV: {e}")
    else:
        payload = {
            "user_id": uid,
            "version_name": version_name.strip(),
            "application_id": application_id,
            "target_company": target_company.strip() if target_company else None,
            "target_position": target_position.strip() if target_position else None,
            "job_url": job_url.strip() if job_url else None,
            "job_description": job_description,
            "tailored_cv": tailored_cv,
            "created_at": now_iso,
            "updated_at": now_iso
        }
        try:
            res = (
                client.table("cv_tailored_versions")
                .insert(payload)
                .execute()
            )
            if not res.data:
                raise RuntimeError("No se recibieron datos tras insertar la versión adaptada de CV.")
            return res.data[0]
        except Exception as e:
            logger.error(f"Error al guardar nueva versión adaptada de CV en Supabase: {e}")
            raise RuntimeError(f"Error al guardar nueva versión adaptada de CV: {e}")


def get_tailored_cv_versions(
    application_id: Optional[int] = None,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> List[Dict[str, Any]]:
    """
    Obtiene todas las versiones adaptadas de CV pertenecientes al usuario autenticado,
    opcionalmente filtradas por application_id, ordenadas por fecha de creación descendente.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return []

    try:
        query = (
            client.table("cv_tailored_versions")
            .select("*")
            .eq("user_id", uid)
        )
        if application_id is not None:
            query = query.eq("application_id", application_id)

        res = query.order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error al listar versiones adaptadas de CV en Supabase: {e}")
        raise RuntimeError(f"Error al listar versiones adaptadas de CV: {e}")


def get_tailored_cv_version_by_id(
    version_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> Optional[Dict[str, Any]]:
    """
    Obtiene una versión adaptada específica por su ID, asegurando pertenencia al usuario.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        return None

    try:
        res = (
            client.table("cv_tailored_versions")
            .select("*")
            .eq("id", version_id)
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        return res.data
    except Exception as e:
        logger.error(f"Error al obtener versión adaptada de CV {version_id} en Supabase: {e}")
        raise RuntimeError(f"Error al obtener versión adaptada de CV: {e}")


def delete_tailored_cv_version(
    version_id: int,
    user_id: Optional[str] = None,
    client: Optional[Client] = None
) -> bool:
    """
    Elimina una versión adaptada de CV acotada estrictamente al usuario autenticado.
    """
    client = client or get_supabase_client()
    uid = user_id or get_current_user_id(client)
    if not client or not uid:
        raise PermissionError("No hay cliente de base de datos o usuario autenticado disponible.")

    try:
        res = (
            client.table("cv_tailored_versions")
            .delete()
            .eq("id", version_id)
            .eq("user_id", uid)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        logger.error(f"Error al eliminar versión adaptada de CV {version_id} en Supabase: {e}")
        raise RuntimeError(f"Error al eliminar versión adaptada de CV: {e}")


if __name__ == "__main__":
    print("Verificando conexión con Supabase...")
    apps_actuales = get_all_applications()
    print(f"Total de aplicaciones en Supabase: {len(apps_actuales)}")
