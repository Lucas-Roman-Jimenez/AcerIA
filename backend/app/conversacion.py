"""Orquestación de /chat: módulo LLM de Nacho + buscador de Alonso + motor de reglas de Lucas.

Flujo por mensaje (docs/contrato.md §1):
    interpretar() -> (pregunta) | buscar exactos y transformables -> pregunta_tras_busqueda() | responder()

El LLM solo interpreta y redacta; qué bultos hay y qué transformaciones son posibles lo decide
el código (RNF-02). Devuelve el mismo formato que la respuesta de prueba de main.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]          # raíz del repo: llm/ y reglas/ viven ahí
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from llm import ErrorLLM, interpretar, pregunta_tras_busqueda, responder  # noqa: E402
from reglas.motor import aplicar_reglas  # noqa: E402

from app.buscador import a_respuesta, buscar_exactos, construir_objetivo  # noqa: E402
from app.db import disponibles  # noqa: E402

CRITERIO_ORDEN = "exactos > % de merma > nº de operaciones"   # RF-14, el mismo que /buscar
MAX_MENSAJES = 40                                            # historial por conversación (RF-08)

# Historial de cada conversación, en memoria: se pierde al reiniciar el servidor.
conversaciones: dict[str, list[dict[str, str]]] = {}


def cargar_env(ruta: Path = RAIZ / ".env") -> None:
    """Carga el .env de la raíz (clave y modelo del gateway). No pisa variables ya definidas."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.strip().startswith("#"):
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


def buscar_transformables(objetivo: dict) -> list[dict]:
    """Bultos disponibles que el motor de Lucas puede adaptar al objetivo, ordenados por merma y operaciones."""
    resultado = []
    for bulto in disponibles():
        for t in aplicar_reglas(bulto, objetivo):
            resultado.append(dict(t, bulto=a_respuesta(bulto)))   # «antes» para la tarjeta y para responder()
    resultado.sort(key=lambda t: (t.get("merma_pct", float("inf")), t.get("num_operaciones", 99)))
    return resultado


def _respuesta(conv_id: str, estado: str, texto: str, especificacion: dict, **extra) -> dict:
    return {
        "conversacion_id": conv_id,
        "estado": estado,
        "especificacion": especificacion,
        "exactos": extra.get("exactos", []),
        "transformables": extra.get("transformables", []),
        "alternativas": [],                       # RF-29: pendiente
        "pregunta": texto if estado == "pregunta" else None,
        "opciones": [],                           # botones: formato pendiente de acordar
        "texto": texto,
        "criterio_orden": CRITERIO_ORDEN,
    }


def responder_chat(conv_id: str | None, mensaje: str) -> dict:
    conv_id = conv_id or "demo-1"
    historial = conversaciones.setdefault(conv_id, [])
    historial.append({"rol": "comercial", "texto": mensaje or ""})

    try:
        r = interpretar(historial)
    except ErrorLLM:
        historial.pop()                           # el mensaje no cuenta: el comercial puede reintentar
        return _respuesta(conv_id, "error", "No he podido procesar la petición. Inténtalo de nuevo o escríbela.", {})

    espec = r.especificacion.a_dict()
    if r.tipo == "pregunta":                      # faltan datos, valor inválido, saludo, precio...
        return _guardar(historial, _respuesta(conv_id, "pregunta", r.pregunta, espec))

    objetivo = construir_objetivo(espec)
    exactos = buscar_exactos(objetivo)
    transformables = buscar_transformables(objetivo)

    p = pregunta_tras_busqueda(r.especificacion, exactos, historial=historial)
    if p:                                         # el stock real se distingue por un dato no dado (RF-07)
        return _guardar(historial, _respuesta(conv_id, "pregunta", p, espec))

    resultado = {"exactos": exactos, "transformables": transformables, "alternativas": [],
                 "criterio_orden": CRITERIO_ORDEN}
    texto = responder(resultado, r.especificacion)
    estado = "resultados" if exactos or transformables else "sin_stock"
    return _guardar(historial, _respuesta(conv_id, estado, texto, espec,
                                          exactos=exactos, transformables=transformables))


def _guardar(historial: list[dict[str, str]], respuesta: dict) -> dict:
    historial.append({"rol": "asistente", "texto": respuesta["texto"]})
    del historial[:-MAX_MENSAJES]
    return respuesta
