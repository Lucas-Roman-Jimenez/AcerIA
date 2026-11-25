"""Condiciones de laminación de las reglas de transformación de AcerIA."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from reglas.configuracion import REGLAS


LAMINACION = REGLAS["laminacion"]
_PROPORCION_MIN = 1 - Decimal(str(LAMINACION["reduccion_max"]))
_PROPORCION_MAX = 1 - Decimal(str(LAMINACION["reduccion_min"]))


def permite_laminacion(
    *,
    formato_origen: str,
    acabado_origen: str,
    espesor_origen: int | float | Decimal,
    acabado_destino: str,
    espesor_destino: int | float | Decimal,
) -> bool:
    """Comprueba el formato, los acabados y la reducción de espesor.

    Los espesores se expresan en la misma unidad. N1 es el código del
    documento de transformaciones para NR.1 en el inventario.
    """
    if acabado_origen == "N1":
        acabado_origen = "NR.1"
    if formato_origen != LAMINACION["formato"] or acabado_origen not in LAMINACION["acabados_origen"]:
        return False
    if acabado_destino != LAMINACION["acabado_destino"]:
        return False

    try:
        origen = Decimal(str(espesor_origen))
        destino = Decimal(str(espesor_destino))
    except InvalidOperation:
        return False
    if not origen.is_finite() or not destino.is_finite() or origen <= 0:
        return False

    return origen * _PROPORCION_MIN <= destino <= origen * _PROPORCION_MAX
