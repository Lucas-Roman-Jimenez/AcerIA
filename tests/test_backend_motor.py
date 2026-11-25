import json
import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import buscador, config
from app.db import crear_db
from app.main import buscar

from evaluar_api import CASOS_TRANSFORMABLES, evaluar


@pytest.fixture
def inventario(tmp_path, monkeypatch):
    if not config.INVENTARIO.exists():
        pytest.skip("Falta el inventario de AcerIA")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "inventario.db")
    crear_db()


def test_buscar_devuelve_las_transformaciones_de_los_bultos_del_contrato(inventario):
    casos = json.loads(CASOS_TRANSFORMABLES.read_text(encoding="utf-8"))
    informe = evaluar(casos, lambda _, datos: buscar(datos), solo_resultados=True)
    assert informe["transformables_api"]["fallos"] == []

    solo_transformables = buscar(casos[1]["esperado"]["especificacion"])
    assert solo_transformables["estado"] == "resultados"
    assert not solo_transformables["exactos"]
    assert solo_transformables["transformables"]


def test_buscar_excluye_bultos_reservados_y_bloqueados_del_motor(inventario, monkeypatch):
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("UPDATE bultos SET estado = 'reservado' WHERE id = '334'")
        conn.execute("UPDATE bultos SET estado = 'bloqueado' WHERE id = '23'")
    motor = buscador.aplicar_reglas

    def comprobar_disponible(bulto, objetivo, max_operaciones):
        assert bulto["estado"] == "disponible"
        assert bulto["id"] not in ("334", "23")
        return motor(bulto, objetivo, max_operaciones)

    monkeypatch.setattr(buscador, "aplicar_reglas", comprobar_disponible)
    casos = json.loads(CASOS_TRANSFORMABLES.read_text(encoding="utf-8"))
    for caso in casos:
        resultado = buscar(caso["esperado"]["especificacion"])
        assert all(t["bulto_id"] not in ("334", "23") for t in resultado["transformables"])


def test_buscar_verifica_el_objetivo_y_ordena_por_porcentaje_y_operaciones(monkeypatch):
    exacto = {
        "id": "exacto", "aisi": "304", "euronorma": "1.4301", "acabado": "2B",
        "formato": "chapa", "espesor_mm": 2, "ancho_mm": 1250, "largo_mm": 2500,
    }
    origenes = [dict(exacto, id=id_, formato="bobina", largo_mm=None)
                for id_ in ("a", "b", "c", "invalido")]
    origenes.append(dict(origenes[0], id="otro-grado", aisi="316", euronorma=None))
    monkeypatch.setattr(buscador, "disponibles", lambda: [exacto, *origenes])
    mermas = {"a": (10, 2, 10), "b": (5, 2, 100), "c": (10, 1, 20), "invalido": (0, 1, 0)}

    def transformar(origen, objetivo, max_operaciones):
        porcentaje, operaciones, kilos = mermas[origen["id"]]
        resultado = dict(exacto, ancho_mm=1300 if origen["id"] == "invalido" else 1250)
        return [{
            "bulto_id": origen["id"], "resultado": resultado, "merma_pct": porcentaje,
            "num_operaciones": operaciones, "merma_kg": kilos,
        }]

    monkeypatch.setattr(buscador, "aplicar_reglas", transformar)
    respuesta = buscar({
        "grado": "304", "formato": "chapa", "acabado": "2B",
        "espesor_mm": 2, "ancho_mm": 1250, "largo_mm": 2500,
    })
    assert [b["id"] for b in respuesta["exactos"]] == ["exacto"]
    assert [t["bulto_id"] for t in respuesta["transformables"]] == ["b", "c", "a"]
    assert [t["bulto"]["id"] for t in respuesta["transformables"]] == ["b", "c", "a"]
