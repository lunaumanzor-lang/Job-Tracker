"""
Test suite for ai_client.py:
- get_ai_api_key resolution
- 429 backoff retry on same model
- 404 / 503 immediate model jumping
- Clean error messaging
"""

import os
import time
from unittest.mock import MagicMock, patch
import pytest

from ai_client import (
    get_ai_api_key,
    generate_content_with_retry,
    _is_429_error,
    _is_404_or_503_error,
    _is_timeout_error,
    AITimeBudgetExceeded
)


def test_error_classification():
    # 429 tests
    class Fake429(Exception):
        code = 429

    assert _is_429_error(Fake429("Rate limit exceeded"))
    assert _is_429_error(Exception("ResourceExhausted: 429 Quota exceeded"))
    assert _is_429_error(Exception("Rate limit reached, please slow down"))
    assert not _is_429_error(Exception("Model not found 404"))
    assert not _is_429_error(Exception("503 Service Unavailable"))

    # 404 / 503 tests
    class Fake404(Exception):
        code = 404

    class Fake503(Exception):
        code = 503

    assert _is_404_or_503_error(Fake404("Not found"))
    assert _is_404_or_503_error(Fake503("Service Unavailable"))
    assert _is_404_or_503_error(Exception("models/gemini-old is not found"))
    assert _is_404_or_503_error(Exception("503 No capacity available for model"))
    assert not _is_404_or_503_error(Fake429("Rate limit"))


def test_429_backoff_and_no_model_jump():
    models_tried = []
    sleeps = []

    class MockModel:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            models_tried.append(model_name)

        def generate_content(self, *args, **kwargs):
            # Always raise 429
            exc = Exception("429 ResourceExhausted: Quota exceeded")
            exc.code = 429
            raise exc

    with patch("ai_client.genai.GenerativeModel", side_effect=MockModel):
        with patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
            with pytest.raises(RuntimeError) as exc_info:
                generate_content_with_retry(
                    contents="test",
                    candidate_models=["model-primary", "model-fallback"],
                    api_key="fake-key",
                    retry_delays=(2.0, 4.0, 8.0)
                )

            msg = str(exc_info.value)
            # Rule 3: clean message, no technical trace
            assert "límite temporal" in msg or "límite" in msg
            assert "Traceback" not in msg
            assert "ResourceExhausted" not in msg

    # Verify that it slept (2.0, 4.0, 8.0)
    assert sleeps == [2.0, 4.0, 8.0], f"Expected [2.0, 4.0, 8.0], got {sleeps}"

    # Verify that it did NOT jump to model-fallback for 429!
    assert models_tried == ["model-primary"], "Must NOT jump to fallback model on 429 error!"


def test_404_503_immediate_model_jump():
    models_tried = []
    sleeps = []

    class MockModelJump:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            models_tried.append(model_name)

        def generate_content(self, *args, **kwargs):
            if self.model_name == "model-1-404":
                exc = Exception("404 Model not found")
                exc.code = 404
                raise exc
            elif self.model_name == "model-2-503":
                exc = Exception("503 UNAVAILABLE: No capacity available")
                exc.code = 503
                raise exc
            else:
                resp = MagicMock()
                resp.text = "Success from healthy model!"
                return resp

    with patch("ai_client.genai.GenerativeModel", side_effect=MockModelJump):
        with patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
            res = generate_content_with_retry(
                contents="test prompt",
                candidate_models=["model-1-404", "model-2-503", "model-3-success"],
                api_key="fake-key"
            )
            assert res.text == "Success from healthy model!"

    # Verify no sleeps occurred because jumps on 404/503 are immediate
    assert sleeps == [], "Jump on 404/503 should NOT sleep!"
    assert models_tried == ["model-1-404", "model-2-503", "model-3-success"]


def test_api_key_resolution():
    # 1. Probar fallback a os.getenv cuando st.secrets no contiene la clave
    with patch("ai_client.st", None):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-gemini-key", "ANTHROPIC_API_KEY": "env-claude-key"}):
            k_g = get_ai_api_key("gemini")
            k_a = get_ai_api_key("anthropic")
            assert k_g == "env-gemini-key"
            assert k_a == "env-claude-key"

    # 2. Probar prioridad de st.secrets sobre os.getenv
    mock_secrets = {"GEMINI_API_KEY": "secret-gemini-key", "ANTHROPIC_API_KEY": "secret-claude-key"}
    with patch("ai_client.st") as mock_st:
        mock_st.secrets = mock_secrets
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-gemini-key"}):
            assert get_ai_api_key("gemini") == "secret-gemini-key"
            assert get_ai_api_key("anthropic") == "secret-claude-key"


