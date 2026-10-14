# ==============================================================================
# PROYECTO: Smart Job Tracker
# Script de Migración Idempotente: SQLite -> Supabase (migrate_to_supabase.py)
# ==============================================================================

import os
import sys
import sqlite3
import getpass
import argparse
import toml
from typing import Dict, Any, List
from supabase import create_client, Client


def normalize(val: Any) -> str:
    """Normaliza texto para comparaciones seguras de unicidad."""
    if val is None:
        return ""
    return str(val).strip().lower()


def parse_args():
    parser = argparse.ArgumentParser(description="Migración segura e idempotente de SQLite a Supabase.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula toda la migración sin escribir ni modificar nada en Supabase."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    is_dry_run = args.dry_run

    print("\n" + "=" * 75)
    print(" 🚀 MIGRACIÓN DE DATOS A SUPABASE" + (" [MODO DRY-RUN / SIMULACIÓN]" if is_dry_run else ""))
    print("=" * 75)
    if is_dry_run:
        print("ℹ️  Modo --dry-run ACTIVO: Se verificarán existencias pero NO se escribirá nada en Supabase.\n")

    # --------------------------------------------------------------------------
    # 1. CONEXIÓN LOCAL A SQLITE (job_tracker.db)
    # --------------------------------------------------------------------------
    db_path = os.path.join(os.path.dirname(__file__), "job_tracker.db")
    if not os.path.exists(db_path):
        print(f"❌ Error crítico: No se encontró la base de datos local en '{db_path}'")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --------------------------------------------------------------------------
    # 2. CONEXIÓN Y AUTENTICACIÓN CON SUPABASE
    # --------------------------------------------------------------------------
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        print(f"❌ Error crítico: No se encontró el archivo de secretos en '{secrets_path}'")
        sys.exit(1)

    secrets = toml.load(secrets_path)
    url = secrets.get("SUPABASE_URL")
    key = secrets.get("SUPABASE_KEY")

    if not url or not key:
        print("❌ Error crítico: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml")
        sys.exit(1)

    supabase: Client = create_client(url, key)

    email = os.environ.get("SUPABASE_EMAIL")
    password = os.environ.get("SUPABASE_PASSWORD")

    if not email:
        email = input("Ingresa tu correo registrado en Supabase: ").strip()
    if not password:
        password = getpass.getpass("Ingresa tu contraseña de Supabase: ").strip()

    print("\n🔐 Autenticando con Supabase para operar bajo políticas RLS...")
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = auth_res.user
        if not user or not auth_res.session:
            print("❌ Error de autenticación: No se obtuvo usuario válido.")
            sys.exit(1)
        supabase.postgrest.auth(auth_res.session.access_token)
        user_id = str(user.id)
        print(f"✅ Autenticado exitosamente como: {user.email} (UUID: {user_id})\n")
    except Exception as e:
        print(f"❌ Falló la autenticación en Supabase: {e}")
        sys.exit(1)

    # Contadores de auditoría y resultado
    stats = {
        "applications_total": 0,
        "applications_recruiter_updated": 0,
        "applications_recruiter_skipped": 0,
        "profile_migrated": 0,
        "profile_skipped": 0,
        "skills_migrated": 0,
        "skills_skipped": 0,
        "education_migrated": 0,
        "education_skipped": 0,
        "experience_migrated": 0,
        "experience_skipped": 0,
        "bullets_migrated": 0,
        "bullets_skipped": 0,
    }

    # ==========================================================================
    # PASO 1: APLICACIONES (applications) Y COPIA DE RECRUITER
    # ==========================================================
    print("-" * 75)
    print("📦 [1/6] Sincronizando campo 'recruiter' en 85 Postulaciones...")
    print("-" * 75)

    cur.execute("SELECT * FROM applications ORDER BY id ASC")
    local_apps = cur.fetchall()
    stats["applications_total"] = len(local_apps)

    res_cloud_apps = supabase.table("applications").select("id, company, position, application_date, recruiter").execute()
    cloud_apps = res_cloud_apps.data or []

    # Diccionario en nube por clave natural (empresa, puesto, fecha)
    cloud_app_map = {}
    for ca in cloud_apps:
        k = (normalize(ca.get("company")), normalize(ca.get("position")), str(ca.get("application_date") or "").strip())
        cloud_app_map[k] = ca

    for la in local_apps:
        k = (normalize(la["company"]), normalize(la["position"]), str(la["application_date"] or "").strip())
        loc_recruiter = (la["recruiter"] or "").strip() if "recruiter" in la.keys() else ""

        if k in cloud_app_map:
            c_app = cloud_app_map[k]
            cloud_recruiter = (c_app.get("recruiter") or "").strip()

            if loc_recruiter and loc_recruiter != cloud_recruiter:
                if is_dry_run:
                    print(f"  [DRY-RUN] Actualizaría recruiter='{loc_recruiter}' en: {la['company']} ({la['position']})")
                else:
                    supabase.table("applications").update({"recruiter": loc_recruiter}).eq("id", c_app["id"]).execute()
                stats["applications_recruiter_updated"] += 1
            else:
                stats["applications_recruiter_skipped"] += 1
        else:
            # Si no existe en la nube, se crea la postulación completa
            new_app_payload = {
                "user_id": user_id,
                "company": la["company"],
                "position": la["position"],
                "application_date": la["application_date"],
                "status": la["status"] or "Applied",
                "salary": la["salary"],
                "work_mode": la["work_mode"] or "TBD",
                "location": la["location"],
                "job_url": la["job_url"],
                "recruiter": loc_recruiter or None,
                "notes": la["notes"],
                "follow_up_date": la["follow_up_date"]
            }
            if is_dry_run:
                print(f"  [DRY-RUN] Insertaría postulación faltante: {la['company']} ({la['position']})")
            else:
                supabase.table("applications").insert(new_app_payload).execute()
            if loc_recruiter:
                stats["applications_recruiter_updated"] += 1

    print(f"  -> Evaluadas: {stats['applications_total']} postulaciones. Actualizadas con recruiter: {stats['applications_recruiter_updated']} | Al día: {stats['applications_recruiter_skipped']}")

    # ==========================================================================
    # PASO 2: PERFIL PROFESIONAL (user_profile)
    # ==========================================================================
    print("\n" + "-" * 75)
    print("👤 [2/6] Migrando Perfil Profesional (user_profile)...")
    print("-" * 75)

    cur.execute("SELECT * FROM user_profile LIMIT 1")
    local_profile = cur.fetchone()

    res_cloud_prof = supabase.table("user_profile").select("*").execute()
    cloud_profiles = res_cloud_prof.data or []

    if local_profile:
        prof_payload = {
            "user_id": user_id,
            "full_name": local_profile["full_name"],
            "current_title": local_profile["current_title"],
            "email": local_profile["email"],
            "phone": local_profile["phone"],
            "location": local_profile["location"],
            "summary": local_profile["summary"],
            "preferred_language": local_profile["preferred_language"] or "es"
        }

        if cloud_profiles:
            print("  ℹ️  El perfil ya existe en Supabase. Se preserva sin duplicar.")
            stats["profile_skipped"] += 1
        else:
            if is_dry_run:
                print(f"  [DRY-RUN] Insertaría user_profile para: {local_profile['full_name']}")
            else:
                supabase.table("user_profile").insert(prof_payload).execute()
            stats["profile_migrated"] += 1
    else:
        print("  ℹ️  No hay registros locales en user_profile.")

    # ==========================================================================
    # PASO 3: HABILIDADES (user_skills)
    # ==========================================================================
    print("\n" + "-" * 75)
    print("🛠️  [3/6] Migrando Habilidades Técnicas (user_skills)...")
    print("-" * 75)

    cur.execute("SELECT * FROM user_skills ORDER BY id ASC")
    local_skills = cur.fetchall()

    res_cloud_skills = supabase.table("user_skills").select("skill_name, category").execute()
    existing_skills = {
        (normalize(s.get("skill_name")), normalize(s.get("category")))
        for s in (res_cloud_skills.data or [])
    }

    for sk in local_skills:
        k = (normalize(sk["skill_name"]), normalize(sk["category"]))
        if k in existing_skills:
            stats["skills_skipped"] += 1
        else:
            skill_payload = {
                "user_id": user_id,
                "skill_name": sk["skill_name"],
                "category": sk["category"],
                "source": sk["source"] or "Manual",
                "proficiency": sk["proficiency"] or "Intermediate",
                "date_added": sk["date_added"]
            }
            if is_dry_run:
                pass
            else:
                supabase.table("user_skills").insert(skill_payload).execute()
                existing_skills.add(k)
            stats["skills_migrated"] += 1

    print(f"  -> Total locales: {len(local_skills)} | Migradas: {stats['skills_migrated']} | Ya existentes (omitidas): {stats['skills_skipped']}")

    # ==========================================================================
    # PASO 4: EDUCACIÓN (education_entries)
    # ==========================================================================
    print("\n" + "-" * 75)
    print("🎓 [4/6] Migrando Educación y Títulos (education_entries)...")
    print("-" * 75)

    cur.execute("SELECT * FROM education_entries ORDER BY order_index ASC, id ASC")
    local_edu = cur.fetchall()

    res_cloud_edu = supabase.table("education_entries").select("institution, credential").execute()
    existing_edu = {
        (normalize(e.get("institution")), normalize(e.get("credential")))
        for e in (res_cloud_edu.data or [])
    }

    for ed in local_edu:
        k = (normalize(ed["institution"]), normalize(ed["credential"]))
        if k in existing_edu:
            stats["education_skipped"] += 1
        else:
            edu_payload = {
                "user_id": user_id,
                "institution": ed["institution"],
                "credential": ed["credential"],
                "start_date": ed["start_date"],
                "end_date": ed["end_date"],
                "order_index": ed["order_index"] or 0
            }
            if is_dry_run:
                print(f"  [DRY-RUN] Insertaría educación: {ed['credential']} en {ed['institution']}")
            else:
                supabase.table("education_entries").insert(edu_payload).execute()
                existing_edu.add(k)
            stats["education_migrated"] += 1

    print(f"  -> Total locales: {len(local_edu)} | Migradas: {stats['education_migrated']} | Ya existentes (omitidas): {stats['education_skipped']}")

    # ==========================================================================
    # PASO 5: EXPERIENCIAS LABORALES (experience_entries) + CONSTRUCCIÓN MAPA IDs
    # ==========================================================================
    print("\n" + "-" * 75)
    print("💼 [5/6] Migrando Experiencias Laborales (experience_entries) con Mapa de IDs...")
    print("-" * 75)

    cur.execute("SELECT * FROM experience_entries ORDER BY order_index ASC, id ASC")
    local_exp = cur.fetchall()

    res_cloud_exp = supabase.table("experience_entries").select("id, company, position").execute()
    cloud_exp_list = res_cloud_exp.data or []

    # Mapa de búsqueda en nube por clave (company, position) -> id de Supabase
    cloud_exp_map = {
        (normalize(e.get("company")), normalize(e.get("position"))): e.get("id")
        for e in cloud_exp_list
    }

    # Diccionario relacional: { id_local_sqlite: id_remoto_supabase }
    exp_id_map: Dict[int, int] = {}

    for exp in local_exp:
        old_id = exp["id"]
        k = (normalize(exp["company"]), normalize(exp["position"]))

        if k in cloud_exp_map:
            # Ya existe en Supabase: enlazamos su ID existente al mapa
            remote_id = cloud_exp_map[k]
            exp_id_map[old_id] = remote_id
            stats["experience_skipped"] += 1
            print(f"  ℹ️  Experiencia ya existe: {exp['company']} ({exp['position']}) -> Mapeada a ID Supabase #{remote_id}")
        else:
            exp_payload = {
                "user_id": user_id,
                "company": exp["company"],
                "position": exp["position"],
                "start_date": exp["start_date"],
                "end_date": exp["end_date"],
                "is_current": bool(exp["is_current"]),
                "order_index": exp["order_index"] or 0
            }
            if is_dry_run:
                # En simulación asignamos un ID ficticio para probar el flujo de bullets
                simulated_id = 9000 + old_id
                exp_id_map[old_id] = simulated_id
                print(f"  [DRY-RUN] Insertaría experiencia: {exp['company']} ({exp['position']}) -> ID simulado #{simulated_id}")
            else:
                res_ins = supabase.table("experience_entries").insert(exp_payload).execute()
                new_remote_id = res_ins.data[0]["id"]
                exp_id_map[old_id] = new_remote_id
                cloud_exp_map[k] = new_remote_id
                print(f"  ✅ Experiencia insertada: {exp['company']} ({exp['position']}) -> Asignado ID Supabase #{new_remote_id}")
            stats["experience_migrated"] += 1

    print(f"  -> Total locales: {len(local_exp)} | Migradas: {stats['experience_migrated']} | Reusadas existentes: {stats['experience_skipped']}")
    print(f"  🔗 Mapa relacional generado: {exp_id_map}")

    # ==========================================================================
    # PASO 6: VIÑETAS DE EXPERIENCIA (resume_bullets) RE-LIGADAS POR MAPA DE IDs
    # ==========================================================================
    print("\n" + "-" * 75)
    print("📝 [6/6] Migrando Viñetas de Logros (resume_bullets) re-ligadas a IDs Supabase...")
    print("-" * 75)

    cur.execute("SELECT * FROM resume_bullets ORDER BY experience_id ASC, order_index ASC, id ASC")
    local_bullets = cur.fetchall()

    res_cloud_bullets = supabase.table("resume_bullets").select("experience_id, bullet_text").execute()
    existing_bullets = {
        (b.get("experience_id"), normalize(b.get("bullet_text")))
        for b in (res_cloud_bullets.data or [])
    }

    for b in local_bullets:
        old_exp_id = b["experience_id"]
        target_exp_id = exp_id_map.get(old_exp_id)

        if not target_exp_id:
            print(f"  ⚠️ Error: No se encontró mapeo para experience_id={old_exp_id}. Viñeta omitida.")
            continue

        bk = (target_exp_id, normalize(b["bullet_text"]))
        if bk in existing_bullets:
            stats["bullets_skipped"] += 1
        else:
            bullet_payload = {
                "user_id": user_id,
                "experience_id": target_exp_id,
                "bullet_text": b["bullet_text"],
                "original_text": b["original_text"] or b["bullet_text"],
                "current_text": b["current_text"] or b["bullet_text"],
                "order_index": b["order_index"] or 0
            }
            if is_dry_run:
                pass
            else:
                supabase.table("resume_bullets").insert(bullet_payload).execute()
                existing_bullets.add(bk)
            stats["bullets_migrated"] += 1

    print(f"  -> Total locales: {len(local_bullets)} | Migradas: {stats['bullets_migrated']} | Ya existentes (omitidas): {stats['bullets_skipped']}")

    # ==========================================================================
    # RESUMEN FINAL Y CONTEOS ESPERADOS (AUDITORÍA DE INTEGRIDAD)
    # ==========================================================================
    print("\n" + "=" * 75)
    print("🎯 CONTEOS FINALES DE INTEGRIDAD:")
    print("=" * 75)
    print(f"  • Postulaciones (applications):     {stats['applications_total']} evaluadas | {stats['applications_recruiter_updated']} con recruiter copiado")
    print(f"  • Perfil Profesional (user_profile): {stats['profile_migrated'] + stats['profile_skipped']} de 1 esperado")
    print(f"  • Habilidades (user_skills):        {stats['skills_migrated'] + stats['skills_skipped']} de 76 esperadas")
    print(f"  • Educación (education_entries):    {stats['education_migrated'] + stats['education_skipped']} de 7 esperados")
    print(f"  • Experiencias (experience_entries): {stats['experience_migrated'] + stats['experience_skipped']} de 4 esperadas")
    print(f"  • Viñetas (resume_bullets):         {stats['bullets_migrated'] + stats['bullets_skipped']} de 15 esperadas")
    print("=" * 75)

    if is_dry_run:
        print("🛡️  SIMULACIÓN COMPLETADA CON ÉXITO: Ningún dato fue escrito en Supabase.")
        print("    Para ejecutar la migración real, corre el script sin el parámetro --dry-run:\n")
        print("    .venv\\Scripts\\python.exe migrate_to_supabase.py\n")
    else:
        print("🎉 ¡MIGRACIÓN COMPLETADA CON ÉXITO! Todos los datos están sincronizados en Supabase.\n")


if __name__ == "__main__":
    main()
