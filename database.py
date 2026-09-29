# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 2: Base de Datos Relacional con SQLite (database.py)
# ==============================================================================

import os
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
        # TABLA 4: user_skills (Mi inventario de habilidades)
        # Guarda las tecnologías y habilidades que domino o estoy aprendiendo.
        # Esta tabla servirá de base de comparación para el analizador con IA.
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill TEXT NOT NULL UNIQUE,
            category TEXT,
            level TEXT DEFAULT 'Intermediate'
        );
        """)

        conn.commit()


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
    notes: Optional[str] = None
) -> bool:
    """
    Actualiza todos los campos editables de una aplicación existente en SQLite.
    """
    query = """
    UPDATE applications
    SET company = ?, position = ?, status = ?, application_date = ?,
        salary = ?, work_mode = ?, location = ?, job_url = ?, notes = ?
    WHERE id = ?;
    """
    params = (
        company, position, status, application_date,
        salary, work_mode, location, job_url, notes, app_id
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
# TEST RÁPIDO DEL MÓDULO (Para ejecutar con F5 o en terminal)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Inicializando base de datos y creando tablas...")
    create_tables()
    print("¡Tablas creadas exitosamente!")
    
    apps_actuales = get_all_applications()
    print(f"Total de aplicaciones en base de datos: {len(apps_actuales)}")
