"""Fichas técnicas en PDF de AcerIA (catálogo de productos), servidas por el backend.

Los PDF están en el workspace de Databricks del hackathon (por defecto bajo /Shared/Dataset-aceria).
La primera vez que se pide una ficha se descarga y se guarda en config.FICHAS_DIR; después sale de ahí,
así la demo no depende de la red. El token se queda en el backend: el navegador solo ve /fichas/{mat}.

Solo se sirven las fichas que tiene el catálogo de Lucas (datos/catalogo.json, «fichas»): se pide por
código MAT («MAT 120») y el archivo sale del catálogo, nunca de la petición.
"""
from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

from app import config


class FichaNoEncontrada(Exception):
    """El código MAT no está en el catálogo."""


class FichaNoDisponible(Exception):
    """La ficha existe en el catálogo pero no se ha podido obtener (sin red, sin token, sin permiso…)."""


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


# ---------- Databricks ----------

def _credenciales() -> tuple[str, str]:
    """Host y token: DATABRICKS_HOST/DATABRICKS_TOKEN si están; si no, los del gateway del LLM (.env)."""
    host = os.getenv("DATABRICKS_HOST") or os.getenv("ANTHROPIC_BASE_URL") or ""
    token = os.getenv("DATABRICKS_TOKEN") or os.getenv("ANTHROPIC_AUTH_TOKEN") or ""
    m = re.match(r"https?://[^/]+", host.strip())
    if not m or not token.strip():
        raise FichaNoDisponible("Falta la configuración de Databricks (host y token en el .env).")
    return m.group(0), token.strip()


def _peticion(ruta: str, **parametros) -> bytes:
    host, token = _credenciales()
    url = f"{host}{ruta}?{urllib.parse.urlencode(parametros)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}),
                                    timeout=config.FICHAS_TIMEOUT_S) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise FichaNoDisponible(f"Databricks respondió {e.code}.") from None   # sin el token ni la URL
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FichaNoDisponible(f"Sin conexión con Databricks ({type(e).__name__}).") from None


_indice: dict[str, str] | None = None
_cerrojo = threading.Lock()


def _indice_databricks() -> dict[str, str]:
    """{nombre de archivo: ruta en el workspace}. Se busca por nombre: la carpeta del catálogo tiene la
    tilde estropeada en Databricks («Cata╠ülogo»), así que no se escribe a mano."""
    global _indice
    if _indice is None:
        indice: dict[str, str] = {}
        pendientes = [(config.DATABRICKS_FICHAS, 0)]
        while pendientes:
            ruta, profundidad = pendientes.pop()
            for o in json.loads(_peticion("/api/2.0/workspace/list", path=ruta)).get("objects", []):
                if o.get("object_type") == "DIRECTORY" and profundidad < 4:
                    pendientes.append((o["path"], profundidad + 1))
                elif o["path"].lower().endswith(".pdf"):
                    indice[o["path"].rsplit("/", 1)[1]] = o["path"]
        _indice = indice
    return _indice


def descargar(archivo: str) -> bytes:
    """PDF del workspace de Databricks. Se puede sustituir en los tests."""
    ruta = _indice_databricks().get(archivo)
    if not ruta:
        raise FichaNoDisponible(f"No está en Databricks: {archivo}")
    datos = _peticion("/api/2.0/workspace/export", path=ruta, direct_download="true")
    if not datos.startswith(b"%PDF"):
        raise FichaNoDisponible("Databricks no ha devuelto un PDF.")
    return datos


def obtener_pdf(mat: str) -> Path:
    """Ruta local del PDF de la ficha; lo descarga la primera vez."""
    archivo = archivo_de(mat)
    destino = config.FICHAS_DIR / archivo
    if destino.exists():
        return destino
    with _cerrojo:                                   # dos peticiones a la vez: una sola descarga
        if not destino.exists():
            datos = descargar(archivo)
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_suffix(".parcial")
            temporal.write_bytes(datos)
            temporal.replace(destino)                # nunca queda un PDF a medias en la caché
    return destino
