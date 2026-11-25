import json
from pathlib import Path
from urllib.error import URLError

import pytest

from evaluar_api import evaluar


@pytest.mark.parametrize(
    "orden,correcto",
    [((0, 1, 2), True), ((1, 0, 2), False), ((0, 2, 1), False), ((0, 1, 2, 3), False)],
    ids=["porcentaje-antes-que-kilos", "porcentaje-incorrecto", "desempate-incorrecto",
         "porcentaje-ausente"],
)
def test_resultados_comprueba_el_orden_de_transformables(orden, correcto):
    archivo = Path(__file__).with_name("casos_evaluacion.json")
    caso = json.loads(archivo.read_text(encoding="utf-8"))[0]
    transformables = [
        {"bulto_id": "10", "merma_kg": 100, "merma_pct": 5, "num_operaciones": 2},
        {"bulto_id": "11", "merma_kg": 10, "merma_pct": 10, "num_operaciones": 1},
        {"bulto_id": "12", "merma_kg": 5, "merma_pct": 10, "num_operaciones": 2},
        {"bulto_id": "13", "merma_kg": 10, "num_operaciones": 1},
    ]

    def enviar(ruta, datos):
        if ruta == "/buscar":
            return {
                "estado": "resultados", "exactos": [{"id": "1276"}],
                "transformables": [transformables[i] for i in orden],
            }
        return {"estado": "sin_stock"}

    resultados = evaluar([caso], enviar)["resultados"]

    assert resultados["aciertos"] == int(correcto)
    if not correcto:
        [fallo] = resultados["fallos"]
        assert fallo["orden_transformables_correcto"] is False
        assert [item["bulto_id"] for item in fallo["transformables"]] == [
            transformables[i]["bulto_id"] for i in orden
        ]


def test_evaluar_separa_metricas_y_fallos_de_las_reglas_locales():
    archivo = Path(__file__).with_name("casos_evaluacion.json")
    casos = json.loads(archivo.read_text(encoding="utf-8"))
    casos = [caso for caso in casos if caso["id"] in ("EX-1276", "CL-01", "RE-01", "RE-05")]
    conversaciones = set()
    rutas = []

    def enviar(ruta, datos):
        rutas.append(ruta)
        if ruta == "/buscar":
            assert datos == {
                "grado": "309", "acabado": "2B", "formato": "chapa",
                "espesor_mm": 3, "ancho_mm": 1000, "largo_mm": 2000,
            }
            return {"estado": "resultados", "exactos": [{"id": "1276"}]}
        assert datos["conversacion_id"] not in conversaciones
        conversaciones.add(datos["conversacion_id"])
        if datos["mensaje"] == casos[0]["peticion"]:
            return {"estado": "resultados", "especificacion": {
                "grado": "309", "acabado": "2B", "formato": "chapa",
                "espesor_mm": 3, "ancho_mm": 1000, "largo_mm": 2000,
            }}
        return {"estado": "pregunta", "especificacion": {"faltan": ["grado"]}}

    informe = evaluar(casos, enviar)

    assert rutas == ["/buscar", "/chat", "/chat"]
    assert informe["resultados"]["porcentaje"] == 100
    assert informe["interpretacion"]["porcentaje"] == 50
    assert informe["interpretacion"]["fallos"][0]["id"] == "CL-01"
    assert informe["interpretacion"]["fallos"][0]["pedir_aclaracion_sobre"] == "espesor_mm"
    assert informe["reglas_locales"]["aciertos"] == 2


def test_evaluar_registra_error_de_red_y_continua():
    casos = json.loads(Path(__file__).with_name("casos_evaluacion.json").read_text(encoding="utf-8"))

    def enviar(ruta, datos):
        raise URLError("API no disponible")

    informe = evaluar(casos, enviar)

    assert informe["interpretacion"]["total"] == 24
    assert informe["interpretacion"]["aciertos"] == 0
    assert informe["resultados"]["total"] == 16
    assert informe["resultados"]["aciertos"] == 0
    assert "API no disponible" in informe["resultados"]["fallos"][0]["error"]
    assert informe["reglas_locales"]["aciertos"] == 8
