"""Tests del módulo LLM. No necesitan clave ni conexión: usan ClienteFalso."""
import json
from pathlib import Path

import pytest

from llm import ClienteFalso, ErrorLLM, Especificacion, interpretar, pregunta_tras_busqueda, responder
from llm.catalogo import Catalogo

CAT = Catalogo.cargar(Path(__file__).resolve().parents[1] / "datos_ejemplo")
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
    r = interpretar(H, cliente=cli, catalogo=CAT, redactar_con_llm=True)
    assert r.pregunta == "Perfecto. ¿Qué espesor necesitas, en milímetros?"


def test_redaccion_llm_rechazada_si_anade_un_valor():
    cli = ClienteFalso([extraccion(grado="304"), "¿Lo quieres de 2 mm o de 3 mm?"])
    r = interpretar(H, cliente=cli, catalogo=CAT, redactar_con_llm=True)
    assert r.pregunta == "¿Qué espesor necesitas, en milímetros?"


def test_redaccion_llm_falla_y_usa_plantilla():
    cli = ClienteFalso([extraccion(grado="304"), ErrorLLM("caído")])
    r = interpretar(H, cliente=cli, catalogo=CAT, redactar_con_llm=True)
    assert r.pregunta == "¿Qué espesor necesitas, en milímetros?"


def test_redaccion_llm_rechazada_si_pierde_una_opcion():
    cli = ClienteFalso([extraccion(espesor_mm=2), "¿Qué grado necesitas, 304 o 316?"])
    r = interpretar(H, cliente=cli, catalogo=CAT, redactar_con_llm=True)
    assert r.pregunta == "¿Qué grado necesitas? Por ejemplo: 304, 316L y 430."   # los habituales (GRADOS_EJEMPLO)


def test_redaccion_llm_rechazada_si_saluda():
    cli = ClienteFalso([extraccion(grado="304"), "Hola, ¿qué espesor necesitas, en milímetros?"])
    r = interpretar(H, cliente=cli, catalogo=CAT, redactar_con_llm=True)
    assert r.pregunta == "¿Qué espesor necesitas, en milímetros?"


# ---------------------------------------------------------------- tras buscar

BULTOS = [{"id": "B-1023", "grado": "304", "acabado": "2B", "espesor_mm": 2.0, "ancho_mm": 1250},
          {"id": "B-1024", "grado": "304", "acabado": "BA", "espesor_mm": 2.0, "ancho_mm": 1250}]


def test_pregunta_tras_busqueda_por_el_dato_que_distingue():
    esp = Especificacion(grado="304", espesor_mm=2.0)
    p = pregunta_tras_busqueda(esp, BULTOS)
    assert p == "Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"


def test_no_pregunta_si_el_dato_ya_se_dio():
    esp = Especificacion(grado="304", acabado="BA", espesor_mm=2.0)
    assert pregunta_tras_busqueda(esp, BULTOS[1:] * 2) is None


def test_no_pregunta_con_un_solo_bulto():
    assert pregunta_tras_busqueda({"grado": "304"}, BULTOS[:1]) is None


def test_prioriza_campo_con_opciones():
    esp = Especificacion(espesor_mm=2.0, opciones={"grado": ["316", "316L"]})
    bultos = [dict(BULTOS[0], grado="316"), dict(BULTOS[1], grado="316L")]
    p = pregunta_tras_busqueda(esp, bultos)
    assert "en 316 y en 316L" in p


def test_pregunta_tras_busqueda_no_usa_el_llm(monkeypatch):
    import llm.interprete as interprete

    def sin_llm():
        raise AssertionError("pregunta_tras_busqueda no debe llamar al LLM")
    monkeypatch.setattr(interprete, "_cliente_defecto", sin_llm)
    esp = Especificacion(grado="304", espesor_mm=2.0)
    assert pregunta_tras_busqueda(esp, BULTOS) == "Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"


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
    responder({"exactos": RES["exactos"]}, cliente=cli, catalogo=CAT, usar_llm=True)
    assert cli.llamadas == []


