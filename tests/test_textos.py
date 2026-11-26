"""Textos de las plantillas con el catálogo real (datos/). Sin LLM."""
from pathlib import Path

from llm.catalogo import Catalogo
from llm.contrato import Especificacion
from llm.interprete import MAX_USOS_EJEMPLO, _respuesta_intencion
from llm.respuesta import _describir_transformable

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
