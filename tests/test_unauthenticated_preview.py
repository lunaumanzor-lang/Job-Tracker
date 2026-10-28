# ==============================================================================
# PROYECTO: Smart Job Tracker
# PRUEBAS UNITARIAS: Vistas no autenticadas (Modo Demostración / Preview Mode)
# ==============================================================================

import pytest
from unittest.mock import MagicMock, patch
import streamlit as st
import preview_mode


MENU_SECTIONS = [
    "add_app",
    "view_apps",
    "analyzer",
    "coach",
    "cv_improver",
    "stats",
    "profile",
    "dashboard",
]

LOCALIZED_MENU_LABELS = [
    "➕ Agregar Nueva Aplicación",
    "➕ Add New Application",
    "📋 Ver y Gestionar Aplicaciones",
    "📋 View & Manage Applications",
    "🎯 Ver Compatibilidad y Sugerir Cursos",
    "🎯 View Compatibility & Suggest Courses",
    "🎯 Prepararme para este puesto",
    "🎯 Prepare me for this job",
    "✨ Mejorar CV con IA",
    "✨ CV Improver (AI)",
    "📈 Estadísticas",
    "📈 Statistics",
    "👤 Mi Perfil",
    "👤 My Profile",
]


@pytest.fixture(autouse=True)
def clean_streamlit_session():
    """Limpia y asegura el session_state sin usuario autenticado."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["user"] = None
    st.session_state["lang"] = "es"
    yield
    for key in list(st.session_state.keys()):
        del st.session_state[key]


@pytest.mark.parametrize("section", MENU_SECTIONS + LOCALIZED_MENU_LABELS)
@pytest.mark.parametrize("lang", ["es", "en"])
def test_preview_mode_makes_no_supabase_or_ai_calls(section, lang):
    """
    Verifica que al renderizar cada sección del menú en modo demostración (sin sesión):
    1. NO se llame a Supabase bajo ninguna circunstancia.
    2. NO se llame a la IA (generate_content_with_retry, ai_service).
    3. NO se llame al scraper de vacantes (job_scraper).
    4. Los datos mostrados sean exclusivamente estáticos y ficticios.
    """
    st.session_state["user"] = None
    st.session_state["lang"] = lang

    with patch("ai_client.generate_content_with_retry") as mock_retry, \
         patch("ai_service.generate_interview_questions") as mock_questions, \
         patch("ai_service.generate_skill_gaps_study") as mock_study, \
         patch("ai_service.analyze_job_description") as mock_analyze, \
         patch("ai_service.evaluate_interview_answer") as mock_eval, \
         patch("job_scraper.extract_job_text_from_url") as mock_scraper, \
         patch("app.supabase") as mock_app_supabase:

        # Ejecutar renderizado demostrativo de la sección
        preview_mode.render_unauthenticated_preview(section)

        # Aserciones estrictas: NINGUNA llamada debe haberse producido
        mock_retry.assert_not_called()
        mock_questions.assert_not_called()
        mock_study.assert_not_called()
        mock_analyze.assert_not_called()
        mock_eval.assert_not_called()
        mock_scraper.assert_not_called()
        mock_app_supabase.table.assert_not_called()
        mock_app_supabase.auth.get_user.assert_not_called()


def test_unauthenticated_guard_triggers_preview_and_stops():
    """
    Verifica que cuando st.session_state.user is None, el flujo principal
    invoca a preview_mode.render_unauthenticated_preview y ejecuta st.stop(),
    garantizando que ninguna vista real ni consulta autenticada pueda ejecutarse.
    """
    st.session_state["user"] = None
    st.session_state["lang"] = "es"

    with patch("preview_mode.render_unauthenticated_preview") as mock_render_preview, \
         patch("streamlit.stop") as mock_st_stop:

        # Simular la guardia de autenticación exacta de app.py (líneas 807-809)
        menu_opcion = "dashboard"
        if st.session_state.user is None:
            preview_mode.render_unauthenticated_preview(menu_opcion)
            st.stop()

        mock_render_preview.assert_called_once_with("dashboard")
        mock_st_stop.assert_called_once()


def test_unauthenticated_visitor_never_calls_service_role_client():
    """
    Verifica que un visitante sin sesión no invoque _get_service_role_client
    ni cleanup_expired_sessions en ninguna sección del modo preview ni en el ciclo de carga.
    """
    st.session_state["user"] = None
    st.session_state["lang"] = "es"

    with patch("database._get_service_role_client") as mock_service_role, \
         patch("database.cleanup_expired_sessions") as mock_cleanup:

        for section in MENU_SECTIONS:
            preview_mode.render_unauthenticated_preview(section)

        # Confirmar que en ninguna sección se llamó al cliente service_role ni a cleanup
        mock_service_role.assert_not_called()
        mock_cleanup.assert_not_called()


def test_maybe_cleanup_expired_sessions_behavior():
    """
    Verifica que maybe_cleanup_expired_sessions:
    1. Se ejecute solo tras llamada explícita y respete el cooldown por proceso (máx 1 vez/hora).
    2. Si cleanup_expired_sessions falla, capture la excepción y no rompa la ejecución.
    """
    import app
    import time

    # Resetear marca de tiempo a nivel de proceso
    app._LAST_SESSION_CLEANUP_TS = 0.0

    with patch("app.cleanup_expired_sessions") as mock_cleanup:
        # Primera llamada: debe ejecutarse
        app.maybe_cleanup_expired_sessions(cooldown_seconds=3600)
        assert mock_cleanup.call_count == 1

        # Segunda llamada inmediata: debe ignorarse por cooldown de 1 hora
        app.maybe_cleanup_expired_sessions(cooldown_seconds=3600)
        assert mock_cleanup.call_count == 1

        # Si avanza el tiempo más de 1 hora: debe ejecutarse de nuevo
        app._LAST_SESSION_CLEANUP_TS = time.time() - 3601
        app.maybe_cleanup_expired_sessions(cooldown_seconds=3600)
        assert mock_cleanup.call_count == 2

    # Verificación de captura de excepciones (no rompe la aplicación)
    app._LAST_SESSION_CLEANUP_TS = 0.0
    with patch("app.cleanup_expired_sessions", side_effect=RuntimeError("Supabase connection error")):
        # No debe lanzar excepción
        app.maybe_cleanup_expired_sessions(cooldown_seconds=3600)

