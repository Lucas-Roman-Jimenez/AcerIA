"""Contrato del cliente inyectable y respuestas simuladas para pruebas."""
from __future__ import annotations

from http.client import HTTPConnection, HTTPSConnection, HTTPException
import json as jsonlib

from typing import Callable, Protocol, Sequence


class ErrorLLM(RuntimeError):
    """Cualquier fallo del proveedor: red, clave, cuota, respuesta vacía..."""


class ClienteLLM(Protocol):
    def completar(self, sistema: str, usuario: str, *, json: bool = False, max_tokens: int = 800,
                  esquema: dict | None = None) -> str: ...


class ClienteClaude:
    def __init__(self, clave: str):
        self.clave = clave

    def completar(self, sistema, usuario, *, json=False, max_tokens=800, esquema=None):
        solicitud = {
            "model": "claude-sonnet-5-5",
            "system": sistema,
            "messages": [{"role": "user", "content": usuario}],
            "max_tokens": max_tokens,
            "output_config": {"effort": "low"},
        }
        if esquema:
            solicitud["output_config"]["format"] = {"type": "json_schema", "schema": esquema}
        elif json:
            solicitud["system"] += "\nDevuelve solo JSON."
        cabeceras = {"content-type": "application/json", "anthropic-version": "2023-06-01",
                     "x-api-key": self.clave}
        conexion = HTTPSConnection("api.anthropic.com", timeout=120)
        try:
            conexion.request("POST", "/v1/messages", jsonlib.dumps(solicitud), cabeceras)
            respuesta = conexion.getresponse()
            if respuesta.status != 200:
                raise ErrorLLM(f"Anthropic respondió con estado {respuesta.status}.")
            datos = jsonlib.loads(respuesta.read())
            texto = "".join(b["text"] for b in datos["content"] if b["type"] == "text")
            if not texto.strip() or datos.get("stop_reason") in ("max_tokens", "refusal"):
                raise ErrorLLM("Claude no devolvió una respuesta completa.")
            return texto
        except (OSError, HTTPException, ValueError, KeyError, TypeError) as error:
            raise ErrorLLM("No se pudo consultar Claude.") from error
        finally:
            conexion.close()


class ClienteOllama:
    def __init__(self, modelo: str):
        self.modelo = modelo

    def completar(self, sistema, usuario, *, json=False, max_tokens=800, esquema=None):
        solicitud = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "stream": False,
            "options": {"temperature": 0, "num_predict": max_tokens},
        }
        if esquema or json:
            solicitud["format"] = esquema or "json"
        conexion = HTTPConnection("127.0.0.1", 11434, timeout=120)
        try:
            conexion.request("POST", "/api/chat", jsonlib.dumps(solicitud), {"Content-Type": "application/json"})
            respuesta = conexion.getresponse()
            if respuesta.status != 200:
                raise ErrorLLM(f"Ollama respondió con estado {respuesta.status}.")
            contenido = jsonlib.loads(respuesta.read())["message"]["content"]
            if not isinstance(contenido, str) or not contenido.strip():
                raise ErrorLLM("Ollama devolvió una respuesta vacía.")
            return contenido
        except (OSError, HTTPException, ValueError, KeyError, TypeError) as error:
            raise ErrorLLM("No se pudo obtener una respuesta de Ollama local.") from error
        finally:
            conexion.close()


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
