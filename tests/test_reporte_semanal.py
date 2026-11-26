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
from app.main import obtener_reporte_semanal, obtener_tendencias_compras
from app.reportes import registrar_compra, reporte_diario_inventario, reporte_semanal
from app.tendencias import tendencias_compras


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


def test_reporte_diario_distingue_reservas_vigentes_y_excluye_bultos_vendidos(base):
    ahora = datetime(2026, 11, 26, 23, 15, tzinfo=timezone.utc)
    ahora_ms = int(ahora.timestamp() * 1000)
    with sqlite3.connect(base) as conexion:
        conexion.executemany(
            """INSERT INTO bultos (id, formato, peso_kg, estado, acabado, espesor_mm, ancho_mm)
               VALUES (?, ?, ?, ?, '2B', 2, 1250)""",
            [("libre", "chapa", 100, "disponible"), ("vigente", "chapa", 200, "disponible"),
             ("caducada", "chapa", 300, "disponible"), ("vendido", "chapa", 400, "vendido"),
             ("bloqueado", "chapa", 500, "bloqueado"), ("estatico", "bobina", 600, "reservado")],
        )
        conexion.executemany(
            "INSERT INTO reservas VALUES (?, 'carrito', ?, ?)",
            [("vigente", ahora_ms - 100, ahora_ms + 1), ("caducada", ahora_ms - 100, ahora_ms)],
        )
    reporte = reporte_diario_inventario(ahora=ahora)
    assert reporte["fecha"] == "2026-11-27"
    assert reporte["consultado_en"] == "2026-11-27T00:15:00+01:00"
    assert reporte["formatos"] == [
        {"formato": "bobina", "total_bultos": 1, "disponibles": 0, "reservados": 1, "bloqueados": 0, "peso_kg": 600},
        {"formato": "chapa", "total_bultos": 4, "disponibles": 2, "reservados": 1, "bloqueados": 1, "peso_kg": 1100},
    ]


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
    reporte = reporte_semanal(ahora=inicio + timedelta(days=7) - milisegundo)
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


def test_tendencias_marca_historico_vacio(base):
    informe = obtener_tendencias_compras(semanas=2, unidad="kg")
    assert informe["materiales"] == []
    assert all(s["estado"] == "sin_historial" for s in informe["semanas"])
    assert all(b["cantidad"] is None for s in informe["semanas"] for b in s["barras"])


def test_tendencias_convierte_toneladas_y_compara_semanas_cerradas(base):
    ahora = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)
    with sqlite3.connect(base) as conexion:
        for n, dia, valor, unidad in (
            ("inicio", 2, 5, "kg"), ("previa", 9, 0.1, "t"), ("actual", 16, 150, "kg"),
            ("bulto", 16, 2, "bultos"), ("futura", 27, 500, "kg"),
        ):
            registrar_compra(conexion, compra_id=n, bulto=BULTO, cantidad=valor, unidad=unidad,
                             comprada_en=datetime(2026, 11, dia, 12, tzinfo=timezone.utc))
    informe = tendencias_compras(5, "kg", ahora=ahora)
    semanas = informe["semanas"]
    assert [s["estado"] for s in semanas] == [
        "sin_historial", "inicio_historial", "completa", "completa", "en_curso",
    ]
    bobinas = [s["barras"][0] for s in semanas]
    assert [b["cantidad"] for b in bobinas] == [None, 5, 100, 150, 0]
    assert bobinas[3]["tendencia"] == "sube"
    assert bobinas[3]["variacion_pct"] == 50
    assert bobinas[4]["variacion_pct"] is None
    assert informe["materiales"][0]["comprado"] == 255
    assert tendencias_compras(5, "bultos", ahora=ahora)["materiales"][0]["comprado"] == 2


def test_tendencias_usa_la_ficha_consolidada_del_reporte_semanal(base):
    ahora = datetime(2026, 11, 26, 10, tzinfo=timezone.utc)
    with sqlite3.connect(base) as conexion:
        guardar(conexion, "primero", ahora - timedelta(days=1))
        registrar_compra(conexion, compra_id="segundo", bulto=dict(BULTO, ancho_mm=1250),
                         cantidad=10, unidad="kg", comprada_en=ahora)
    [compra] = reporte_semanal(ahora=ahora)["compras"]
    [material] = tendencias_compras(1, "kg", ahora=ahora)["materiales"]
    assert material["formato"] == compra["formato"] == "bobina"
    assert material["ancho_mm"] == compra["caracteristicas"]["ancho_mm"] == 1250
    assert material["comprado"] == compra["cantidades_sustraidas"][0]["valor"] == 310.5
