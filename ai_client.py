"""
Módulo centralizado para clientes de Inteligencia Artificial (Google Gemini y Anthropic).

Responsabilidades:
1. get_ai_api_key(provider): Lee la clave exclusivamente del servidor (st.secrets y os.getenv).
   Nunca inyecta en os.environ ni guarda en archivos .env.
2. generate_content_with_retry: Función central para invocar modelos Gemini con:
   - Reintentos con espera creciente (2s, 4s, 8s) EXCLUSIVAMENTE para errores 429 (ResourceExhausted / Rate limit / Quota).
   - Salto inmediato al siguiente modelo en cascada EXCLUSIVAMENTE para errores 404 (NotFound) y 503 (Unavailable / Overloaded).
   - Mensajes limpios y amigables al usuario ante cuota agotada o indisponibilidad, sin trazas técnicas.
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
import google.generativeai as genai

try:
    import streamlit as st
except ImportError:
    st = None

logger = logging.getLogger(__name__)


def get_ai_api_key(provider: str = "gemini") -> Optional[str]:
    """
    Obtiene la clave de API para el proveedor indicado ('gemini' o 'anthropic').
    Prioridad de lectura estrictamente del servidor:
    1. st.secrets (secrets.toml / Streamlit Cloud Secrets)
    2. os.getenv (Variables de entorno del sistema operativo)
    No inyecta ni modifica variables en os.environ ni archivos .env.
    """
    prov = (provider or "gemini").lower()
    key_name = "GEMINI_API_KEY" if prov in ("gemini", "google") else "ANTHROPIC_API_KEY"
    alt_name = "GOOGLE_API_KEY" if prov in ("gemini", "google") else None

    # 1. Intentar desde st.secrets si está disponible
    if st is not None:
        try:
            if hasattr(st, "secrets"):
                if key_name in st.secrets:
                    val = str(st.secrets[key_name]).strip()
                    if val:
                        return val
                if alt_name and alt_name in st.secrets:
                    val = str(st.secrets[alt_name]).strip()
                    if val:
                        return val
        except Exception:
            pass

    # 2. Intentar desde os.getenv
    val_env = os.getenv(key_name)
    if val_env and val_env.strip():
        return val_env.strip()

    if alt_name:
        val_alt = os.getenv(alt_name)
        if val_alt and val_alt.strip():
            return val_alt.strip()

    return None


def _is_429_error(exc: Exception) -> bool:
    """Verifica si la excepción corresponde a error HTTP 429 (TooManyRequests / ResourceExhausted / Quota)."""
    code = getattr(exc, "code", None)
    if code == 429:
        return True
    exc_type = type(exc).__name__
    if exc_type in ("ResourceExhausted", "TooManyRequests"):
        return True
    msg = str(exc).lower()
    if "429" in msg or "resource_exhausted" in msg or "resourceexhausted" in msg or "quota" in msg or "rate limit" in msg:
        return True
    return False


def _is_404_or_503_error(exc: Exception) -> bool:
    """Verifica si la excepción corresponde a 404 (NotFound / modelo no existe) o 503 (Unavailable / sin capacidad)."""
    code = getattr(exc, "code", None)
    if code in (404, 503):
        return True
    exc_type = type(exc).__name__
    if exc_type in ("NotFound", "ServiceUnavailable", "Unavailable"):
        return True
    msg = str(exc).lower()
    if "404" in msg or "not_found" in msg or "not found" in msg:
        return True
    if "503" in msg or "unavailable" in msg or "no capacity" in msg or "service_unavailable" in msg:
        return True
    return False


def _is_timeout_error(exc: Exception) -> bool:
    """Verifica si la excepción corresponde a un timeout o DeadlineExceeded (504/408/Deadline)."""
    code = getattr(exc, "code", None)
    if code in (504, 408):
        return True
    exc_type = type(exc).__name__
    if exc_type in ("DeadlineExceeded", "TimeoutError", "ConnectTimeout", "ReadTimeout"):
        return True
    msg = str(exc).lower()
    if "deadline" in msg or "timeout" in msg or "timed out" in msg or "504" in msg:
        return True
    return False


class AITimeBudgetExceeded(RuntimeError):
    """Excepción elevada cuando una operación o llamada de IA supera su tiempo límite (deadline)."""
    pass


def generate_content_with_retry(
    contents: Any,
    candidate_models: List[str],
    generation_config: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    request_options: Optional[Dict[str, Any]] = None,
    retry_delays: Tuple[float, ...] = (2.0, 4.0, 8.0),
    deadline: Optional[float] = None,
    timeout_per_call: float = 15.0
) -> Any:
    """
    Ejecuta generate_content en Gemini con cascada de modelos y política estricta de reintentos:
    - Timeout por llamada: 15 s por defecto vía request_options / timeout_per_call.
    - Deadline: Si se especifica, limita el tiempo total de la llamada; el timeout efectivo
      es min(timeout_per_call, tiempo_restante) y aborta con AITimeBudgetExceeded si se supera.
    - Errores 429 (ResourceExhausted): Reintenta en el MISMO modelo con espera creciente (ej. 2s, 4s, 8s).
      Si la espera supera el deadline, aborta inmediatamente con AITimeBudgetExceeded en vez de dormir.
    - Errores 404/503/Timeout: Salta INMEDIATAMENTE al siguiente modelo en candidate_models.
    - Otros errores: Registra advertencia y continúa al siguiente modelo de respaldo si existe.
    """
    key = api_key or get_ai_api_key("gemini")
    if not key:
        raise RuntimeError(
            "⚠️ Servicio de IA no disponible temporalmente. Por favor, intenta más tarde."
        )

    genai.configure(api_key=key)

    if not candidate_models:
        raise RuntimeError(
            "⚠️ Servicio de IA no disponible temporalmente (sin modelos configurados)."
        )

    # Base timeout configurado
    req_options = dict(request_options) if request_options else {}
    base_timeout = float(req_options.get("timeout", timeout_per_call))

    last_error: Optional[Exception] = None

    for model_name in candidate_models:
        # Regla (2): antes de probar cada modelo, si el deadline ya pasó, aborta la cascada
        if deadline is not None and time.monotonic() >= deadline:
            logger.warning(f"Presupuesto de tiempo agotado antes de probar modelo '{model_name}'. Abortando cascada.")
            raise AITimeBudgetExceeded("⏱️ El tiempo límite asignado para la operación de IA ha sido superado.")

        logger.info(f"Llamando a Gemini con modelo: '{model_name}'...")
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config
            )
        except Exception as init_err:
            logger.warning(f"Error al inicializar modelo '{model_name}': {init_err}")
            if _is_404_or_503_error(init_err):
                continue
            last_error = init_err
            continue

        # Reintentos con espera creciente SOLO para errores 429
        max_attempts = len(retry_delays) + 1
        for attempt in range(max_attempts):
            # Regla (3): el timeout efectivo de cada llamada es min(timeout_per_call, tiempo_restante)
            call_options = dict(req_options)
            if deadline is not None:
                tiempo_restante = deadline - time.monotonic()
                if tiempo_restante <= 0:
                    raise AITimeBudgetExceeded("⏱️ El tiempo límite asignado para la operación de IA ha sido superado.")
                effective_timeout = min(base_timeout, tiempo_restante)
                call_options["timeout"] = effective_timeout
            else:
                call_options["timeout"] = base_timeout

            try:
                response = model.generate_content(
                    contents,
                    request_options=call_options
                )
                if response and (hasattr(response, "text") or hasattr(response, "parts")):
                    return response
                logger.warning(f"Respuesta vacía recibida del modelo '{model_name}'.")
                break
            except Exception as exc:
                last_error = exc
                if _is_429_error(exc):
                    if attempt < len(retry_delays):
                        delay = retry_delays[attempt]
                        # Regla (4): antes de cada sleep por 429, si ahora + delay >= deadline, aborta en vez de dormir
                        if deadline is not None and (time.monotonic() + delay) >= deadline:
                            logger.warning(
                                f"Reintento de 429 en '{model_name}' con espera {delay}s excedería el deadline ({deadline}). Abortando."
                            )
                            raise AITimeBudgetExceeded("⏱️ El tiempo límite de la operación de IA no permite esperar al reintento de cuota.")

                        logger.warning(
                            f"Límite temporal 429 en '{model_name}'. Reintentando en {delay}s "
                            f"(intento {attempt + 1}/{len(retry_delays)})..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        # Reintentos de 429 agotados: Mensaje claro y limpio sin trazas técnicas
                        logger.error(f"Reintentos por 429 agotados en '{model_name}'.")
                        raise RuntimeError(
                            "⏳ El servicio de inteligencia artificial ha alcanzado su límite temporal de peticiones. "
                            "Por favor, espera unos segundos e intenta nuevamente."
                        )
                elif _is_404_or_503_error(exc):
                    # Salto al siguiente modelo solo para 404/503
                    logger.warning(
                        f"Modelo '{model_name}' no disponible ({exc}). "
                        "Saltando inmediatamente al siguiente modelo en cascada..."
                    )
                    break
                elif _is_timeout_error(exc):
                    # Salto inmediato al siguiente modelo en caso de timeout
                    logger.warning(
                        f"Timeout ({call_options.get('timeout')}s) en modelo '{model_name}' ({exc}). "
                        "Saltando inmediatamente al siguiente modelo en cascada..."
                    )
                    break
                else:
                    # Cualquier otro error no recuperable en este modelo
                    logger.warning(f"Error no clasificable con '{model_name}': {exc}")
                    break

    logger.error(f"No se pudo completar la llamada con ningún modelo candidato: {last_error}")
    raise RuntimeError(
        "⚠️ El servicio de inteligencia artificial no está disponible en este momento. "
        "Por favor, intenta más tarde."
    )
