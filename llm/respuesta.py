"""responder(): resultado del backend -> texto para el comercial (RF-15, RF-16, RNF-01).

El texto del LLM se acepta solo si no añade cifras, valores del catálogo ni bultos
que no estén en el resultado. Si no, o si el LLM falla, se usa una plantilla.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from . import prompts
from .catalogo import Catalogo
from .contrato import Especificacion
from .control import fmt_num, no_inventa
from .proveedores import ClienteLLM, ErrorLLM

_ID = re.compile(r"\b[A-Z]{1,4}-\d{2,}\b")


def _describir_bulto(b: dict[str, Any]) -> str:
    partes = []
    tipo = " ".join(str(b[k]) for k in ("grado", "acabado") if b.get(k))
    if tipo:
        partes.append(tipo)
    medidas = [fmt_num(b[k]) for k in ("espesor_mm", "ancho_mm", "largo_mm") if b.get(k)]
    if medidas:
        partes.append(" × ".join(medidas) + " mm")
    if b.get("peso_kg"):
        partes.append(f"{fmt_num(b['peso_kg'])} kg")
    if b.get("ubicacion"):
        partes.append(str(b["ubicacion"]))
    return f"{b['id']} ({', '.join(partes)})" if partes else str(b["id"])


def _describir_transformable(t: dict[str, Any]) -> str:
    detalle = "; ".join(t.get("acciones") or [])
    if t.get("merma_kg") is not None:
        detalle += f"; merma {fmt_num(t['merma_kg'])} kg"
    return f"{t['id']} ({detalle})" if detalle else str(t["id"])


def plantilla(resultado: dict[str, Any]) -> str:
    exactos = resultado.get("exactos") or []
    transf = resultado.get("transformables") or []
    alts = resultado.get("alternativas") or []
    frases = []
    if exactos:
        n = len(exactos)
        frases.append(f"{'Hay 1 bulto que cumple' if n == 1 else f'Hay {n} bultos que cumplen'} la petición: "
                      + "; ".join(_describir_bulto(b) for b in exactos) + ".")
    if transf:
        inicio = "También se pueden adaptar" if exactos else "No hay ningún bulto que cumpla directamente, pero se pueden adaptar"
        frases.append(f"{inicio}: " + "; ".join(_describir_transformable(t) for t in transf) + ".")
    if not exactos and not transf:
        frases.append("No hay stock que cumpla la petición ni bultos que se puedan transformar para cumplirla.")
        if alts:
            frases.append("Como alternativa, sin cumplir exactamente lo pedido, hay: "
                          + "; ".join(_describir_bulto(b) for b in alts) + ".")
    return " ".join(frases)


def _texto_valido(texto: str, resultado: dict[str, Any], fuente: Any, catalogo: Catalogo) -> bool:
    ids = {str(b["id"]) for k in ("exactos", "transformables", "alternativas") for b in resultado.get(k) or []}
    if not texto or not no_inventa(texto, fuente, catalogo):
        return False
    if not ids <= set(_ID.findall(texto)) | {i for i in ids if i in texto}:
        return False  # se ha dejado algún bulto
    if set(_ID.findall(texto)) - ids:
        return False  # ha inventado un identificador
    if resultado.get("alternativas") and not (resultado.get("exactos") or resultado.get("transformables")):
        if "alternativ" not in texto.lower():
            return False  # las alternativas deben presentarse como tales
    return True


def responder(resultado: dict[str, Any], especificacion: Especificacion | dict | None = None, *,
              cliente: Optional[ClienteLLM] = None, catalogo: Optional[Catalogo] = None,
              usar_llm: bool = True) -> str:
    """resultado: {"exactos": [...], "transformables": [...], "alternativas": [...]} del backend.

    Para respuestas sencillas (0 o 1 bulto) se usa directamente la plantilla, que es
    instantánea (RNF-05). Nunca lanza excepción: si el LLM falla, devuelve la plantilla.
    """
    texto_plantilla = plantilla(resultado)
    total = sum(len(resultado.get(k) or []) for k in ("exactos", "transformables", "alternativas"))
    if not usar_llm or total <= 1:
        return texto_plantilla

    from .interprete import _catalogo_defecto, _cliente_defecto  # evita import circular
    catalogo = catalogo or _catalogo_defecto()
    try:
        cliente = cliente or _cliente_defecto()
        esp = especificacion.a_dict() if isinstance(especificacion, Especificacion) else (especificacion or {})
        usuario = prompts.USUARIO_RESPUESTA.format(
            especificacion=json.dumps(esp, ensure_ascii=False),
            resultado=json.dumps(resultado, ensure_ascii=False))
        texto = cliente.completar(prompts.SISTEMA_RESPUESTA, usuario, max_tokens=400).strip()
    except ErrorLLM:
        return texto_plantilla
    fuente = {"especificacion": esp, "resultado": resultado, "plantilla": texto_plantilla}
    return texto if _texto_valido(texto, resultado, fuente, catalogo) else texto_plantilla
