import json
from pathlib import Path

import pytest

from llm import ClienteFalso, ErrorLLM, Especificacion, interpretar, pregunta_tras_busqueda
from llm.catalogo import Catalogo


HISTORIAL = [{"rol": "comercial", "texto": "Buenas, busco una chapa."}]
CATALOGO = Catalogo.cargar(Path(__file__).resolve().parents[1] / "datos_ejemplo")
BULTOS = [
    {"id": "B-1023", "grado": "304", "acabado": "2B", "espesor_mm": 2, "ancho_mm": 1250},
    {"id": "B-1024", "grado": "304", "acabado": "BA", "espesor_mm": 2, "ancho_mm": 1500},
]


def test_elige_en_la_extraccion_que_dato_pedir_primero():
    cliente = ClienteFalso(['{"formato":"chapa","campo_aclaracion":"espesor_mm"}'])
    resultado = interpretar(HISTORIAL, cliente=cliente, catalogo=CATALOGO, redactar_con_llm=False)

    assert resultado.pregunta == "¿Qué espesor necesitas, en milímetros?"
    assert resultado.especificacion.faltan == ["grado", "espesor_mm"]
    assert len(cliente.llamadas) == 1
    assert HISTORIAL[0]["texto"] in cliente.llamadas[0][1]
    assert "grado, espesor_mm" in cliente.llamadas[0][0]


@pytest.mark.parametrize("sugerencia", ["formato", "ancho_mm", ["espesor_mm"], None])
def test_descarta_sugerencias_que_no_son_campos_minimos_pendientes(sugerencia):
    cliente = ClienteFalso([json.dumps({"formato": "chapa", "campo_aclaracion": sugerencia})])
    resultado = interpretar(HISTORIAL, cliente=cliente, catalogo=CATALOGO, redactar_con_llm=False)
    assert resultado.pregunta.startswith("¿Qué grado necesitas?")


def test_una_propuesta_del_modelo_no_pide_aclaracion_si_el_pedido_ya_es_valido():
    cliente = ClienteFalso(['{"grado":"304","espesor_mm":2,"campo_aclaracion":"ancho_mm"}'])
    resultado = interpretar(HISTORIAL, cliente=cliente, catalogo=CATALOGO)
    assert resultado.tipo == "especificacion"
    assert resultado.pregunta is None


# Después de buscar, la pregunta NO pasa por el LLM (decisión de Nacho, Parte 4): es la pregunta de la
# demo (RF-07) y tiene que salir siempre igual y en ~1 s. Se pregunta por el primer campo que distingue
# el stock, en el orden de ORDEN_DISTINGUIR (acabado, grado, formato, medidas).

def test_post_busqueda_pregunta_por_el_primer_campo_que_distingue_sin_llm(monkeypatch):
    import llm.interprete as interprete

    def sin_llm():
        raise AssertionError("pregunta_tras_busqueda no debe llamar al LLM")
    monkeypatch.setattr(interprete, "_cliente_defecto", sin_llm)
    esp = Especificacion(grado="304", espesor_mm=2)
    pregunta = pregunta_tras_busqueda(esp, BULTOS, historial=HISTORIAL)
    assert pregunta == "Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"


def test_post_busqueda_no_repite_la_misma_pregunta():
    esp = Especificacion(grado="304", espesor_mm=2)
    pregunta = "Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"
    historial = [
        *HISTORIAL,
        {"rol": "asistente", "texto": pregunta},
        {"rol": "comercial", "texto": "Enséñame las opciones."},
    ]
    assert pregunta_tras_busqueda(esp, BULTOS, historial=historial) is None


def test_post_busqueda_es_determinista():
    esp = Especificacion(grado="304", espesor_mm=2)
    preguntas = {pregunta_tras_busqueda(esp, BULTOS, historial=HISTORIAL) for _ in range(5)}
    assert preguntas == {"Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"}
