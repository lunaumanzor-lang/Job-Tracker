# ==============================================================================
# PROYECTO: AI Job Application Tracker
# FASE 3: Application Tracker con Streamlit (app.py)
# ==============================================================================

import os
from datetime import datetime, date
import streamlit as st
import pandas as pd

# Importamos las funciones de la base de datos de la Fase 2
from database import (
    create_tables,
    insert_application,
    get_all_applications,
    get_application_by_id,
    update_application,
    delete_application,
    get_dashboard_counts
)

# ------------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Job Application Tracker",
    page_icon="💼",
    layout="wide"  # 'wide' aprovecha mejor el ancho de la pantalla para tablas y formularios
)

# Aseguramos la existencia de las tablas
create_tables()

# Título y encabezado
st.title("💼 AI Job Application Tracker")
st.caption("Fase 4a: Dashboard de Métricas y Gestión de Postulaciones")

# Valores exactos de Status requeridos por el proyecto
STATUS_OPTIONS = [
    "Applied",
    "Recruiter Screen",
    "Technical Interview",
    "Final Interview",
    "Offer",
    "Rejected",
    "Ghosted"
]

# Opciones de modalidad de trabajo
WORK_MODE_OPTIONS = ["Remote", "Hybrid", "On-site", "TBD"]


# ------------------------------------------------------------------------------
# CONCEPTO STREAMLIT - st.tabs():
# Creamos tres pestañas principales: Dashboard, Ver/Gestionar y Agregar.
# ------------------------------------------------------------------------------
tab_dash, tab_ver, tab_agregar = st.tabs([
    "📊 Dashboard",
    "📋 Ver y Gestionar Aplicaciones",
    "➕ Agregar Nueva Aplicación"
])


# ==============================================================================
# PESTAÑA 0: DASHBOARD (Sub-fase 4a: Conteos Simples en Tiempo Real)
# ==============================================================================
with tab_dash:
    st.subheader("📈 Resumen General de Postulaciones")
    st.caption("Métricas clave calculadas en tiempo real directamente desde SQLite mediante consultas SQL COUNT().")

    # Obtenemos los conteos calculados por SQL
    metricas = get_dashboard_counts()

    # --------------------------------------------------------------------------
    # CONCEPTO STREAMLIT - st.metric():
    # st.metric() crea una tarjeta destacada con un valor numérico grande,
    # un título pequeño ('label') y opcionalmente un texto de ayuda o delta.
    # Usamos st.columns(5) para distribuirlas horizontalmente en una sola fila.
    # --------------------------------------------------------------------------
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

    with col_m1:
        st.metric(
            label="Total Applications",
            value=metricas["total_applications"]
        )

    with col_m2:
        st.metric(
            label="Interviews 🎯",
            value=metricas["interviews"],
            help="Regla de negocio: incluye Recruiter Screen, Technical Interview y Final Interview"
        )

    with col_m3:
        st.metric(
            label="Offers 🎉",
            value=metricas["offers"]
        )

    with col_m4:
        st.metric(
            label="Rejections ❌",
            value=metricas["rejections"]
        )

    with col_m5:
        st.metric(
            label="Follow-ups ⏰",
            value=metricas["follow_ups"],
            help="Aplicaciones con fecha de seguimiento registrada próxima o vencida"
        )

    st.divider()

    # Explicación pedagógica de las consultas de agregación utilizadas
    with st.expander("ℹ️ ¿Cómo se calculan estas métricas en SQL? (Explicación técnica)"):
        st.markdown("""
        * **Total Applications:** `SELECT COUNT(*) FROM applications;`  
          Cuenta el número total de filas en la tabla.
        * **Interviews:** `SELECT COUNT(*) FROM applications WHERE status IN ('Recruiter Screen', 'Technical Interview', 'Final Interview');`  
          La cláusula `IN (...)` agrupa los 3 estados de entrevista en una sola condición.
        * **Offers:** `SELECT COUNT(*) FROM applications WHERE status = 'Offer';`
        * **Rejections:** `SELECT COUNT(*) FROM applications WHERE status = 'Rejected';`
        * **Follow-ups:** `SELECT COUNT(*) FROM applications WHERE follow_up_date IS NOT NULL AND date(follow_up_date) <= date('now');`  
          Compara la fecha de seguimiento contra la fecha actual (`date('now')` en SQLite).
        """)



