"""Clientes de LLM intercambiables. El proveedor se elige con variables de entorno:

    LLM_PROVEEDOR = anthropic | openai
    LLM_MODELO    = nombre del modelo (obligatorio para openai)
    ANTHROPIC_API_KEY / OPENAI_API_KEY  (en el .env, nunca en el repositorio)
"""
from __future__ import annotations

import os
from typing import Callable, Protocol, Sequence


class ErrorLLM(RuntimeError):
    """Cualquier fallo del proveedor: red, clave, cuota, respuesta vacía..."""


class ClienteLLM(Protocol):
    def completar(self, sistema: str, usuario: str, *, json: bool = False, max_tokens: int = 800,
                  esquema: dict | None = None) -> str: ...


class ClienteAnthropic:
    def __init__(self, modelo: str | None = None, timeout: float = 10.0):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise ErrorLLM("Falta el paquete 'anthropic' (pip install anthropic)") from e
        # 10 s y 1 reintento: si falla, el error con «reintentar» llega en ~20 s y no en más de un minuto (RNF-14).
        self._cli = anthropic.Anthropic(timeout=timeout, max_retries=1)
        self.modelo = modelo or os.getenv("LLM_MODELO") or "claude-sonnet-5-5"

    def completar(self, sistema, usuario, *, json=False, max_tokens=800, esquema=None):
        extra = {}
        if esquema:
            # Salida estructurada: el JSON siempre es válido y cumple el esquema. Esfuerzo bajo: es una
            # extracción corta y así responde antes (RNF-05). Sonnet 5.5 no admite temperature.
            extra["output_config"] = {"format": {"type": "json_schema", "schema": esquema}, "effort": "low"}
        elif json:
            usuario += "\n\nResponde únicamente con el objeto JSON, sin texto adicional."
        try:
            r = self._cli.messages.create(model=self.modelo, max_tokens=max_tokens, system=sistema,
                                          messages=[{"role": "user", "content": usuario}], **extra)
        except Exception as e:
            raise ErrorLLM(str(e)) from e
        if r.stop_reason in ("refusal", "max_tokens"):
            raise ErrorLLM(f"Respuesta incompleta del LLM ({r.stop_reason})")
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


class ClienteOpenAI:
    def __init__(self, modelo: str | None = None, timeout: float = 20.0):
        try:
            import openai
        except ImportError as e:  # pragma: no cover
            raise ErrorLLM("Falta el paquete 'openai' (pip install openai)") from e
        self.modelo = modelo or os.getenv("LLM_MODELO")
        if not self.modelo:
            raise ErrorLLM("Define LLM_MODELO con el modelo de OpenAI que vayáis a usar")
        self._cli = openai.OpenAI(timeout=timeout)

    def completar(self, sistema, usuario, *, json=False, max_tokens=800, esquema=None):
        try:
            extra = {"response_format": {"type": "json_object"}} if json or esquema else {}
            r = self._cli.chat.completions.create(
                model=self.modelo, max_tokens=max_tokens,
                messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], **extra)
            return r.choices[0].message.content or ""
        except Exception as e:
            raise ErrorLLM(str(e)) from e


class ClienteFalso:
    """Para tests y para trabajar sin clave: devuelve respuestas preparadas en orden,
    o las calcula con una función (sistema, usuario) -> texto."""

    def __init__(self, respuestas: Sequence[str] | Callable[[str, str], str] = ()):
        self._resp = respuestas if callable(respuestas) else list(respuestas)
        self.llamadas: list[tuple[str, str]] = []
        self.esquemas: list[dict | None] = []

    def completar(self, sistema, usuario, *, json=False, max_tokens=800, esquema=None):
        self.llamadas.append((sistema, usuario))
        self.esquemas.append(esquema)
        if callable(self._resp):
            return self._resp(sistema, usuario)
        if not self._resp:
            raise ErrorLLM("ClienteFalso sin más respuestas preparadas")
        r = self._resp.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def crear_cliente() -> ClienteLLM:
    proveedor = (os.getenv("LLM_PROVEEDOR") or "anthropic").lower()
    if proveedor == "anthropic":
        return ClienteAnthropic()
    if proveedor == "openai":
        return ClienteOpenAI()
    raise ErrorLLM(f"LLM_PROVEEDOR desconocido: {proveedor}")
