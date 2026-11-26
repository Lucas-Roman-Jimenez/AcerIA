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


# ---------- Paso 3: un bulto reservado no sale en /buscar, /chat ni /stock ----------

from app.buscador import buscar_bultos, construir_objetivo, valores_disponibles  # noqa: E402

# Bulto 334 del inventario real: bobina 304L/304 2B de 2 × 1500 mm.
ESPEC_334 = {"grado": "304", "acabado": "2B", "formato": "bobina", "espesor_mm": 2.0, "ancho_mm": 1500.0}


def _ids_ofrecidos(espec=ESPEC_334):
    exactos, transformables = buscar_bultos(construir_objetivo(espec))
    return {b["id"] for b in exactos} | {t["bulto_id"] for t in transformables}


def _ms(momento):
    return int(momento.timestamp() * 1000)


def test_un_bulto_reservado_desaparece_de_disponibles(base):
    assert "334" in {b["id"] for b in db.disponibles()}
    reservar(["334"], "a")
    assert "334" not in {b["id"] for b in db.disponibles()}


def test_un_bulto_reservado_no_sale_en_la_busqueda_ni_siquiera_para_su_titular(base):
    assert "334" in _ids_ofrecidos()
    reservar(["334"], "a")
    assert "334" not in _ids_ofrecidos()                     # ni como exacto ni como transformable


def test_un_bulto_reservado_no_cuenta_en_los_valores_del_stock(base):
    def bultos_de_2mm():
        return next(v["bultos"] for v in valores_disponibles("espesor_mm", ESPEC_334) if v["valor"] == 2.0)
    antes = bultos_de_2mm()
    reservar(["334"], "a")
    assert bultos_de_2mm() == antes - 1


def test_al_liberarlo_vuelve_a_salir(base):
    reservar(["334"], "a")
    liberar("334", "a")
    assert "334" in _ids_ofrecidos()


def test_al_caducar_vuelve_a_salir(base):
    reservar(["334"], "a", ahora=T0)
    assert "334" not in {b["id"] for b in db.disponibles(_ms(_min(config.RESERVA_MINUTOS - 1)))}
    assert "334" in {b["id"] for b in db.disponibles(_ms(_min(config.RESERVA_MINUTOS)))}


def test_la_api_de_busqueda_no_ofrece_bultos_reservados(base):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app

    cliente = TestClient(app)
    ids = lambda r: {b["id"] for b in r.json()["exactos"]}  # noqa: E731
    assert "334" in ids(cliente.post("/buscar", json=ESPEC_334))
    reservar(["334"], "a")
    assert "334" not in ids(cliente.post("/buscar", json=ESPEC_334))


# ---------- Paso 4: venta estricta, solo lo reservado por uno mismo ----------

from app.ventas import vender  # noqa: E402


def _estado(ruta, bulto_id):
    with sqlite3.connect(ruta) as conn:
        return conn.execute("SELECT estado FROM bultos WHERE id = ?", (bulto_id,)).fetchone()[0]


def test_se_vende_lo_reservado_por_uno_mismo_y_la_reserva_desaparece(base):
    reservar(["334", "23"], "a", ahora=T0)
    r = vender(["334", "23"], "a", ahora=_min(5))
    assert r["vendidos"] == ["334", "23"]
    assert _estado(base, "334") == _estado(base, "23") == "vendido"
    assert _num_reservas(base) == 0


def test_no_se_vende_lo_que_no_esta_reservado(base):
    with pytest.raises(BultosNoDisponibles) as e:
        vender(["334"], "a", ahora=T0)
    assert e.value.ids == ["334"]
    assert _estado(base, "334") == "disponible"


def test_no_se_vende_lo_reservado_por_otro(base):
    reservar(["334"], "a", ahora=T0)
    with pytest.raises(BultosNoDisponibles):
        vender(["334"], "b", ahora=_min(1))
    assert _estado(base, "334") == "disponible"
    assert [m["bulto_id"] for m in mis_reservas("a", ahora=_min(1))] == ["334"]   # la reserva de a sigue


def test_no_se_vende_con_la_reserva_caducada(base):
    reservar(["334"], "a", ahora=T0)
    with pytest.raises(BultosNoDisponibles):
        vender(["334"], "a", ahora=_min(config.RESERVA_MINUTOS))
    assert _estado(base, "334") == "disponible"


def test_venta_estricta_es_todo_o_nada(base):
    reservar(["334"], "a", ahora=T0)
    with pytest.raises(BultosNoDisponibles) as e:
        vender(["334", "23"], "a", ahora=_min(1))             # 23 no está reservado
    assert e.value.ids == ["23"]
    assert _estado(base, "334") == "disponible"
    assert len(mis_reservas("a", ahora=_min(1))) == 1           # la reserva de 334 se conserva


@pytest.mark.parametrize("titular", ["", "  ", None])
def test_sin_titular_no_se_vende(base, titular):
    reservar(["334"], "a", ahora=T0)
    with pytest.raises(ValueError):
        vender(["334"], titular, ahora=_min(1))


