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


def test_nomenclatura_aisi_conserva_equivalencias_y_procedencia():
    datos = json.loads((DATOS / "catalogo.json").read_text(encoding="utf-8"))
    nomenclatura = datos["nomenclatura_grados"]
    grados = nomenclatura["grados"]
    referencias = nomenclatura["referencias_en"]
    assert nomenclatura["referencia"] == "AISI"
    assert grados["301LN"] == {"sistema": "AISI", "en": ["1.4318"]}
    assert grados["316L"]["en"] == ["1.4404", "1.4432", "1.4435"]
    assert grados["2205"]["sistema"] == "dúplex"
    assert grados["1.4828"]["sistema"] == "EN"
    assert set(en for grado in grados.values() for en in grado["en"]) == set(referencias)
    assert set(referencias) == {f["en"] for f in datos["fichas"]} | {"1.4306"}
    for ficha in datos["fichas"]:
        campos = ("mat", "designacion_comercial", "grado_comercial", "uns")
        assert {campo: ficha[campo] for campo in campos} in referencias[ficha["en"]]["fichas"]
        assert ficha["fuente"]["archivo"] and ficha["fuente"]["pagina"] == 1
    assert referencias["1.4306"]["otras_fuentes"][0]["grado_comercial"] == "304L"
    assert "304L/304" in nomenclatura["codigos_inventario_compuestos"]["1.4301/1.4307"]
    assert nomenclatura["codigos_inventario_sin_validacion_en"]["1.4310Mo"] == ["301"]


def test_aliases_ambiguos_siguen_admitidos_sin_asignar_un_unico_en():
    catalogo = Catalogo.cargar(DATOS)
    assert catalogo.normalizar("grado", "AISI 316L") == "316L"
    assert catalogo.grados_en_por_comercial["316L"] == {"1.4404", "1.4432", "1.4435"}
    assert catalogo.grados_en_por_comercial["304L"] == {"1.4306", "1.4307"}
    assert catalogo.grados_en_por_comercial["301"] == {"1.4310"}
    assert catalogo.etiqueta_en("1.4318") == "AISI 301LN (EN 1.4318)"
    assert catalogo.etiqueta_en("1.4828") == "EN 1.4828"


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
