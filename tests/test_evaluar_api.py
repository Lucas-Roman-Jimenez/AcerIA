import json
from pathlib import Path
from urllib.error import URLError

from evaluar_api import evaluar


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
