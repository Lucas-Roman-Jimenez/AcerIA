"""Un corte a fleje tiene que estrechar el bulto y quedar por debajo de 600 mm."""

import sys
from pathlib import Path

import pytest

from reglas.configuracion import REGLAS
from reglas.motor import aplicar_reglas


def bulto(id_, formato, ancho, largo=None, peso=1000):
    return {
        "id": id_, "aisi": "304L/304", "euronorma": "4301/4307",
        "acabado": "2B", "formato": formato, "espesor_mm": 1,
        "ancho_mm": ancho, "largo_mm": largo, "peso_kg": peso,
    }


def objetivo_fleje(ancho=None):
    return {
        "formato": "fleje", "grados": ["304"], "acabados": ["2B"],
        "espesor_mm": 1, "ancho_mm": ancho, "largo_mm": None,
        "tolerancias": {"espesor_mm": 0, "ancho_mm": 0, "largo_mm": 0},
    }


BOBINA = bulto("1", "bobina", 1500)
CHAPA = bulto("2", "chapa", 1250, 2500)


def test_fleje_sin_ancho_no_da_flejes_falsos():
    assert aplicar_reglas(BOBINA, objetivo_fleje()) == []


def test_fleje_mas_estrecho_que_la_bobina_es_valido():
    rutas = aplicar_reglas(BOBINA, objetivo_fleje(300))
    assert len(rutas) == 1
    assert [a["regla"] for a in rutas[0]["acciones"]] == ["CORTE_BOBINA_FLEJE"]
    assert rutas[0]["resultado"]["piezas"] == 5


def test_fleje_de_600_mm_o_mas_no_es_fleje():
    assert aplicar_reglas(BOBINA, objetivo_fleje(800)) == []
    assert aplicar_reglas(BOBINA, objetivo_fleje(600)) == []


def test_chapa_a_fleje_del_mismo_ancho_no_es_valido():
    assert aplicar_reglas(CHAPA, objetivo_fleje(1250)) == []


def test_umbral_de_fleje_coincide_con_el_backend():
    pytest.importorskip("pandas")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app import config

    assert REGLAS["fleje"]["ancho_max_mm"] == config.UMBRAL_FLEJE_MM


def test_flejes_del_inventario_real_estrechan_y_miden_menos_de_600(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app import config
    from app.buscador import buscar_bultos, construir_objetivo
    from app.db import crear_db

    if not config.INVENTARIO.exists():
        pytest.skip("Falta el inventario de AcerIA")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "inventario.db")
    crear_db()

    pedido = {"grado": "304", "acabado": "2B", "formato": "fleje", "espesor_mm": 1}

    _, sin_ancho = buscar_bultos(construir_objetivo(pedido))
    assert sin_ancho == []   # antes salían 121 «flejes» del mismo ancho que la bobina

    _, transformables = buscar_bultos(construir_objetivo(dict(pedido, ancho_mm=300)))
    assert transformables   # sin esto, el bucle de abajo pasaría sin comprobar nada
    for t in transformables:
        assert t["resultado"]["ancho_mm"] < t["bulto"]["ancho_mm"]
        assert t["resultado"]["ancho_mm"] < config.UMBRAL_FLEJE_MM
        assert t["resultado"]["piezas"] >= 2
