"""Reposición: últimas 4 semanas completas, cobertura = stock ÷ (ventas ÷ 28)."""
from datetime import datetime, timedelta
from itertools import count
from pathlib import Path
import sqlite3
import sys

import pytest

pytest.importorskip("pandas")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import config
from app.db import SCHEMA
from app.reportes import ZONA_REPORTE, registrar_compra
from app.tendencias import recomendaciones_reposicion


# Jueves; la semana en curso empieza el lunes 23/11 y el periodo va del 26/10 al 22/11.
AHORA = datetime(2026, 11, 26, 12, tzinfo=ZONA_REPORTE)
LUNES_ACTUAL = datetime(2026, 11, 23, 10, tzinfo=ZONA_REPORTE)
_ids = count()


@pytest.fixture
def base(tmp_path, monkeypatch):
    ruta = tmp_path / "inventario.db"
    monkeypatch.setattr(config, "DB_PATH", ruta)
    with sqlite3.connect(ruta) as conexion:
        conexion.executescript(SCHEMA.read_text(encoding="utf-8"))
    return ruta


def bulto(ancho, peso_kg=1000):
    return {"id": f"b{next(_ids)}", "formato": "bobina", "aisi": "304", "acabado": "2B",
            "espesor_mm": 2, "ancho_mm": ancho, "peso_kg": peso_kg}


def vender(base, ancho, kg_por_semana, *, unidad="kg", cantidad=None):
    """Una venta por semana; la semana 0 es la última completa (16/11) y la 3 la primera (26/10)."""
    with sqlite3.connect(base) as conexion:
        for semanas_atras, kg in kg_por_semana.items():
            fecha = LUNES_ACTUAL - timedelta(weeks=semanas_atras + 1)
            registrar_compra(conexion, compra_id=f"c{next(_ids)}", bulto=bulto(ancho, kg),
                             cantidad=cantidad if cantidad is not None else kg,
                             unidad=unidad, comprada_en=fecha)


