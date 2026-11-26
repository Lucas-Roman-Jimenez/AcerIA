"""Arreglos de seguridad: CORS limitado, longitud máxima del mensaje e ID de conversación no compartido.

Sin LLM ni base de datos: interpretar() se sustituye para que falle (ErrorLLM) y no se llama al proveedor.
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

from app import config, conversacion  # noqa: E402
from app.main import app  # noqa: E402
from llm import ErrorLLM  # noqa: E402

FRONTEND = "http://127.0.0.1:5173"


@pytest.fixture
def cliente(monkeypatch):
    def sin_llm(historial):
        raise ErrorLLM("sin LLM en el test")

    monkeypatch.setattr(conversacion, "interpretar", sin_llm)
    return TestClient(app)


def preflight(cliente, origen):
    return cliente.options("/compras", headers={
        "Origin": origen, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })


# ---------- 2. CORS ----------

def test_cors_por_defecto_solo_admite_el_frontend_local():
    assert "*" not in config.CORS_ORIGENES
    assert FRONTEND in config.CORS_ORIGENES


def test_cors_permite_el_frontend(cliente):
    r = preflight(cliente, FRONTEND)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == FRONTEND


def test_cors_rechaza_otra_web(cliente):
    """Una web cualquiera abierta en el navegador del comercial no puede vender bultos."""
    r = preflight(cliente, "https://web-maliciosa.example")
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.parametrize("ruta", ["/compras", "/chat", "/buscar"])
@pytest.mark.parametrize("tipo", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"])
def test_post_simple_sin_preflight_no_se_acepta(cliente, ruta, tipo):
    """Un navegador solo salta el preflight de CORS con estos tipos: la API no debe aceptarlos."""
    r = cliente.post(ruta, content='{"bultos": ["1"], "mensaje": "hola"}', headers={"Content-Type": tipo})
    assert r.status_code == 422


# ---------- 3. Longitud máxima ----------

@pytest.mark.parametrize("campo", ["mensaje", "texto"])
def test_mensaje_demasiado_largo_se_rechaza_sin_llamar_al_llm(cliente, monkeypatch, campo):
    llamadas = []
    monkeypatch.setattr(conversacion, "interpretar", lambda h: llamadas.append(h))
    r = cliente.post("/chat", json={"conversacion_id": "largo", campo: "x" * (config.MAX_LONGITUD_MENSAJE + 1)})
    assert r.status_code == 422
    assert llamadas == []


def test_mensaje_en_el_limite_se_acepta(cliente):
    r = cliente.post("/chat", json={"conversacion_id": "limite", "mensaje": "x" * config.MAX_LONGITUD_MENSAJE})
    assert r.status_code == 200


def test_conversacion_id_demasiado_largo_se_rechaza(cliente):
    r = cliente.post("/chat", json={"conversacion_id": "c" * 101, "mensaje": "hola"})
    assert r.status_code == 422


# ---------- 1. ID de conversación ----------

def test_sin_conversacion_id_cada_peticion_es_una_conversacion_nueva(cliente):
    ids = {cliente.post("/chat", json={"mensaje": "hola"}).json()["conversacion_id"] for _ in range(2)}
    assert len(ids) == 2
    assert "demo-1" not in ids


def test_el_frontend_genera_ids_aleatorios_no_basados_en_la_hora():
    app_jsx = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    linea = next(l for l in app_jsx.splitlines() if l.startswith("const nuevoId"))
    assert "getRandomValues" in linea and "Date.now" not in linea


# ---------- 4. Sin endpoint de pruebas ----------

def test_chat_prueba_ya_no_existe(cliente):
    """Las respuestas falsas están en frontend/src/mock.js; la API real no las publica."""
    assert cliente.post("/chat/prueba", json={"mensaje": "2b"}).status_code in (404, 405)


# ---------- 5. Vite solo sirve lo que importa el frontend ----------

def test_vite_no_sirve_todo_el_repositorio():
    config_vite = (Path(__file__).resolve().parents[1] / "frontend" / "vite.config.js").read_text(encoding="utf-8")
    assert "allow: ['..']" not in config_vite
    assert "'../datos'" in config_vite and "'../voz'" in config_vite


# ---------- 6. Errores de /compras con texto fijo ----------

def test_compras_vacia_devuelve_un_mensaje_fijo(cliente):
    r = cliente.post("/compras", json={"bultos": []})
    assert r.status_code == 422
    assert r.json() == {"detail": "Datos no válidos.",                 # tarea 6: formato común de los 422
                        "errores": [{"campo": "bultos", "mensaje": "no puede estar vacío"}]}
