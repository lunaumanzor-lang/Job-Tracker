# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 2: Integración con Base de Datos Relacional SQLite (main.py)
# ==============================================================================

import os
from database import (
    create_tables,
    get_all_applications,
    get_application_by_id,
    insert_application,
    update_application_status,
    delete_application,
    get_connection,
    DB_NAME
)


# ------------------------------------------------------------------------------
# 1. FUNCIONES PARA MOSTRAR DATOS DESDE SQLITE
# ------------------------------------------------------------------------------
def mostrar_resumen_status():
    """
    Realiza una consulta de agregación (GROUP BY) en SQLite para contar
    cuántas aplicaciones hay por cada estado.
    """
    query = """
    SELECT status, COUNT(*) as cantidad
    FROM applications
    GROUP BY status
    ORDER BY cantidad DESC;
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        filas = cursor.fetchall()
        
        print("Aplicaciones por status (desde SQLite):")
        for fila in filas:
            print(f"- {fila['status']}: {fila['cantidad']}")


def mostrar_aplicaciones(lista_apps, limite: int = 10):
    """
    Imprime en consola las aplicaciones obtenidas desde SQLite.
    Muestra hasta 'limite' aplicaciones para mantener la consola legible.
    """
    total = len(lista_apps)
    print(f"\nMostrando las primeras {min(limite, total)} aplicaciones de {total}:\n")
    
    for app in lista_apps[:limite]:
        app_id = app["id"]
        empresa = app["company"]
        puesto = app["position"]
        estado = app["status"]
        modalidad = app["work_mode"] or "N/A"
        fecha = app["application_date"] or "Sin fecha"
        
        print(f"[{app_id:02d}] {empresa} - {puesto} | {estado} | {modalidad} | {fecha}")


# ------------------------------------------------------------------------------
# 2. BLOQUE PRINCIPAL DE EJECUCIÓN (main)
# ------------------------------------------------------------------------------
def main():
    print("=" * 65)
    print("=== AI Job Application Tracker (Fase 2: SQLite Database) ===")
    print("=" * 65)
    print()

    # 1. Asegurar que las tablas existan en SQLite
    create_tables()

    # 2. Consultar todas las aplicaciones guardadas en la base de datos real
    aplicaciones = get_all_applications()
    total = len(aplicaciones)

    print(f"Base de datos activa: {DB_NAME}")
    print(f"Total de aplicaciones registradas en SQLite: {total}")
    print()

    if total == 0:
        print("No hay aplicaciones cargadas aún.")
        print("Ejecuta 'python import_excel.py' para importar tus datos desde Excel.")
        return

    # 3. Mostrar desglose por status mediante SQL
    mostrar_resumen_status()

    # 4. Mostrar listado de aplicaciones
    mostrar_aplicaciones(aplicaciones, limite=10)

    print("\n" + "=" * 65)
    print("DEMOSTRACIÓN DE OPERACIONES CRUD EN SQLITE")
    print("=" * 65)

    # A) CREATE (INSERT): Insertar una postulación de prueba
    print("\n[C - Create]: Insertando nueva postulación de prueba en SQLite...")
    nuevo_id = insert_application(
        company="NVIDIA",
        position="AI Infrastructure Engineer",
        status="Applied",
        work_mode="Remote",
        salary="6500 USD",
        notes="Postulación de prueba agregada en vivo"
    )
    print(f">> Postulación creada con éxito. ID asignado por SQLite: {nuevo_id}")

    # B) READ (SELECT): Consultar el registro recién insertado por su ID
    print("\n[R - Read]: Consultando el registro con ID", nuevo_id)
    app_recien_creada = get_application_by_id(nuevo_id)
    print(f">> Encontrado: {app_recien_creada['company']} - {app_recien_creada['position']} ({app_recien_creada['status']})")

    # C) UPDATE: Cambiar el estado a 'Interview'
    print("\n[U - Update]: Actualizando estado a 'Technical Interview'...")
    update_application_status(nuevo_id, "Technical Interview")
    app_actualizada = get_application_by_id(nuevo_id)
    print(f">> Nuevo estado verificado en BD: {app_actualizada['status']}")

    # D) DELETE: Eliminar el registro de prueba para dejar la base de datos limpia
    print("\n[D - Delete]: Eliminando registro de prueba...")
    eliminado = delete_application(nuevo_id)
    print(f">> ¿Eliminado correctamente?: {eliminado}")
    print("=" * 65)
    print("¡Fase 2 completada con éxito! La persistencia en SQLite funciona al 100%.")
    print("=" * 65)


if __name__ == "__main__":
    main()
