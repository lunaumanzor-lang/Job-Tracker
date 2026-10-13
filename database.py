# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 2: Base de Datos Relacional con SQLite (database.py)
# ==============================================================================

import os
import re
import sqlite3
from typing import List, Dict, Optional, Any
from supabase import Client

# Directorio base del proyecto (donde reside este archivo .py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ruta absoluta de la base de datos local
DB_NAME = os.path.join(BASE_DIR, "job_tracker.db")



# ------------------------------------------------------------------------------
# CONEXIÓN Y CONFIGURACIÓN
# ------------------------------------------------------------------------------
def get_connection():
    """
    Crea y retorna una conexión a la base de datos SQLite.
    
    CONCEPTO - row_factory:
    Por defecto, sqlite3 devuelve cada fila como una tupla: (1, 'Google', ...).
    Al activar sqlite3.Row, podemos acceder a las columnas tanto por índice
    como por su NOMBRE exacto: fila['company'], lo cual hace el código mucho
    más legible y reduce errores.
    
    CONCEPTO - PRAGMA foreign_keys = ON:
    Por compatibilidad histórica, SQLite viene con el soporte de llaves foráneas
    desactivado por defecto. Es una buena práctica activarlo en cada conexión
    para garantizar la integridad referencial de los datos.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ------------------------------------------------------------------------------
# 1. CREACIÓN DEL SCHEMA (Tablas Relacionales)
# ------------------------------------------------------------------------------
def create_tables():
    """
    Crea las 4 tablas principales del sistema si no existen:
    1. applications  -> Registro principal de cada postulación
    2. interviews    -> Entrevistas vinculadas a una postulación (1 a N)
    3. skills        -> Habilidades requeridas por el puesto de trabajo (1 a N)
    4. user_skills   -> Habilidades reales del candidato (mi perfil)
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # ----------------------------------------------------------------------
        # TABLA 1: applications
        # Representa la entidad raíz. Cada fila es una postulación individual.
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            position TEXT NOT NULL,
            application_date TEXT,
            status TEXT NOT NULL DEFAULT 'Applied',
            salary TEXT,
            work_mode TEXT,
            location TEXT,
            job_url TEXT,
            recruiter TEXT,
            notes TEXT,
            follow_up_date TEXT
        );
        """)

        # ----------------------------------------------------------------------
        # TABLA 2: interviews
        # Relación 1 a N: Una postulación puede tener múltiples etapas de entrevista
        # (ej. HR Screen, Technical Interview, Hiring Manager).
        # FOREIGN KEY asegura que application_id pertenezca a una aplicación real.
        # ON DELETE CASCADE: Si se borra la postulación, se borran sus entrevistas.
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            interview_type TEXT NOT NULL,
            notes TEXT,
            result TEXT DEFAULT 'Pending',
            FOREIGN KEY (application_id) REFERENCES applications (id) ON DELETE CASCADE
        );
        """)

        # ----------------------------------------------------------------------
        # TABLA 3: skills (Skills de la oferta laboral)
        # Relación 1 a N: Una vacante pide múltiples skills técnicas o blandas.
        # match_status: 'Match', 'Missing' o 'Learning' (lo usaremos con la IA en Fase 5).
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            skill TEXT NOT NULL,
            match_status TEXT DEFAULT 'Pending',
            FOREIGN KEY (application_id) REFERENCES applications (id) ON DELETE CASCADE
        );
        """)

        # ----------------------------------------------------------------------
        # TABLA 4: user_profile (Perfil del Usuario / Master Profile)
        # Guarda información general del usuario (un solo registro, id=1).
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            full_name TEXT,
            current_title TEXT,
            email TEXT,
            phone TEXT,
            location TEXT,
            summary TEXT,
            preferred_language TEXT DEFAULT NULL,
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)

        # Migración Fase 6.1: asegurar que user_profile tenga la columna preferred_language
        cursor.execute("PRAGMA table_info(user_profile);")
        profile_cols = [col[1] for col in cursor.fetchall()]
        if profile_cols and "preferred_language" not in profile_cols:
            cursor.execute("ALTER TABLE user_profile ADD COLUMN preferred_language TEXT DEFAULT NULL;")

        # ----------------------------------------------------------------------
        # TABLA 5: user_skills (Mi inventario maestro de habilidades)
        # Guarda las tecnologías y habilidades que domino, su procedencia y nivel.
        # ----------------------------------------------------------------------
        cursor.execute("PRAGMA table_info(user_skills);")
        cols = [col[1] for col in cursor.fetchall()]
        if cols and "skill_name" not in cols:
            cursor.execute("DROP TABLE user_skills;")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            source TEXT DEFAULT 'Manual',
            proficiency TEXT DEFAULT 'Intermediate',
            date_added TEXT DEFAULT (date('now'))
        );
        """)

        # ----------------------------------------------------------------------
        # FASE 5.7: REINICIO LIMPIO DE RESUME_BULLETS Y NUEVAS TABLAS
        # 1. experience_entries: experiencia laboral estructurada (fechas normalizadas)
        # 2. resume_bullets: bullets con foreign key experience_id
        # 3. education_entries: historial educativo y certificaciones
        # ----------------------------------------------------------------------
        cursor.execute("PRAGMA table_info(resume_bullets);")
        cols_b = [col[1] for col in cursor.fetchall()]
        if cols_b and "section" in cols_b:
            cursor.execute("DROP TABLE IF EXISTS resume_bullets;")
            cursor.execute("DROP TABLE IF EXISTS experience_entries;")
            cursor.execute("DROP TABLE IF EXISTS education_entries;")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS experience_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            position TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            is_current INTEGER DEFAULT 0,
            order_index INTEGER DEFAULT 0
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS resume_bullets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experience_id INTEGER NOT NULL,
            bullet_text TEXT NOT NULL,
            original_text TEXT NOT NULL,
            current_text TEXT NOT NULL,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY (experience_id) REFERENCES experience_entries (id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS education_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institution TEXT NOT NULL,
            credential TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            order_index INTEGER DEFAULT 0
        );
        """)

        # ----------------------------------------------------------------------
        # TABLA: auth_sessions (Persistencia de sesión 4 horas)
        # Permite mantener la sesión activa entre refrescos (F5) con validez de 4 horas
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_email TEXT NOT NULL,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        """)

    conn.commit()


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
# 2. OPERACIONES CRUD: CREATE (Insertar)
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
    follow_up_date: Optional[str] = None
) -> int:
    """
    Inserta una nueva aplicación en la base de datos usando consultas parametrizadas (?)
    para evitar inyecciones SQL.
    
    Retorna:
        El ID autogenerado del nuevo registro insertado.
    """
    query = """
    INSERT INTO applications (
        company, position, status, application_date, salary,
        work_mode, location, job_url, recruiter, notes, follow_up_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    params = (
        company, position, status, application_date, salary,
        work_mode, location, job_url, recruiter, notes, follow_up_date
    )
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid


def insert_application_skills(application_id: int, skills: List[Dict[str, str]]) -> int:
    """
    Inserta las habilidades asociadas a una vacante con su estado de coincidencia ('strong', 'partial', 'missing').
    
    Parámetros:
        application_id: ID de la aplicación en la tabla applications.
        skills: Lista de diccionarios, ej. [{"skill": "Python", "match_status": "strong"}]
        
    Retorna:
        Cantidad de habilidades insertadas.
    """
    query = """
    INSERT INTO skills (application_id, skill, match_status)
    VALUES (?, ?, ?);
    """
    insertados = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for item in skills:
            nombre = item.get("skill", "").strip()
            status = item.get("match_status", "strong").strip()
            if nombre:
                cursor.execute(query, (application_id, nombre, status))
                insertados += 1
        conn.commit()
    return insertados


def get_skills_by_application(application_id: int) -> List[Dict[str, Any]]:
    """
    Recupera todas las habilidades vinculadas a una postulación específica,
    indicando el estado de match ('strong', 'partial', 'missing').
    """
    query = "SELECT id, application_id, skill, match_status FROM skills WHERE application_id = ? ORDER BY id ASC;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (application_id,))
        return [dict(row) for row in cursor.fetchall()]


# ------------------------------------------------------------------------------
# 3. OPERACIONES CRUD: READ (Consultar)
# ------------------------------------------------------------------------------
def get_all_applications() -> List[Dict[str, Any]]:
    """
    Obtiene todas las aplicaciones ordenadas por ID de forma descendente.
    Retorna una lista de diccionarios limpios.
    """
    query = "SELECT * FROM applications ORDER BY id DESC;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        # Convertimos sqlite3.Row a dict estándar de Python
        return [dict(row) for row in rows]


def get_application_by_id(app_id: int) -> Optional[Dict[str, Any]]:
    """
    Busca una aplicación específica por su identificador primario (id).
    """
    query = "SELECT * FROM applications WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (app_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ------------------------------------------------------------------------------
# 4. OPERACIONES CRUD: UPDATE (Actualizar)
# ------------------------------------------------------------------------------
def update_application_status(app_id: int, new_status: str) -> bool:
    """
    Actualiza el estado de una aplicación existente (ej. de 'Applied' a 'Interview').
    """
    query = "UPDATE applications SET status = ? WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (new_status, app_id))
        conn.commit()
        return cursor.rowcount > 0


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
    follow_up_date: Optional[str] = None
) -> bool:
    """
    Actualiza todos los campos editables de una aplicación existente en SQLite,
    incluyendo la fecha de seguimiento (follow_up_date).
    """
    query = """
    UPDATE applications
    SET company = ?, position = ?, status = ?, application_date = ?,
        salary = ?, work_mode = ?, location = ?, job_url = ?, notes = ?, follow_up_date = ?
    WHERE id = ?;
    """
    params = (
        company, position, status, application_date,
        salary, work_mode, location, job_url, notes, follow_up_date, app_id
    )
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount > 0




# ------------------------------------------------------------------------------
# 5. OPERACIONES CRUD: DELETE (Eliminar)
# ------------------------------------------------------------------------------
def delete_application(app_id: int) -> bool:
    """
    Elimina una aplicación por su ID y reacomoda los IDs de todas las aplicaciones
    posteriores (id = id - 1) para mantener una secuencia continua sin huecos.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("DELETE FROM applications WHERE id = ?;", (app_id,))
        deleted = cursor.rowcount > 0
        if deleted:
            cursor.execute("DELETE FROM skills WHERE application_id = ?;", (app_id,))
            cursor.execute("DELETE FROM interviews WHERE application_id = ?;", (app_id,))
            cursor.execute("UPDATE applications SET id = id - 1 WHERE id > ?;", (app_id,))
            cursor.execute("UPDATE skills SET application_id = application_id - 1 WHERE application_id > ?;", (app_id,))
            cursor.execute("UPDATE interviews SET application_id = application_id - 1 WHERE application_id > ?;", (app_id,))
            cursor.execute("UPDATE sqlite_sequence SET seq = COALESCE((SELECT MAX(id) FROM applications), 0) WHERE name = 'applications';")
        cursor.execute("PRAGMA foreign_keys = ON;")
        conn.commit()
        return deleted


