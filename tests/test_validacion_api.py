"""Tarea 6: validación con Pydantic de todo lo que entra en la API (backend/app/modelos.py).

Sin LLM: interpretar() se sustituye para que falle (ErrorLLM) y no se llama al proveedor.
Ejecutar desde la raíz del repositorio:  python -m pytest -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
pytest.importorskip("pandas")
pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from typing import get_args  # noqa: E402

from app import config, conversacion, db  # noqa: E402
from app.buscador import CAMPOS_VALORES  # noqa: E402
from app.main import app  # noqa: E402
from app.modelos import CampoStock  # noqa: E402
from llm import ErrorLLM  # noqa: E402

H = {"X-Carrito": "k-test"}
ESPEC_OK = {"grado": "304", "acabado": "2B", "formato": "chapa", "espesor_mm": 2, "ancho_mm": 1000}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "aceria.db")
    monkeypatch.setattr(config, "ESTADOS_DEMO", tmp_path / "sin_estados_demo.csv")
    db.crear_db()

    def sin_llm(historial):
        raise ErrorLLM("sin LLM en el test")

    monkeypatch.setattr(conversacion, "interpretar", sin_llm)
    return TestClient(app, raise_server_exceptions=False)


# ---------- Paso 1: lo mal formado da 422 (nunca 500 ni 200) ----------

MALAS_BUSQUEDAS = {
    "espesor no numérico": {"espesor_mm": "abc"},
    "espesor negativo": {"espesor_mm": -2},
    "espesor cero": {"espesor_mm": 0},
    "espesor por encima del límite": {"espesor_mm": config.MAX_ESPESOR_MM + 1},
    "ancho por encima del límite": {"ancho_mm": config.MAX_ANCHO_MM + 1},
    "largo negativo": {"largo_mm": -1},
    "formato inventado": {"formato": "tubo"},
    "grado como lista": {"grado": ["304", {"x": 1}]},
    "grado vacío": {"grado": "  "},
    "grado demasiado largo": {"grado": "3" * (config.MAX_LONGITUD_VALOR + 1)},
    "opciones que no son listas de textos": {"opciones": {"acabado": 5}},
    "demasiadas opciones": {"opciones": {"acabado": [f"A{i}" for i in range(config.MAX_OPCIONES + 1)]}},
    "el cuerpo no es un objeto": [1, 2],
}


@pytest.mark.parametrize("cuerpo", MALAS_BUSQUEDAS.values(), ids=MALAS_BUSQUEDAS.keys())
def test_buscar_rechaza_lo_mal_formado(cliente, cuerpo):
    assert cliente.post("/buscar", json=cuerpo).status_code == 422


def test_buscar_acepta_lo_que_mandan_el_frontend_y_la_evaluacion(cliente):
    r = cliente.post("/buscar", json={**ESPEC_OK, "largo_mm": 2000, "opciones": {}})
    assert r.status_code == 200 and r.json()["estado"] == "resultados"


def test_buscar_ignora_los_campos_que_no_conoce(cliente):
    """La especificación completa de Nacho (uso, avisos, cantidad…) se puede mandar tal cual."""
    r = cliente.post("/buscar", json={**ESPEC_OK, "uso": "fachada", "avisos": [], "cantidad": {"valor": 2, "unidad": "t"},
                                      "indiferentes": ["largo_mm"], "faltan": []})
    assert r.status_code == 200


def test_buscar_formato_en_mayusculas_se_acepta(cliente):
    assert cliente.post("/buscar", json={**ESPEC_OK, "formato": " Chapa "}).json()["objetivo"]["formato"] == "chapa"


def test_buscar_un_grado_que_no_existe_no_es_un_error_sino_sin_stock(cliente):
    r = cliente.post("/buscar", json={**ESPEC_OK, "grado": "999X"})
    assert r.status_code == 200 and r.json()["estado"] == "sin_stock"


MALOS_VALORES = {
    "campo inventado": "campo=zzz",
    "espesor negativo": "campo=grado&espesor_mm=-1",
    "espesor no numérico": "campo=grado&espesor_mm=abc",
    "ancho por encima del límite": f"campo=grado&ancho_mm={config.MAX_ANCHO_MM + 1}",
    "formato inventado": "campo=grado&formato=tubo",
    "grado demasiado largo": f"campo=acabado&grado={'3' * (config.MAX_LONGITUD_VALOR + 1)}",
}


@pytest.mark.parametrize("consulta", MALOS_VALORES.values(), ids=MALOS_VALORES.keys())
def test_stock_valores_rechaza_lo_mal_formado(cliente, consulta):
    assert cliente.get(f"/stock/valores?{consulta}").status_code == 422


def test_stock_valores_un_grado_que_no_existe_da_cero_bultos(cliente):
    """El frontend marca «sin stock» con esto: no puede ser un 422."""
    r = cliente.get("/stock/valores?campo=espesor_mm&grado=999X")
    assert r.status_code == 200 and r.json()["total_bultos"] == 0


def test_los_campos_de_stock_valores_coinciden_con_el_buscador():
    assert set(get_args(CampoStock)) == set(CAMPOS_VALORES)


@pytest.mark.parametrize("limite,codigo", [(0, 422), (-5, 422), (config.MAX_LIMITE_RESUMEN + 1, 422),
                                           (1, 200), (config.MAX_LIMITE_RESUMEN, 200)])
def test_stock_resumen_limite(cliente, limite, codigo):
    assert cliente.get(f"/stock/resumen?limite={limite}").status_code == codigo


@pytest.mark.parametrize("ruta", ["/compras", "/reservas"])
@pytest.mark.parametrize("bultos", [
    "334",                                                      # no es una lista
    [str(i) for i in range(config.MAX_BULTOS_CARRITO + 1)],    # demasiados
    ["x" * (config.MAX_LONGITUD_ID + 1)],                       # ID demasiado largo
    [{"id": "334"}],                                            # no son textos
], ids=["no-lista", "demasiados", "id-largo", "no-textos"])
def test_carrito_rechaza_listas_mal_formadas(cliente, ruta, bultos):
    assert cliente.post(ruta, json={"bultos": bultos}, headers=H).status_code == 422


@pytest.mark.parametrize("cabecera", ["con espacio", "k;DROP", "ñ" * 3, "x" * 101])
def test_x_carrito_con_caracteres_raros_se_rechaza(cliente, cabecera):
    assert cliente.get("/reservas", headers={"X-Carrito": cabecera.encode("utf-8")}).status_code == 422


def test_x_carrito_del_frontend_se_acepta(cliente):
    assert cliente.get("/reservas", headers={"X-Carrito": "k-" + "0a" * 16}).status_code == 200


@pytest.mark.parametrize("cuerpo", [{}, {"mensaje": ""}, {"texto": "   "}, {"conversacion_id": "c-1"}])
def test_chat_sin_mensaje_se_rechaza_sin_llamar_al_llm(cliente, monkeypatch, cuerpo):
    llamadas = []
    monkeypatch.setattr(conversacion, "interpretar", lambda h: llamadas.append(h))
    assert cliente.post("/chat", json=cuerpo).status_code == 422
    assert llamadas == []


def test_chat_conversacion_id_con_caracteres_raros_se_rechaza(cliente):
    assert cliente.post("/chat", json={"conversacion_id": "c 1/../x", "mensaje": "hola"}).status_code == 422


def test_ninguna_entrada_mala_provoca_un_500(cliente):
    respuestas = [cliente.post("/buscar", json=c) for c in MALAS_BUSQUEDAS.values()]
    respuestas += [cliente.get(f"/stock/valores?{q}") for q in MALOS_VALORES.values()]
    assert all(r.status_code < 500 for r in respuestas)
