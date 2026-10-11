"""
Implementación de LLMProvider utilizando Google Gemini (genai).
Utiliza la API Key de Gemini configurada en .env o en el entorno,
con cascada de modelos para garantizar alta disponibilidad.
"""

import os
import logging
from typing import Optional
import google.generativeai as genai
from .provider_base import LLMProvider

logger = logging.getLogger(__name__)

GEMINI_MODELS_CASCADE = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest"
]


class GeminiProvider(LLMProvider):
    """Proveedor de IA utilizando Google Gemini."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("No se encontró la clave GEMINI_API_KEY ni GOOGLE_API_KEY en el entorno.")
        genai.configure(api_key=self.api_key)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> str:
        """Invoca la API de Gemini usando la cascada de modelos disponibles."""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        ultimo_error = None
        for model_name in GEMINI_MODELS_CASCADE:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens
                    }
                )
                response = model.generate_content(full_prompt)
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                ultimo_error = e
                logger.warning(f"Fallo temporal con modelo {model_name}: {e}. Probando siguiente en cascada...")

        raise RuntimeError(f"No se pudo generar respuesta con ningún modelo de Gemini: {ultimo_error}")