# ------------------------------------------------------------------------------
# 6. CONSULTAS DE AGREGACIÓN PARA EL DASHBOARD (Sub-fase 4a)
# ------------------------------------------------------------------------------
def get_dashboard_counts() -> Dict[str, int]:
    """
    Ejecuta consultas de agregación SQL (COUNT) para calcular las 5 métricas clave:
    1. Total applications: conteo absoluto de postulaciones.
    2. Interviews: según la regla de negocio (Recruiter Screen, Technical Interview, Final Interview).
    3. Offers: ofertas recibidas.
    4. Rejections: postulaciones rechazadas.
    5. Follow-ups: postulaciones con fecha de seguimiento asignada que esté próxima o vencida.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Total Applications (COUNT(*) cuenta todas las filas)
        cursor.execute("SELECT COUNT(*) FROM applications;")
        total_apps = cursor.fetchone()[0]

        # 2. Interviews (Cláusula IN para múltiples valores)
        cursor.execute("""
            SELECT COUNT(*) FROM applications
            WHERE status IN ('Recruiter Screen', 'Technical Interview', 'Final Interview');
        """)
        interviews = cursor.fetchone()[0]

        # 3. Offers
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'Offer';")
        offers = cursor.fetchone()[0]

        # 4. Rejections
        cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'Rejected';")
        rejections = cursor.fetchone()[0]

        # 5. Follow-ups: con fecha de seguimiento definida y vencida o para hoy
        cursor.execute("""
            SELECT COUNT(*) FROM applications
            WHERE follow_up_date IS NOT NULL
              AND follow_up_date != ''
              AND date(follow_up_date) <= date('now');
        """)
        follow_ups = cursor.fetchone()[0]

        return {
            "total_applications": total_apps,
            "interviews": interviews,
            "offers": offers,
            "rejections": rejections,
            "follow_ups": follow_ups
        }


def get_status_breakdown() -> Dict[str, int]:
    """
    Obtiene la cantidad de aplicaciones agrupadas por cada estado (Status).
    
    CONCEPTO SQL - GROUP BY:
    En lugar de hacer 7 consultas con WHERE para cada estado, GROUP BY le pide
    al motor de base de datos que agrupe las filas que tengan el mismo 'status'
    y aplique COUNT(*) a cada uno de esos grupos en una sola operación de alto rendimiento.
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
    # Inicializamos el diccionario con 0 para que todos los estados existan
    breakdown = {estado: 0 for estado in estados_base}

    query = "SELECT status, COUNT(*) FROM applications GROUP BY status;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        for row in cursor.fetchall():
            status_name = row[0]
            count = row[1]
            breakdown[status_name] = count

    return breakdown


