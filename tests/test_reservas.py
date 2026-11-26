"""Tarea 4: reservas del carrito para que dos comerciales no cojan el mismo bulto.

Ejecutar desde la raíz del repositorio:  python -m pytest -q
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
pytest.importorskip("pandas")
pytest.importorskip("openpyxl")

from app import config, db  # noqa: E402


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "aceria.db")
    monkeypatch.setattr(config, "ESTADOS_DEMO", tmp_path / "sin_estados_demo.csv")
    db.crear_db()
    return config.DB_PATH


def _reservar_a_mano(ruta, bulto_id="1", titular="a"):
    with sqlite3.connect(ruta) as conn:
        conn.execute("INSERT INTO reservas VALUES (?, ?, ?, ?)", (bulto_id, titular, 1, 2))


def _num_reservas(ruta):
    with sqlite3.connect(ruta) as conn:
        return conn.execute("SELECT COUNT(*) FROM reservas").fetchone()[0]


# ---------- Paso 1: tabla, caducidad configurable y vaciado al arrancar ----------

def test_la_caducidad_es_configurable():
    assert config.RESERVA_MINUTOS > 0


def test_la_tabla_de_reservas_existe_y_un_bulto_solo_tiene_una(base):
    _reservar_a_mano(base, "1", "a")
    with pytest.raises(sqlite3.IntegrityError):
        _reservar_a_mano(base, "1", "b")


def test_cada_arranque_vacia_las_reservas(base):
    _reservar_a_mano(base)
    db.crear_db()
    assert _num_reservas(base) == 0


def test_reiniciar_demo_vacia_las_reservas(base):
    _reservar_a_mano(base)
    db.crear_db(reiniciar_ventas=True)
    assert _num_reservas(base) == 0
