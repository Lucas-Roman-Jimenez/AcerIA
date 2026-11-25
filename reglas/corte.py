"""Formatos permitidos y límites geométricos comprobables del corte."""

from __future__ import annotations

from reglas.configuracion import REGLAS


def cumple_condiciones_corte(
    *,
    formato_origen: str,
    formato_destino: str,
    ancho_origen: float,
    ancho_destino: float,
    largo_origen: float | None = None,
    largo_destino: float | None = None,
) -> bool:
    """Comprueba formatos y dimensiones, sin calcular disponibilidad ni merma."""
    if formato_destino not in REGLAS["cortes"].get(formato_origen, {}):
        return False
    if not 0 < ancho_destino <= ancho_origen < float("inf"):
        return False
    if formato_destino == "fleje":
        return True
    if largo_destino is None or not 0 < largo_destino < float("inf"):
        return False
    if formato_origen == "bobina" and largo_origen is None:
        return True
    return largo_origen is not None and largo_destino <= largo_origen < float("inf")
