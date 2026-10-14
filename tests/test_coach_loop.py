# ==============================================================================
# PRUEBAS UNITARIAS: Prevención de bucles en Interview Coach (render_interview_coach)
# Verifica que ante respuestas con menos de 7 preguntas (ej. 5), la IA se llame una sola vez.
# ==============================================================================

import unittest
from unittest.mock import MagicMock, patch
import streamlit as st


class TestCoachInterviewLoopPrevention(unittest.TestCase):
    def setUp(self):
        # Limpiar session_state antes de cada prueba
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.session_state["user"] = MagicMock(email="test_user@example.com")
        st.session_state["lang"] = "es"

    @patch("app.generate_skill_gaps_study")
    @patch("app.generate_interview_questions")
    @patch("app.get_skills_by_application")
    @patch("app.get_all_user_skills")
    @patch("app.st.rerun")
    @patch("app.st.spinner")
    @patch("app.st.tabs")
    @patch("app.st.button")
    def test_five_questions_calls_ai_only_once(
        self,
        mock_button,
        mock_tabs,
        mock_spinner,
        mock_rerun,
        mock_get_user_skills,
        mock_get_app_skills,
        mock_gen_questions,
        mock_gen_study
    ):
        """
        Simula que la IA devuelve exactamente 5 preguntas y comprueba que:
        1. Se llama a la IA una sola vez en el primer renderizado.
        2. En la siguiente recarga/rerun no se vuelve a llamar a la IA (no hay bucle).
        3. Se aceptan y conservan las 5 preguntas devueltas.
        """
        from app import render_interview_coach

        # Configuración de mocks
        mock_get_app_skills.return_value = []
        mock_get_user_skills.return_value = []
        mock_gen_study.return_value = [{"skill": "Docker", "importance": "Required"}]

        # Simular que Gemini devuelve únicamente 5 preguntas
        cinco_preguntas = [
            {"id": i, "category": "Fortaleza Técnica", "focus_skill": f"Skill {i}", "question": f"Pregunta {i}", "tip": "Tip"}
            for i in range(1, 6)
        ]
        mock_gen_questions.return_value = cinco_preguntas
        mock_button.return_value = False
        mock_tabs.return_value = [MagicMock(), MagicMock(), MagicMock()]

        app_mock = {
            "id": 999,
            "position": "Backend Developer",
            "company": "Tech Corp",
            "notes": "Testing notes"
        }

        # PRIMERA EJECUCIÓN (Carga inicial)
        render_interview_coach(app_actual=app_mock, show_close_button=False)

        # Verificaciones tras la primera ejecución:
        # 1. generate_interview_questions se llamó exactamente 1 vez
        self.assertEqual(mock_gen_questions.call_count, 1)
        # 2. Las 5 preguntas quedaron guardadas en la sesión
        self.assertEqual(len(st.session_state["coach_session"]["questions"]), 5)
        # 3. La bandera questions_attempted quedó en True
        self.assertTrue(st.session_state["coach_session"]["questions_attempted"])
        # 4. Se solicitó el rerun de Streamlit
        self.assertTrue(mock_rerun.called)

        # SEGUNDA EJECUCIÓN (Simula el rerun/recarga de la página)
        render_interview_coach(app_actual=app_mock, show_close_button=False)

        # Verificaciones tras la segunda ejecución:
        # 1. generate_interview_questions NO se volvió a llamar (sigue siendo 1)
        self.assertEqual(mock_gen_questions.call_count, 1)
        # 2. Se mantienen y muestran las 5 preguntas tal cual sin entrar en bucle
        self.assertEqual(len(st.session_state["coach_session"]["questions"]), 5)


if __name__ == "__main__":
    unittest.main()
