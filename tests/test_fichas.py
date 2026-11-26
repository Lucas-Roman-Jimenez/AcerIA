"""Fichas técnicas en PDF (GET /fichas/{mat}). Sin red: la descarga de Databricks se simula."""
from pathlib import Path
import sys

import pytest

pytest.importorskip("fastapi")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, fichas  # noqa: E402
from app.main import app  # noqa: E402

PDF = b"%PDF-1.7 ficha de prueba"
ARCHIVO_304 = "Inoxidable_austenitico_1.4301_AISI_304_ASTM_S30400_MAT120.pdf"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """Caché en una carpeta temporal y descarga simulada que cuenta las llamadas."""
    monkeypatch.setattr(config, "FICHAS_DIR", tmp_path / "fichas")
    llamadas = []

    def descargar(archivo):
        llamadas.append(archivo)
        return PDF
    monkeypatch.setattr(fichas, "descargar", descargar)
    return TestClient(app), llamadas


def test_las_41_fichas_del_catalogo_tienen_archivo():
    catalogo = fichas.fichas_del_catalogo()
    assert len(catalogo) == 41 and catalogo["MAT 120"] == ARCHIVO_304
    assert all(a.endswith(".pdf") for a in catalogo.values())


def test_sirve_el_pdf_y_lo_guarda_en_cache(cliente):
    c, llamadas = cliente
    for mat in ("MAT 120", "mat120", "MAT-120"):
        r = c.get(f"/fichas/{mat}")
        assert r.status_code == 200 and r.content == PDF
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["content-disposition"].startswith("inline")
    assert llamadas == [ARCHIVO_304]                       # descargado una vez, luego sale de la caché
    assert (config.FICHAS_DIR / ARCHIVO_304).read_bytes() == PDF


def test_una_ficha_que_no_esta_en_el_catalogo_da_404(cliente):
    c, llamadas = cliente
    assert c.get("/fichas/MAT 999").status_code == 404
    assert llamadas == []


@pytest.mark.parametrize("ruta", ["/fichas/..%2F..%2Fsecreto", "/fichas/MAT%20120.pdf", "/fichas/x"])
def test_no_acepta_rutas_ni_nombres_libres(cliente, ruta):
    c, llamadas = cliente
    assert c.get(ruta).status_code in (404, 422)
    assert llamadas == []


def test_si_databricks_no_responde_da_503_sin_detalles(cliente, monkeypatch):
    c, _ = cliente

    def falla(archivo):
        raise fichas.FichaNoDisponible("Databricks respondió 403.")
    monkeypatch.setattr(fichas, "descargar", falla)
    r = c.get("/fichas/MAT 120")
    assert r.status_code == 503 and "403" not in r.text
    assert not (config.FICHAS_DIR / ARCHIVO_304).exists()   # nada a medias en la caché


def test_sin_configuracion_de_databricks_no_rompe(monkeypatch):
    for var in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(fichas.FichaNoDisponible):
        fichas._credenciales()
