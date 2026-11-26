"""RF-29: alternativas con la regla de sustitución de dimensiones de AcerIA.

Solo chapa del mismo grado, acabado y espesor con otra medida (ancho × largo).
Sin inventario real: disponibles() se sustituye con monkeypatch.
Ejecutar desde la raíz del repositorio:  python -m pytest -q
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from app import buscador, config  # noqa: E402
from app.buscador import buscar_alternativas, construir_objetivo  # noqa: E402

PEDIDO = {"grado": "304", "acabado": "2B", "formato": "chapa",
          "espesor_mm": 2, "ancho_mm": 1250, "largo_mm": 2500}


def chapa(id_="1", **cambios):
    base = {"id": id_, "aisi": "304L/304", "euronorma": "1.4301/1.4307", "acabado": "2B",
            "formato": "chapa", "espesor_mm": 2.0, "ancho_mm": 1000.0, "largo_mm": 2000.0,
            "peso_kg": 500.0, "estado": "disponible"}
    return {**base, **cambios}


def alternativas(*bultos, **pedido):
    return buscar_alternativas(construir_objetivo({**PEDIDO, **pedido}), list(bultos))


def test_chapa_mas_pequena_es_alternativa_con_sus_diferencias():
    [alt] = alternativas(chapa())
    assert alt["id"] == "1" and alt["grado"] == "304L/304"
    assert alt["diferencias"] == ["ancho 1000 mm (pedido 1250 mm)", "largo 2000 mm (pedido 2500 mm)"]


@pytest.mark.parametrize("cambios", [
    {"acabado": "BA"},
    {"espesor_mm": 2.5},
    {"aisi": "316L", "euronorma": "1.4404"},
    {"formato": "bobina", "largo_mm": None},
], ids=["acabado-no-se-relaja", "espesor-no-se-relaja", "grado-no-se-relaja", "solo-chapa"])
def test_no_relaja_grado_acabado_espesor_ni_formato(cambios):
    assert alternativas(chapa(**cambios)) == []


def test_devuelve_las_mas_cercanas_ordenadas_por_distancia_y_por_id():
    stock = [
        chapa("50", ancho_mm=1000, largo_mm=2000),   # distancia 750
        chapa("40", ancho_mm=1200, largo_mm=2500),   # 50
        chapa("30", ancho_mm=1250, largo_mm=2000),   # 500
        chapa("100", ancho_mm=1250, largo_mm=2400),  # 100
        chapa("99", ancho_mm=1250, largo_mm=2400),   # 100, empata con "100": va antes
    ]
    assert config.MAX_ALTERNATIVAS == 3
    assert [a["id"] for a in alternativas(*stock)] == ["40", "99", "100"]


@pytest.mark.parametrize("estado", ["reservado", "bloqueado"])
def test_bulto_no_disponible_nunca_es_alternativa(estado):
    assert alternativas(chapa(estado=estado)) == []


def test_sin_medida_pedida_no_hay_alternativas_de_medida():
    assert alternativas(chapa(), ancho_mm=None, largo_mm=None) == []


# ---------- /buscar y /chat ----------

@pytest.fixture
def cliente(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app

    def con_stock(*bultos):
        monkeypatch.setattr(buscador, "disponibles", lambda: list(bultos))
        return TestClient(app)
    return con_stock


def test_buscar_con_exacto_no_da_alternativas(cliente):
    exacto = chapa("exacto", ancho_mm=1250.0, largo_mm=2500.0)
    r = cliente(exacto, chapa()).post("/buscar", json=PEDIDO).json()
    assert r["estado"] == "resultados"
    assert [b["id"] for b in r["exactos"]] == ["exacto"]
    assert r["alternativas"] == []


def test_buscar_sin_stock_devuelve_alternativas_y_sigue_siendo_sin_stock(cliente):
    r = cliente(chapa()).post("/buscar", json=PEDIDO).json()
    assert r["estado"] == "sin_stock"                  # el evaluador y el frontend dependen de esto
    assert r["exactos"] == [] and r["transformables"] == []
    assert [a["id"] for a in r["alternativas"]] == ["1"]


def test_chat_sin_stock_presenta_las_alternativas(cliente, monkeypatch):
    import llm.interprete as interprete
    from llm import ClienteFalso
    from llm.catalogo import Catalogo

    catalogo = Catalogo({
        "grados": ["304"], "acabados": ["2B"], "formatos": ["chapa"],
        "productos": [{"grado": "304", "acabado": "2B", "formato": "chapa",
                       "espesor_mm": [0.3, 10], "ancho_mm": [100, 2000]}],
        "usos": []}, {"terminos": []})
    extraccion = {"intencion": "pedido", **PEDIDO, "cantidad": None, "uso": None,
                  "opciones": {"grado": [], "acabado": [], "formato": []},
                  "contradicciones": [], "indiferentes": []}
    monkeypatch.setattr(interprete, "_cliente", ClienteFalso([json.dumps(extraccion)]))
    monkeypatch.setattr(interprete, "_catalogo", catalogo)

    r = cliente(chapa()).post("/chat", json={"conversacion_id": "rf29",
                                             "mensaje": "chapa 304 2B de 2 x 1250 x 2500"}).json()
    assert r["estado"] == "sin_stock"
    assert [a["id"] for a in r["alternativas"]] == ["1"]
    assert "alternativa" in r["texto"].lower()
