"""Venta simulada del carrito (POST /compras): marca los bultos como vendidos y los registra en compras."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import sys

import pytest

pytest.importorskip("pandas")
pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.db import crear_db, disponibles  # noqa: E402
from app.main import app  # noqa: E402
from app.reportes import reporte_semanal  # noqa: E402
from app.reservas import reservar  # noqa: E402
from app.ventas import BultosNoDisponibles, vender  # noqa: E402


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Inventario real cargado en una base temporal (no toca backend/data/aceria.db)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "inventario.db")
    monkeypatch.setattr(config, "ESTADOS_DEMO", tmp_path / "sin_estados_demo.csv")
    crear_db()
    return config.DB_PATH


TITULAR = "carrito-test"


def reservar_y_vender(ids, titular=TITULAR, **kw):
    """Venta estricta (tarea 4): primero se reserva, como hace el frontend al añadir al carrito."""
    reservar(ids, titular)
    return vender(ids, titular, **kw)


def estado(base, bulto_id):
    with sqlite3.connect(base) as c:
        return c.execute("SELECT estado FROM bultos WHERE id = ?", (bulto_id,)).fetchone()[0]


def test_vender_marca_vendido_y_aparece_en_el_reporte(base):
    ahora = datetime.now(timezone.utc)
    r = reservar_y_vender(["334", "23"], ahora=ahora)
    assert r["vendidos"] == ["334", "23"]
    assert estado(base, "334") == estado(base, "23") == "vendido"
    assert not {"334", "23"} & {b["id"] for b in disponibles()}          # ya no salen en /buscar ni /chat
    compras = reporte_semanal(ahora=ahora)["compras"]
    assert {c["caracteristicas"]["id"] for c in compras} == {"334", "23"}
    c334 = next(c for c in compras if c["caracteristicas"]["id"] == "334")
    assert c334["cantidades_sustraidas"] == [{"valor": 745.0, "unidad": "kg"}]
    with sqlite3.connect(base) as conn:
        [material] = conn.execute(
            "SELECT material_json FROM compras WHERE id = ?", (r["compras"][0]["compra_id"],),
        ).fetchone()
    assert json.loads(material)["estado"] == "disponible"  # ficha guardada antes de la baja


def test_si_un_bulto_no_esta_disponible_no_se_vende_ninguno(base):
    reservar_y_vender(["334"])
    reservar(["23"], TITULAR)
    with pytest.raises(BultosNoDisponibles) as e:
        vender(["23", "334", "no-existe"], TITULAR)
    assert e.value.ids == ["334", "no-existe"]
    assert estado(base, "23") == "disponible"                            # todo o nada
    assert len(reporte_semanal()["compras"]) == 1


def test_al_reiniciar_se_conservan_las_ventas_y_el_reporte(base):
    reservar_y_vender(["334"])
    crear_db()                                                           # arranque normal: se recarga el Excel
    assert estado(base, "334") == "vendido"
    assert estado(base, "23") == "disponible"
    assert [c["caracteristicas"]["id"] for c in reporte_semanal()["compras"]] == ["334"]


def test_reiniciar_la_demo_deja_todo_como_al_principio(base):
    reservar_y_vender(["334"])
    crear_db(reiniciar_ventas=True)                                      # python arrancar.py --reiniciar-demo
    assert estado(base, "334") == "disponible"
    assert reporte_semanal()["compras"] == []


@pytest.mark.parametrize("valor,vendido", [("0", True), ("1", False)])
def test_el_arranque_del_backend_respeta_la_opcion_de_reinicio(base, monkeypatch, valor, vendido):
    reservar_y_vender(["334"])
    monkeypatch.setenv("ACERIA_REINICIAR_DEMO", valor)
    with TestClient(app):                                                # ejecuta el arranque (lifespan)
        pass
    assert (estado(base, "334") == "vendido") is vendido


def test_endpoint_compras(base):
    cliente = TestClient(app, headers={"X-Carrito": TITULAR})
    reservar(["334"], TITULAR)
    ok = cliente.post("/compras", json={"bultos": ["334"]})
    assert ok.status_code == 200 and ok.json()["vendidos"] == ["334"]
    repetida = cliente.post("/compras", json={"bultos": ["334"]})
    assert repetida.status_code == 409 and repetida.json()["detail"]["no_disponibles"] == ["334"]
    vacia = cliente.post("/compras", json={"bultos": []})
    assert vacia.status_code == 422
    assert cliente.get("/reportes/compras/semanal").json()["compras"][0]["caracteristicas"]["id"] == "334"
