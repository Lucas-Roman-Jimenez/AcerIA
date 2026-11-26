"""Registro de compras confirmadas y lectura del reporte semanal."""

from contextlib import closing
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json
import math
import sqlite3
from zoneinfo import ZoneInfo

from app.db import COLUMNAS, get_conn


ZONA_REPORTE = ZoneInfo("Europe/Madrid")
UNIDADES_COMPRA = {"kg", "t", "bultos", "piezas"}


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
