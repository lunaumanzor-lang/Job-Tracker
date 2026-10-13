# ==============================================================================
# PROYECTO: AI Job Application Tracker
# Script de Auditoría y Conciliación (Solo Lectura): SQLite vs Supabase
# ==============================================================================

import os
import sys
import sqlite3
import getpass
import toml
from supabase import create_client


def run_audit(email: str = None, password: str = None):
    print("\n" + "=" * 70)
    print(" 🔍 AUDITORÍA DE CONCILIACIÓN: SQLite vs Supabase (SOLO LECTURA)")
    print("=" * 70)

    # 1. Leer SQLite Local (job_tracker.db)
    db_path = os.path.join(os.path.dirname(__file__), "job_tracker.db")
    if not os.path.exists(db_path):
        print(f"❌ Error: No se encontró la base de datos local en {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM applications ORDER BY id ASC")
    local_apps = cur.fetchall()
    print(f"📦 Total de postulaciones en SQLite local: {len(local_apps)}")

    # 2. Conectar con Supabase
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        print(f"❌ Error: No se encontró {secrets_path}")
        return

    secrets = toml.load(secrets_path)
    url = secrets.get("SUPABASE_URL")
    key = secrets.get("SUPABASE_KEY")

    if not url or not key:
        print("❌ Error: Faltan credenciales de Supabase en secrets.toml")
        return

    supabase = create_client(url, key)

    # 3. Autenticación con Supabase
    email = email or os.environ.get("SUPABASE_EMAIL")
    password = password or os.environ.get("SUPABASE_PASSWORD")

    if not email:
        email = input("\nIngresa tu correo registrado en Supabase: ").strip()
    if not password:
        password = getpass.getpass("Ingresa tu contraseña de Supabase: ").strip()

    print("\n🔐 Autenticando con Supabase para evaluar permisos RLS...")
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = auth_res.user
        if not user or not auth_res.session:
            print("❌ Error: No se pudo obtener la sesión de usuario.")
            return
        supabase.postgrest.auth(auth_res.session.access_token)
        print(f"✅ Autenticado exitosamente como: {user.email} (ID: {user.id})")
    except Exception as e:
        print(f"❌ Error de autenticación en Supabase: {e}")
        return

    # 4. Descargar aplicaciones de Supabase
    print("☁️  Consultando tabla 'applications' en Supabase...")
    try:
        res_cloud = supabase.table("applications").select("*").order("id", desc=False).execute()
        cloud_apps = res_cloud.data or []
        print(f"☁️  Total de postulaciones en Supabase para este usuario: {len(cloud_apps)}")
    except Exception as e:
        print(f"❌ Error al consultar Supabase: {e}")
        return

    # 5. Conciliación y Comparación
    def normalize_key(c, p, d):
        return (
            str(c or "").strip().lower(),
            str(p or "").strip().lower(),
            str(d or "").strip()
        )

    cloud_dict = {normalize_key(a.get("company"), a.get("position"), a.get("application_date")): a for a in cloud_apps}
    local_dict = {normalize_key(a["company"], a["position"], a["application_date"]): a for a in local_apps}

    exact_matches = []
    only_in_local = []
    only_in_cloud = []
    diffs = []

    for k, l_row in local_dict.items():
        if k in cloud_dict:
            c_row = cloud_dict[k]
            exact_matches.append(k)

            # Comparar diferencias en campos
            row_diffs = []
            for field in ["status", "salary", "work_mode", "location", "job_url", "notes"]:
                l_val = str(l_row[field] or "").strip()
                c_val = str(c_row.get(field) or "").strip()
                if l_val != c_val:
                    row_diffs.append(f"{field}: (Local='{l_val}' vs Nube='{c_val}')")
            if row_diffs:
                diffs.append((l_row["company"], l_row["position"], l_row["application_date"], row_diffs))
        else:
            only_in_local.append(l_row)

    for k, c_row in cloud_dict.items():
        if k not in local_dict:
            only_in_cloud.append(c_row)

    # 6. Reporte Final
    print("\n" + "=" * 70)
    print("📊 RESULTADO DE LA AUDITORÍA:")
    print("=" * 70)
    print(f"  ✅ Coincidencias exactas (en ambos lados): {len(exact_matches)} de {len(local_apps)}")
    print(f"  📦 Presentes solo en SQLite local:        {len(only_in_local)}")
    print(f"  ☁️  Presentes solo en Supabase:             {len(only_in_cloud)}")
    print(f"  📝 Registros con diferencias en campos:    {len(diffs)}")
    print("=" * 70)

    if only_in_local:
        print(f"\n⚠️  Listado de postulaciones pendientes de subir a Supabase ({len(only_in_local)}):")
        for r in only_in_local[:10]:
            print(f"   - {r['company']} | {r['position']} | {r['application_date']}")
        if len(only_in_local) > 10:
            print(f"   ... y {len(only_in_local) - 10} más.")

    if only_in_cloud:
        print(f"\n⚠️  Listado de postulaciones creadas en la nube pero no en SQLite ({len(only_in_cloud)}):")
        for r in only_in_cloud[:10]:
            print(f"   - {r.get('company')} | {r.get('position')} | {r.get('application_date')}")

    if diffs:
        print(f"\n⚠️  Diferencias encontradas en campos específicos ({len(diffs)}):")
        for comp, pos, date_val, d_list in diffs[:10]:
            print(f"   - [{comp} - {pos} ({date_val})]:")
            for d in d_list:
                print(f"       • {d}")

    print("\n🛡️  Auditoría completada. No se modificó ningún dato en ninguna base de datos.\n")


if __name__ == "__main__":
    run_audit()
