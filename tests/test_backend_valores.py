"""Tests de valores_disponibles(): «¿qué grosores/acabados/grados hay?» con stock real.

Ejecutar desde la raíz del repositorio:  python -m pytest -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from app.buscador import valores_disponibles  # noqa: E402


def bulto(id, **cambios):
    base = {"id": id, "aisi": "304L/304", "euronorma": "1.4301/1.4307", "acabado": "2B",
            "formato": "chapa", "espesor_mm": 2.0, "ancho_mm": 1250.0, "largo_mm": 2500.0,
            "peso_kg": 1000.0, "estado": "disponible"}
    return {**base, **cambios}


BULTOS = [
    bulto("A"),
    bulto("B", espesor_mm=1.5),
    bulto("C", espesor_mm=1.5, acabado="BA", peso_kg=500.0),
    bulto("D", aisi="316L", euronorma="1.4404", espesor_mm=3.0),
]


def test_espesores_de_un_grado_ordenados_y_contados():
    vs = valores_disponibles("espesor_mm", {"grado": "304"}, BULTOS)
    assert vs == [{"valor": 1.5, "bultos": 2, "toneladas": 1.5}, {"valor": 2.0, "bultos": 1, "toneladas": 1.0}]


def test_filtra_por_lo_ya_pedido():
    vs = valores_disponibles("acabado", {"grado": "304", "espesor_mm": 1.5}, BULTOS)
    assert [v["valor"] for v in vs] == ["2B", "BA"]


def test_grados_sin_filtro_por_toneladas():
    vs = valores_disponibles("grado", {}, BULTOS)
    assert [v["valor"] for v in vs] == ["304L/304", "316L"]


def test_sin_stock_devuelve_lista_vacia():
    assert valores_disponibles("espesor_mm", {"grado": "430"}, BULTOS) == []


def test_campo_no_consultable():
    with pytest.raises(ValueError):
        valores_disponibles("peso_kg", {}, BULTOS)
