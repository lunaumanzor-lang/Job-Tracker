# ==============================================================================
# PROYECTO: Smart Job Tracker
# MÓDULO: preview_mode.py - Vistas Demostrativas / Informativas para Usuarios No Autenticados
# ==============================================================================

import streamlit as st
import pandas as pd
from translations import t

def _render_auth_callout():
    is_en = st.session_state.get("lang") == "en"
    msg = (
        "🔒 **Modo Demostración / Vista Previa:** Estás explorando las funcionalidades de **Smart Job Tracker**. "
        "Para guardar tus postulaciones y utilizar todas las herramientas con tus datos personales, "
        "ingresa tu usuario y contraseña en el menú superior."
        if not is_en else
        "🔒 **Demonstration / Preview Mode:** You are exploring the features of **Smart Job Tracker**. "
        "To save your applications and use all tools with your personal data, "
        "please enter your username and password in the top menu."
    )
    st.info(msg)


def render_unauthenticated_preview(menu_opcion: str):
    """
    Renderiza una vista demostrativa rica y estética de la sección seleccionada
    cuando el usuario aún no ha iniciado sesión.
    """
    is_en = st.session_state.get("lang") == "en"

    # 1. Agregar Nueva Aplicación
    if menu_opcion in ("add_app", "➕ Agregar Nueva Aplicación", "➕ Add New Application"):
        st.subheader("➕ " + ("Agregar Nueva Aplicación" if not is_en else "Add New Application"))
        st.caption(
            "Registra oportunidades laborales con detalles de empresa, puesto, salario, enlaces y notas."
            if not is_en else
            "Track job opportunities with company details, position, compensation, links and notes."
        )
        _render_auth_callout()

        with st.container(border=True):
            st.markdown("#### 📝 " + ("Formulario de Registro de Vacante" if not is_en else "Job Registration Form"))
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("🏢 " + ("Empresa" if not is_en else "Company"), value="Google", disabled=True)
                st.text_input("💼 " + ("Puesto" if not is_en else "Position"), value="Senior Python Developer", disabled=True)
                st.selectbox("📍 " + ("Modalidad de Trabajo" if not is_en else "Work Mode"), ["Remote", "Hybrid", "On-site"], index=0, disabled=True)
                st.text_input("💵 " + ("Salario Estimado" if not is_en else "Estimated Salary"), value="$85,000 USD / año", disabled=True)
            with col2:
                st.selectbox("📌 " + ("Estado Inicial" if not is_en else "Initial Status"), ["Applied", "Recruiter Screen", "Technical Interview"], index=0, disabled=True)
                st.text_input("🔗 " + ("Enlace a la Oferta (URL)" if not is_en else "Job Posting URL"), value="https://careers.google.com/jobs/results/123456", disabled=True)
                st.text_area(
                    "📝 " + ("Notas / Descripción" if not is_en else "Notes / Description"),
                    value="Requisitos clave: Python 3.12, FastAPI, PostgreSQL, Docker, GCP, Microservicios.",
                    height=110,
                    disabled=True
                )
            st.button(
                "💾 " + ("Guardar Postulación (Requiere Iniciar Sesión)" if not is_en else "Save Application (Login Required)"),
                disabled=True,
                use_container_width=True
            )

    # 2. Ver y Gestionar Aplicaciones
    elif menu_opcion in ("view_apps", "📋 Ver y Gestionar Aplicaciones", "📋 View & Manage Applications"):
        st.subheader("📋 " + ("Ver y Gestionar Aplicaciones" if not is_en else "View & Manage Applications"))
        st.caption(
            "Visualiza, filtra y audita tus postulaciones activas con control de estados y edición rápida."
            if not is_en else
            "View, filter and audit your active applications with status tracking and fast editing."
        )
        _render_auth_callout()

        col_f1, col_f2 = st.columns([0.6, 0.4])
        with col_f1:
            st.text_input("🔍 " + ("Buscar por empresa o puesto" if not is_en else "Search by company or position"), value="", placeholder="Ej: Google, Backend...", disabled=True)
        with col_f2:
            st.selectbox("📌 " + ("Filtrar por Estado" if not is_en else "Filter by Status"), ["Todos / All", "Applied", "Technical Interview", "Offer"], index=0, disabled=True)

        demo_df = pd.DataFrame([
            {"#": 1, "Empresa / Company": "Google", "Puesto / Position": "Senior Python Developer", "Estado / Status": "Technical Interview", "Modalidad": "Remote", "Fecha": "2026-10-12"},
            {"#": 2, "Empresa / Company": "Stripe", "Puesto / Position": "Backend Platform Engineer", "Estado / Status": "Recruiter Screen", "Modalidad": "Remote", "Fecha": "2026-10-10"},
            {"#": 3, "Empresa / Company": "AWS", "Puesto / Position": "Cloud Solutions Architect", "Estado / Status": "Applied", "Modalidad": "Hybrid", "Fecha": "2026-10-08"},
            {"#": 4, "Empresa / Company": "Spotify", "Puesto / Position": "Staff Data Engineer", "Estado / Status": "Final Interview", "Modalidad": "Remote", "Fecha": "2026-10-04"}
        ])
        st.dataframe(demo_df, use_container_width=True, hide_index=True)

    # 3. Ver Compatibilidad y Sugerir Cursos
    elif menu_opcion in ("analyzer", "🎯 Ver Compatibilidad y Sugerir Cursos", "🎯 View Compatibility & Suggest Courses", "🎯 Analizar Compatibilidad y Sugerir Cursos", "🎯 Analyze Compatibility & Suggest Courses", "🤖 AI Job Analyzer"):
        st.subheader("🎯 " + ("Ver Compatibilidad y Sugerir Cursos" if not is_en else "View Compatibility & Suggest Courses"))
        st.caption(
            "Compara los requisitos de cualquier oferta con tu perfil profesional y obtén recomendaciones de estudio."
            if not is_en else
            "Compare vacancy requirements against your profile and get targeted study recommendations."
        )
        _render_auth_callout()

        with st.container(border=True):
            col_m1, col_m2 = st.columns([0.35, 0.65])
            with col_m1:
                st.metric(
                    label="📊 " + ("Compatibilidad con la vacante" if not is_en else "Match Compatibility"),
                    value="88%",
                    delta="+12% vs promedio" if not is_en else "+12% vs average"
                )
                st.progress(0.88)
            with col_m2:
                st.markdown("##### ✅ " + ("Habilidades Coincidentes Detectadas" if not is_en else "Matched Skills Detected"))
                st.markdown("`Python` `FastAPI` `PostgreSQL` `Docker` `REST APIs` `Git`")
                st.markdown("##### ⚠️ " + ("Brechas Técnicas Identificadas" if not is_en else "Identified Technical Gaps"))
                st.markdown("`Kubernetes` `Terraform`")

            st.divider()
            st.markdown("#### 🎓 " + ("Cursos Recomendados por IA para Cerrar Brechas" if not is_en else "AI Recommended Courses to Bridge Gaps"))
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                with st.container(border=True):
                    st.markdown("**🐳 Kubernetes for Developers & Cloud Architecture**")
                    st.caption("Plataforma: Coursera / Linux Foundation • Duración: 15h • Costo: Gratuito (Auditoría)")
            with col_c2:
                with st.container(border=True):
                    st.markdown("**☁️ Terraform: Infrastructure as Code from Scratch**")
                    st.caption("Plataforma: edX / HashiCorp Certified • Duración: 12h • Costo: Gratuito")

    # 4. Prepararme para este puesto (Interview Coach)
    elif menu_opcion in ("coach", "🎯 Prepararme para este puesto", "🎯 Prepare me for this job"):
        st.subheader("🎯 " + ("Prepararme para este puesto (Interview Coach con IA)" if not is_en else "Prepare me for this job (AI Interview Coach)"))
        st.caption(
            "Simulador de entrevistas técnicas y conductuales con evaluación bajo la metodología STAR."
            if not is_en else
            "Technical and behavioral interview simulator with real-time feedback using the STAR framework."
        )
        _render_auth_callout()

        with st.container(border=True):
            st.markdown("#### 🧠 " + ("Pregunta de Práctica de Entrevista (Ejemplo)" if not is_en else "Sample Interview Practice Question"))
            st.info(
                "**Pregunta #1 (Técnica / Arquitectura):**\n\n"
                "\"Describe cómo diseñarías un servicio de ingesta de datos en Python capaz de procesar 50,000 eventos concurrentes por minuto sin pérdida de mensajes.\""
                if not is_en else
                "**Question #1 (Technical / Architecture):**\n\n"
                "\"How would you design a Python data ingestion pipeline capable of handling 50,000 concurrent events per minute without message loss?\""
            )
            st.text_area(
                "💬 " + ("Tu Respuesta (Simulador)" if not is_en else "Your Answer (Simulator)"),
                value="Utilizaría una cola de mensajería asíncrona como Kafka o RabbitMQ junto con workers de FastAPI y Celery, asegurando persistencia y reintentos idempotentes...",
                disabled=True,
                height=90
            )
            st.markdown("##### 🌟 " + ("Evaluación STAR de la IA" if not is_en else "AI STAR Feedback"))
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            col_s1.metric("Situación", "9/10")
            col_s2.metric("Tarea", "8/10")
            col_s3.metric("Acción", "9/10")
            col_s4.metric("Resultado", "8.5/10")

    # 5. CV Improver
    elif menu_opcion in ("cv_improver", "✨ Mejorar CV con IA", "✨ CV Improver (AI)"):
        st.subheader("✨ " + ("Mejorar CV con IA (CV Improver)" if not is_en else "AI CV Improver"))
        st.caption(
            "Optimiza los logros de tu currículum usando la fórmula XYZ de Google y descárgalo en plantillas ATS."
            if not is_en else
            "Enhance your resume achievements using Google's XYZ formula and export with ATS templates."
        )
        _render_auth_callout()

        with st.container(border=True):
            st.markdown("#### 🔄 " + ("Optimización de Bullets con IA (Antes vs Después)" if not is_en else "AI Bullet Optimization (Before vs After)"))
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.error(
                    "❌ **" + ("Redacción Original:" if not is_en else "Original Bullet:") + "**\n\n"
                    "\"Desarrollé APIs para el backend de la plataforma y ayudé a mejorar la base de datos.\""
                    if not is_en else
                    "\"Developed backend APIs for the platform and helped improve the database.\""
                )
            with col_b2:
                st.success(
                    "✅ **" + ("Optimizado con Fórmula XYZ de Google:" if not is_en else "Optimized with Google XYZ Formula:") + "**\n\n"
                    "\"Diseñé e implementé 14 endpoints RESTful en FastAPI, **reduciendo el tiempo de respuesta en un 38%** y procesando **60,000 solicitudes diarias** sin tiempos de inactividad.\""
                    if not is_en else
                    "\"Architected and deployed 14 RESTful endpoints using FastAPI, **reducing API latency by 38%** and processing **60,000 daily requests** with zero downtime.\""
                )
            st.markdown("##### 📄 " + ("Plantillas Disponibles para Descarga PDF y DOCX" if not is_en else "Available ATS Export Templates"))
            col_t1, col_t2, col_t3 = st.columns(3)
            col_t1.button("🎨 Modern Tech ATS", disabled=True, use_container_width=True)
            col_t2.button("📄 Minimalist Professional", disabled=True, use_container_width=True)
            col_t3.button("💼 Executive Classic", disabled=True, use_container_width=True)

    # 6. Estadísticas
    elif menu_opcion in ("stats", "📈 Estadísticas", "📈 Statistics"):
        st.subheader("📈 " + ("Estadísticas y Métricas de Postulación" if not is_en else "Statistics & Application Analytics"))
        st.caption(
            "Monitorea tus tasas de conversión por etapa, tiempos de respuesta y efectividad global."
            if not is_en else
            "Monitor conversion rates by stage, response timelines and overall job search performance."
        )
        _render_auth_callout()

        col_st1, col_st2, col_st3, col_st4 = st.columns(4)
        col_st1.metric("📨 " + ("Tasa de Respuesta" if not is_en else "Response Rate"), "42%", "+8%")
        col_st2.metric("⏱️ " + ("Días hasta 1ª Entrevista" if not is_en else "Days to 1st Interview"), "5.2 días", "-1.4 días")
        col_st3.metric("🎯 " + ("Conversión a Final" if not is_en else "Final Conversion"), "28%", "+5%")
        col_st4.metric("🎉 " + ("Ofertas Recibidas" if not is_en else "Offers Received"), "2", "+1")

    # 7. Mi Perfil
    elif menu_opcion in ("profile", "👤 Mi Perfil", "👤 My Profile"):
        st.subheader("👤 " + ("Mi Perfil Profesional y Habilidades" if not is_en else "My Profile & Master Skills"))
        st.caption(
            "Gestiona tu inventario de habilidades, carga tu CV maestro y ajusta tus preferencias."
            if not is_en else
            "Manage your skills inventory, upload your master resume and configure preferences."
        )
        _render_auth_callout()

        with st.container(border=True):
            st.markdown("#### 💼 " + ("Perfil Maestro del Candidato" if not is_en else "Candidate Master Profile"))
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.text_input("👤 " + ("Nombre Completo" if not is_en else "Full Name"), value="Usuario Demostración", disabled=True)
                st.text_input("💼 " + ("Título Profesional" if not is_en else "Professional Title"), value="Senior Python & Cloud Engineer", disabled=True)
                st.text_input("⏳ " + ("Años de Experiencia" if not is_en else "Years of Experience"), value="6 años", disabled=True)
            with col_p2:
                st.markdown("##### 🛠️ " + ("Habilidades Técnicas Registradas" if not is_en else "Registered Technical Skills"))
                st.markdown("`Python` `SQL` `FastAPI` `PostgreSQL` `Docker` `Streamlit` `GCP` `Git` `REST APIs`")
                st.markdown("##### 🤝 " + ("Habilidades Blandas" if not is_en else "Soft Skills"))
                st.markdown("`Trabajo en equipo` `Resolución de problemas` `Comunicación técnica`")

    # 8. Dashboard
    else:
        st.subheader("📊 " + ("Career Dashboard" if not is_en else "Career Dashboard"))
        st.caption(
            "Resumen ejecutivo del estado de tus aplicaciones y pipeline de entrevistas."
            if not is_en else
            "Executive overview of application pipeline and scheduled interview milestones."
        )
        _render_auth_callout()

        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        col_d1.metric("💼 " + ("Total Postulaciones" if not is_en else "Total Applications"), "18")
        col_d2.metric("🔄 " + ("En Proceso" if not is_en else "In Progress"), "7")
        col_d3.metric("🎯 " + ("Entrevistas Activas" if not is_en else "Active Interviews"), "3")
        col_d4.metric("🏆 " + ("Ofertas" if not is_en else "Offers"), "1")
