"""
Implementación de LLMProvider utilizando Google Gemini (genai).
Utiliza la API Key de Gemini configurada en .env o en el entorno,
con cascada de modelos para garantizar alta disponibilidad.
"""

import logging
from typing import Optional
from .provider_base import LLMProvider
from ai_client import get_ai_api_key, generate_content_with_retry, GEMINI_MODEL_CASCADE

logger = logging.getLogger(__name__)

# Cascada de modelos centralizada en ai_client.py
GEMINI_MODELS_CASCADE = GEMINI_MODEL_CASCADE


class GeminiProvider(LLMProvider):
    """Proveedor de IA utilizando Google Gemini con cliente centralizado."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_ai_api_key("gemini")
        if not self.api_key:
            raise ValueError("No se encontró la clave GEMINI_API_KEY en el servidor ni en el entorno.")

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        deadline: Optional[float] = None,
        timeout_per_call: float = 15.0
    ) -> str:
        """Invoca la API de Gemini usando la función central con reintentos para 429 y salto para 404/503."""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        response = generate_content_with_retry(
            contents=full_prompt,
            candidate_models=GEMINI_MODELS_CASCADE,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens
            },
            api_key=self.api_key,
            deadline=deadline,
            timeout_per_call=timeout_per_call
        )
        if response and response.text:
            return response.text.strip()
        raise RuntimeError("Respuesta vacía recibida del servicio de IA.")
