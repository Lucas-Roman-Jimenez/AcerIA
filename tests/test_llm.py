"""Tests del módulo LLM. No necesitan clave ni conexión: usan ClienteFalso."""
import json

import pytest

from llm import ClienteFalso, ErrorLLM, Especificacion, interpretar, pregunta_tras_busqueda, responder
from llm.catalogo import Catalogo

CAT = Catalogo.cargar()
H = [{"rol": "comercial", "texto": "lo que sea"}]


def extraccion(**campos):
    base = {"fuera_de_tema": False, "grado": None, "acabado": None, "formato": None, "espesor_mm": None,
            "ancho_mm": None, "largo_mm": None, "cantidad": None, "uso": None, "opciones": {}, "contradicciones": []}
    base.update(campos)
    return json.dumps(base)


def interp(*respuestas, **kw):
    cli = ClienteFalso(list(respuestas))
    return interpretar(H, cliente=cli, catalogo=CAT, redactar_con_llm=False, **kw), cli


# ---------------------------------------------------------------- interpretar

def test_especificacion_completa():
    r, _ = interp(extraccion(grado="AISI 304", acabado="ba", formato="chapa", espesor_mm=2,
                             cantidad={"valor": 500, "unidad": "kg"}))
    assert r.tipo == "especificacion"
    e = r.especificacion
    assert (e.grado, e.acabado, e.formato, e.espesor_mm) == ("304", "BA", "chapa", 2.0)
    assert e.cantidad.valor == 500 and e.cantidad.unidad == "kg"


def test_json_entre_marcas_de_codigo():
    r, _ = interp("```json\n" + extraccion(grado="304", espesor_mm=2) + "\n```")
    assert r.tipo == "especificacion"


def test_json_mal_formado_reintenta_una_vez():
    r, cli = interp("no es json", extraccion(grado="304", espesor_mm=2))
    assert r.tipo == "especificacion" and len(cli.llamadas) == 2


def test_json_mal_formado_dos_veces_lanza_error():
    with pytest.raises(ErrorLLM):
        interp("nada", "tampoco")


def test_acabado_inventado_se_descarta_y_pregunta():
    r, _ = interp(extraccion(grado="304", acabado="Supermagico", espesor_mm=2))
    assert r.tipo == "pregunta"
    assert r.especificacion.acabado is None
    assert "Supermagico" in r.pregunta and r.especificacion.avisos


def test_termino_ambiguo_queda_en_opciones_y_se_puede_buscar():
    r, _ = interp(extraccion(grado="304", espesor_mm=2, opciones={"acabado": ["BA", "2R", "XX"]}))
    assert r.tipo == "especificacion"
    assert r.especificacion.opciones == {"acabado": ["BA", "2R"]}


def test_opcion_unica_valida_se_fija():
    r, _ = interp(extraccion(grado="304", espesor_mm=2, opciones={"acabado": ["BA", "XX"]}))
    assert r.especificacion.acabado == "BA" and not r.especificacion.opciones


def test_falta_dato_minimo_pregunta_solo_por_uno():
    r, _ = interp(extraccion(grado="304"))
    assert r.tipo == "pregunta" and "espesor" in r.pregunta
    assert r.especificacion.faltan == ["espesor_mm"]


def test_minimos_configurables():
    r, _ = interp(extraccion(grado="304"), minimos=("grado",))
    assert r.tipo == "especificacion"


def test_fuera_de_tema():
    r, _ = interp(extraccion(fuera_de_tema=True))
    assert r.tipo == "pregunta" and "inventario" in r.pregunta


def test_contradiccion():
    r, _ = interp(extraccion(grado="304", contradicciones=[{"campo": "espesor_mm", "valores": [2, 3]}]))
    assert r.tipo == "pregunta" and "2 mm" in r.pregunta and "3 mm" in r.pregunta


def test_combinacion_inexistente_dice_que_existe():
    # 304 BA chapa solo existe hasta 3 mm en los datos de ejemplo
    r, _ = interp(extraccion(grado="304", acabado="BA", formato="chapa", espesor_mm=5))
    assert r.tipo == "pregunta"
    assert "entre 0,4 y 3 mm" in r.pregunta


def test_uso_respaldado_por_catalogo():
    r, _ = interp(extraccion(uso="ambiente marino", espesor_mm=2))
    assert r.tipo == "especificacion"
    assert r.especificacion.opciones["grado"] == ["316", "316L"]
    assert r.especificacion.fuente_uso


def test_uso_no_respaldado_pregunta_grado():
    r, _ = interp(extraccion(uso="para la luna", espesor_mm=2))
    assert r.tipo == "pregunta" and "para la luna" in r.pregunta


def test_faltan_se_rellena_aunque_se_pregunte_por_otra_cosa():
    r, _ = interp(extraccion(grado="304", acabado="Supermagico"))
    assert r.tipo == "pregunta" and "Supermagico" in r.pregunta
    assert r.especificacion.faltan == ["espesor_mm"]


def test_opciones_sin_combinacion_se_recortan():
    # 430 en bobina solo existe en BA en los datos de ejemplo
    r, _ = interp(extraccion(grado="430", formato="bobina", espesor_mm=1, opciones={"acabado": ["BA", "2R"]}))
    assert r.tipo == "especificacion"
    assert r.especificacion.acabado == "BA" and not r.especificacion.opciones
    assert any("2R" in a for a in r.especificacion.avisos)


def test_uso_que_no_cuadra_con_el_grado_avisa_sin_cambiarlo():
    r, _ = interp(extraccion(grado="430", uso="ambiente marino", espesor_mm=1))
    assert r.tipo == "especificacion" and r.especificacion.grado == "430"
    assert any("316" in a for a in r.especificacion.avisos)


