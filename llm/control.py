"""Utilidades compartidas: formato de números y control de que un texto del LLM
no añade cifras ni valores del catálogo que no estaban en los datos (RNF-01)."""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

from .catalogo import Catalogo

_NUM = re.compile(r"(?<![\w-])\d+(?:[.,]\d+)?(?![\w])")


def fmt_num(x: float) -> str:
    """2.0 -> '2', 1.5 -> '1,5' (coma decimal en español)."""
    x = float(x)
    if x.is_integer():
        return str(int(x))
    return f"{x:g}".replace(".", ",")


def lista_y(items: Iterable[str], prefijo: str = "") -> str:
    """['2B','BA','2D'] -> 'en 2B, en BA y en 2D' con prefijo 'en '."""
    xs = [f"{prefijo}{i}" for i in items]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def lista_o(items: Iterable[str]) -> str:
    """['2B','BA','2D'] -> '2B, BA o 2D'."""
    xs = [str(i) for i in items]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " o " + xs[-1]


def numeros(texto: str) -> set[float]:
    return {float(n.replace(",", ".")) for n in _NUM.findall(texto)}


def numeros_en_datos(datos: Any) -> set[float]:
    """Todos los números que aparecen en una estructura (y en sus textos)."""
    return numeros(json.dumps(datos, ensure_ascii=False))


def valores_catalogo(texto: str, catalogo: Catalogo) -> set[str]:
    """Grados, acabados y formatos del catálogo mencionados en el texto (palabras completas).
    Los acabados solo numéricos ('4') se controlan como números."""
    encontrados = set()
    for v in catalogo.grados + catalogo.acabados + catalogo.formatos:
        if v.isdigit() and v in catalogo.acabados and v not in catalogo.grados:
            continue
        if re.search(rf"(?<![\w]){re.escape(v)}(?![\w])", texto, flags=re.I if v.islower() else 0):
            encontrados.add(v)
    return encontrados


def conserva_datos(texto: str, original: str, catalogo: Catalogo) -> bool:
    """True si el texto mantiene todos los números, valores del catálogo y textos entre «» del original."""
    citas = re.findall(r"«([^»]+)»", original)
    return (numeros(original) <= numeros(texto)
            and valores_catalogo(original, catalogo) <= valores_catalogo(texto, catalogo)
            and all(c in texto for c in citas))


def no_inventa(texto_llm: str, fuente: Any, catalogo: Catalogo, conteos_permitidos: int = 10) -> bool:
    """True si el texto del LLM solo usa números y valores de catálogo presentes en `fuente`.

    Se permiten los números pequeños (1..conteos_permitidos) porque el LLM puede contar
    («hay 2 bultos») y los ordinales de las listas.
    """
    texto_fuente = fuente if isinstance(fuente, str) else json.dumps(fuente, ensure_ascii=False)
    permitidos = numeros(texto_fuente) | {float(i) for i in range(conteos_permitidos + 1)}
    if not numeros(texto_llm) <= permitidos:
        return False
    return valores_catalogo(texto_llm, catalogo) <= valores_catalogo(texto_fuente, catalogo)