# ==============================================================================
# PESTAÑA 1: VER, BUSCAR, FILTRAR, EDITAR Y ELIMINAR APLICACIONES
# ==============================================================================
with tab_ver:
    # 1. Obtenemos todas las aplicaciones desde SQLite
    todas_las_apps = get_all_applications()

    if not todas_las_apps:
        st.info("No hay aplicaciones registradas todavía. Ve a la pestaña '➕ Agregar Nueva Aplicación' para crear la primera.")
    else:
        # Convertimos la lista de diccionarios a un DataFrame de pandas para facilitar búsquedas y filtros
        df = pd.DataFrame(todas_las_apps)

        # ----------------------------------------------------------------------
        # BÚSQUEDA Y FILTROS (Requisito 6)
        # ----------------------------------------------------------------------
        st.subheader("🔍 Buscar y Filtrar")
        col_busq, col_f_status, col_f_mode = st.columns([2, 1, 1])

        with col_busq:
            busqueda = st.text_input("Buscar por Empresa o Puesto:", placeholder="Ej. Citi, DevOps, AWS...")

        with col_f_status:
            filtro_status = st.selectbox("Filtrar por Status:", options=["Todos"] + STATUS_OPTIONS)

        with col_f_mode:
            filtro_mode = st.selectbox("Filtrar por Modalidad:", options=["Todos"] + WORK_MODE_OPTIONS)

        # Aplicamos los filtros al DataFrame en memoria
        df_filtrado = df.copy()

        # Filtro de texto (búsqueda insensible a mayúsculas/minúsculas)
        if busqueda.strip():
            patron = busqueda.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado["company"].str.lower().str.contains(patron, na=False) |
                df_filtrado["position"].str.lower().str.contains(patron, na=False)
            ]

        # Filtro por Status
        if filtro_status != "Todos":
            df_filtrado = df_filtrado[df_filtrado["status"] == filtro_status]

        # Filtro por Work Mode
        if filtro_mode != "Todos":
            df_filtrado = df_filtrado[df_filtrado["work_mode"] == filtro_mode]

        # Mostramos contador de resultados
        st.caption(f"Mostrando **{len(df_filtrado)}** de **{len(df)}** aplicaciones.")

        # ----------------------------------------------------------------------
        # TABLA DE APLICACIONES (Requisito 2)
        # ----------------------------------------------------------------------
        columnas_tabla = ["id", "company", "position", "status", "work_mode", "salary", "application_date"]
        # Filtramos solo columnas existentes por seguridad
        cols_mostrar = [c for c in columnas_tabla if c in df_filtrado.columns]

        st.dataframe(
            df_filtrado[cols_mostrar],
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # ----------------------------------------------------------------------
        # SELECCIONAR UNA APLICACIÓN PARA EDITAR, VER DETALLES O ELIMINAR (Requisitos 3, 4 y 5)
        # ----------------------------------------------------------------------
        st.subheader("⚙️ Gestionar una Aplicación (Editar / Detalles / Eliminar)")

        # Creamos una lista de opciones claras para el selectbox: "[ID] Empresa - Puesto"
        opciones_apps = {
            f"#{row['id']:02d} | {row['company']} — {row['position']} ({row['status']})": row['id']
            for _, row in df_filtrado.iterrows()
        }

        if not opciones_apps:
            st.warning("No hay aplicaciones que coincidan con los filtros seleccionados.")
        else:
            col_sel, _ = st.columns([2, 1])
            with col_sel:
                seleccion_texto = st.selectbox(
                    "Selecciona una aplicación de la lista para verla o modificarla:",
                    options=list(opciones_apps.keys())
                )

            app_id_seleccionado = opciones_apps[seleccion_texto]
            app_actual = get_application_by_id(app_id_seleccionado)

            if app_actual:
                # Mostramos los detalles y el formulario de edición
                col_detalle, col_edicion = st.columns([1, 1], gap="large")

                # PANEL IZQUIERDO: DETALLE COMPLETO (Requisito 3)
                with col_detalle:
                    st.markdown("### 📄 Detalles de la Postulación")
                    st.info(f"**Empresa:** {app_actual['company']}\n\n"
                            f"**Puesto:** {app_actual['position']}\n\n"
                            f"**Estado actual:** `{app_actual['status']}`\n\n"
                            f"**Modalidad:** {app_actual['work_mode'] or 'No especificada'}\n\n"
                            f"**Salario registrado:** {app_actual['salary'] or 'No especificado'}\n\n"
                            f"**Fecha de postulación:** {app_actual['application_date'] or 'Sin fecha'}\n\n"
                            f"**Ubicación:** {app_actual['location'] or 'N/A'}")

                    if app_actual.get("job_url"):
                        st.markdown(f"🔗 [Abrir enlace de la vacante]({app_actual['job_url']})")

                    if app_actual.get("notes"):
                        with st.expander("📝 Ver Notas / Descripción completa"):
                            st.write(app_actual["notes"])

                    # SECCIÓN DE ELIMINACIÓN CON CONFIRMACIÓN (Requisito 5)
                    st.markdown("---")
                    st.markdown("#### 🗑️ Zona de peligro")
                    with st.expander("Eliminar esta postulación"):
                        st.warning(f"¿Estás seguro de que deseas eliminar permanentemente la postulación a **{app_actual['company']}**?")
                        confirmar_borrado = st.checkbox("Sí, confirmo que deseo eliminar este registro.", key=f"conf_del_{app_actual['id']}")
                        
                        if st.button("🚨 Eliminar Definitivamente", type="primary", disabled=not confirmar_borrado):
                            delete_application(app_actual["id"])
                            st.success(f"Postulación #{app_actual['id']} eliminada con éxito.")
                            # CONCEPTO - st.rerun():
                            # Fuerza a Streamlit a recargar la página para que la tabla
                            # y los selectores muestren los datos actualizados de SQLite.
                            st.rerun()

                # PANEL DERECHO: FORMULARIO DE EDICIÓN (Requisito 4)
                with col_edicion:
                    st.markdown("### ✏️ Editar Datos")
                    st.caption("Modifica los campos necesarios (por ejemplo cambiar 'TBD' por la empresa real) y guarda los cambios.")

                    with st.form(f"form_editar_{app_actual['id']}"):
                        edit_company = st.text_input("Company *", value=app_actual["company"])
                        edit_position = st.text_input("Position *", value=app_actual["position"])

                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            # Parseamos la fecha existente o usamos hoy por defecto
                            fecha_default = date.today()
                            if app_actual.get("application_date"):
                                try:
                                    fecha_default = datetime.strptime(app_actual["application_date"][:10], "%Y-%m-%d").date()
                                except Exception:
                                    pass
                            edit_date = st.date_input("Application Date", value=fecha_default)

                        with col_e2:
                            # Buscamos el índice actual en STATUS_OPTIONS
                            idx_status = STATUS_OPTIONS.index(app_actual["status"]) if app_actual["status"] in STATUS_OPTIONS else 0
                            edit_status = st.selectbox("Status", options=STATUS_OPTIONS, index=idx_status)

                        col_e3, col_e4 = st.columns(2)
                        with col_e3:
                            # Modalidad
                            mode_val = app_actual.get("work_mode") or "Remote"
                            idx_mode = WORK_MODE_OPTIONS.index(mode_val) if mode_val in WORK_MODE_OPTIONS else 0
                            edit_mode = st.selectbox("Work Mode", options=WORK_MODE_OPTIONS, index=idx_mode)
                        with col_e4:
                            edit_salary = st.text_input("Salary", value=app_actual.get("salary") or "")

                        edit_location = st.text_input("Location", value=app_actual.get("location") or "")
                        edit_job_url = st.text_input("Job URL", value=app_actual.get("job_url") or "")
                        edit_notes = st.text_area("Notes", value=app_actual.get("notes") or "", height=150)

                        btn_guardar_edicion = st.form_submit_button("💾 GUARDAR CAMBIOS", use_container_width=True)

                    if btn_guardar_edicion:
                        if not edit_company.strip() or not edit_position.strip():
                            st.error("Company y Position no pueden estar vacíos.")
                        else:
                            # Actualizamos en SQLite
                            fecha_str = edit_date.strftime("%Y-%m-%d")
                            update_application(
                                app_id=app_actual["id"],
                                company=edit_company.strip(),
                                position=edit_position.strip(),
                                status=edit_status,
                                application_date=fecha_str,
                                salary=edit_salary.strip() if edit_salary else None,
                                work_mode=edit_mode,
                                location=edit_location.strip() if edit_location else None,
                                job_url=edit_job_url.strip() if edit_job_url else None,
                                notes=edit_notes.strip() if edit_notes else None
                            )
                            st.success(f"✅ ¡Postulación #{app_actual['id']} actualizada con éxito!")
                            st.rerun()


# ==============================================================================
# PESTAÑA 2: AGREGAR NUEVA APLICACIÓN (Requisito 1)
# ==============================================================================
with tab_agregar:
    st.subheader("➕ Formulario de Nueva Aplicación")
    st.caption("Ingresa los datos de una nueva vacante para registrarla en la base de datos.")

    with st.form("form_nueva_aplicacion", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("Company *", placeholder="Ej. Microsoft, Akamai...")
        with col2:
            position = st.text_input("Position *", placeholder="Ej. DevOps Engineer, SRE...")

        col3, col4 = st.columns(2)
        with col3:
            app_date = st.date_input("Application Date", value=date.today(), key="new_app_date")
        with col4:
            status = st.selectbox("Status", options=STATUS_OPTIONS, index=0, key="new_status")

        col5, col6 = st.columns(2)
        with col5:
            work_mode = st.radio("Work Mode", options=["Remote", "Hybrid", "On-site"], horizontal=True, key="new_work_mode")
        with col6:
            salary_input = st.text_input("Salary (USD)", placeholder="Ej. 5000", key="new_salary")

        col7, col8 = st.columns(2)
        with col7:
            job_url = st.text_input("Job URL", placeholder="https://linkedin.com/jobs/...", key="new_url")
        with col8:
            location = st.text_input("Location", placeholder="Ej. San José, Costa Rica / Remote US", key="new_location")

        notes = st.text_area("Notes / Job Description", placeholder="Pega aquí requisitos clave o notas...", key="new_notes")

        btn_crear = st.form_submit_button("💾 SAVE APPLICATION", use_container_width=True)

    if btn_crear:
        errores = []
        if not company.strip():
            errores.append("El campo **Company** es obligatorio.")
        if not position.strip():
            errores.append("El campo **Position** es obligatorio.")

        salary_limpio = None
        if salary_input.strip():
            salario_txt = salary_input.replace("$", "").replace(",", "").strip()
            try:
                salario_num = float(salario_txt)
                salary_limpio = f"{int(salario_num)} USD"
            except ValueError:
                errores.append("El campo **Salary** debe ser un número válido (ej. 5000).")

        if errores:
            for err in errores:
                st.error(f"⚠️ {err}")
        else:
            fecha_str = app_date.strftime("%Y-%m-%d")
            nuevo_id = insert_application(
                company=company.strip(),
                position=position.strip(),
                status=status,
                application_date=fecha_str,
                salary=salary_limpio,
                work_mode=work_mode,
                location=location.strip() if location else None,
                job_url=job_url.strip() if job_url else None,
                notes=notes.strip() if notes else None
            )
            st.success(f"🎉 ¡Aplicación a **{company}** guardada con éxito con ID #{nuevo_id}!")
