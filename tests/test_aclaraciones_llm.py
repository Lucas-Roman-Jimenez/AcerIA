import json

import pytest

from llm import ClienteFalso, ErrorLLM, Especificacion, interpretar, pregunta_tras_busqueda
from llm.catalogo import Catalogo


HISTORIAL = [{"rol": "comercial", "texto": "Buenas, busco una chapa."}]
CATALOGO = Catalogo.cargar()
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


def test_post_busqueda_elige_entre_los_campos_que_distinguen_el_stock():
    cliente = ClienteFalso(['{"campo":"ancho_mm"}'])
    esp = Especificacion(grado="304", espesor_mm=2)
    pregunta = pregunta_tras_busqueda(esp, BULTOS, historial=HISTORIAL, cliente=cliente)

    assert pregunta == "Tengo 304 de 2 mm con ancho de 1250 y 1500 mm. ¿Cuál prefieres?"
    contexto = json.loads(cliente.llamadas[0][1])
    assert contexto["opciones_por_campo"] == {"acabado": ["2B", "BA"], "ancho_mm": [1250, 1500]}
    assert HISTORIAL[0]["texto"] in contexto["conversacion"]


def test_post_busqueda_no_repite_una_pregunta_elegida_por_el_llm():
    esp = Especificacion(grado="304", espesor_mm=2)
    pregunta = "Tengo 304 de 2 mm con ancho de 1250 y 1500 mm. ¿Cuál prefieres?"
    historial = [
        *HISTORIAL,
        {"rol": "asistente", "texto": pregunta},
        {"rol": "comercial", "texto": "Enséñame las opciones."},
    ]
    cliente = ClienteFalso([])
    assert pregunta_tras_busqueda(esp, BULTOS, historial=historial, cliente=cliente) is None
    assert not cliente.llamadas


@pytest.mark.parametrize("respuesta", ['{"campo":"largo_mm"}', "Inválida", ErrorLLM("proveedor caído")])
def test_post_busqueda_usa_una_pregunta_valida_si_falla_la_eleccion(respuesta):
    cliente = ClienteFalso([respuesta])
    esp = Especificacion(grado="304", espesor_mm=2)
    pregunta = pregunta_tras_busqueda(esp, BULTOS, historial=HISTORIAL, cliente=cliente)
    assert pregunta == "Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"