def test_llm_valido_se_acepta():
    texto = ("Tienes el bulto B-1023, 304 BA de 2 × 1250 mm y 520 kg en Nave 3. "
             "También puedes adaptar el B-0877 cortando el ancho de 1500 a 1250 mm, con 40 kg de merma.")
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT, usar_llm=True) == texto


def test_llm_que_inventa_un_peso_se_rechaza():
    texto = "Tienes el B-1023 con 900 kg y el B-0877 adaptable."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT, usar_llm=True) == responder(RES, usar_llm=False)


def test_llm_que_inventa_un_bulto_se_rechaza():
    texto = "Tienes el B-1023, el B-0877 y también el B-5555."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT, usar_llm=True) == responder(RES, usar_llm=False)


def test_llm_que_omite_un_bulto_se_rechaza():
    texto = "Tienes el B-1023 en Nave 3."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT, usar_llm=True) == responder(RES, usar_llm=False)


def test_llm_que_inventa_un_grado_se_rechaza():
    texto = "Tienes el B-1023 y el B-0877, ambos en 316."
    assert responder(RES, cliente=ClienteFalso([texto]), catalogo=CAT, usar_llm=True) == responder(RES, usar_llm=False)


def test_llm_caido_usa_plantilla():
    assert responder(RES, cliente=ClienteFalso([ErrorLLM("x")]), catalogo=CAT, usar_llm=True) == responder(RES, usar_llm=False)


# ---------------------------------------------------------------- escenarios de la batería

# P1: «me da igual» y no repetir preguntas
def test_indiferente_no_se_pregunta_tras_buscar():
    esp = Especificacion(grado="304", espesor_mm=2.0, indiferentes=["acabado"])
    assert pregunta_tras_busqueda(esp, BULTOS) is None


def test_indiferente_no_cuenta_como_falta_y_quita_opciones():
    r, _ = interp(extraccion(espesor_mm=2, indiferentes=["grado", "acabado"], opciones={"acabado": ["BA", "2R"]}))
    assert r.tipo == "especificacion"
    assert r.especificacion.indiferentes == ["grado", "acabado"] and r.especificacion.faltan == []
    assert r.especificacion.opciones == {}


def test_indiferente_invalido_se_ignora():
    r, _ = interp(extraccion(grado="304", espesor_mm=2, indiferentes=["grado", "color", 7]))
    assert r.especificacion.indiferentes == []


def test_no_repite_la_misma_pregunta_tras_buscar():
    esp = Especificacion(grado="304", espesor_mm=2.0)
    pregunta = "Tengo 304 de 2 mm en 2B y en BA. ¿Cuál prefieres?"
    historial = [{"rol": "comercial", "texto": "304 de 2 mm"}, {"rol": "asistente", "texto": pregunta},
                 {"rol": "comercial", "texto": "el brillante"}]
    assert pregunta_tras_busqueda(esp, BULTOS, historial=historial) is None
    assert pregunta_tras_busqueda(esp, BULTOS, historial=historial[:1]) == pregunta


# P2 y P6: textos veraces
def test_combinacion_imposible_no_dice_que_el_grado_no_existe():
    # 430 existe en el catálogo, pero no en 2B de 2 mm
    r, _ = interp(extraccion(grado="430", acabado="2B", espesor_mm=2))
    assert r.tipo == "pregunta"
    assert "no existe 430 2B de 2 mm" in r.pregunta
    assert "no hay grado 430" not in r.pregunta


def test_dos_productos_de_uno_en_uno():
    r, _ = interp(extraccion(espesor_mm=2, contradicciones=[{"campo": "grado", "valores": ["304", "316L"]}]))
    assert r.tipo == "pregunta" and "uno en uno" in r.pregunta and "304 y 316L" in r.pregunta


