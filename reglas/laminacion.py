"""Condiciones de laminación de las reglas de transformación de AcerIA."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def permite_laminacion(
    *,
    formato_origen: str,
    acabado_origen: str,
    espesor_origen: int | float | Decimal,
    acabado_destino: str,
    espesor_destino: int | float | Decimal,
) -> bool:
    """Comprueba el formato, los acabados y la reducción de espesor.

    Los espesores se expresan en la misma unidad. Los acabados usan los
    códigos del documento de reglas.
    """
    if formato_origen != "bobina" or acabado_origen not in ("2B", "N1"):
        return False
    if acabado_destino != "2B":
        return False

    try:
        origen = Decimal(str(espesor_origen))
        destino = Decimal(str(espesor_destino))
    except InvalidOperation:
        return False
    if not origen.is_finite() or not destino.is_finite() or origen <= 0:
        return False

    # Una reducción del 50 % al 75 % deja entre el 25 % y el 50 % del espesor.
    return origen * Decimal("0.25") <= destino <= origen * Decimal("0.50")
