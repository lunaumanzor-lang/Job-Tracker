"""
Implementación de LLMProvider utilizando la API oficial de Anthropic.
Obtiene la clave de API desde la variable de entorno ANTHROPIC_API_KEY o explícitamente.
"""

from typing import Optional
import anthropic
from .provider_base import LLMProvider
from ai_client import get_ai_api_key


class AnthropicProvider(LLMProvider):
    """Proveedor de IA usando Anthropic Claude."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022"
    ):
        self.api_key = api_key or get_ai_api_key("anthropic")
        if not self.api_key:
            raise ValueError(
                "No se encontró la clave de API de Anthropic en el servidor ni en el entorno."
            )
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        deadline: Optional[float] = None,
        timeout_per_call: float = 15.0
    ) -> str:
        """Invoca la API de Messages de Anthropic."""
        import time
        from ai_client import AITimeBudgetExceeded

        if deadline is not None and time.time() >= deadline:
            raise AITimeBudgetExceeded("⏱️ El tiempo límite asignado para la operación de IA ha sido superado.")

        effective_timeout = timeout_per_call
        if deadline is not None:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise AITimeBudgetExceeded("⏱️ El tiempo límite asignado para la operación de IA ha sido superado.")
            effective_timeout = min(timeout_per_call, remaining)

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "timeout": effective_timeout
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
