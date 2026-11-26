"""Evalúa por separado el resultado de /buscar y la interpretación de /chat."""

import argparse
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from reglas.corte import cumple_condiciones_corte
from reglas.laminacion import permite_laminacion


CASOS = Path(__file__).with_name("casos_evaluacion.json")
CASOS_TRANSFORMABLES = CASOS.with_name("casos_transformables_api.json")
UMBRAL = 85
REGLAS = {"corte": cumple_condiciones_corte, "laminacion": permite_laminacion}
_MEDIDAS = {
    "espesor_mm": "Gauge",
    "ancho_mm": "Width",
    "largo_mm": "Lenght (Solo para chapas)",
}


def _especificacion_exacta(campos):
    return {
        "grado": campos["AISI"],
        "acabado": campos["Euronorma Sup.Finish"],
        "formato": "chapa",
        **{destino: float(campos[origen].replace(".", "").replace(",", "."))
           for destino, origen in _MEDIDAS.items()},
    }


def _post(base_url, endpoint, datos, timeout):
    solicitud = Request(
        base_url.rstrip("/") + endpoint, method="POST",
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(solicitud, timeout=timeout) as respuesta:
        cuerpo = json.load(respuesta)
    if not isinstance(cuerpo, dict):
        raise ValueError("La respuesta JSON debe ser un objeto.")
    return cuerpo


def _resultado_stock(respuesta, referencia):
    ids = [str(bulto["id"]) for bulto in respuesta.get("exactos", [])]
    transformables = respuesta.get("transformables", [])
    orden_correcto = _orden_correcto(transformables)
    return (
        respuesta.get("estado") == "resultados" and str(referencia) in ids and orden_correcto,
        {
            "estado": respuesta.get("estado"),
            "ids_exactos": ids,
            "orden_transformables_correcto": orden_correcto,
            "transformables": [
                {campo: item.get(campo) for campo in ("bulto_id", "merma_pct", "num_operaciones")}
                for item in transformables
            ],
        },
    )


def _orden_correcto(transformables):
    ranking = [_criterio_transformable(item) for item in transformables]
    return None not in ranking and ranking == sorted(ranking)


def _sin_stock(respuesta, _esperado):
    exactos = respuesta.get("exactos")
    transformables = respuesta.get("transformables")
    estado = respuesta.get("estado")
    return estado == "sin_stock" and exactos == [] and transformables == [], {
        "estado": estado, "exactos": exactos, "transformables": transformables,
    }


def _criterio_transformable(item):
    porcentaje = item.get("merma_pct")
    operaciones = item.get("num_operaciones")
    if type(porcentaje) not in (int, float) or not math.isfinite(porcentaje):
        return None
    if type(operaciones) is not int:
        return None
    return porcentaje, operaciones


def _resultado_transformable(respuesta, esperado):
    transformables = respuesta.get("transformables", [])
    referencia = esperado["bulto_id"]
    orden_correcto = _orden_correcto(transformables)
    objetivo = esperado["especificacion"]
    resultado_esperado = {
        **{campo: objetivo[campo] for campo in ("formato", "acabado", *_MEDIDAS)},
        "piezas": esperado["piezas"],
    }
    casos_bulto = []
    for item in transformables:
        if str(item.get("bulto_id")) != referencia:
            continue
        resultado = item.get("resultado") or {}
        observado = {
            **{campo: item.get(campo) for campo in ("merma_kg", "merma_pct", "merma_estimada")},
            "num_operaciones": item.get("num_operaciones"),
            "reglas": [
                accion.get("regla") if isinstance(accion, dict) else None
                for accion in item.get("acciones", [])
            ],
            "resultado": {campo: resultado.get(campo) for campo in resultado_esperado},
        }
        casos_bulto.append(observado)

    transformacion_esperada = {
        **{campo: esperado[campo] for campo in ("merma_kg", "merma_pct", "merma_estimada", "reglas")},
        "num_operaciones": len(esperado["reglas"]),
        "resultado": resultado_esperado,
    }
    estado = respuesta.get("estado")
    valido = estado == "resultados" and orden_correcto and transformacion_esperada in casos_bulto
    return valido, {
        "estado": estado,
        "bulto_id": referencia,
        "orden_transformables_correcto": orden_correcto,
        "esperado": transformacion_esperada,
        "recibido": casos_bulto,
    }


def _interpretacion_exacta(respuesta, especificacion):
    recibida = respuesta.get("especificacion") or {}
    diferencias = {
        campo: {"esperado": valor, "recibido": recibida.get(campo)}
        for campo, valor in especificacion.items()
        if recibida.get(campo) != valor or isinstance(recibida.get(campo), bool)
    }
    estado = respuesta.get("estado")
    return estado in ("resultados", "sin_stock") and not diferencias, {
        "estado": estado, "diferencias": diferencias,
    }


def _aclaracion(respuesta, campo):
    especificacion = respuesta.get("especificacion") or {}
    faltan = especificacion.get("faltan") or []
    opciones = especificacion.get("opciones") or {}
    estado = respuesta.get("estado")
    return estado == "pregunta" and (campo in faltan or bool(opciones.get(campo))), {
        "estado": estado, "faltan": faltan, "opciones": opciones,
    }


def _evaluar_peticion(enviar, endpoint, datos, comprobar, esperado):
    try:
        return comprobar(enviar(endpoint, datos), esperado)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return False, {"error": str(error)}


def _resumir(anotaciones):
    fallos = [detalle for aprobado, detalle in anotaciones if not aprobado]
    total = len(anotaciones)
    aciertos = total - len(fallos)
    return {
        "total": total,
        "aciertos": aciertos,
        "porcentaje": round(100 * aciertos / total, 2) if total else None,
        "cumple_umbral": bool(total and 100 * aciertos >= UMBRAL * total),
        "fallos": fallos,
    }


def evaluar(casos, enviar, *, solo_resultados=False):
    interpretacion, resultados, transformables, reglas_locales = [], [], [], []
    for caso in casos:
        esperado = caso["esperado"]
        detalle = {"id": caso["id"], "peticion": caso["peticion"]}
        categoria = caso["categoria"]
        if categoria in ("transformacion", "imposible"):
            actual = REGLAS[esperado["regla"]](**esperado["entrada"])
            reglas_locales.append((actual == esperado["cumple_condiciones"],
                                   dict(detalle, esperado=esperado["cumple_condiciones"],
                                        recibido=actual)))
            continue

        if categoria == "exacta":
            especificacion = _especificacion_exacta(esperado["campos_fuente"])
            referencia = esperado["id_referencia_excel"]
            acierto, observado = _evaluar_peticion(
                enviar, "/buscar", especificacion, _resultado_stock, referencia,
            )
            resultados.append((acierto, dict(detalle, id_referencia_excel=referencia, **observado)))
            comprobar, objetivo = _interpretacion_exacta, especificacion
        elif categoria == "transformable_api":
            especificacion = esperado["especificacion"]
            acierto, observado = _evaluar_peticion(
                enviar, "/buscar", especificacion, _resultado_transformable, esperado,
            )
            transformables.append((acierto, dict(detalle, **observado)))
            comprobar, objetivo = _interpretacion_exacta, especificacion
        elif categoria == "sin_stock":
            especificacion = esperado["especificacion"]
            acierto, observado = _evaluar_peticion(
                enviar, "/buscar", especificacion, _sin_stock, None,
            )
            resultados.append((acierto, dict(detalle, **observado)))
            comprobar, objetivo = _interpretacion_exacta, especificacion
        elif categoria == "aclaracion":
            campo = esperado["pedir_aclaracion_sobre"]
            comprobar = _aclaracion
            objetivo = {"espesor": "espesor_mm"}.get(campo, campo)
            detalle["pedir_aclaracion_sobre"] = objetivo
        else:
            raise ValueError(f"Categoría desconocida: {categoria!r}")

        if solo_resultados:
            continue
        chat = {"conversacion_id": str(uuid4()), "mensaje": caso["peticion"]}
        acierto, observado = _evaluar_peticion(enviar, "/chat", chat, comprobar, objetivo)
        interpretacion.append((acierto, dict(detalle, **observado)))

    informe = {
        "umbral_pct": UMBRAL,
        "resultados": _resumir(resultados),
        "reglas_locales": _resumir(reglas_locales),
    }
    if not solo_resultados:
        informe["interpretacion"] = _resumir(interpretacion)
    if transformables:
        informe["transformables_api"] = _resumir(transformables)
    return informe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="URL base de la API de Alonso")
    parser.add_argument("--timeout", type=float, default=30, help="Segundos por petición")
    parser.add_argument("--solo-resultados", action="store_true",
                        help="Evalúa /buscar y las reglas locales sin llamar a /chat")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout debe ser positivo")
    with CASOS.open(encoding="utf-8") as archivo:
        casos = json.load(archivo)
    with CASOS_TRANSFORMABLES.open(encoding="utf-8") as archivo:
        casos.extend(json.load(archivo))

    def enviar(endpoint, datos):
        return _post(args.base_url, endpoint, datos, args.timeout)

    informe = evaluar(casos, enviar, solo_resultados=args.solo_resultados)
    print(json.dumps(informe, ensure_ascii=False, indent=2))
    metricas = ["resultados", "transformables_api"]
    if not args.solo_resultados:
        metricas.append("interpretacion")
    correcto = all(informe[metrica]["cumple_umbral"] for metrica in metricas)
    return 0 if correcto and not informe["reglas_locales"]["fallos"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