def test_opciones_que_no_vienen_del_glosario_preguntan():
    # 2B y BA no son las opciones de ningún término del glosario de ejemplo
    r, _ = interp(extraccion(grado="304", espesor_mm=2, opciones={"acabado": ["2B", "BA"]}))
    assert r.tipo == "pregunta" and "2B o BA" in r.pregunta
    assert r.especificacion.acabado is None and not r.especificacion.opciones


# ---------------------------------------------------------------- modo mixto

def test_redaccion_llm_aceptada_si_no_anade_nada():
    cli = ClienteFalso([extraccion(grado="304"), "Perfecto. ¿Qué espesor necesitas, en milímetros?"])
    r = interpretar(H, cliente=cli, catalogo=CAT)
    assert r.pregunta == "Perfecto. ¿Qué espesor necesitas, en milímetros?"


def test_redaccion_llm_rechazada_si_anade_un_valor():
    cli = ClienteFalso([extraccion(grado="304"), "¿Lo quieres de 2 mm o de 3 mm?"])
    r = interpretar(H, cliente=cli, catalogo=CAT)
    assert r.pregunta == "¿Qué espesor necesitas, en milímetros?"


def test_redaccion_llm_falla_y_usa_plantilla():
    cli = ClienteFalso([extraccion(grado="304"), ErrorLLM("caído")])
    r = interpretar(H, cliente=cli, catalogo=CAT)
    assert r.pregunta == "¿Qué espesor necesitas, en milímetros?"


# ---------------------------------------------------------------- tras buscar

BULTOS = [{"id": "B-1023", "grado": "304", "acabado": "2B", "espesor_mm": 2.0, "ancho_mm": 1250},
          {"id": "B-1024", "grado": "304", "acabado": "BA", "espesor_mm": 2.0, "ancho_mm": 1250}]


def test_pregunta_tras_busqueda_por_el_dato_que_distingue():
    esp = Especificacion(grado="304", espesor_mm=2.0)
    p = pregunta_tras_busqueda(esp, BULTOS, catalogo=CAT, redactar_con_llm=False)
    assert p == "Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"


def test_no_pregunta_si_el_dato_ya_se_dio():
    esp = Especificacion(grado="304", acabado="BA", espesor_mm=2.0)
    assert pregunta_tras_busqueda(esp, BULTOS[1:] * 2, catalogo=CAT, redactar_con_llm=False) is None


def test_no_pregunta_con_un_solo_bulto():
    assert pregunta_tras_busqueda({"grado": "304"}, BULTOS[:1], catalogo=CAT, redactar_con_llm=False) is None


def test_prioriza_campo_con_opciones():
    esp = Especificacion(espesor_mm=2.0, opciones={"grado": ["316", "316L"]})
    bultos = [dict(BULTOS[0], grado="316"), dict(BULTOS[1], grado="316L")]
    p = pregunta_tras_busqueda(esp, bultos, catalogo=CAT, redactar_con_llm=False)
    assert "en 316 y en 316L" in p


# ---------------------------------------------------------------- responder

RES = {"exactos": [{"id": "B-1023", "grado": "304", "acabado": "BA", "espesor_mm": 2.0, "ancho_mm": 1250,
                    "peso_kg": 520, "ubicacion": "Nave 3"}],
       "transformables": [{"id": "B-0877", "acciones": ["Cortar ancho 1500 → 1250 mm"], "merma_kg": 40}],
       "alternativas": []}


def test_sin_stock():
    t = responder({"exactos": [], "transformables": [], "alternativas": []}, usar_llm=False)
    assert "No hay stock" in t


def test_alternativas_marcadas_como_tales():
    t = responder({"exactos": [], "transformables": [], "alternativas": [{"id": "B-0999", "grado": "304"}]},
                  usar_llm=False)
    assert "alternativa" in t and "B-0999" in t


def test_plantilla_incluye_todo():
    t = responder(RES, usar_llm=False)
    assert "B-1023" in t and "B-0877" in t and "merma 40 kg" in t and "Nave 3" in t


def test_un_solo_bulto_no_llama_al_llm():
    cli = ClienteFalso([])
    responder({"exactos": RES["exactos"]}, cliente=cli, catalogo=CAT)
    assert cli.llamadas == []


def test_llm_valido_se_acepta():
    texto = ("Tienes el bulto B-1023, 304 BA de 2 × 1250 mm y 520 kg en Nave 3. "
             "También puedes adaptar el B-0877 cortando el ancho de 1500 a 1250 mm, con 40 kg de merma.")
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT) == texto


def test_llm_que_inventa_un_peso_se_rechaza():
    texto = "Tienes el B-1023 con 900 kg y el B-0877 adaptable."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT) == responder(RES, usar_llm=False)


def test_llm_que_inventa_un_bulto_se_rechaza():
    texto = "Tienes el B-1023, el B-0877 y también el B-5555."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT) == responder(RES, usar_llm=False)


def test_llm_que_omite_un_bulto_se_rechaza():
    texto = "Tienes el B-1023 en Nave 3."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT) == responder(RES, usar_llm=False)


def test_llm_que_inventa_un_grado_se_rechaza():
    texto = "Tienes el B-1023 y el B-0877, ambos en 316."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT) == responder(RES, usar_llm=False)


def test_llm_caido_usa_plantilla():
    assert responder(RES, cliente=ClienteFalso([ErrorLLM("x")]), catalogo=CAT) == responder(RES, usar_llm=False)
