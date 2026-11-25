import pytest

from reglas.motor import aplicar_reglas


def bulto(id_, acabado, formato, espesor, ancho, largo, peso):
    return {
        "id": id_, "aisi": "304L/304", "euronorma": "4301/4307",
        "acabado": acabado, "formato": formato, "espesor_mm": espesor,
        "ancho_mm": ancho, "largo_mm": largo, "peso_kg": peso,
    }


def objetivo(formato, acabado, espesor, ancho, largo=None, grado="304"):
    return {
        "formato": formato, "grados": [grado], "acabados": [acabado],
        "espesor_mm": espesor, "ancho_mm": ancho, "largo_mm": largo,
        "tolerancias": {"espesor_mm": 0, "ancho_mm": 0, "largo_mm": 0},
    }


BOBINA_334 = bulto("334", "2B", "bobina", 2, 1500, None, 745)
BOBINA_23 = bulto("23", "NR.1", "bobina", 3, 1500, None, 4020)
CHAPA_2039 = bulto("2039", "BA", "chapa", 1.5, 1000, 2000, 814)


@pytest.mark.parametrize(
    "origen,pedido,max_ops,reglas,piezas,merma,porcentaje,estimada",
    [
        (BOBINA_334, objetivo("chapa", "2B", 2, 1250, 2500), 1,
         ["CORTE_BOBINA_CHAPA"], 12, 152.5, 20.5, True),
        (BOBINA_23, objetivo("bobina", "2B", 1, 1500), 1,
         ["LAMINACION"], 1, 0, 0, False),
        (BOBINA_23, objetivo("chapa", "2B", 1, 1250, 2500), 2,
         ["LAMINACION", "CORTE_BOBINA_CHAPA"], 135, 687.2, 17.1, True),
        (CHAPA_2039, objetivo("fleje", "BA", 1.5, 200), 1,
         ["CORTE_CHAPA_FLEJE"], 5, 0, 0, False),
    ],
    ids=["contrato-1", "contrato-2", "contrato-3", "contrato-5"],
)
def test_transformaciones_del_contrato(
    origen, pedido, max_ops, reglas, piezas, merma, porcentaje, estimada,
):
    [salida] = aplicar_reglas(origen, pedido, max_ops)
    assert salida["bulto_id"] == origen["id"]
    assert salida["num_operaciones"] == len(reglas)
    assert [a["regla"] for a in salida["acciones"]] == reglas
    assert [a["orden"] for a in salida["acciones"]] == list(range(1, len(reglas) + 1))
    assert all(a["descripcion"] and a["parametros"] for a in salida["acciones"])
    assert sum(a["merma_kg"] for a in salida["acciones"]) == merma
    assert salida["merma_kg"] == merma
    assert salida["merma_pct"] == porcentaje
    assert salida["merma_estimada"] is estimada
    assert bool(salida["avisos"]) is estimada
    resultado = salida["resultado"]
    assert resultado["piezas"] == piezas
    assert resultado["peso_util_kg"] == pytest.approx(origen["peso_kg"] - merma, abs=0.05)
    assert resultado["aisi"] == origen["aisi"]
    assert resultado["euronorma"] == origen["euronorma"]
    assert resultado["acabado"] == pedido["acabados"][0]
    for campo in ("formato", "espesor_mm", "ancho_mm"):
        assert resultado[campo] == pedido[campo]
    assert resultado["largo_mm"] == (
        origen["largo_mm"] if pedido["formato"] == "fleje" else pedido["largo_mm"]
    )


@pytest.mark.parametrize(
    "origen,pedido,max_ops",
    [
        (BOBINA_23, objetivo("chapa", "2B", 1, 1250, 2500), 1),
        (BOBINA_334, objetivo("bobina", "2B", 1.2, 1500), 1),
        (CHAPA_2039, objetivo("chapa", "BA", 1.5, 1250, 2500), 2),
        (BOBINA_334, objetivo("chapa", "BA", 2, 1250, 2500), 2),
        (BOBINA_334, objetivo("chapa", "2B", 2, 1250, 2500, "316L"), 2),
    ],
    ids=["contrato-4", "contrato-6", "contrato-7", "contrato-8", "contrato-9"],
)
def test_transformaciones_rechazadas_por_el_contrato(origen, pedido, max_ops):
    assert aplicar_reglas(origen, pedido, max_ops) == []


def test_certificado_euronorma_y_tolerancia_del_objetivo():
    pedido = objetivo("chapa", "2B", 2.01, 1250, 2500, "4307")
    assert aplicar_reglas(BOBINA_334, pedido) == []
    pedido["tolerancias"]["espesor_mm"] = 0.01
    [salida] = aplicar_reglas(BOBINA_334, pedido)
    assert salida["resultado"]["espesor_mm"] == 2


def test_no_lamina_nr_1_l_ni_devuelve_operaciones_para_un_exacto():
    assert aplicar_reglas(
        dict(BOBINA_23, acabado="NR.1 L"), objetivo("bobina", "2B", 1, 1500),
    ) == []
    assert aplicar_reglas(BOBINA_334, objetivo("bobina", "2B", 2, 1500)) == []


def test_devuelve_corte_directo_y_encadenado_si_el_espesor_no_los_distingue():
    pedido = objetivo("chapa", "2B", 1, 1250, 2500)
    pedido["tolerancias"]["espesor_mm"] = 1
    salidas = aplicar_reglas(BOBINA_334, pedido)
    assert [salida["num_operaciones"] for salida in salidas] == [1, 2]


def test_corte_chapa_a_chapa_cuenta_piezas_en_ambas_dimensiones():
    [salida] = aplicar_reglas(CHAPA_2039, objetivo("chapa", "BA", 1.5, 400, 1000))
    assert salida["acciones"][0]["regla"] == "CORTE_CHAPA_CHAPA"
    assert salida["resultado"]["piezas"] == 4
    assert salida["merma_kg"] == 162.8
    assert salida["merma_estimada"] is False


def test_corte_bobina_a_fleje_y_largo_inviable_para_chapa():
    [salida] = aplicar_reglas(BOBINA_334, objetivo("fleje", "2B", 2, 400))
    assert salida["acciones"][0]["regla"] == "CORTE_BOBINA_FLEJE"
    assert salida["resultado"]["piezas"] == 3
    assert salida["merma_kg"] == 149
    assert aplicar_reglas(BOBINA_334, objetivo("chapa", "2B", 2, 1250, 32000)) == []
