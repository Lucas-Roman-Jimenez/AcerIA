"""Tests del buscador del backend (Alonso, meta 5).

Ejecutar desde la raíz del repositorio:  python -m pytest -q
"""
import sys
from pathlib import Path

import pytest

# El código del backend vive en backend/app: lo añadimos al path solo para estos tests,
# sin tocar la configuración compartida de pytest.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

# Si un compañero no ha instalado backend/requirements.txt, se saltan en vez de fallar.
pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from app import config  # noqa: E402
from app.buscador import construir_objetivo, cumple  # noqa: E402


def bulto(**cambios):
    base = {"id": "X", "aisi": "304L/304", "euronorma": "1.4301/1.4307", "acabado": "2B",
            "formato": "chapa", "espesor_mm": 2.0, "ancho_mm": 1250.0, "largo_mm": 2500.0,
            "peso_kg": 500.0, "estado": "disponible"}
    return {**base, **cambios}


def objetivo(**espec):
    return construir_objetivo(espec)


def test_cumple_exacto():
    assert cumple(bulto(), objetivo(grado="304", acabado="2B", formato="chapa",
                                    espesor_mm=2.0, ancho_mm=1250, largo_mm=2500))


def test_doble_certificado_vale_para_304_y_304L_y_euronorma():
    for g in ["304", "304L", "1.4301"]:
        assert cumple(bulto(), objetivo(grado=g))


def test_grado_distinto_no_cumple():
    assert not cumple(bulto(), objetivo(grado="316L"))


def test_acabado_en_minusculas_y_opciones():
    assert cumple(bulto(), objetivo(acabado="2b"))
    assert cumple(bulto(acabado="BA"), objetivo(acabado=None, opciones={"acabado": ["BA", "2R"]}))
    assert not cumple(bulto(acabado="2D"), objetivo(opciones={"acabado": ["BA", "2R"]}))


def test_campo_no_pedido_vale_cualquiera():
    assert cumple(bulto(ancho_mm=1500.0), objetivo(grado="304", espesor_mm=2.0))


def test_fuera_de_tolerancia_no_cumple():
    assert not cumple(bulto(espesor_mm=2.1), objetivo(espesor_mm=2.0))


def test_largo_pedido_y_bobina_sin_largo_no_cumple():
    assert not cumple(bulto(formato="bobina", largo_mm=None), objetivo(largo_mm=2500))


def test_formato_distinto_no_cumple():
    assert not cumple(bulto(formato="bobina", largo_mm=None), objetivo(formato="chapa"))


# ---------- integración con el inventario real ----------

@pytest.fixture(scope="module")
def db():
    if not config.INVENTARIO.exists():
        pytest.skip("Falta backend/data/inventario.xlsx (el Excel de AcerIA)")
    from app.db import crear_db
    crear_db()


def test_busqueda_real_solo_disponibles_que_cumplen(db):
    from app.buscador import buscar_exactos
    from app.db import obtener_bulto
    obj = objetivo(grado="304", acabado="2B", formato="chapa", espesor_mm=2.0, ancho_mm=1250, largo_mm=2500)
    res = buscar_exactos(obj)
    ids = {b["id"] for b in res}
    assert "1312" in ids
    for b in res:
        real = obtener_bulto(b["id"])            # existe en la BD (RNF-01)
        assert real is not None and real["estado"] == "disponible"
        assert cumple(real, obj)


def test_bulto_reservado_nunca_sale(db):
    import sqlite3
    from app.buscador import buscar_exactos
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("UPDATE bultos SET estado = 'reservado' WHERE id = '1312'")
    obj = objetivo(grado="304", acabado="2B", formato="chapa", espesor_mm=2.0, ancho_mm=1250, largo_mm=2500)
    assert "1312" not in {b["id"] for b in buscar_exactos(obj)}