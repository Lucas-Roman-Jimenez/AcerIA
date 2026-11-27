"""Fichas PDF locales autorizadas por el catálogo de materiales."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app import config


class FichaNoEncontrada(Exception):
    """El código MAT no está en el catálogo."""


class FichaNoDisponible(Exception):
    """La ficha existe en el catálogo, pero falta su archivo local."""


@lru_cache(maxsize=1)
def fichas_del_catalogo() -> dict[str, str]:
    """{«MAT 120»: «Inoxidable_austenitico_1.4301_AISI_304_…_MAT120.pdf»} según datos/catalogo.json."""
    catalogo = json.loads(config.CATALOGO.read_text(encoding="utf-8"))
    return {f["mat"]: f["fuente"]["archivo"] for f in catalogo.get("fichas", []) if f.get("fuente", {}).get("archivo")}


def _normalizar_mat(mat: str) -> str:
    """«mat120», «MAT-120», «MAT 120» -> «MAT 120»."""
    m = re.fullmatch(r"\s*mat[\s_-]*(\d{3})\s*", mat or "", flags=re.I)
    return f"MAT {m.group(1)}" if m else (mat or "").strip()


def archivo_de(mat: str) -> str:
    archivo = fichas_del_catalogo().get(_normalizar_mat(mat))
    if not archivo:
        raise FichaNoEncontrada(mat)
    return archivo


def obtener_pdf(mat: str) -> Path:
    """Devuelve la ruta del PDF instalado localmente."""
    destino = config.FICHAS_DIR / archivo_de(mat)
    if not destino.is_file():
        raise FichaNoDisponible("El PDF no está instalado localmente.")
    return destino
