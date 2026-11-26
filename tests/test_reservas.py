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


# ---------- Paso 2: reservar, liberar, caducidad y concurrencia ----------

from datetime import datetime, timedelta  # noqa: E402
import threading  # noqa: E402

from app.reportes import ZONA_REPORTE  # noqa: E402
from app.reservas import liberar, liberar_todas, mis_reservas, reservar  # noqa: E402
from app.ventas import BultosNoDisponibles  # noqa: E402

T0 = datetime(2026, 11, 26, 10, 0, tzinfo=ZONA_REPORTE)


def _min(m):
    return T0 + timedelta(minutes=m)


def _poner_estado(ruta, bulto_id, estado):
    with sqlite3.connect(ruta) as conn:
        conn.execute("UPDATE bultos SET estado = ? WHERE id = ?", (estado, bulto_id))


def test_reservar_devuelve_la_caducidad(base):
    [r] = reservar(["334"], "a", ahora=T0)
    assert r["bulto_id"] == "334"
    assert datetime.fromisoformat(r["expira_en"]) == _min(config.RESERVA_MINUTOS)
    assert [m["bulto_id"] for m in mis_reservas("a", ahora=T0)] == ["334"]


def test_un_bulto_reservado_por_otro_no_se_puede_reservar(base):
    reservar(["334"], "a", ahora=T0)
    with pytest.raises(BultosNoDisponibles) as e:
        reservar(["334"], "b", ahora=_min(1))
    assert e.value.ids == ["334"]
    assert mis_reservas("b", ahora=_min(1)) == []


def test_reservar_es_todo_o_nada(base):
    reservar(["334"], "a", ahora=T0)
    with pytest.raises(BultosNoDisponibles) as e:
        reservar(["23", "334", "no-existe"], "b", ahora=T0)
    assert e.value.ids == ["334", "no-existe"]
    assert mis_reservas("b", ahora=T0) == []             # 23 tampoco se ha reservado


@pytest.mark.parametrize("estado", ["vendido", "reservado", "bloqueado"])
def test_solo_se_reservan_bultos_disponibles(base, estado):
    _poner_estado(base, "334", estado)
    with pytest.raises(BultosNoDisponibles):
        reservar(["334"], "a", ahora=T0)


def test_volver_a_reservar_lo_propio_renueva_la_caducidad(base):
    reservar(["334"], "a", ahora=T0)
    [r] = reservar(["334"], "a", ahora=_min(10))
    assert datetime.fromisoformat(r["expira_en"]) == _min(10 + config.RESERVA_MINUTOS)
    with pytest.raises(BultosNoDisponibles):                 # sigue siendo de a pasados los 15 min iniciales
        reservar(["334"], "b", ahora=_min(config.RESERVA_MINUTOS + 1))


def test_al_caducar_otro_puede_reservarlo(base):
    reservar(["334"], "a", ahora=T0)
    with pytest.raises(BultosNoDisponibles):
        reservar(["334"], "b", ahora=_min(config.RESERVA_MINUTOS - 1))
    reservar(["334"], "b", ahora=_min(config.RESERVA_MINUTOS))
    assert mis_reservas("a", ahora=_min(config.RESERVA_MINUTOS)) == []
    assert [m["bulto_id"] for m in mis_reservas("b", ahora=_min(config.RESERVA_MINUTOS))] == ["334"]


def test_solo_el_titular_libera_su_reserva(base):
    reservar(["334"], "a", ahora=T0)
    assert liberar("334", "b") is False
    with pytest.raises(BultosNoDisponibles):
        reservar(["334"], "b", ahora=T0)
    assert liberar("334", "a") is True
    reservar(["334"], "b", ahora=T0)                         # al quitarlo del carrito vuelve a estar libre


def test_vaciar_el_carrito_solo_libera_lo_propio(base):
    reservar(["334", "23"], "a", ahora=T0)
    reservar(["1"], "b", ahora=T0)
    assert liberar_todas("a") == 2
    assert mis_reservas("a", ahora=T0) == []
    assert len(mis_reservas("b", ahora=T0)) == 1


@pytest.mark.parametrize("titular", ["", "   ", None])
def test_sin_titular_no_se_reserva(base, titular):
    with pytest.raises(ValueError):
        reservar(["334"], titular, ahora=T0)


def test_carrito_vacio_no_se_reserva(base):
    with pytest.raises(ValueError):
        reservar([" ", ""], "a", ahora=T0)


def test_dos_carritos_a_la_vez_sobre_el_mismo_bulto_solo_gana_uno(base):
    """Ocho comerciales pulsan «Añadir al carrito» en el mismo instante: solo uno se lo lleva."""
    n = 8
    salida = threading.Barrier(n)
    ganadores, perdedores, errores = [], [], []

    def comercial(titular):
        salida.wait()
        try:
            reservar(["334"], titular, ahora=T0)
            ganadores.append(titular)
        except BultosNoDisponibles:
            perdedores.append(titular)
        except Exception as e:                               # p. ej. «database is locked»
            errores.append(e)

    hilos = [threading.Thread(target=comercial, args=(f"t{i}",)) for i in range(n)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []
    assert len(ganadores) == 1 and len(perdedores) == n - 1
    assert _num_reservas(base) == 1