# ------------------------------------------------------------------------------
# 7. CONSULTAS Y CÁLCULOS ESTADÍSTICOS (Fase 7: Statistics)
# ------------------------------------------------------------------------------
def get_work_mode_breakdown() -> Dict[str, int]:
    """
    Obtiene el número de aplicaciones por modalidad de trabajo (Remote, Hybrid, On-site).
    Utiliza SQL GROUP BY work_mode.
    """
    modalidades = {"Remote": 0, "Hybrid": 0, "On-site": 0}
    query = """
    SELECT work_mode, COUNT(*) 
    FROM applications 
    WHERE work_mode IS NOT NULL AND work_mode != ''
    GROUP BY work_mode;
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        for row in cursor.fetchall():
            mode, count = row[0], row[1]
            if mode in modalidades:
                modalidades[mode] = count
            else:
                modalidades[mode or "Otro"] = count
    return modalidades


def get_salary_statistics() -> Dict[str, Any]:
    """
    Calcula métricas salariales (mínimo, promedio, máximo y cantidad de registros válidos).
    
    Lógica de limpieza y cálculo:
    - Extrae únicamente valores numéricos en USD (ignorando monedas locales como CRC o campos vacíos).
    - Si una fila tiene un rango salarial (ej. '4500-5000 USD'), calcula el punto medio del rango.
    - Ignora valores no numéricos ('TBD', vacíos) para no alterar el promedio.
    """
    query = "SELECT salary FROM applications WHERE salary IS NOT NULL AND salary != '';"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

    salarios_validos = []
    non_usd_codes = ["CRC", "EUR", "GBP", "CAD", "MXN", "GTQ", "HNL", "NIO", "PAB", "DOP", "BRL", "COP", "ARS", "CLP", "PEN", "UYU", "BOB", "PYG", "VES", "CHF", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "BGN", "ISK", "TRY"]
    for row in rows:
        val = str(row[0])
        val_upper = val.upper()
        # Ignoramos monedas explícitamente no USD para no mezclar unidades (ej. CRC, EUR, etc.)
        if any(c in val_upper for c in non_usd_codes):
            continue
        # Buscamos números mayores o iguales a 500 para evitar números de versión o ruido
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", val.replace(",", "")) if float(n) >= 500]
        if nums:
            # Promedio del rango o el valor individual
            salarios_validos.append(sum(nums) / len(nums))

    if not salarios_validos:
        return {"min": 0.0, "avg": 0.0, "max": 0.0, "count": 0}

    return {
        "min": round(min(salarios_validos), 2),
        "avg": round(sum(salarios_validos) / len(salarios_validos), 2),
        "max": round(max(salarios_validos), 2),
        "count": len(salarios_validos)
    }


def get_monthly_applications() -> List[Dict[str, Any]]:
    """
    Obtiene la cantidad de postulaciones agrupadas cronológicamente por mes (YYYY-MM).
    
    CONCEPTO SQL:
    Usa la función substr(application_date, 1, 7) para extraer el año y mes ('2026-04'),
    agrupa por esa fecha truncada con GROUP BY y ordena cronológicamente con ORDER BY.
    """
    query = """
    SELECT substr(application_date, 1, 7) as mes, COUNT(*) as total
    FROM applications 
    WHERE application_date IS NOT NULL AND application_date != ''
    GROUP BY mes
    ORDER BY mes ASC;
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return [{"mes": row[0], "total": row[1]} for row in cursor.fetchall()]


