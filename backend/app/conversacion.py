"""Orquestación de /chat con el intérprete local, el buscador y el motor de reglas.

Flujo por mensaje (docs/contrato.md §1):
    interpretar() -> (pregunta) | buscar_bultos() -> pregunta_tras_busqueda() | responder()

El buscador determina qué bultos hay y qué transformaciones son posibles.
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[2]          # raíz del repo: llm/ y reglas/ viven ahí
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from llm import ErrorLLM, aviso_ia, interpretar, pregunta_tras_busqueda, responder  # noqa: E402

from app.buscador import CRITERIO_ORDEN, buscar_alternativas, buscar_bultos, construir_objetivo  # noqa: E402

MAX_MENSAJES = 40                                            # historial por conversación (RF-08)

# Historial de cada conversación, en memoria: se pierde al reiniciar el servidor.
conversaciones: dict[str, list[dict[str, str]]] = {}


def _respuesta(conv_id: str, estado: str, texto: str, especificacion: dict, **extra) -> dict:
    return {
        "conversacion_id": conv_id,
        "estado": estado,
        "especificacion": especificacion,
        "exactos": extra.get("exactos", []),
        "transformables": extra.get("transformables", []),
        "alternativas": extra.get("alternativas", []),   # RF-29: solo si no hay exactos ni transformables
        "pregunta": texto if estado == "pregunta" else None,
        "opciones": [],                           # botones: formato pendiente de acordar
        "texto": texto,
        "criterio_orden": CRITERIO_ORDEN,
        # Conserva el campo del contrato para indicar el origen de la respuesta.
        "aviso_ia": None if estado == "error" else aviso_ia(),
    }


def responder_chat(conv_id: str | None, mensaje: str) -> dict:
    conv_id = conv_id or f"c-{uuid4().hex}"     # sin ID, conversación nueva: nunca una compartida
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

    # Buscador de Alonso: exactos y transformables del motor de Lucas, verificados y ordenados (RF-10 a RF-14).
    objetivo = construir_objetivo(espec)
    exactos, transformables = buscar_bultos(objetivo)

    p = pregunta_tras_busqueda(r.especificacion, exactos, historial=historial)
    if p:                                         # el stock real se distingue por un dato no dado (RF-07)
        return _guardar(historial, _respuesta(conv_id, "pregunta", p, espec))

    alternativas = [] if exactos or transformables else buscar_alternativas(objetivo)   # RF-29
    resultado = {"exactos": exactos, "transformables": transformables, "alternativas": alternativas,
                 "criterio_orden": CRITERIO_ORDEN}
    texto = responder(resultado, r.especificacion)
    estado = "resultados" if exactos or transformables else "sin_stock"
    return _guardar(historial, _respuesta(conv_id, estado, texto, espec,
                                          exactos=exactos, transformables=transformables,
                                          alternativas=alternativas))


def _guardar(historial: list[dict[str, str]], respuesta: dict) -> dict:
    historial.append({"rol": "asistente", "texto": respuesta["texto"]})
    del historial[:-MAX_MENSAJES]
    return respuesta
