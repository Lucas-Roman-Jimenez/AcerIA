from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys

import pytest

pytest.importorskip("pandas")
pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import config
from app.db import SCHEMA
from app.main import obtener_reporte_semanal
from app.reportes import registrar_compra, reporte_semanal


BULTO = {"id": "334", "formato": "bobina", "aisi": "304L/304", "acabado": "2B",
         "ancho_mm": 1500, "espesor_mm": 2, "peso_kg": 745, "cantidad": 15}


@pytest.fixture
def base(tmp_path, monkeypatch):
    ruta = tmp_path / "inventario.db"
    monkeypatch.setattr(config, "DB_PATH", ruta)
    with sqlite3.connect(ruta) as conexion:
        conexion.executescript(SCHEMA.read_text(encoding="utf-8"))
    return ruta


def guardar(conexion, identificador, fecha):
    registrar_compra(conexion, compra_id=identificador, bulto=BULTO,
                     cantidad=300.5, unidad="kg", comprada_en=fecha)


def test_reporte_filtra_la_semana_madrid_y_conserva_la_ficha(base):
    # En noviembre, las 23:00 UTC del domingo son las 00:00 del lunes en Madrid.
    inicio = datetime(2026, 11, 22, 23, tzinfo=timezone.utc)
    milisegundo = timedelta(milliseconds=1)
    with sqlite3.connect(base) as conexion:
        guardar(conexion, "anterior", inicio - milisegundo)
        guardar(conexion, "primera", inicio)
        guardar(conexion, "ultima", inicio + timedelta(days=7) - milisegundo)
        guardar(conexion, "siguiente", inicio + timedelta(days=7))
        conexion.executescript(SCHEMA.read_text(encoding="utf-8"))
    reporte = reporte_semanal(ahora=inicio + timedelta(days=2))
    assert reporte["semana"] == {
        "inicio": "2026-11-23", "fin": "2026-11-29", "zona_horaria": "Europe/Madrid",
    }
    [compra] = reporte["compras"]
    assert compra["nombre_material"] == "Bobina de acero inoxidable"
    assert compra["caracteristicas"] == {
        "id": "334", "grado": "304L/304", "acabado": "2B",
        "espesor_mm": 2, "ancho_mm": 1500, "peso_kg": 745,
    }
    assert compra["cantidades_sustraidas"] == [{"valor": 601, "unidad": "kg"}]


def test_el_rollback_de_la_baja_tambien_revierte_el_registro(base):
    with sqlite3.connect(base) as conexion:
        guardar(conexion, "revertida", datetime.now(timezone.utc))
        conexion.rollback()
    reporte = obtener_reporte_semanal()
    assert reporte["titulo"] == "Reporte semanal de compras"
    assert reporte["compras"] == []


def test_reporte_muestra_el_largo_y_usa_euronorma_si_falta_aisi(base):
    chapa = dict(BULTO, formato="chapa", aisi=None, euronorma="1.4404", largo_mm=2500)
    with sqlite3.connect(base) as conexion:
        registrar_compra(conexion, compra_id="chapa", bulto=chapa,
                         cantidad=1, unidad="bultos", comprada_en=datetime.now(timezone.utc))
    [compra] = obtener_reporte_semanal()["compras"]
    assert compra["nombre_material"] == "Chapa de acero inoxidable"
    assert compra["caracteristicas"]["grado"] == "1.4404"
    assert compra["caracteristicas"]["largo_mm"] == 2500


def test_reporte_consolida_cada_bulto_sin_mezclar_unidades(base):
    hoy = datetime.now(timezone.utc)
    with sqlite3.connect(base) as conexion:
        guardar(conexion, "peso", hoy)
        registrar_compra(conexion, compra_id="piezas", bulto=BULTO,
                         cantidad=2, unidad="piezas", comprada_en=hoy)
        registrar_compra(conexion, compra_id="otro", bulto=dict(BULTO, id="335"),
                         cantidad=1, unidad="bultos", comprada_en=hoy)
    filas = {c["caracteristicas"]["id"]: c for c in obtener_reporte_semanal()["compras"]}
    assert set(filas) == {"334", "335"}
    assert filas["334"]["cantidades_sustraidas"] == [
        {"valor": 300.5, "unidad": "kg"}, {"valor": 2, "unidad": "piezas"},
    ]