def get_monthly_interviews() -> List[Dict[str, Any]]:
    """
    Obtiene la cantidad de entrevistas agrupadas por mes.
    Aproximación definida en la Fase 4: utiliza application_date como proxy
    para aplicaciones cuyo estado es una entrevista ('Recruiter Screen',
    'Technical Interview', 'Final Interview').
    """
    query = """
    SELECT substr(application_date, 1, 7) as mes, COUNT(*) as total
    FROM applications 
    WHERE status IN ('Recruiter Screen', 'Technical Interview', 'Final Interview')
      AND application_date IS NOT NULL AND application_date != ''
    GROUP BY mes
    ORDER BY mes ASC;
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return [{"mes": row[0], "total": row[1]} for row in cursor.fetchall()]


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
# GESTIÓN DE SESIONES PERSISTENTES (4 HORAS)
# ------------------------------------------------------------------------------
def save_auth_session(session_id: str, user_id: str, user_email: str, access_token: str, refresh_token: str, hours: int = 4) -> None:
    """
    Guarda o actualiza una sesión de usuario con expiración de 4 horas.
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    expires_at = now + timedelta(hours=hours)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO auth_sessions (
                session_id, user_id, user_email, access_token, refresh_token, created_at, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            session_id,
            user_id,
            user_email,
            access_token,
            refresh_token,
            now.isoformat(),
            expires_at.isoformat()
        ))
        conn.commit()


