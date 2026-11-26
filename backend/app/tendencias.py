"""Agregaciones semanales para las barras de compras del frontend."""

from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal

from app.db import get_conn
from app.reportes import ZONA_REPORTE, reporte_de_semana


FORMATOS = ("bobina", "chapa", "fleje")


def _lunes(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _variacion(actual, anterior):
    if anterior is None:
        return {"tendencia": "sin_comparacion", "variacion_pct": None}
    tendencia = "sube" if actual > anterior else "baja" if actual < anterior else "estable"
    porcentaje = round(float((actual - anterior) * 100 / anterior), 2) if anterior else None
    return {"tendencia": tendencia, "variacion_pct": porcentaje}


def _material(bulto):
    return (
        bulto.get("formato"), bulto.get("grado") or bulto.get("aisi") or bulto.get("euronorma"),
        bulto.get("acabado"), bulto.get("espesor_mm"), bulto.get("ancho_mm"), bulto.get("largo_mm"),
    )


def tendencias_compras(semanas: int, unidad: str, *, ahora: datetime | None = None) -> dict:
    ahora = (ahora or datetime.now(ZONA_REPORTE)).astimezone(ZONA_REPORTE)
    actual = _lunes(ahora.date())
    inicio = actual - timedelta(weeks=semanas - 1)
    hasta = int(ahora.timestamp() * 1000)
    lunes_del_periodo = [inicio + timedelta(weeks=n) for n in range(semanas)]
    con_stock = unidad in ("kg", "bultos")
    with closing(get_conn()) as conexion:
        conexion.execute("BEGIN")
        primer_ms = conexion.execute(
            "SELECT MIN(comprada_en_ms) FROM compras WHERE comprada_en_ms <= ?", (hasta,),
        ).fetchone()[0]
        reportes = [
            reporte_de_semana(conexion, lunes, hasta_ms=hasta) for lunes in lunes_del_periodo
        ]
        stock = conexion.execute(
            """SELECT formato, aisi, euronorma, acabado, espesor_mm, ancho_mm, largo_mm, peso_kg
               FROM bultos WHERE estado = 'disponible'""",
        ).fetchall() if con_stock else []

    def semana_de(ms):
        return _lunes(datetime.fromtimestamp(ms / 1000, ZONA_REPORTE).date())

    primera = semana_de(primer_ms) if primer_ms is not None else None
    por_semana = defaultdict(Decimal)
    compras = defaultdict(Decimal)
    disponibilidades = defaultdict(Decimal)
    for lunes, reporte in zip(lunes_del_periodo, reportes):
        for compra in reporte["compras"]:
            material = _material(dict(compra["caracteristicas"], formato=compra["formato"]))
            for importe in compra["cantidades_sustraidas"]:
                registrada = importe["unidad"]
                if registrada == unidad:
                    cantidad = Decimal(str(importe["valor"]))
                elif unidad == "kg" and registrada == "t":
                    cantidad = Decimal(str(importe["valor"])) * 1000
                else:
                    continue
                por_semana[lunes, material[0]] += cantidad
                compras[material] += cantidad

    for bulto in stock:
        disponibilidades[_material(dict(bulto))] += Decimal(str(bulto["peso_kg"])) if unidad == "kg" else 1

    serie = []
    anterior = None
    for lunes, reporte in zip(lunes_del_periodo, reportes):
        sin_historial = primera is None or lunes < primera
        completa = not sin_historial and primera < lunes < actual
        barras = []
        for formato in FORMATOS:
            cantidad = por_semana[lunes, formato]
            previa = por_semana[anterior, formato] if completa and anterior is not None else None
            barras.append({
                "formato": formato,
                "cantidad": None if sin_historial else float(cantidad),
                **_variacion(cantidad, previa),
            })
        serie.append({
            "inicio": reporte["semana"]["inicio"],
            "fin": reporte["semana"]["fin"],
            "estado": ("sin_historial" if sin_historial else "en_curso" if lunes == actual
                       else "completa" if completa else "inicio_historial"),
            "barras": barras,
        })
        anterior = lunes if completa else None

    campos = ("formato", "grado", "acabado", "espesor_mm", "ancho_mm", "largo_mm")
    materiales = [
        {**dict(zip(campos, material)), "comprado": float(cantidad),
         "stock_actual": float(disponibilidades[material]) if con_stock else None}
        for material, cantidad in sorted(compras.items(), key=lambda par: (-par[1], str(par[0])))
    ]
    return {"unidad": unidad, "zona_horaria": ZONA_REPORTE.key,
            "semanas": serie, "materiales": materiales}
