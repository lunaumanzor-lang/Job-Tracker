# ==============================================================================
# PROYECTO: AI Job Application Tracker
# Script CLI: Sincronizar SQLite a Supabase (sync_to_supabase.py)
# ==============================================================================

import os
import sys
import getpass
import toml
from supabase import create_client
from sync_service import sync_sqlite_to_supabase


def main():
    print("=" * 65)
    print("  🔄 Sincronizador de Postulaciones: SQLite -> Supabase")
    print("=" * 65)

    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        print("❌ Error: No se encontró el archivo .streamlit/secrets.toml")
        sys.exit(1)

    secrets = toml.load(secrets_path)
    url = secrets.get("SUPABASE_URL")
    key = secrets.get("SUPABASE_KEY")

    if not url or not key:
        print("❌ Error: Faltan SUPABASE_URL o SUPABASE_KEY en secrets.toml")
        sys.exit(1)

    supabase = create_client(url, key)

    email = os.environ.get("SUPABASE_EMAIL")
    password = os.environ.get("SUPABASE_PASSWORD")

    if not email:
        email = input("\nIngresa tu correo registrado en Supabase: ").strip()
    if not password:
        password = getpass.getpass("Ingresa tu contraseña: ").strip()

    print("\n🔐 Autenticando con Supabase...")
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        if not user:
            print("❌ Error: No se pudo obtener el usuario autenticado.")
            sys.exit(1)

        # Inyectar el token para pasar Row-Level Security
        if res.session:
            supabase.postgrest.auth(res.session.access_token)

        print(f"✅ Autenticado exitosamente como: {user.email} (ID: {user.id})")
    except Exception as e:
        print(f"❌ Error de autenticación: {e}")
        sys.exit(1)

    print("\n📦 Iniciando sincronización de postulaciones desde SQLite...")

    def progress(current, total, msg):
        print(f"[{current}/{total}] {msg}")

    result = sync_sqlite_to_supabase(supabase, user.id, progress_callback=progress)

    print("\n" + "=" * 65)
    print("📊 RESUMEN DE LA SINCRONIZACIÓN:")
    print(f"- Total en SQLite local:  {result['total']}")
    print(f"- Subidas con éxito:      {result['inserted']}")
    print(f"- Omitidas (duplicadas):  {result['skipped']}")
    if result["errors"]:
        print(f"- Errores:               {len(result['errors'])}")
        for err in result["errors"][:5]:
            print(f"  ⚠️ {err}")
    print("=" * 65)
    print("\n🎉 ¡Listo! Tus aplicaciones ahora están sincronizadas en Supabase.")


if __name__ == "__main__":
    main()