def test_api_compras_usa_la_cabecera_x_carrito(base):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app

    cliente = TestClient(app)
    reservar(["334"], "a")
    otro = cliente.post("/compras", json={"bultos": ["334"]}, headers={"X-Carrito": "b"})
    assert otro.status_code == 409 and otro.json()["detail"]["no_disponibles"] == ["334"]
    sin_cabecera = cliente.post("/compras", json={"bultos": ["334"]})
    assert sin_cabecera.status_code == 422
    assert sin_cabecera.json()["detail"] == "El carrito está vacío o no es válido."
    ok = cliente.post("/compras", json={"bultos": ["334"]}, headers={"X-Carrito": "a"})
    assert ok.status_code == 200 and ok.json()["vendidos"] == ["334"]


# ---------- Paso 5: endpoints /reservas y CORS ----------

@pytest.fixture
def api(base):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def _h(titular):
    return {"X-Carrito": titular}


def test_api_flujo_completo_del_carrito(api, base):
    r = api.post("/reservas", json={"bultos": ["334", "23"]}, headers=_h("a"))
    assert r.status_code == 200
    assert [x["bulto_id"] for x in r.json()["reservas"]] == ["334", "23"]
    assert r.json()["minutos"] == config.RESERVA_MINUTOS
    assert [x["bulto_id"] for x in api.get("/reservas", headers=_h("a")).json()["reservas"]] == ["334", "23"]

    assert api.delete("/reservas/23", headers=_h("a")).status_code == 204         # quitar del carrito
    assert [x["bulto_id"] for x in api.get("/reservas", headers=_h("a")).json()["reservas"]] == ["334"]

    venta = api.post("/compras", json={"bultos": ["334"]}, headers=_h("a"))
    assert venta.status_code == 200 and venta.json()["vendidos"] == ["334"]
    assert api.get("/reservas", headers=_h("a")).json()["reservas"] == []


def test_api_reservar_lo_que_tiene_otro_da_409(api):
    api.post("/reservas", json={"bultos": ["334"]}, headers=_h("a"))
    r = api.post("/reservas", json={"bultos": ["23", "334"]}, headers=_h("b"))
    assert r.status_code == 409
    assert r.json()["detail"]["no_disponibles"] == ["334"]
    assert api.get("/reservas", headers=_h("b")).json()["reservas"] == []           # todo o nada


def test_api_no_se_puede_quitar_la_reserva_de_otro(api):
    api.post("/reservas", json={"bultos": ["334"]}, headers=_h("a"))
    assert api.delete("/reservas/334", headers=_h("b")).status_code == 404
    assert len(api.get("/reservas", headers=_h("a")).json()["reservas"]) == 1


def test_api_vaciar_el_carrito(api):
    api.post("/reservas", json={"bultos": ["334", "23"]}, headers=_h("a"))
    api.post("/reservas", json={"bultos": ["1"]}, headers=_h("b"))
    r = api.delete("/reservas", headers=_h("a"))
    assert r.status_code == 200 and r.json() == {"liberadas": 2}
    assert len(api.get("/reservas", headers=_h("b")).json()["reservas"]) == 1


@pytest.mark.parametrize("metodo,ruta,cuerpo", [
    ("post", "/reservas", {"bultos": ["334"]}), ("get", "/reservas", None),
    ("delete", "/reservas/334", None), ("delete", "/reservas", None),
])
def test_api_sin_cabecera_x_carrito_da_422(api, metodo, ruta, cuerpo):
    kw = {"json": cuerpo} if cuerpo is not None else {}
    r = getattr(api, metodo)(ruta, **kw)
    assert r.status_code == 422
    assert r.json()["detail"] == "Falta la cabecera X-Carrito."


def test_api_reservar_sin_bultos_da_422_con_texto_fijo(api):
    r = api.post("/reservas", json={"bultos": []}, headers=_h("a"))
    assert r.status_code == 422                                   # tarea 6: lo valida Pydantic
    assert r.json() == {"detail": "Datos no válidos.", "errores": [{"campo": "bultos", "mensaje": "no puede estar vacío"}]}


def test_api_cabecera_x_carrito_demasiado_larga_da_422(api):
    assert api.get("/reservas", headers=_h("x" * 101)).status_code == 422


@pytest.mark.parametrize("metodo", ["DELETE", "POST"])
def test_cors_deja_al_frontend_reservar_y_quitar_con_x_carrito(api, metodo):
    r = api.options("/reservas", headers={
        "Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": metodo,
        "Access-Control-Request-Headers": "content-type,x-carrito"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_cors_no_deja_a_otra_web_quitar_reservas(api):
    r = api.options("/reservas", headers={
        "Origin": "https://web-maliciosa.example", "Access-Control-Request-Method": "DELETE",
        "Access-Control-Request-Headers": "x-carrito"})
    assert "access-control-allow-origin" not in r.headers
