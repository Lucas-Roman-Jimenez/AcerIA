"""Condiciones para ofrecer dimensiones alternativas de una chapa."""


def permite_sustituir_dimensiones(
    *,
    hay_medida_exacta: bool,
    grado_pedido: str,
    acabado_pedido: str,
    espesor_pedido: float,
    dimensiones_pedidas: tuple[float, float],
    grado_alternativo: str,
    acabado_alternativo: str,
    espesor_alternativo: float,
    dimensiones_alternativas: tuple[float, float],
) -> bool:
    """Compara dos chapas por grado, acabado, espesor y par ancho × largo."""
    return (
        not hay_medida_exacta
        and grado_pedido == grado_alternativo
        and acabado_pedido == acabado_alternativo
        and espesor_pedido == espesor_alternativo
        and dimensiones_pedidas != dimensiones_alternativas
    )
