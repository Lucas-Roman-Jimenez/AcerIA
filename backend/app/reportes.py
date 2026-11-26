"""Reportes de compras confirmadas e inventario."""

from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
import math
import sqlite3
from zoneinfo import ZoneInfo

from app.db import COLUMNAS, get_conn, grados
from llm.catalogo import Catalogo


ZONA_REPORTE = ZoneInfo("Europe/Madrid")
UNIDADES_COMPRA = {"kg", "t", "bultos", "piezas"}


def _clave_producto(formato: str, acabado: str, grado: str) -> tuple[str, str, str]:
    return formato.casefold(), acabado.casefold(), grado.casefold()


def _medida_en_catalogo(limites, medida: float) -> bool:
    return limites is None or limites[0] <= medida <= limites[1]


def _productos_del_bulto(bulto, por_clave):
    for grado in grados(bulto):
        clave = _clave_producto(bulto["formato"], bulto["acabado"], grado)
        for indice, producto in por_clave.get(clave, ()):
            if (_medida_en_catalogo(producto.get("espesor_mm"), bulto["espesor_mm"])
                    and _medida_en_catalogo(producto.get("ancho_mm"), bulto["ancho_mm"])):
                yield indice


def _texto_medida(limites) -> str:
    if limites is None:
        return "-"
    extremos = [format(Decimal(str(n)).normalize(), "f") for n in limites]
    return extremos[0] if extremos[0] == extremos[1] else f"{extremos[0]}–{extremos[1]}"


def _material_agotado(producto: dict, catalogo: Catalogo, fecha_agotado: str | None) -> dict:
    formato, grado, acabado = (producto[campo] for campo in ("formato", "grado", "acabado"))
    espesor = _texto_medida(producto.get("espesor_mm"))
    ancho = _texto_medida(producto.get("ancho_mm"))
    nombre_grado = catalogo.etiqueta_en(grado) if grado.startswith("1.") and grado[2:].isdigit() else grado
    medidas = [f"{v.replace('.', ',')} mm {etiqueta}"
               for v, etiqueta in ((espesor, "de espesor"), (ancho, "de ancho")) if v != "-"]
    return {
        "id": "|".join((formato, grado, acabado, espesor, ancho)),
        "nombre": " · ".join([f"{formato.capitalize()} de acero inoxidable {nombre_grado}", acabado, *medidas]),
        "fecha_sin_stock": fecha_agotado,
    }


def reporte_diario_inventario(*, ahora: datetime | None = None, catalogo: Catalogo | None = None) -> dict:
    """Combinaciones del catálogo sin unidades físicas y última baja acreditada por compras."""
    momento = (ahora or datetime.now(ZONA_REPORTE)).astimezone(ZONA_REPORTE)
    catalogo = catalogo if catalogo is not None else Catalogo.cargar()
    productos = catalogo.productos
    por_clave = defaultdict(list)
    for indice, producto in enumerate(productos):
        clave = _clave_producto(producto["formato"], producto["acabado"], producto["grado"])
        por_clave[clave].append((indice, producto))

    with closing(get_conn()) as conexion:
        conexion.execute("BEGIN")
        bultos = conexion.execute(
            "SELECT id, aisi, euronorma, acabado, formato, espesor_mm, ancho_mm, estado FROM bultos"
        ).fetchall()
        compras = conexion.execute(
            "SELECT material_json, comprada_en_ms FROM compras WHERE comprada_en_ms <= ?",
            (int(momento.timestamp() * 1000),),
        ).fetchall()

    con_stock = set()
    vendidos_por_producto = defaultdict(set)
    ids_actuales = set()
    for bulto in bultos:
        ids_actuales.add(bulto["id"])
        indices = _productos_del_bulto(bulto, por_clave)
        if bulto["estado"] == "vendido":
            for indice in indices:
                vendidos_por_producto[indice].add(bulto["id"])
        else:
            con_stock.update(indices)

    bajas = {}
    for compra in compras:
        bulto = json.loads(compra["material_json"])
        id_bulto = bulto["id"]
        bajas[id_bulto] = max(bajas.get(id_bulto, compra["comprada_en_ms"]), compra["comprada_en_ms"])
        # El inventario de origen puede haber dejado de incluir un bulto ya vendido.
        if id_bulto not in ids_actuales and all(bulto.get(campo) is not None for campo in
                                                ("formato", "acabado", "espesor_mm", "ancho_mm")):
            for indice in _productos_del_bulto(bulto, por_clave):
                vendidos_por_producto[indice].add(id_bulto)

    materiales = []
    for indice, producto in enumerate(productos):
        if indice in con_stock:
            continue
        ids_vendidos = vendidos_por_producto[indice]
        fecha_agotado = None
        if ids_vendidos and ids_vendidos <= bajas.keys():
            ultimo_ms = max(bajas[id_bulto] for id_bulto in ids_vendidos)
            fecha_agotado = datetime.fromtimestamp(ultimo_ms / 1000, ZONA_REPORTE).date().isoformat()
        materiales.append(_material_agotado(producto, catalogo, fecha_agotado))
    return {
        "titulo": "Reporte diario",
        "fecha": momento.date().isoformat(),
        "materiales_sin_stock": materiales,
    }


