"""Contrato del cliente inyectable y respuestas simuladas para pruebas."""
from __future__ import annotations

from typing import Callable, Protocol, Sequence


class ErrorLLM(RuntimeError):
    """Cualquier fallo del proveedor: red, clave, cuota, respuesta vacía..."""


class ClienteLLM(Protocol):
    def completar(self, sistema: str, usuario: str, *, json: bool = False, max_tokens: int = 800,
                  esquema: dict | None = None) -> str: ...


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
