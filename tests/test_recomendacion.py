"""Recomendación cuando al comercial le da igual un dato («me da igual el acabado»). Sin LLM."""
from llm.contrato import Cantidad, Especificacion
from llm.respuesta import _nota_recomendacion, responder


def bulto(i, acabado, kg, ancho=1250):
    return {"id": str(i), "grado": "430", "acabado": acabado, "espesor_mm": 0.7, "ancho_mm": ancho, "peso_kg": kg}


# 2B: 3 bultos, 3000 kg · BA: 2 bultos, 9000 kg · 2D: 1 bulto, 500 kg
EXACTOS = [bulto(1, "2B", 1000), bulto(2, "BA", 4000), bulto(3, "2B", 1000),
           bulto(4, "BA", 5000), bulto(5, "2B", 1000), bulto(6, "2D", 500)]


def esp(**k):
    return Especificacion(grado="430", espesor_mm=0.7, indiferentes=["acabado"], **k)


def test_sin_cantidad_recomienda_el_de_mas_bultos():
    nota = _nota_recomendacion({"exactos": EXACTOS}, esp())
    assert nota == ("Te da igual el acabado: te recomiendo 2B, el que más stock tiene (3 bultos, 3000 kg). "
                    "También hay BA (2 bultos, 9000 kg) y 2D (1 bulto, 500 kg).")


def test_pedido_en_kg_o_t_recomienda_el_de_mas_peso():
    for unidad in ("kg", "t"):
        nota = _nota_recomendacion({"exactos": EXACTOS}, esp(cantidad=Cantidad(2, unidad)))
        assert nota.startswith("Te da igual el acabado: te recomiendo BA, el que más peso tiene (9000 kg, 2 bultos).")


def test_pedido_en_bultos_recomienda_por_bultos():
    nota = _nota_recomendacion({"exactos": EXACTOS}, esp(cantidad=Cantidad(2, "bultos")))
    assert "te recomiendo 2B" in nota


def test_empate_en_bultos_lo_decide_el_peso():
    exactos = [bulto(1, "2B", 1000), bulto(2, "BA", 3000)]
    assert "te recomiendo BA" in _nota_recomendacion({"exactos": exactos}, esp())


def test_sin_indiferentes_o_un_solo_valor_no_hay_nota():
    assert _nota_recomendacion({"exactos": EXACTOS}, Especificacion(grado="430", espesor_mm=0.7)) == ""
    solo_2b = [b for b in EXACTOS if b["acabado"] == "2B"]
    assert _nota_recomendacion({"exactos": solo_2b}, esp()) == ""
    assert _nota_recomendacion({"exactos": []}, esp()) == ""


def test_campo_numerico_con_unidades():
    exactos = [bulto(1, "2B", 900, ancho=1000), bulto(2, "2B", 900, ancho=1250), bulto(3, "2B", 900, ancho=1250)]
    nota = _nota_recomendacion({"exactos": exactos}, Especificacion(grado="430", indiferentes=["ancho_mm"]))
    assert nota.startswith("Te da igual el ancho: te recomiendo 1250 mm,")
    assert "1000 mm (1 bulto, 900 kg)" in nota


def test_solo_transformables_cuenta_lo_que_queda_tras_transformar():
    transf = [{"bulto": {"id": str(i), "acabado": "2B", "peso_kg": 800},
               "resultado": {"acabado": a}, "acciones": []} for i, a in enumerate(["BA", "2B", "BA"])]
    nota = _nota_recomendacion({"exactos": [], "transformables": transf}, esp())
    assert nota.startswith("Te da igual el acabado: te recomiendo BA, el que más stock tiene (2 bultos, 1600 kg).")


def test_mas_de_cuatro_valores_resume_el_resto():
    exactos = [bulto(i, a, 100 * (6 - i)) for i, a in enumerate(["2B", "BA", "2D", "NR.1", "1D"])]
    nota = _nota_recomendacion({"exactos": exactos}, esp())
    assert nota.endswith("y 1 más.")


def test_responder_incluye_la_recomendacion_y_no_cambia_el_orden():
    resultado = {"exactos": EXACTOS, "transformables": [], "alternativas": []}
    texto = responder(resultado, esp())
    assert "te recomiendo 2B" in texto
    assert texto.index("1 (") < texto.index("2 (")          # los bultos siguen en el orden del backend
