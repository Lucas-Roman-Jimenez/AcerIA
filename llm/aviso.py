"""Avisos de las respuestas del asistente local."""

import os

AVISO_INICIO = (
    "El asistente interpreta tu petición con reglas locales y busca en el inventario de ejemplo. "
    "Revisa los bultos antes de confirmar."
)
AVISO_RESPUESTA = "Respuesta del asistente local basada en el inventario y las reglas de AcerIA."


def aviso_ia() -> dict:
    if os.environ.get("ACERIA_CLAUDE_KEY"):
        aviso = "Consulta interpretada con Claude Sonnet 5.5 de Anthropic."
        return {"generado_por_ia": True, "texto": aviso, "texto_voz": aviso, "inicio": aviso}
    if os.environ.get("ACERIA_OLLAMA_MODELO"):
        aviso = "Consulta interpretada con un modelo de IA local."
        return {"generado_por_ia": True, "texto": aviso, "texto_voz": aviso, "inicio": aviso}
    return {"generado_por_ia": False, "texto": AVISO_RESPUESTA, "texto_voz": "", "inicio": AVISO_INICIO}
