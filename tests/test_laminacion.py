import unittest

from reglas.laminacion import permite_laminacion


class TestLaminacion(unittest.TestCase):
    def comprobar(self, esperado, **cambios):
        caso = {
            "formato_origen": "bobina",
            "acabado_origen": "2B",
            "espesor_origen": 4,
            "acabado_destino": "2B",
            "espesor_destino": 2,
        }
        self.assertEqual(permite_laminacion(**(caso | cambios)), esperado)

    def test_ejemplos_del_documento(self):
        self.comprobar(True)
        self.comprobar(True, acabado_origen="N1", espesor_origen=8, espesor_destino=3)

    def test_limites_de_reduccion(self):
        self.comprobar(True, espesor_destino=1)
        self.comprobar(False, espesor_destino=0.99)
        self.comprobar(False, espesor_destino=2.01)

    def test_formato_y_acabados(self):
        self.comprobar(False, formato_origen="chapa")
        self.comprobar(False, acabado_origen="BA")
        self.comprobar(False, acabado_destino="N1")

    def test_espesores_invalidos(self):
        self.comprobar(False, espesor_origen=0, espesor_destino=0)
        self.comprobar(False, espesor_destino=float("nan"))


if __name__ == "__main__":
    unittest.main()
