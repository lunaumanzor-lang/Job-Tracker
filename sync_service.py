# ==============================================================================
# PROYECTO: AI Job Application Tracker
# Módulo de Sincronización: SQLite <-> Supabase (sync_service.py)
# ==============================================================================

import sqlite3
from database import get_all_applications


def sync_sqlite_to_supabase(supabase_client, user_id: str, progress_callback=None) -> dict:
    """
    Sube todas las postulaciones de SQLite local (job_tracker.db)
    a la cuenta del usuario en Supabase.
    
    Evita duplicados verificando la combinación (company, position, application_date).
    """
    apps_locales = get_all_applications()
    if not apps_locales:
        return {"total": 0, "inserted": 0, "skipped": 0, "errors": []}

    # 1. Consultar registros ya existentes en Supabase para evitar duplicados
    existentes = set()
    try:
        res = supabase_client.table("applications").select("company, position, application_date").execute()
        for row in (res.data or []):
            c = str(row.get("company") or "").strip().lower()
            p = str(row.get("position") or "").strip().lower()
            d = str(row.get("application_date") or "").strip()
            existentes.add((c, p, d))
    except Exception:
        existentes = set()

    inserted = 0
    skipped = 0
    errors = []
    total = len(apps_locales)

    for idx, app in enumerate(apps_locales):
        c = str(app.get("company") or "").strip().lower()
        p = str(app.get("position") or "").strip().lower()
        d = str(app.get("application_date") or "").strip()
        clave = (c, p, d)

        if clave in existentes:
            skipped += 1
            if progress_callback:
                progress_callback(idx + 1, total, f"Omitiendo ya existente: {app.get('company')}")
            continue

        payload = {
            "user_id": user_id,
            "company": str(app.get("company") or "").strip(),
            "position": str(app.get("position") or "").strip(),
            "status": app.get("status") or "Applied",
            "application_date": app.get("application_date"),
            "salary": app.get("salary"),
            "work_mode": app.get("work_mode") or "TBD",
            "location": app.get("location"),
            "job_url": app.get("job_url"),
            "notes": app.get("notes")
        }

        # Incluir follow_up_date si existe
        if app.get("follow_up_date"):
            payload["follow_up_date"] = app.get("follow_up_date")

        try:
            supabase_client.table("applications").insert(payload).execute()
            inserted += 1
            existentes.add(clave)
        except Exception as ex:
            # Si el error es por follow_up_date no existiendo en la tabla remota, intentar sin ella
            if "follow_up_date" in str(ex).lower():
                payload.pop("follow_up_date", None)
                try:
                    supabase_client.table("applications").insert(payload).execute()
                    inserted += 1
                    existentes.add(clave)
                except Exception as ex2:
                    errors.append(f"{app.get('company')} - {app.get('position')}: {ex2}")
            else:
                errors.append(f"{app.get('company')} - {app.get('position')}: {ex}")

        if progress_callback:
            progress_callback(idx + 1, total, f"Subiendo: {app.get('company')} - {app.get('position')}")

    return {
        "total": total,
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors
    }