# P3: cantidad
EXACTO = {"id": "B-2001", "grado": "316L", "acabado": "2B", "espesor_mm": 2.0, "peso_kg": 610}


def test_cantidad_en_toneladas_que_no_llega():
    esp = {"grado": "316L", "cantidad": {"valor": 2, "unidad": "t"}}
    texto = responder({"exactos": [EXACTO]}, esp, usar_llm=False)
    assert "Pides 2 t y lo que cumple suma 610 kg." in texto


def test_cantidad_en_bultos_que_no_llega():
    esp = {"grado": "316L", "cantidad": {"valor": 3, "unidad": "bultos"}}
    assert "Pides 3 bultos y hay 1 que cumple." in responder({"exactos": [EXACTO]}, esp, usar_llm=False)
    dos = [EXACTO, dict(EXACTO, id="B-2002")]
    assert "Pides 3 bultos y hay 2 que cumplen." in responder({"exactos": dos}, esp, usar_llm=False)


def test_cantidad_cubierta_no_anade_nada():
    esp = {"grado": "316L", "cantidad": {"valor": 500, "unidad": "kg"}}
    assert "Pides" not in responder({"exactos": [EXACTO]}, esp, usar_llm=False)


# P4: intenciones con respuesta fija (sin pasar por el LLM)
@pytest.mark.parametrize("intencion, esperado", [
    ("saludo", "¡Hola!"),
    ("agradecimiento", "De nada"),
    ("reserva", "añádelo al carrito"),
    ("plazo", "plazos de entrega"),
    ("fuera_de_tema", "inventario"),
])
def test_intenciones_con_respuesta_fija(intencion, esperado):
    r, cli = interp(extraccion(intencion=intencion))
    assert r.tipo == "pregunta" and esperado in r.pregunta
    assert len(cli.llamadas) == 1  # solo la extracción


def test_precio_ofrece_buscar_lo_entendido_y_conserva_la_especificacion():
    r, _ = interp(extraccion(intencion="precio", grado="304", acabado="BA", espesor_mm=2))
    assert "No tengo información de precios" in r.pregunta and "304 BA de 2 mm" in r.pregunta
    assert r.especificacion.grado == "304"


def test_consulta_tecnica_solo_cita_usos_del_catalogo():
    r, _ = interp(extraccion(intencion="consulta_tecnica"))
    assert "No puedo comparar propiedades" in r.pregunta
    assert "(por ejemplo, industria alimentaria o ambiente marino)" in r.pregunta   # preferidos primero


def test_consulta_tecnica_con_uso_del_catalogo_cita_los_grados():
    # «¿Qué acero me recomiendas para ambiente marino?»: no se le vuelve a pedir el uso.
    r, cli = interp(extraccion(intencion="consulta_tecnica", uso="ambiente marino"))
    assert r.tipo == "pregunta"
    assert r.pregunta.startswith("Para ambiente marino, el catálogo indica 316 y 316L (fuente: ")
    assert "No puedo comparar" not in r.pregunta and "Si me dices para qué es" not in r.pregunta
    assert r.pregunta.endswith("¿Qué espesor necesitas, en milímetros?")
    assert r.especificacion.opciones["grado"] == ["316", "316L"] and r.especificacion.uso == "ambiente marino"
    assert len(cli.llamadas) == 1                 # solo la extracción


def test_consulta_tecnica_con_uso_y_espesor_busca():
    r, _ = interp(extraccion(intencion="consulta_tecnica", uso="ambiente marino", espesor_mm=2))
    assert r.tipo == "especificacion" and r.especificacion.espesor_mm == 2.0


def test_consulta_tecnica_con_uso_desconocido_lo_dice():
    r, _ = interp(extraccion(intencion="consulta_tecnica", uso="terreno montañoso"))
    assert r.tipo == "pregunta"
    assert r.pregunta.startswith("El catálogo no indica qué grado es adecuado para «terreno montañoso»")
    assert "Si me dices para qué es" not in r.pregunta


