"""Registro de compras confirmadas y lectura del reporte semanal."""

from contextlib import closing
from datetime import datetime, time, timedelta, timezone
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


def reporte_semanal(*, ahora: datetime | None = None) -> dict:
    fecha_local = (ahora or datetime.now(ZONA_REPORTE)).astimezone(ZONA_REPORTE).date()
    inicio = fecha_local - timedelta(days=fecha_local.weekday())
    siguiente = inicio + timedelta(days=7)
    limites = [
        int(datetime.combine(fecha, time.min, ZONA_REPORTE).timestamp() * 1000)
        for fecha in (inicio, siguiente)
    ]
    with closing(get_conn()) as conexion:
        filas = conexion.execute(
            """SELECT id, comprada_en_ms, material_json, cantidad, unidad FROM compras
               WHERE comprada_en_ms >= ? AND comprada_en_ms < ?
               ORDER BY comprada_en_ms DESC, id""",
            limites,
        ).fetchall()

    compras = []
    for fila in filas:
        material = json.loads(fila["material_json"])
        formato = material.get("formato")
        compras.append({
            "id": fila["id"],
            "fecha_compra": datetime.fromtimestamp(fila["comprada_en_ms"] / 1000, timezone.utc).isoformat(),
            "nombre_material": f"{formato.capitalize()} de acero inoxidable" if formato else "Acero inoxidable",
            "caracteristicas": material,
            "cantidad_sustraida": {"valor": fila["cantidad"], "unidad": fila["unidad"]},
        })
    return {
        "titulo": "Reporte semanal de compras",
        "semana": {
            "inicio": inicio.isoformat(),
            "fin": (siguiente - timedelta(days=1)).isoformat(),
            "zona_horaria": ZONA_REPORTE.key,
        },
        "compras": compras,
    }
