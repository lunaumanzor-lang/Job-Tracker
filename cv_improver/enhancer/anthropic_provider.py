"""
Implementación de LLMProvider utilizando la API oficial de Anthropic.
Obtiene la clave de API desde la variable de entorno ANTHROPIC_API_KEY o explícitamente.
"""

import os
from typing import Optional
import anthropic
from .provider_base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Proveedor de IA usando Anthropic Claude."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022"
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "No se encontró la clave de API de Anthropic. Configura la variable de entorno "
                "ANTHROPIC_API_KEY o pásala al inicializar AnthropicProvider."
            )
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> str:
        """Invoca la API de Messages de Anthropic."""
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)
        # Extraer bloques de texto
        output_chunks = []
        for block in response.content:
            if getattr(block, "type", "") == "text":
                output_chunks.append(block.text)
        return "".join(output_chunks).strip()
