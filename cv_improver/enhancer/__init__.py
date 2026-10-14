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
from typing import Optional, Tuple
from ai_client import get_ai_api_key


def get_active_llm_provider(
    anthropic_key: Optional[str] = None,
    gemini_key: Optional[str] = None
) -> Tuple[Optional[LLMProvider], str]:
    """
    Detecta y retorna la mejor instancia de LLMProvider disponible.
    Prioriza Gemini si está configurada en el servidor, o Claude si se especifica.
    """
    g_key = gemini_key or get_ai_api_key("gemini")
    a_key = anthropic_key or get_ai_api_key("anthropic")

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

