"""Fichas técnicas locales en PDF (GET /fichas/{mat})."""
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
    carpeta = tmp_path / "fichas"
    carpeta.mkdir()
    (carpeta / ARCHIVO_304).write_bytes(PDF)
    monkeypatch.setattr(config, "FICHAS_DIR", carpeta)
    return TestClient(app)


def test_las_41_fichas_del_catalogo_tienen_archivo():
    catalogo = fichas.fichas_del_catalogo()
    assert len(catalogo) == 41 and catalogo["MAT 120"] == ARCHIVO_304
    assert all(a.endswith(".pdf") for a in catalogo.values())


def test_sirve_el_pdf_local(cliente):
    for mat in ("MAT 120", "mat120", "MAT-120"):
        r = cliente.get(f"/fichas/{mat}")
        assert r.status_code == 200 and r.content == PDF
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["content-disposition"].startswith("inline")
    assert (config.FICHAS_DIR / ARCHIVO_304).read_bytes() == PDF


def test_una_ficha_que_no_esta_en_el_catalogo_da_404(cliente):
    assert cliente.get("/fichas/MAT 999").status_code == 404


@pytest.mark.parametrize("ruta", ["/fichas/..%2F..%2Fsecreto", "/fichas/MAT%20120.pdf", "/fichas/x"])
def test_no_acepta_rutas_ni_nombres_libres(cliente, ruta):
    assert cliente.get(ruta).status_code in (404, 422)


def test_si_falta_el_archivo_local_da_503(cliente):
    (config.FICHAS_DIR / ARCHIVO_304).unlink()
    r = cliente.get("/fichas/MAT 120")
    assert r.status_code == 503
    assert ARCHIVO_304 not in r.text
