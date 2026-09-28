# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 2: Importador y Limpiador de Excel a SQLite (import_excel.py)
# ==============================================================================

import os
import sqlite3
from datetime import datetime
import pandas as pd
from database import DB_NAME, get_connection, create_tables

# Ruta del archivo Excel de origen
EXCEL_FILE = "Applications 2026.xlsx"


# ------------------------------------------------------------------------------
# 1. FUNCIONES AUXILIARES DE LIMPIEZA Y NORMALIZACIÓN
# ------------------------------------------------------------------------------
# CONCEPTO - LIMPIEZA DE DATOS (Data Cleaning):
# Los datos del mundo real suelen tener valores nulos (NaN), inconsistencias
# de mayúsculas/minúsculas y formatos variados. Antes de guardarlos en una
# base de datos relacional, debemos transformar cada campo a su formato estándar.
# ------------------------------------------------------------------------------

def limpiar_work_mode(valor) -> str:
    """
    Normaliza modalidades de trabajo variadas a un estándar unificado:
    'Remote', 'Hybrid', 'On-site' o 'TBD'.
    """
    if pd.isna(valor):
        return "TBD"
    
    val = str(valor).strip().lower()
    if "remot" in val:
        return "Remote"
    elif "hibrid" in val or "hybrid" in val:
        return "Hybrid"
    elif "on-site" in val or "onsite" in val or "presencial" in val:
        return "On-site"
    else:
        return "TBD"


def limpiar_status(valor) -> str:
    """
    Normaliza el estado de la postulación:
    - Si está vacío (NaN), asigna 'Applied' (definido por el usuario).
    - Mantiene estados descriptivos como 'Recruiter Screen', 'Technical Interview',
      'Final Interview', 'Rejected', 'Ghosted'.
    """
    if pd.isna(valor) or str(valor).strip() == "":
        return "Applied"
    
    return str(valor).strip()


def limpiar_fecha(valor) -> str | None:
    """
    Convierte fechas a formato estándar ISO 'AAAA-MM-DD'.
    Reglas aplicadas:
    - 'me contactaron' -> Se ignora (None).
    - 'sep' -> Se asigna '2026-09-01'.
    - Timestamps válidos -> Se formatean a 'AAAA-MM-DD'.
    """
    if pd.isna(valor):
        return None
    
    # Si pandas ya lo detectó como fecha/timestamp
    if isinstance(valor, (pd.Timestamp, datetime)):
        return valor.strftime("%Y-%m-%d")
    
    texto = str(valor).strip().lower()
    
    if "me contactaron" in texto:
        return None
    elif "sep" in texto:
        return "2026-09-01"
    
    # Intentamos parsear otros posibles formatos de fecha en texto
    try:
        dt = pd.to_datetime(valor, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def construir_salario(row) -> str | None:
    """
    Construye una cadena descriptiva para el salario combinando
    expectativa, mínimos/máximos y moneda si están disponibles.
    """
    exp = row.get("salary_expectation")
    moneda = row.get("salary_currency")
    
    moneda_str = str(moneda).strip() if pd.notna(moneda) else "USD"
    
    if pd.notna(exp):
        return f"{exp} {moneda_str}".strip()
    
    s_min = row.get("salary_min")
    s_max = row.get("salary_max")
    if pd.notna(s_min) or pd.notna(s_max):
        return f"{s_min or ''}-{s_max or ''} {moneda_str}".strip()
        
    return None


# ------------------------------------------------------------------------------
# 2. PROCESO PRINCIPAL DE IMPORTACIÓN
# ------------------------------------------------------------------------------
# CONCEPTO - executemany():
# En lugar de hacer 72 viajes individuales a la base de datos (con 72 execute),
# executemany() envía todos los registros en un solo lote masivo optimizado,
# dentro de una sola transacción atómica (un solo commit).
# ------------------------------------------------------------------------------

def importar_desde_excel(limpiar_antes: bool = True):
    """
    Lee el archivo Excel, aplica la limpieza de datos e inserta masivamente
    en la tabla 'applications' de SQLite.
    
    Si limpiar_antes es True, limpia la tabla antes de importar para evitar
    duplicar los registros si se ejecuta varias veces.
    """
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: No se encontró el archivo '{EXCEL_FILE}' en la carpeta actual.")
        return

    print("=" * 60)
    print(f"Iniciando importación desde: {EXCEL_FILE}")
    print("=" * 60)

    # 1. Asegurar que las tablas existan
    create_tables()

    # Si se pide reiniciar la tabla para sincronización limpia
    if limpiar_antes:
        with get_connection() as conn:
            conn.execute("DELETE FROM applications;")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='applications';")
            conn.commit()

    # 2. Leer con pandas
    df = pd.read_excel(EXCEL_FILE)
    total_filas = len(df)
    print(f"Filas encontradas en el archivo: {total_filas}\n")

    registros_a_insertar = []
    filas_descartadas = 0

    # 3. Recorrer y limpiar cada fila
    for index, row in df.iterrows():
        # Validar posición: es el dato indispensable para identificar la vacante
        puesto = row.get("position")
        if pd.isna(puesto) or str(puesto).strip() == "":
            filas_descartadas += 1
            continue

        position = str(puesto).strip()

        # Limpiar empresa (si no viene, colocar 'TBD')
        empresa_raw = row.get("company")
        company = str(empresa_raw).strip() if pd.notna(empresa_raw) else "TBD"

        # Aplicar nuestras funciones de limpieza
        status = limpiar_status(row.get("status"))
        work_mode = limpiar_work_mode(row.get("work_mode"))
        app_date = limpiar_fecha(row.get("application_date"))
        salary = construir_salario(row)
        
        # Enlaces y notas
        job_url_raw = row.get("job_url")
        job_url = str(job_url_raw).strip() if pd.notna(job_url_raw) else None

        # Guardamos la descripción de trabajo y fuente en notes (vital para Fase 5 con IA)
        desc_raw = row.get("Job Description")
        desc = str(desc_raw).strip() if pd.notna(desc_raw) else ""
        source = str(row.get("source")).strip() if pd.notna(row.get("source")) else ""
        notes = f"[Fuente: {source}]\n{desc}".strip() if desc or source else None

        # Campos opcionales
        location = None
        recruiter = None
        follow_up_date = None

        # Agregamos la tupla con los valores en el orden exacto del INSERT
        registros_a_insertar.append((
            company,
            position,
            status,
            app_date,
            salary,
            work_mode,
            location,
            job_url,
            recruiter,
            notes,
            follow_up_date
        ))

    # 4. Inserción masiva en SQLite
    query = """
    INSERT INTO applications (
        company, position, status, application_date, salary,
        work_mode, location, job_url, recruiter, notes, follow_up_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, registros_a_insertar)
        conn.commit()

    # 5. Resumen final pedagógico
    print("=" * 60)
    print("RESUMEN DE IMPORTACIÓN")
    print("=" * 60)
    print(f"Total de filas leídas:        {total_filas}")
    print(f"Total de filas importadas:    {len(registros_a_insertar)}")
    print(f"Filas descartadas (sin cargo): {filas_descartadas}")
    print()

    # 6. Verificación directa consultando la base de datos
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) as cantidad FROM applications GROUP BY status ORDER BY cantidad DESC;")
        resumen_status = cursor.fetchall()

        print("Distribución en base de datos (SQLite) por status:")
        for fila in resumen_status:
            print(f"- {fila['status']}: {fila['cantidad']}")
    print("=" * 60)


if __name__ == "__main__":
    importar_desde_excel()
