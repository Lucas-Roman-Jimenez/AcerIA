"""Tests de /chat (backend/app/conversacion.py): módulo LLM + buscador + motor de reglas.

Sin clave ni conexión: el LLM se sustituye por ClienteFalso. Usan la BD real (se crea con crear_db()).
Ejecutar desde la raíz del repositorio:  python -m pytest -q
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
pytest.importorskip("pandas")
pytest.importorskip("openpyxl")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import llm.interprete as interprete  # noqa: E402
from llm import ClienteFalso, ErrorLLM  # noqa: E402
from llm.catalogo import Catalogo  # noqa: E402


def extraccion(**campos):
    base = {"intencion": "pedido", "grado": None, "acabado": None, "formato": None, "espesor_mm": None,
            "ancho_mm": None, "largo_mm": None, "cantidad": None, "uso": None,
            "opciones": {"grado": [], "acabado": [], "formato": []}, "contradicciones": [], "indiferentes": []}
    base.update(campos)
    return json.dumps(base)


# Catálogo mínimo con valores que existen en el inventario real (el real lo prepara Lucas).
CATALOGO = Catalogo({
    "grados": ["304", "304L", "316L", "430"], "acabados": ["2B", "BA"], "formatos": ["chapa", "bobina", "fleje"],
    "productos": [{"grado": g, "acabado": a, "formato": f, "espesor_mm": [0.3, 10], "ancho_mm": [100, 2000]}
                  for g in ("304", "304L", "316L", "430") for a in ("2B", "BA") for f in ("chapa", "bobina", "fleje")],
    "usos": []}, {"terminos": []})


@pytest.fixture(scope="module")
def api():
    from app.db import crear_db
    crear_db()
    from app import conversacion
    from app.main import app
    return TestClient(app), conversacion


@pytest.fixture
def llm_falso(monkeypatch):
    def preparar(*respuestas):
        monkeypatch.setattr(interprete, "_cliente", ClienteFalso(list(respuestas)))
        monkeypatch.setattr(interprete, "_catalogo", CATALOGO)
    return preparar


def chat(cliente, mensaje, conv="t"):
    r = cliente.post("/chat", json={"conversacion_id": conv, "mensaje": mensaje})
    assert r.status_code == 200
    return r.json()


def test_exactos_reales_con_formato_de_la_api(api, llm_falso):
    cliente, _ = api
    llm_falso(extraccion(grado="304", acabado="2B", formato="chapa", espesor_mm=2, ancho_mm=1250, largo_mm=2500))
    r = chat(cliente, "chapa 304 2B de 2 x 1250 x 2500", conv="exactos")
    assert r["estado"] == "resultados" and r["tipo"] == "respuesta" and r["error"] is None
    assert r["exactos"] and all(b["acabado"] == "2B" and b["espesor_mm"] == 2 for b in r["exactos"])
    assert r["texto"].startswith("Hay ") and r["especificacion"]["grado"] == "304"
    assert r["criterio_orden"]


def test_transformables_por_chat_con_bulto_de_origen_y_ordenados(api, llm_falso):
    cliente, _ = api
    llm_falso(extraccion(grado="304", acabado="2B", formato="chapa", espesor_mm=2, ancho_mm=1000, largo_mm=2000))
    r = chat(cliente, "chapa 304 2B de 2 x 1000 x 2000", conv="transformables")
    ts = r["transformables"]
    assert ts, "el inventario real tiene bultos 304 2B que se pueden cortar a 2 × 1000 × 2000"
    assert all(t["bulto"]["id"] == t["bulto_id"] == t["id"] for t in ts)       # compatibilizar() de Alonso
    claves = [(t["merma_pct"], t["num_operaciones"]) for t in ts]
    assert claves == sorted(claves)                                          # RF-14


def test_pregunta_antes_de_buscar(api, llm_falso):
    cliente, _ = api
    llm_falso(extraccion(grado="304"))
    r = chat(cliente, "304", conv="pregunta")
    assert r["estado"] == "pregunta" and r["tipo"] == "pregunta" and r["pregunta"] == r["texto"]
    assert r["especificacion"]["faltan"] == ["espesor_mm"]


@pytest.mark.parametrize("acabado,opciones", [(None, {"acabado": ["BA", "2R"]}), ("BA", {})])
def test_cl08_aclara_brillante_y_acepta_un_acabado_explicito(api, llm_falso, monkeypatch, acabado, opciones):
    from evaluar_api import CASOS, evaluar

    cliente, conversacion = api
    caso = next(c for c in json.loads(CASOS.read_text(encoding="utf-8")) if c["id"] == "CL-08")
    llm_falso(
        extraccion(grado="304", formato="chapa", espesor_mm=2, acabado=acabado, opciones=opciones),
        extraccion(grado="304", formato="chapa", espesor_mm=2, acabado="BA"),
    )
    monkeypatch.setattr(interprete, "_catalogo", Catalogo.cargar())
    consultadas = []
    buscar = conversacion.buscar_bultos

    def buscar_con_registro(objetivo):
        consultadas.append(objetivo)
        return buscar(objetivo)

    monkeypatch.setattr(conversacion, "buscar_bultos", buscar_con_registro)
    respuestas = []

    def enviar(ruta, datos):
        assert ruta == "/chat"
        respuestas.append(datos["conversacion_id"])
        respuesta = chat(cliente, datos["mensaje"], conv=datos["conversacion_id"])
        assert respuesta["pregunta"] == "Cuando dices «brillante», ¿qué acabado concreto necesitas?"
        assert respuesta["especificacion"]["acabado"] is None
        assert "acabado" not in respuesta["especificacion"]["opciones"]
        return respuesta

    informe = evaluar([caso], enviar)
    assert informe["interpretacion"]["aciertos"] == 1
    assert consultadas == []
    aclarada = chat(cliente, "BA", conv=respuestas[0])
    assert aclarada["especificacion"]["acabado"] == "BA"
    assert consultadas[0]["acabados"] == ["BA"]


def test_el_historial_se_guarda_por_conversacion(api, llm_falso):
    cliente, conversacion = api
    llm_falso(extraccion(grado="304"), extraccion(grado="304", espesor_mm=2, acabado="2B"))
    chat(cliente, "304", conv="historial")
    chat(cliente, "de 2 mm en 2B", conv="historial")
    roles = [m["rol"] for m in conversacion.conversaciones["historial"]]
    assert roles == ["comercial", "asistente", "comercial", "asistente"]
    usuario = interprete._cliente.llamadas[1][1]
    assert "Comercial: 304" in usuario and "Comercial: de 2 mm en 2B" in usuario


def test_error_del_llm_deja_reintentar(api, llm_falso):
    cliente, conversacion = api
    llm_falso(ErrorLLM("caído"))
    r = chat(cliente, "304 de 2 mm", conv="error")
    assert r["estado"] == "error" and r["tipo"] == "error" and r["error"]
    assert conversacion.conversaciones["error"] == []                 # el mensaje fallido no queda


def test_formato_del_frontend_con_texto(api, llm_falso):
    cliente, _ = api
    llm_falso(extraccion(intencion="saludo"))
    r = cliente.post("/chat", json={"conversacion_id": "front", "texto": "hola"}).json()
    assert r["tipo"] == "pregunta" and r["texto"].startswith("¡Hola!")


def test_buscar_devuelve_transformables_del_motor(api):
    cliente, _ = api
    espec = {"grado": "304", "acabado": "2B", "formato": "chapa", "espesor_mm": 2, "ancho_mm": 1250, "largo_mm": 2500}
    r = cliente.post("/buscar", json=espec).json()
    t334 = [t for t in r["transformables"] if t["bulto_id"] == "334"]
    assert r["estado"] == "resultados" and t334
    assert (t334[0]["merma_kg"], t334[0]["merma_pct"], t334[0]["num_operaciones"]) == (152.5, 20.5, 1)
