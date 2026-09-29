# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 2: Base de Datos Relacional con SQLite (database.py)
# ==============================================================================

import os
import re
import sqlite3
from typing import List, Dict, Optional, Any

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
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """)

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

        conn.commit()


# ------------------------------------------------------------------------------
# CONSTANTES DE DOMINIO (Fase 5.1: My Profile)
# ------------------------------------------------------------------------------
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
    Elimina una aplicación por su ID. Gracias a ON DELETE CASCADE,
    sus entrevistas y skills asociadas también se limpiarán automáticamente.
    """
    query = "DELETE FROM applications WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (app_id,))
        conn.commit()
        return cursor.rowcount > 0


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
    for row in rows:
        val = str(row[0])
        # Ignoramos monedas no USD para no mezclar unidades (ej. CRC)
        if "CRC" in val:
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
# 8. OPERACIONES CRUD: USER PROFILE & USER SKILLS (Fase 5.1: My Profile)
# ------------------------------------------------------------------------------
def save_user_profile(
    full_name: Optional[str] = None,
    current_title: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    location: Optional[str] = None,
    summary: Optional[str] = None
) -> bool:
    """
    Inserta o actualiza el perfil único del usuario (id=1) usando UPSERT.
    """
    query = """
    INSERT INTO user_profile (id, full_name, current_title, email, phone, location, summary, updated_at)
    VALUES (1, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
    ON CONFLICT(id) DO UPDATE SET
        full_name = excluded.full_name,
        current_title = excluded.current_title,
        email = excluded.email,
        phone = excluded.phone,
        location = excluded.location,
        summary = excluded.summary,
        updated_at = datetime('now', 'localtime');
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (full_name, current_title, email, phone, location, summary))
        conn.commit()
        return True


def get_user_profile() -> Optional[Dict[str, Any]]:
    """
    Obtiene la información del perfil del usuario (id=1).
    """
    query = "SELECT * FROM user_profile WHERE id = 1;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        return dict(row) if row else None


def add_user_skill(
    skill_name: str,
    category: str,
    source: str = "Manual",
    proficiency: str = "Intermediate"
) -> bool:
    """
    Agrega o actualiza una habilidad en el inventario del usuario.
    Usa ON CONFLICT(skill_name) para actualizar la categoría y proficiency sin duplicar.
    """
    query = """
    INSERT INTO user_skills (skill_name, category, source, proficiency, date_added)
    VALUES (?, ?, ?, ?, date('now'))
    ON CONFLICT(skill_name) DO UPDATE SET
        category = excluded.category,
        proficiency = excluded.proficiency,
        source = CASE WHEN excluded.source = 'Manual' THEN 'Manual' ELSE user_skills.source END;
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (skill_name.strip(), category, source, proficiency))
        conn.commit()
        return True


def add_user_skills_bulk(skills: List[Dict[str, str]], source: str = "Resume") -> int:
    """
    Inserta múltiples habilidades extraídas por la IA en una sola transacción.
    Retorna la cantidad de habilidades procesadas.
    """
    insertados = 0
    query = """
    INSERT INTO user_skills (skill_name, category, source, proficiency, date_added)
    VALUES (?, ?, ?, ?, date('now'))
    ON CONFLICT(skill_name) DO UPDATE SET
        category = excluded.category,
        proficiency = excluded.proficiency;
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        for item in skills:
            name = item.get("skill_name", "").strip()
            cat = item.get("category", "DevOps")
            prof = item.get("proficiency", "Intermediate")
            if name:
                cursor.execute(query, (name, cat, source, prof))
                insertados += 1
        conn.commit()
    return insertados


def get_all_user_skills() -> List[Dict[str, Any]]:
    """
    Obtiene todas las habilidades del usuario ordenadas por categoría y nombre.
    """
    query = "SELECT * FROM user_skills ORDER BY category ASC, skill_name ASC;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def update_user_skill_proficiency(skill_id: int, new_proficiency: str) -> bool:
    """
    Modifica el nivel de dominio (proficiency) de una habilidad existente.
    """
    query = "UPDATE user_skills SET proficiency = ? WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (new_proficiency, skill_id))
        conn.commit()
        return cursor.rowcount > 0


def update_user_skill_category(skill_id: int, new_category: str) -> bool:
    """
    Modifica la categoría asignada a una habilidad existente.
    """
    query = "UPDATE user_skills SET category = ? WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (new_category, skill_id))
        conn.commit()
        return cursor.rowcount > 0



def delete_user_skill(skill_id: int) -> bool:
    """
    Elimina una habilidad del perfil del usuario por su ID.
    """
    query = "DELETE FROM user_skills WHERE id = ?;"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (skill_id,))
        conn.commit()
        return cursor.rowcount > 0



if __name__ == "__main__":
    print("Inicializando base de datos y creando tablas...")
    create_tables()
    print("¡Tablas creadas exitosamente!")
    
    apps_actuales = get_all_applications()
    print(f"Total de aplicaciones en base de datos: {len(apps_actuales)}")

