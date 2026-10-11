"""
Submódulo de mejora de contenido con LLMs (Anthropic, etc.).
"""

from .provider_base import LLMProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider
from .bullet_enhancer import (
    improve_bullet_point,
    enhance_summary,
    enhance_resume_content
)
import os
from typing import Optional, Tuple


def get_active_llm_provider(
    anthropic_key: Optional[str] = None,
    gemini_key: Optional[str] = None
) -> Tuple[Optional[LLMProvider], str]:
    """
    Detecta y retorna la mejor instancia de LLMProvider disponible.
    Prioriza Gemini si está configurada en .env o por el usuario, o Claude si se especifica.
    """
    g_key = gemini_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    a_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY")

    if g_key and g_key.strip():
        try:
            return GeminiProvider(api_key=g_key.strip()), "Google Gemini"
        except Exception as e:
            pass

    if a_key and a_key.strip():
        try:
            return AnthropicProvider(api_key=a_key.strip()), "Anthropic Claude"
        except Exception as e:
            pass

    return None, "Reglas Estructuradas ATS (Heurístico)"


__all__ = [
    "LLMProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "get_active_llm_provider",
    "improve_bullet_point",
    "enhance_summary",
    "enhance_resume_content"
]