def test_intencion_desconocida_se_trata_como_pedido():
    r, _ = interp(extraccion(intencion="inventada", grado="304", espesor_mm=2))
    assert r.tipo == "especificacion"


# P5: mensaje vacío
def test_mensaje_vacio_no_llama_al_llm():
    cli = ClienteFalso([])  # lanzaría ErrorLLM si se le llamara
    r = interpretar([{"rol": "comercial", "texto": "   "}], cliente=cli, catalogo=CAT)
    assert r.tipo == "pregunta" and r.pregunta == "¿Qué material necesitas?"
    assert cli.llamadas == [] and r.especificacion.faltan == ["grado", "espesor_mm"]


def test_mensaje_vacio_con_contexto_usa_el_resto_del_historial():
    cli = ClienteFalso([extraccion(grado="304", espesor_mm=2)])
    h = [{"rol": "comercial", "texto": "304 de 2 mm"}, {"rol": "comercial", "texto": ""}]
    r = interpretar(h, cliente=cli, catalogo=CAT, redactar_con_llm=False)
    assert r.tipo == "especificacion" and "Comercial: \n" not in cli.llamadas[0][1]


# ---------------------------------------------------------------- parte 5: respuesta

def test_varios_bultos_por_defecto_no_llama_al_llm():
    cli = ClienteFalso([])
    t = responder(RES, cliente=cli, catalogo=CAT)
    assert cli.llamadas == [] and t == responder(RES, usar_llm=False)


def test_cita_la_fuente_del_uso():
    esp = {"uso": "ambiente marino", "fuente_uso": "Catálogo p. 12", "opciones": {"grado": ["316", "316L"]}}
    t = responder({"exactos": [EXACTO]}, esp, catalogo=CAT)
    assert "Para ambiente marino, el catálogo indica 316 y 316L (fuente: Catálogo p. 12)." in t


def test_sin_uso_no_cita_nada():
    assert "catálogo indica" not in responder({"exactos": [EXACTO]}, {"grado": "316L"}, catalogo=CAT)


def test_criterio_de_orden_si_lo_manda_el_backend():
    res = dict(RES, criterio="sin transformar primero; después, menor merma y menos operaciones")
    assert "Orden: sin transformar primero; después, menor merma y menos operaciones." in responder(res)
    assert "Orden:" not in responder(RES)


def test_transformable_con_resultado_dice_como_queda():
    t = {"id": "B-1030", "acciones": ["Cortar ancho 1500 → 1250 mm"], "merma_kg": 150,
         "resultado": {"grado": "304", "acabado": "2B", "espesor_mm": 3.0, "ancho_mm": 1250}}
    texto = responder({"exactos": [], "transformables": [t]})
    assert "B-1030 (Cortar ancho 1500 → 1250 mm; merma 150 kg; queda 304 2B, 3 × 1250 mm)" in texto


def test_por_defecto_una_sola_llamada_al_llm():
    cli = ClienteFalso([extraccion(grado="304")])  # sin segunda respuesta: fallaría si se redactara
    r = interpretar(H, cliente=cli, catalogo=CAT)
    assert r.pregunta == "¿Qué espesor necesitas, en milímetros?" and len(cli.llamadas) == 1


# ---------------------------------------------------------------- integración con el backend de Alonso

TRANSF_BACKEND = {
    "bulto": {"id": "334", "grado": "304L/304", "acabado": "2B", "formato": "bobina",
              "espesor_mm": 2.0, "ancho_mm": 1500, "largo_mm": None, "peso_kg": 745},
    "acciones": ["Cortar bobina 2 × 1500 mm a chapa 2 × 1250 × 2500 mm"],
    "resultado": {"formato": "chapa", "acabado": "2B", "espesor_mm": 2.0,
                  "ancho_mm": 1250, "largo_mm": 2500, "piezas": 12},
    "merma_kg": 152.5, "merma_pct": 20.5, "num_operaciones": 1, "merma_estimada": True, "avisos": [],
}