def get_auth_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene la sesión si existe y no ha expirado. Si expiró, la elimina automáticamente.
    """
    from datetime import datetime
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, user_id, user_email, access_token, refresh_token, created_at, expires_at
            FROM auth_sessions
            WHERE session_id = ?;
        """, (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        expires_at_str = row["expires_at"]
        try:
            exp_dt = datetime.fromisoformat(expires_at_str)
            if datetime.now() > exp_dt:
                cursor.execute("DELETE FROM auth_sessions WHERE session_id = ?;", (session_id,))
                conn.commit()
                return None
        except Exception:
            return None
        return dict(row)


def update_auth_session_tokens(session_id: str, access_token: str, refresh_token: str) -> None:
    """
    Actualiza los tokens de acceso y refresco de una sesión existente.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE auth_sessions
            SET access_token = ?, refresh_token = ?
            WHERE session_id = ?;
        """, (access_token, refresh_token, session_id))
        conn.commit()


def delete_auth_session(session_id: str) -> None:
    """
    Elimina una sesión activa (por ejemplo, al hacer logout).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM auth_sessions WHERE session_id = ?;", (session_id,))
        conn.commit()


def cleanup_expired_sessions() -> None:
    """
    Limpia todas las sesiones expiradas en la base de datos.
    """
    from datetime import datetime
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM auth_sessions
            WHERE expires_at < ?;
        """, (datetime.now().isoformat(),))
        conn.commit()



if __name__ == "__main__":
    print("Inicializando base de datos y creando tablas...")
    create_tables()
    print("¡Tablas creadas exitosamente!")
    
    apps_actuales = get_all_applications()
    print(f"Total de aplicaciones en base de datos: {len(apps_actuales)}")

