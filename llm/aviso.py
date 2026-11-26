"""Aviso de contenido generado por IA (Reglamento (UE) 2024/1689, art. 50). Ver docs/legal_ia.md.

Va en cada respuesta de POST /chat como "aviso_ia": la marca legible por máquina (art. 50.2)
y los textos que pinta el frontend (art. 50.1). Un único sitio para que todos digan lo mismo.
"""
AVISO_INICIO = ("Estás hablando con un asistente de inteligencia artificial. Interpreta tu petición y busca en el "
                "inventario real de AcerIA, pero puede equivocarse: revisa los bultos antes de confirmar.")
AVISO_RESPUESTA = ("Respuesta generada por IA. Los bultos y las transformaciones salen del inventario y las reglas "
                   "de AcerIA; revísalos antes de confirmar.")
AVISO_VOZ = "Respuesta generada por inteligencia artificial."


def aviso_ia() -> dict:
    return {"generado_por_ia": True, "texto": AVISO_RESPUESTA, "texto_voz": AVISO_VOZ, "inicio": AVISO_INICIO}
