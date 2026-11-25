import unittest

from reglas.corte import cumple_condiciones_corte
from reglas.sustitucion import permite_sustituir_dimensiones


class TestCorte(unittest.TestCase):
    def test_ejemplos_del_documento(self):
        self.assertTrue(cumple_condiciones_corte(
            formato_origen="bobina", formato_destino="chapa",
            ancho_origen=1550, ancho_destino=1500, largo_destino=3000,
        ))
        self.assertTrue(cumple_condiciones_corte(
            formato_origen="bobina", formato_destino="fleje",
            ancho_origen=1550, ancho_destino=200,
        ))

    def test_formatos_y_dimensiones_de_chapa(self):
        caso = dict(
            formato_origen="chapa", formato_destino="chapa",
            ancho_origen=1550, ancho_destino=1500,
            largo_origen=3000, largo_destino=2500,
        )
        self.assertTrue(cumple_condiciones_corte(**caso))
        for cambios in (
            {"formato_origen": "fleje"},
            {"formato_destino": "bobina"},
            {"ancho_destino": 1600},
            {"largo_destino": 3500},
            {"largo_destino": None},
            {"largo_origen": None},
        ):
            with self.subTest(cambios=cambios):
                self.assertFalse(cumple_condiciones_corte(**(caso | cambios)))
        self.assertTrue(cumple_condiciones_corte(**(caso | {
            "formato_destino": "fleje", "largo_destino": None,
        })))


class TestSustitucion(unittest.TestCase):
    def test_alternativa_si_falta_la_medida_y_se_conserva_el_material(self):
        caso = dict(
            hay_medida_exacta=False,
            grado_pedido="304", grado_alternativo="304",
            acabado_pedido="2B", acabado_alternativo="2B",
            espesor_pedido=2, espesor_alternativo=2,
            dimensiones_pedidas=(1500, 3000),
            dimensiones_alternativas=(1500, 2500),
        )
        self.assertTrue(permite_sustituir_dimensiones(**caso))
        for cambios in (
            {"hay_medida_exacta": True},
            {"grado_alternativo": "316"},
            {"acabado_alternativo": "BA"},
            {"espesor_alternativo": 3},
            {"dimensiones_alternativas": (1500, 3000)},
        ):
            with self.subTest(cambios=cambios):
                self.assertFalse(permite_sustituir_dimensiones(**(caso | cambios)))
