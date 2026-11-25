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
    def completar(self, sistema: str, usuario: str, *, json: bool = False, max_tokens: int = 800) -> str: ...


class ClienteAnthropic:
    def __init__(self, modelo: str | None = None, timeout: float = 20.0):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise ErrorLLM("Falta el paquete 'anthropic' (pip install anthropic)") from e
        self._cli = anthropic.Anthropic(timeout=timeout)
        self.modelo = modelo or os.getenv("LLM_MODELO") or "claude-sonnet-5-5"

    def completar(self, sistema, usuario, *, json=False, max_tokens=800):
        if json:
            usuario += "\n\nResponde únicamente con el objeto JSON, sin texto adicional."
        try:
            r = self._cli.messages.create(model=self.modelo, max_tokens=max_tokens, system=sistema,
                                          messages=[{"role": "user", "content": usuario}])
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        except Exception as e:
            raise ErrorLLM(str(e)) from e


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

    def completar(self, sistema, usuario, *, json=False, max_tokens=800):
        try:
            extra = {"response_format": {"type": "json_object"}} if json else {}
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

    def completar(self, sistema, usuario, *, json=False, max_tokens=800):
        self.llamadas.append((sistema, usuario))
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
