"""Equivalencias de transcripción recogidas en los requisitos de Lucas."""

import json
import re
from pathlib import Path


_EQUIVALENCIAS = json.loads(
    Path(__file__).with_name("equivalencias.json").read_text(encoding="utf-8")
)
_PATRON = re.compile(
    r"\b(?:" + "|".join(
        r"\s+".join(map(re.escape, expresion.split()))
        for expresion in _EQUIVALENCIAS
    ) + r")\b",
    re.IGNORECASE,
)


def normalizar_transcripcion(texto: str) -> str:
    """Sustituye las expresiones documentadas dentro de la transcripción."""
    return _PATRON.sub(
        lambda coincidencia: _EQUIVALENCIAS[" ".join(coincidencia[0].lower().split())],
        texto,
    )
