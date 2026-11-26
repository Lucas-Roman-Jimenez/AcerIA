import json
from pathlib import Path

from llm import ClienteFalso, interpretar
from llm.catalogo import Catalogo


DATOS = Path(__file__).resolve().parents[1] / "datos"


def test_catalogo_de_stock_conserva_los_codigos_y_las_medidas_observadas():
    catalogo = Catalogo.cargar(DATOS)
    assert catalogo.normalizar("acabado", "nr.1") == "NR.1"
    assert catalogo.normalizar("acabado", "2R") == "BA"
    assert catalogo.normalizar("acabado", "brillante") == "BA"
    assert catalogo.normalizar("acabado", "N4-G-180") == "N4-G-180"
    assert catalogo.normalizar("grado", "AISI 304L") == "304L"
    assert catalogo.productos_compatibles("304", "NR.1", "bobina", 3, 1500)
    assert all(p["espesor_mm"][0] == p["espesor_mm"][1] and p["ancho_mm"][0] == p["ancho_mm"][1]
               for p in catalogo.productos)
    assert catalogo.validar_combinaciones is False


def test_glosario_operativo_apunta_a_codigos_presentes_en_el_inventario():
    catalogo = Catalogo.cargar(DATOS)
    terminos = {t["termino"]: t["valores"] for t in catalogo.terminos}
    assert terminos["dos be"] == ["2B"]
    assert terminos["trescientos dieciséis ele"] == ["316L"]
    assert terminos["N1"] == ["NR.1"]
    assert terminos["18/8"] == ["304"]
    assert terminos["MAT 240"] == ["1.4404"]
    assert len([termino for termino in terminos if termino.startswith("MAT ")]) == 41
    for termino in catalogo.terminos:
        assert all(catalogo.normalizar(termino["campo"], valor) == valor for valor in termino["valores"])


def test_usos_del_catalogo_conservan_la_ficha_y_distinguen_ambiente_marino():
    catalogo = Catalogo.cargar(DATOS)
    alimentaria = catalogo.uso("industria alimentaria")
    assert "1.4404" in alimentaria["grados"]
    assert catalogo.grado_indicado_para_uso("316L", alimentaria["grados"])
    assert any(f["mat"] == "MAT 240" and f["pagina"] == 1 for f in alimentaria["fuentes"])
    assert catalogo.uso("atmósfera marina")["grados"] == ["1.4462"]
    assert catalogo.uso("para agua salada") is None


def test_una_medida_ausente_del_stock_pasa_al_buscador():
    catalogo = Catalogo.cargar(DATOS)
    assert not catalogo.productos_compatibles("304", "2B", "chapa", 1, 4321)
    bruto = {"grado": "304", "acabado": "2B", "formato": "chapa", "espesor_mm": 1, "ancho_mm": 4321}
    historial = [{"rol": "comercial", "texto": "Chapa 304 2B de 1 mm y 4321 mm de ancho."}]
    resultado = interpretar(historial, cliente=ClienteFalso([json.dumps(bruto)]), redactar_con_llm=False)
    assert resultado.tipo == "especificacion"
    assert resultado.especificacion.ancho_mm == 4321