def stock(base, ancho, kg, estado="disponible"):
    with sqlite3.connect(base) as conexion:
        b = bulto(ancho, kg)
        conexion.execute(
            """INSERT INTO bultos (id, formato, aisi, acabado, espesor_mm, ancho_mm, peso_kg, estado)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (b["id"], b["formato"], b["aisi"], b["acabado"], b["espesor_mm"], b["ancho_mm"], kg, estado),
        )


def por_ancho(informe):
    return {fila["ancho_mm"]: (nombre, fila)
            for nombre, filas in informe["secciones"].items() for fila in filas}


def test_base_sin_ventas(base):
    informe = recomendaciones_reposicion(ahora=AHORA)
    assert informe["secciones"] == {"reponer": [], "vigilar": [], "puntual": []}
    assert informe["periodo"] == {"inicio": "2026-10-26", "fin": "2026-11-22", "semanas": 4,
                                  "dias": 28, "zona_horaria": "Europe/Madrid"}
    assert informe["umbrales"]["cobertura_reponer_dias"] == 7
    assert informe["filtro"] == {"vendido_min_t": 2, "stock_max_t": 2}


def test_limites_de_cobertura(base):
    # 2800 kg en 28 días = 100 kg/día.
    for ancho, kg_stock in ((1000, 699), (1001, 700), (1002, 1400), (1003, 1401)):
        vender(base, ancho, {0: 1400, 2: 1400})
        stock(base, ancho, kg_stock)
    filas = por_ancho(recomendaciones_reposicion(ahora=AHORA))
    assert filas[1000][0] == "reponer"
    assert filas[1001][0] == "vigilar" and filas[1001][1]["cobertura_dias"] == 7
    assert filas[1002][0] == "vigilar" and filas[1002][1]["cobertura_dias"] == 14
    assert 1003 not in filas


def test_stock_cero_y_no_disponible(base):
    vender(base, 1000, {0: 500, 1: 500})
    stock(base, 1000, 5000, estado="bloqueado")
    _, fila = por_ancho(recomendaciones_reposicion(ahora=AHORA))[1000]
    assert fila["seccion"] == "reponer"
    assert (fila["disponible_t"], fila["cobertura_dias"], fila["semanas_con_ventas"]) == (0, 0, 2)


def test_salida_puntual_con_2_t_exactas(base):
    for ancho, kg_stock in ((1000, 1999), (1001, 2000)):
        vender(base, ancho, {1: 3000})
        stock(base, ancho, kg_stock)
    filas = por_ancho(recomendaciones_reposicion(ahora=AHORA))
    assert filas[1000][0] == "puntual"
    assert 1001 not in filas


def test_excluye_la_semana_en_curso_y_la_anterior_al_periodo(base):
    vender(base, 1000, {0: 1000})
    vender(base, 1000, {4: 1000})                      # 19/10, fuera del periodo
    with sqlite3.connect(base) as conexion:            # semana en curso
        registrar_compra(conexion, compra_id="hoy", bulto=bulto(1000, 1000),
                         cantidad=1000, unidad="kg", comprada_en=LUNES_ACTUAL)
    _, fila = por_ancho(recomendaciones_reposicion(ahora=AHORA))[1000]
    assert (fila["seccion"], fila["semanas_con_ventas"], fila["vendido_t"]) == ("puntual", 1, 1)


def test_unidades_toneladas_bultos_y_piezas(base):
    vender(base, 1000, {0: 1, 1: 1}, unidad="t")                    # 2000 kg
    vender(base, 1001, {0: 800, 1: 800}, unidad="bultos", cantidad=1)
    vender(base, 1002, {0: 800, 1: 800}, unidad="piezas", cantidad=3)
    filas = por_ancho(recomendaciones_reposicion(ahora=AHORA))
    assert filas[1000][1]["vendido_t"] == 2
    assert filas[1001][1]["vendido_t"] == 1.6
    assert 1002 not in filas


def test_orden_y_filtro_sin_cambiar_la_seccion(base):
    vender(base, 1000, {0: 1000, 1: 1000})      # 2 t vendidas exactas: no pasa el filtro
    vender(base, 1001, {0: 1500, 1: 1500})      # 3 t, stock 0: misma cobertura, más volumen
    vender(base, 1002, {0: 20000, 1: 20000})
    stock(base, 1002, 1999)                     # pasa el filtro
    vender(base, 1003, {0: 20000, 1: 20000})
    stock(base, 1003, 2000)                     # 2 t disponibles exactas: no pasa
    informe = recomendaciones_reposicion(ahora=AHORA)
    reponer = informe["secciones"]["reponer"]
    assert [f["ancho_mm"] for f in reponer] == [1001, 1000, 1002, 1003]
    assert [f["cumple_filtro"] for f in reponer] == [True, False, True, False]
    assert all(f["seccion"] == "reponer" for f in reponer)


def test_endpoint_reposicion(base):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app

    respuesta = TestClient(app).get("/reportes/reposicion")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"periodo", "stock_a", "umbrales", "filtro", "secciones"}
    assert set(cuerpo["secciones"]) == {"reponer", "vigilar", "puntual"}


def test_limites_de_la_semana_en_hora_de_madrid(base):
    domingo = datetime(2026, 11, 22, 23, 59, 59, 999000, tzinfo=ZONA_REPORTE)
    lunes_antes = datetime(2026, 10, 26, tzinfo=ZONA_REPORTE)
    with sqlite3.connect(base) as conexion:
        for fecha in (domingo, lunes_antes, lunes_antes - timedelta(milliseconds=1), LUNES_ACTUAL.replace(hour=0)):
            registrar_compra(conexion, compra_id=f"c{next(_ids)}", bulto=bulto(1000, 1000),
                             cantidad=1000, unidad="kg", comprada_en=fecha)
    _, fila = por_ancho(recomendaciones_reposicion(ahora=AHORA))[1000]
    assert (fila["vendido_t"], fila["semanas_con_ventas"]) == (2, 2)


def test_periodo_que_cruza_el_cambio_de_hora(base):
    # El 25/10/2026 termina el horario de verano: la semana del 19/10 dura 169 horas.
    ahora = datetime(2026, 11, 5, 12, tzinfo=ZONA_REPORTE)
    domingo_cambio = datetime(2026, 10, 25, 23, 30, tzinfo=ZONA_REPORTE)
    with sqlite3.connect(base) as conexion:
        for fecha in (datetime(2026, 10, 5, tzinfo=ZONA_REPORTE), domingo_cambio):
            registrar_compra(conexion, compra_id=f"c{next(_ids)}", bulto=bulto(1000, 1000),
                             cantidad=1000, unidad="kg", comprada_en=fecha)
    informe = recomendaciones_reposicion(ahora=ahora)
    assert (informe["periodo"]["inicio"], informe["periodo"]["fin"]) == ("2026-10-05", "2026-11-01")
    _, fila = por_ancho(informe)[1000]
    assert (fila["vendido_t"], fila["semanas_con_ventas"]) == (2, 2)


def test_una_semana_nunca_es_reponer_y_recurrente_con_poco_stock_no_es_puntual(base):
    vender(base, 1000, {0: 10000})              # cobertura 2,8 días, pero una sola semana
    stock(base, 1000, 1000)
    vender(base, 1001, {0: 100, 1: 100})         # recurrente, 1 t de stock = 140 días
    stock(base, 1001, 1000)
    filas = por_ancho(recomendaciones_reposicion(ahora=AHORA))
    assert filas[1000][0] == "puntual"
    assert 1001 not in filas
