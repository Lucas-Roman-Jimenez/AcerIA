"""Validación con Pydantic de la salida del LLM (llm/modelos.py). Sin LLM."""
import pytest

from llm.modelos import Extraccion


def test_extraccion_correcta():
    e = Extraccion.desde_llm({"grado": "304", "acabado": "2B", "espesor_mm": 2, "ancho_mm": "1250",
                              "cantidad": {"valor": 500, "unidad": "kg"}, "indiferentes": ["formato"],
                              "intencion": "pedido"})
    assert (e.grado, e.acabado, e.espesor_mm, e.ancho_mm) == ("304", "2B", 2.0, 1250.0)
    assert e.cantidad.valor == 500 and e.cantidad.unidad == "kg"
    assert e.indiferentes == ["formato"] and e.intencion == "pedido"


@pytest.mark.parametrize("valor,esperado", [("2,5", 2.5), ("0,7", 0.7), (3, 3.0), ("dos", None), (0, None),
                                            (-1, None), (True, None), (None, None), ([2], None)])
def test_medidas(valor, esperado):
    assert Extraccion.desde_llm({"espesor_mm": valor}).espesor_mm == esperado


@pytest.mark.parametrize("cantidad", [{"valor": 5, "unidad": "toneladas"}, {"valor": 0, "unidad": "kg"},
                                      {"valor": "mucho", "unidad": "kg"}, {"unidad": "kg"}, "500 kg", 500])
def test_cantidad_mal_formada_se_descarta(cantidad):
    assert Extraccion.desde_llm({"cantidad": cantidad}).cantidad is None


def test_un_campo_mal_formado_no_invalida_los_demas():
    e = Extraccion.desde_llm({"grado": {"x": 1}, "acabado": True, "formato": "", "espesor_mm": "2",
                              "uso": 7, "indiferentes": "acabado", "contradicciones": "no",
                              "intencion": ["pedido"], "fuera_de_tema": "sí", "campo_extra": 1})
    assert e.espesor_mm == 2.0
    assert e.grado is e.acabado is e.formato is e.uso is e.intencion is None
    assert e.indiferentes == [] and e.contradicciones == [] and e.fuera_de_tema is False


def test_varios_valores_en_un_campo_pasan_a_opciones():
    e = Extraccion.desde_llm({"acabado": ["BA", "2R", None, True], "opciones": {"grado": "304"}})
    assert e.acabado is None
    assert e.opciones == {"acabado": ["BA", "2R"], "grado": ["304"]}


def test_listas_filtradas():
    e = Extraccion.desde_llm({"indiferentes": ["acabado", "color", 7, "ancho_mm"],
                              "contradicciones": [{"campo": "espesor_mm", "valores": [2, 3]}, {"campo": 5}, "x"]})
    assert e.indiferentes == ["acabado", "ancho_mm"]
    assert [c.model_dump() for c in e.contradicciones] == [{"campo": "espesor_mm", "valores": [2, 3]}]


@pytest.mark.parametrize("bruto", [None, [], "texto", 5])
def test_lo_que_no_es_un_objeto_da_una_extraccion_vacia(bruto):
    assert Extraccion.desde_llm(bruto) == Extraccion()
