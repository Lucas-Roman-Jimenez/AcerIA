import unittest

from voz.normalizacion import normalizar_transcripcion


class TestNormalizacion(unittest.TestCase):
    def test_equivalencias_del_pdf_en_una_peticion(self):
        self.assertEqual(
            normalizar_transcripcion("Una chapa trescientos dieciséis ele, dos be."),
            "Una chapa 316L, 2B.",
        )

    def test_mayusculas_y_espacios(self):
        self.assertEqual(normalizar_transcripcion("Acabado DOS  BE."), "Acabado 2B.")

    def test_conserva_el_resto_de_la_transcripcion(self):
        texto = "2B, 316L, dos barras, acabado dos beige."
        self.assertEqual(normalizar_transcripcion(texto), texto)