def test_timeout_classification_and_immediate_jump():
    # Classification tests
    class Fake504(Exception):
        code = 504

    class DeadlineExceeded(Exception):
        pass

    assert _is_timeout_error(Fake504("Gateway Timeout"))
    assert _is_timeout_error(DeadlineExceeded("Deadline expired before operation could complete"))
    assert _is_timeout_error(Exception("504 Deadline expired"))
    assert _is_timeout_error(Exception("Connection timed out"))
    assert not _is_timeout_error(Exception("404 Not Found"))
    assert not _is_timeout_error(Exception("429 Rate limit"))

    # Immediate jump on timeout
    models_tried = []
    received_options = []

    class MockModelTimeout:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name
            models_tried.append(model_name)

        def generate_content(self, *args, **kwargs):
            received_options.append(kwargs.get("request_options"))
            if self.model_name == "model-timeout":
                exc = DeadlineExceeded("504 Deadline expired")
                exc.code = 504
                raise exc
            resp = MagicMock()
            resp.text = "Success after timeout fallback"
            return resp

    with patch("ai_client.genai.GenerativeModel", side_effect=MockModelTimeout):
        res = generate_content_with_retry(
            contents="test prompt",
            candidate_models=["model-timeout", "model-healthy"],
            api_key="fake-key"
        )
        assert res.text == "Success after timeout fallback"
        assert models_tried == ["model-timeout", "model-healthy"]
        # Verify 15s default timeout was passed
        assert received_options[0] == {"timeout": 15.0}
        assert received_options[1] == {"timeout": 15.0}


def test_cascade_aborts_on_deadline_with_simulated_clock():
    """Regla (7a): La cascada no excede el deadline aunque todos los modelos fallen con timeout."""
    clock = [100.0]
    models_called = []

    def fake_time():
        return clock[0]

    class MockTimingOutModel:
        def __init__(self, model_name, **kwargs):
            self.model_name = model_name

        def generate_content(self, *args, **kwargs):
            models_called.append(self.model_name)
            # Simula que cada llamada tarda 10 segundos antes de dar timeout
            clock[0] += 10.0
            exc = Exception("504 Deadline expired")
            exc.code = 504
            raise exc

    # Presupuesto: 25 segundos (deadline = 125.0)
    deadline = 125.0
    cascade = ["model-1", "model-2", "model-3", "model-4"]

    with patch("time.monotonic", side_effect=fake_time):
        with patch("ai_client.time.monotonic", side_effect=fake_time):
            with patch("ai_client.genai.GenerativeModel", side_effect=MockTimingOutModel):
                with pytest.raises(AITimeBudgetExceeded):
                    generate_content_with_retry(
                        contents="prompt",
                        candidate_models=cascade,
                        api_key="fake-key",
                        deadline=deadline
                    )

    # model-1: t=100 -> t=110 (timeout)
    # model-2: t=110 -> t=120 (timeout)
    # model-3: t=120 -> t=130 (timeout)
    # model-4: antes de probar model-4, t=130 >= 125, aborta por deadline
    assert "model-4" not in models_called, "model-4 no debió llamarse al haberse superado el deadline"


def test_429_does_not_sleep_if_exceeding_deadline():
    """Regla (7b): Un error 429 no duerme si la espera excede el deadline."""
    clock = [100.0]
    sleeps = []

    def fake_time():
        return clock[0]

    class Mock429Model:
        def __init__(self, model_name, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            exc = Exception("429 ResourceExhausted")
            exc.code = 429
            raise exc

    # Deadline a 1 segundo en el futuro (101.0), pero el primer delay de 429 es de 2.0 s
    deadline = 101.0

    with patch("time.monotonic", side_effect=fake_time):
        with patch("ai_client.time.monotonic", side_effect=fake_time):
            with patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
                with patch("ai_client.time.sleep", side_effect=lambda s: sleeps.append(s)):
                    with patch("ai_client.genai.GenerativeModel", side_effect=Mock429Model):
                        with pytest.raises(AITimeBudgetExceeded):
                            generate_content_with_retry(
                                contents="prompt",
                                candidate_models=["model-primary"],
                                api_key="fake-key",
                                deadline=deadline,
                                retry_delays=(2.0, 4.0, 8.0)
                            )

    # Verifica que NUNCA durmió porque now + delay (100 + 2 = 102) >= deadline (101)
    assert sleeps == [], f"No debió dormirse al superar el deadline, pero se llamó a sleep({sleeps})"


def test_effective_timeout_capped_by_remaining_time():
    """Regla (7c): El timeout efectivo de cada llamada nunca supera el tiempo restante."""
    clock = [100.0]
    received_timeout = []

    def fake_time():
        return clock[0]

    class MockCaptureTimeoutModel:
        def __init__(self, model_name, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            opts = kwargs.get("request_options", {})
            received_timeout.append(opts.get("timeout"))
            resp = MagicMock()
            resp.text = "OK"
            return resp

    # timeout_per_call = 15.0, pero tiempo restante es solo 6.5 s (deadline = 106.5)
    deadline = 106.5

    with patch("time.monotonic", side_effect=fake_time):
        with patch("ai_client.time.monotonic", side_effect=fake_time):
            with patch("ai_client.genai.GenerativeModel", side_effect=MockCaptureTimeoutModel):
                res = generate_content_with_retry(
                    contents="prompt",
                    candidate_models=["model-quick"],
                    api_key="fake-key",
                    deadline=deadline,
                    timeout_per_call=15.0
                )
                assert res.text == "OK"

    assert len(received_timeout) == 1
    assert received_timeout[0] == pytest.approx(6.5, rel=1e-3), (
        f"El timeout efectivo debió ser 6.5s, se obtuvo {received_timeout[0]}"
    )


