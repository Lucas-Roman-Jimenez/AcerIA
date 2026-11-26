"""Textos de las plantillas con el catálogo real (datos/). Sin LLM."""
from pathlib import Path

import json

from llm.catalogo import Catalogo
from llm.contrato import Especificacion
from llm.interprete import MAX_USOS_EJEMPLO, _respuesta_intencion, interpretar, pregunta_tras_busqueda
from llm.proveedores import ClienteFalso
from llm.respuesta import _describir_transformable, _texto_valido, responder

CATALOGO_REAL = Catalogo.cargar(Path(__file__).resolve().parents[1] / "datos")


def test_consulta_tecnica_nombra_pocos_usos():
    texto = _respuesta_intencion(Especificacion(), "consulta_tecnica", CATALOGO_REAL)
    assert len(CATALOGO_REAL.usos) > MAX_USOS_EJEMPLO
    assert "(por ejemplo, atmósfera marina, industria alimentaria, " in texto
    assert texto.count(",") <= MAX_USOS_EJEMPLO + 1 and len(texto) < 300


def test_una_pieza_en_singular():
    t = {"bulto": {"id": "29", "formato": "bobina", "grado": "304", "acabado": "NR.1", "espesor_mm": 8},
         "acciones": [], "resultado": {"formato": "bobina", "acabado": "2B", "espesor_mm": 2.2, "piezas": 1}}
    assert "1 pieza)" in _describir_transformable(t)
    t["resultado"]["piezas"] = 13
    assert "13 piezas)" in _describir_transformable(t)


# ---------- obra: se conservan los datos ya dados (RF-18) ----------

def extraccion(**campos):
    base = {"intencion": "pedido", "grado": None, "acabado": None, "formato": None, "espesor_mm": None,
            "ancho_mm": None, "largo_mm": None, "cantidad": None, "uso": None,
            "opciones": {"grado": [], "acabado": [], "formato": []}, "contradicciones": [], "indiferentes": [],
            "campo_aclaracion": None}
    base.update(campos)
    return json.dumps(base)


def test_consejo_de_obra_conserva_formato_y_espesor():
    r = interpretar([{"rol": "comercial", "texto": "chapa de 2 mm para una fachada"}],
                    cliente=ClienteFalso([extraccion(formato="chapa", espesor_mm=2, uso="fachada")]),
                    catalogo=CATALOGO_REAL)
    esp = r.especificacion
    assert r.tipo == "pregunta" and esp.uso == "fachada"
    assert esp.formato == "chapa" and esp.espesor_mm == 2.0
    assert esp.faltan == ["grado"] and esp.grado is None and "grado" not in esp.opciones


def test_consejo_de_obra_no_rellena_el_grado_deducido_del_uso():
    r = interpretar([{"rol": "comercial", "texto": "chapa de 2 mm para una fachada"}],
                    cliente=ClienteFalso([extraccion(espesor_mm=2, uso="adornos arquitectónicos")]),
                    catalogo=CATALOGO_REAL)
    assert r.especificacion.grado is None and "grado" not in r.especificacion.opciones
    assert r.especificacion.espesor_mm == 2.0


# ---------- avisos del uso también en el texto ----------

AVISO = "Según el catálogo, para industria de la construcción se indican 1.4318."
BULTOS = [{"id": "1", "ancho_mm": 1000}, {"id": "2", "ancho_mm": 1250}]


def test_la_pregunta_tras_buscar_dice_el_aviso_del_uso():
    esp = Especificacion(grado="316L", espesor_mm=2, formato="chapa", avisos=[AVISO])
    p = pregunta_tras_busqueda(esp, BULTOS)
    assert p.startswith(AVISO + " Tengo chapa 316L de 2 mm con ancho de 1000 y 1250 mm.")


def test_el_aviso_no_se_repite_ni_la_pregunta_tampoco():
    esp = Especificacion(grado="316L", espesor_mm=2, formato="chapa", avisos=[AVISO])
    primera = pregunta_tras_busqueda(esp, BULTOS)
    historial = [{"rol": "asistente", "texto": primera}]
    assert pregunta_tras_busqueda(esp, BULTOS, historial=historial) is None      # ya preguntado: se enseña todo
    otra = [{"rol": "asistente", "texto": AVISO + " ¿Qué espesor necesitas?"}]
    assert pregunta_tras_busqueda(esp, BULTOS, historial=otra).startswith("Tengo chapa")  # aviso ya dicho


def test_la_respuesta_dice_que_el_uso_no_esta_en_el_catalogo():
    aviso = "El catálogo no indica qué grado es adecuado para «sitio con mucha humedad»."
    esp = Especificacion(grado="304", espesor_mm=2, avisos=[aviso, "«X» no es un grado del catálogo."])
    texto = responder({"exactos": [{"id": "1", "grado": "304"}]}, esp)
    assert aviso in texto and "«X»" not in texto


# ---------- nombres de grado para el comercial: AISI y pocos ----------

def test_ejemplos_de_grado_habituales_y_no_los_primeros_del_catalogo():
    r = interpretar([{"rol": "comercial", "texto": "algo de 2 mm"}],
                    cliente=ClienteFalso([extraccion(espesor_mm=2)]), catalogo=CATALOGO_REAL)
    assert r.pregunta == "¿Qué grado necesitas? Por ejemplo: 304, 316L y 430."


def test_grado_que_no_existe_sin_parecidos_sugiere_los_habituales():
    for valor in ("titanio", "999X"):
        r = interpretar([{"rol": "comercial", "texto": f"{valor} de 2 mm"}],
                        cliente=ClienteFalso([extraccion(grado=valor, espesor_mm=2)]), catalogo=CATALOGO_REAL)
        assert r.pregunta.endswith("¿Te refieres a alguno de estos: 304, 316L, 430 y 304L?"), r.pregunta
    r = interpretar([{"rol": "comercial", "texto": "340 de 2 mm"}],
                    cliente=ClienteFalso([extraccion(grado="340", espesor_mm=2)]), catalogo=CATALOGO_REAL)
    assert "430" in r.pregunta and "1.4016" not in r.pregunta                 # parecidos de verdad


def test_opciones_de_grado_en_aisi_y_como_mucho_cuatro():
    en = ["1.4310", "1.4362", "1.4401", "1.4404", "1.4432", "1.4435", "1.4482", "1.4539", "1.4571"]
    esp = Especificacion(espesor_mm=1, opciones={"grado": en})
    p = pregunta_tras_busqueda(esp, [{"id": "1", "acabado": "2B"}, {"id": "2", "acabado": "BA"}],
                               catalogo=CATALOGO_REAL)
    # 1.4404, 1.4432 y 1.4435 son los tres 316L: quedan 7 nombres distintos
    assert p == "Tengo 301, 1.4362, 316, 316L u otros 3 de 1 mm en 2B y en BA. ¿Cuál prefieres?"
    assert esp.opciones["grado"] == en                     # la búsqueda sigue con los valores del catálogo


# ---------- control del texto del LLM con IDs numéricos ----------

def test_ids_numericos_como_palabra_completa():
    resultado = {"exactos": [{"id": "1", "peso_kg": 500}, {"id": "1343", "peso_kg": 700}]}
    assert not _texto_valido("Hay 2 bultos: 1343 (700 kg).", resultado, resultado, CATALOGO_REAL)
    assert _texto_valido("Hay 2 bultos: 1 (500 kg) y 1343 (700 kg).", resultado, resultado, CATALOGO_REAL)