def registrar_compra(
    conexion: sqlite3.Connection, *, compra_id: str, bulto: dict,
    cantidad: float, unidad: str, comprada_en: datetime,
) -> None:
    """Guarda el bulto anterior a la baja dentro de la transacción del llamador."""
    if not compra_id or not bulto.get("id"):
        raise ValueError("La compra y el bulto deben tener identificador.")
    if unidad not in UNIDADES_COMPRA or not math.isfinite(cantidad) or cantidad <= 0:
        raise ValueError("Indica una cantidad positiva y una unidad de compra válida.")
    if comprada_en.utcoffset() is None:
        raise ValueError("La fecha de compra debe incluir zona horaria.")
    material = {campo: bulto.get(campo) for campo in COLUMNAS}
    conexion.execute(
        """INSERT INTO compras (id, comprada_en_ms, material_json, cantidad, unidad)
           VALUES (?, ?, ?, ?, ?)""",
        (compra_id, int(comprada_en.timestamp() * 1000),
         json.dumps(material, ensure_ascii=False, allow_nan=False), cantidad, unidad),
    )


def reporte_de_semana(conexion: sqlite3.Connection, inicio: date, *, hasta_ms: int) -> dict:
    """Construye el mismo reporte exportable para cualquier lunes del historial."""
    siguiente = inicio + timedelta(days=7)
    limites = [
        int(datetime.combine(fecha, time.min, ZONA_REPORTE).timestamp() * 1000)
        for fecha in (inicio, siguiente)
    ]
    filas = conexion.execute(
        """SELECT material_json, cantidad, unidad FROM compras
           WHERE comprada_en_ms >= ? AND comprada_en_ms < ? AND comprada_en_ms <= ?
           ORDER BY comprada_en_ms DESC, id""",
        (*limites, hasta_ms),
    ).fetchall()

    compras = {}
    cantidades = {}
    for fila in filas:
        material = json.loads(fila["material_json"])
        bulto_id = material["id"]
        unidad = fila["unidad"]
        totales = cantidades.setdefault(bulto_id, {})
        totales[unidad] = totales.get(unidad, Decimal(0)) + Decimal(str(fila["cantidad"]))
        if bulto_id in compras:
            continue
        formato = material.get("formato")
        caracteristicas = {
            "id": material["id"],
            "grado": material.get("aisi") or material.get("euronorma"),
            "acabado": material.get("acabado"),
            "espesor_mm": material.get("espesor_mm"),
            "ancho_mm": material.get("ancho_mm"),
            "peso_kg": material.get("peso_kg"),
        }
        if material.get("largo_mm") is not None:
            caracteristicas["largo_mm"] = material["largo_mm"]
        compras[bulto_id] = {
            "nombre_material": f"{formato.capitalize()} de acero inoxidable" if formato else "Acero inoxidable",
            "formato": formato,
            "caracteristicas": caracteristicas,
        }
    for bulto_id, compra in compras.items():
        compra["cantidades_sustraidas"] = [
            {"valor": float(valor), "unidad": unidad}
            for unidad, valor in sorted(cantidades[bulto_id].items())
        ]
    return {
        "titulo": "Reporte semanal de compras",
        "semana": {
            "inicio": inicio.isoformat(),
            "fin": (siguiente - timedelta(days=1)).isoformat(),
            "zona_horaria": ZONA_REPORTE.key,
        },
        "compras": list(compras.values()),
    }


def reporte_semanal(*, ahora: datetime | None = None) -> dict:
    ahora = (ahora or datetime.now(ZONA_REPORTE)).astimezone(ZONA_REPORTE)
    fecha_local = ahora.date()
    inicio = fecha_local - timedelta(days=fecha_local.weekday())
    with closing(get_conn()) as conexion:
        return reporte_de_semana(conexion, inicio, hasta_ms=int(ahora.timestamp() * 1000))
