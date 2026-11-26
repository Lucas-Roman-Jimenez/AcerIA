"""Agregaciones semanales para las barras de compras del frontend."""

from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal

from app.db import get_conn
from app.reportes import ZONA_REPORTE, reporte_de_semana


FORMATOS = ("bobina", "chapa", "fleje")
CAMPOS_MATERIAL = ("formato", "grado", "acabado", "espesor_mm", "ancho_mm", "largo_mm")


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


def _stock_disponible(conexion):
    return conexion.execute(
        """SELECT formato, aisi, euronorma, acabado, espesor_mm, ancho_mm, largo_mm, peso_kg
           FROM bultos WHERE estado = 'disponible'""",
    ).fetchall()


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
        stock = _stock_disponible(conexion) if con_stock else []

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

    materiales = [
        {**dict(zip(CAMPOS_MATERIAL, material)), "comprado": float(cantidad),
         "stock_actual": float(disponibilidades[material]) if con_stock else None}
        for material, cantidad in sorted(compras.items(), key=lambda par: (-par[1], str(par[0])))
    ]
    return {"unidad": unidad, "zona_horaria": ZONA_REPORTE.key,
            "semanas": serie, "materiales": materiales}


# --- Reposición ---------------------------------------------------------------

SEMANAS_REPOSICION = 4
DIAS_REPOSICION = SEMANAS_REPOSICION * 7
UMBRALES_REPOSICION = {
    "semanas_minimas_recurrente": 2,     # reponer y vigilar: ventas en al menos 2 semanas
    "cobertura_reponer_dias": 7,         # reponer: cobertura < 7
    "cobertura_vigilar_max_dias": 14,    # vigilar: 7 <= cobertura <= 14
    "puntual_stock_max_t": 2,            # salida puntual: 1 semana con ventas y stock < 2 t
}
FILTRO_REPOSICION = {"vendido_min_t": 2, "stock_max_t": 2}   # ambos estrictos
SECCIONES_REPOSICION = ("reponer", "vigilar", "puntual")


def _kg_vendidos(compra) -> Decimal:
    """Kilos de una compra consolidada; 0 si el peso no se puede reconstruir.

    kg y t se suman directamente. Un bulto entero solo cuenta si no hay kg ni t
    registrados y se conoce su peso. Las piezas no cuentan: la ficha del reporte
    no trae las piezas del bulto.
    """
    kg = Decimal(0)
    bultos = None
    for importe in compra["cantidades_sustraidas"]:
        valor = Decimal(str(importe["valor"]))
        if importe["unidad"] == "kg":
            kg += valor
        elif importe["unidad"] == "t":
            kg += valor * 1000
        elif importe["unidad"] == "bultos":
            bultos = valor
    peso = compra["caracteristicas"].get("peso_kg")
    if not kg and bultos == 1 and peso:
        kg = Decimal(str(peso))
    return kg


def _seccion(semanas: int, cobertura: Decimal, stock_kg: Decimal) -> str | None:
    u = UMBRALES_REPOSICION
    if semanas >= u["semanas_minimas_recurrente"]:
        if cobertura < u["cobertura_reponer_dias"]:
            return "reponer"
        if cobertura <= u["cobertura_vigilar_max_dias"]:
            return "vigilar"
    elif semanas == 1 and stock_kg < u["puntual_stock_max_t"] * 1000:
        return "puntual"
    return None


def recomendaciones_reposicion(*, ahora: datetime | None = None) -> dict:
    """Clasifica las referencias vendidas en las últimas 4 semanas completas según su cobertura."""
    ahora = (ahora or datetime.now(ZONA_REPORTE)).astimezone(ZONA_REPORTE)
    actual = _lunes(ahora.date())
    lunes_del_periodo = [actual - timedelta(weeks=n) for n in range(SEMANAS_REPOSICION, 0, -1)]
    hasta = int(ahora.timestamp() * 1000)
    with closing(get_conn()) as conexion:
        conexion.execute("BEGIN")
        reportes = [reporte_de_semana(conexion, lunes, hasta_ms=hasta) for lunes in lunes_del_periodo]
        stock = _stock_disponible(conexion)

    vendido = defaultdict(Decimal)
    semanas_con_venta = defaultdict(set)
    for lunes, reporte in zip(lunes_del_periodo, reportes):
        for compra in reporte["compras"]:
            kg = _kg_vendidos(compra)
            if kg <= 0:
                continue
            material = _material(dict(compra["caracteristicas"], formato=compra["formato"]))
            vendido[material] += kg
            semanas_con_venta[material].add(lunes)

    disponible = defaultdict(Decimal)
    for bulto in stock:
        if bulto["peso_kg"] is not None:
            disponible[_material(dict(bulto))] += Decimal(str(bulto["peso_kg"]))

    filas = []
    for material, kg in vendido.items():
        stock_kg = disponible[material]
        semanas = len(semanas_con_venta[material])
        cobertura = stock_kg / (kg / DIAS_REPOSICION)
        seccion = _seccion(semanas, cobertura, stock_kg)
        if seccion is None:
            continue
        filas.append((cobertura, -kg, str(material), {
            **dict(zip(CAMPOS_MATERIAL, material)),
            "seccion": seccion,
            "vendido_t": round(float(kg / 1000), 3),
            "disponible_t": round(float(stock_kg / 1000), 3),
            "semanas_con_ventas": semanas,
            "cobertura_dias": round(float(cobertura), 1),
            "cumple_filtro": (kg > FILTRO_REPOSICION["vendido_min_t"] * 1000
                              and stock_kg < FILTRO_REPOSICION["stock_max_t"] * 1000),
        }))
    filas.sort(key=lambda fila: fila[:3])
    secciones = {nombre: [] for nombre in SECCIONES_REPOSICION}
    for *_, fila in filas:
        secciones[fila["seccion"]].append(fila)

    return {
        "periodo": {
            "inicio": lunes_del_periodo[0].isoformat(),
            "fin": (actual - timedelta(days=1)).isoformat(),
            "semanas": SEMANAS_REPOSICION,
            "dias": DIAS_REPOSICION,
            "zona_horaria": ZONA_REPORTE.key,
        },
        "stock_a": ahora.isoformat(timespec="seconds"),
        "umbrales": UMBRALES_REPOSICION,
        "filtro": FILTRO_REPOSICION,
        "secciones": secciones,
    }
