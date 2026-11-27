"""Avisos de las respuestas del asistente local."""

AVISO_INICIO = (
    "El asistente interpreta tu petición con reglas locales y busca en el inventario de ejemplo. "
    "Revisa los bultos antes de confirmar."
)
AVISO_RESPUESTA = "Respuesta del asistente local basada en el inventario y las reglas de AcerIA."


def aviso_ia() -> dict:
    return {"generado_por_ia": False, "texto": AVISO_RESPUESTA, "texto_voz": "", "inicio": AVISO_INICIO}