def test_transformable_con_formato_del_backend():
    texto = responder({"exactos": [], "transformables": [TRANSF_BACKEND]})
    assert ("334 (bobina 304L/304 2B, 2 × 1500 mm, 745 kg; Cortar bobina 2 × 1500 mm a chapa 2 × 1250 × 2500 mm; "
            "merma 152,5 kg (20,5 %); queda chapa 2B, 2 × 1250 × 2500 mm, 12 piezas)") in texto


def test_criterio_orden_del_backend():
    res = {"exactos": [EXACTO, dict(EXACTO, id="B-2002")], "criterio_orden": "exactos > % de merma > nº de operaciones"}
    assert "Orden: exactos > % de merma > nº de operaciones." in responder(res)


def test_llm_valida_ids_del_formato_del_backend():
    res = {"exactos": [EXACTO], "transformables": [TRANSF_BACKEND]}
    texto = "Tienes el B-2001 (316L 2B) y puedes cortar el 334 con 152,5 kg de merma."
    assert responder(res, cliente=ClienteFalso([texto]), catalogo=CAT, usar_llm=True) == texto
    sin_334 = "Tienes el B-2001 (316L 2B)."
    assert responder(res, cliente=ClienteFalso([sin_334]), catalogo=CAT, usar_llm=True) == responder(res)


# ---------------------------------------------------------------- inventario real

CAT_REAL = Catalogo(
    {"grados": ["304", "304L", "316L", "316TI", "409L", "430"],
     "acabados": ["2B", "BA", "NR.1", "N4-G-180", "SCOTCH BRITE"],
     "formatos": ["chapa", "bobina", "fleje"],
     "productos": [{"grado": "409L", "acabado": "NR.1", "formato": "fleje", "espesor_mm": [6, 6]},
                   {"grado": "304", "acabado": "N4-G-180", "formato": "chapa", "espesor_mm": [1, 1]}],
     "usos": []},
    {"terminos": [{"termino": "satinado", "campo": "acabado", "valores": ["4"]}]})


def test_normalizar_no_se_come_la_n_de_los_acabados_reales():
    assert CAT_REAL.normalizar("acabado", "NR.1") == "NR.1"
    assert CAT_REAL.normalizar("acabado", "n4-g-180") == "N4-G-180"
    assert CAT.normalizar("acabado", "n.º 4") == "4"   # el prefijo se sigue quitando si va antes de un número
    assert CAT.normalizar("grado", "AISI-304") == "304"


def test_sugiere_valores_parecidos():
    r = interpretar(H, cliente=ClienteFalso([extraccion(grado="316", espesor_mm=2)]), catalogo=CAT_REAL)
    assert "316L y 316TI" in r.pregunta


def test_termino_sin_ningun_valor_en_el_catalogo_pregunta():
    r = interpretar(H, cliente=ClienteFalso([extraccion(grado="304", espesor_mm=1, opciones={"acabado": ["4"]})]),
                    catalogo=CAT_REAL)
    assert r.tipo == "pregunta" and "«satinado»" in r.pregunta


def test_pregunta_por_formato_bien_redactada():
    esp = Especificacion(grado="304", acabado="2B", espesor_mm=2.0)
    bultos = [dict(BULTOS[0], formato=f) for f in ("bobina", "chapa", "fleje")]
    assert pregunta_tras_busqueda(esp, bultos) == "Tengo 304 2B de 2 mm en bobina, chapa y fleje. ¿Qué formato prefieres?"


def test_como_mucho_cinco_bultos_en_el_texto():
    muchos = [dict(EXACTO, id=f"B-{i:04d}") for i in range(271)]
    texto = responder({"exactos": muchos})
    assert texto.startswith("Hay 271 bultos que cumplen la petición: B-0000")
    assert "B-0004" in texto and "B-0005" not in texto and "y 266 más (ver las tarjetas)" in texto


