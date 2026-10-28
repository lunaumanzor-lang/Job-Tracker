"""
Interfaz abstracta para proveedores de modelos de lenguaje (LLMProvider).
Permite desacoplar la lógica de negocio del proveedor de IA (Anthropic, Gemini, OpenAI, etc.).
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json
import re


class LLMProvider(ABC):
    """Contrato base para cualquier proveedor de IA que implemente análisis o generación de CV."""

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        deadline: Optional[float] = None,
        timeout_per_call: float = 15.0
    ) -> str:
        """Genera una respuesta de texto libre dado un prompt."""
        pass

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        deadline: Optional[float] = None,
        timeout_per_call: float = 15.0
    ) -> Dict[str, Any]:
        """
        Envía un prompt solicitando salida estructurada en JSON y retorna el diccionario parseado.
        Limpia automáticamente bloques de código markdown como ```json ... ```.
        """
        try:
            raw_output = self.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                deadline=deadline,
                timeout_per_call=timeout_per_call
            )
        except TypeError as te:
            if "deadline" in str(te) or "timeout_per_call" in str(te):
                raw_output = self.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                raise
        cleaned = self._clean_json_string(raw_output)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as err:
            # Intento de extracción por expresión regular si el LLM incluyó texto antes o después
            match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"La respuesta del LLM no es un JSON válido: {err}\nSalida recibida:\n{raw_output}")

    @staticmethod
    def _clean_json_string(text: str) -> str:
        """Remueve bloques ```json y ``` y espacios circundantes."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