def test_sin_propuestas_no_dice_el_criterio():
    sin_stock = {"exactos": [], "transformables": [], "criterio_orden": "exactos > % de merma"}
    assert "Orden:" not in responder(sin_stock)


# ---------------------------------------------------------------- parte 2: extracción

def test_la_extraccion_pide_salida_estructurada():
    from llm import prompts
    _, cli = interp(extraccion(grado="304", espesor_mm=2))
    assert cli.esquemas[0] is prompts.ESQUEMA_EXTRACCION


def test_json_con_tipos_raros_no_rompe():
    raro = extraccion(grado=["304"], acabado={"x": 1}, formato=True, opciones=["BA"], contradicciones="no",
                      indiferentes="acabado", uso=7, espesor_mm="dos", intencion=["pedido"])
    r, _ = interp(raro)
    assert r.tipo == "pregunta" and r.especificacion.grado == "304" and r.especificacion.faltan == ["espesor_mm"]
    assert r.especificacion.acabado is None and r.especificacion.formato is None


def test_contradiccion_con_valores_en_texto():
    r, _ = interp(extraccion(grado="304", contradicciones=[{"campo": "espesor_mm", "valores": ["2", "3"]}]))
    assert "2 mm y 3 mm" in r.pregunta


class _RespuestaFalsa:
    def __init__(self, stop_reason, texto=""):
        from types import SimpleNamespace
        self.stop_reason = stop_reason
        self.content = [SimpleNamespace(type="text", text=texto)]


def _anthropic_falso(respuesta):
    from types import SimpleNamespace
    from llm.proveedores import ClienteAnthropic
    llamadas = []
    cli = ClienteAnthropic.__new__(ClienteAnthropic)
    cli.modelo = "modelo-de-prueba"
    cli._cli = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: llamadas.append(kw) or respuesta))
    return cli, llamadas


def test_anthropic_envia_el_esquema_con_esfuerzo_bajo():
    cli, llamadas = _anthropic_falso(_RespuestaFalsa("end_turn", "{}"))
    assert cli.completar("s", "u", json=True, esquema={"type": "object"}) == "{}"
    assert llamadas[0]["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}},
                                            "effort": "low"}


@pytest.mark.parametrize("motivo", ["refusal", "max_tokens"])
def test_anthropic_respuesta_incompleta_lanza_error(motivo):
    cli, _ = _anthropic_falso(_RespuestaFalsa(motivo, "{"))
    with pytest.raises(ErrorLLM):
        cli.completar("s", "u", esquema={"type": "object"})


def test_solo_medidas_se_describe_como_material():
    r, _ = interp(extraccion(intencion="precio", espesor_mm=2))
    assert "¿Quieres que busque material de 2 mm?" in r.pregunta
    esp = Especificacion(espesor_mm=2.0, indiferentes=["grado"])
    bultos = [dict(BULTOS[0], acabado=a) for a in ("2B", "BA")]
    assert pregunta_tras_busqueda(esp, bultos) == "Tengo material de 2 mm en 2B y en BA. ¿Cuál prefieres?"


def test_acciones_del_motor_de_lucas_como_objetos():
    t = {"bulto_id": "334", "bulto": TRANSF_BACKEND["bulto"],
         "acciones": [{"regla": "R-CORTE", "descripcion": "Cortar bobina a chapa 2 × 1250 × 2500 mm",
                       "parametros": {}, "merma_kg": 152.5, "orden": 1}],
         "merma_kg": 152.5, "merma_pct": 20.5, "num_operaciones": 1}
    texto = responder({"exactos": [], "transformables": [t]})
    assert "334 (" in texto and "Cortar bobina a chapa 2 × 1250 × 2500 mm; merma 152,5 kg (20,5 %)" in texto
