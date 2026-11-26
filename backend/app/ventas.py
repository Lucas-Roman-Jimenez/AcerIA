"""Venta de los bultos del carrito (simulación para la demo: no toca los sistemas de AcerIA).

Al reiniciar se conserva lo vendido y el reporte. Para empezar la demo de cero:
python arrancar.py --reiniciar-demo (vacía las compras y el inventario vuelve a estar completo).

Cada bulto vendido se registra en `compras` con registrar_compra() de Lucas (lo lee el reporte semanal)
y pasa a estado «vendido», así deja de salir en /buscar, /chat y /stock. Todo en una sola transacción:
o se venden todos los bultos del carrito o ninguno.

Venta estricta (tarea 4): solo se vende lo que el titular tiene reservado y vigente (app/reservas.py).
Al vender se borran esas reservas.
"""
from __future__ import annotations

import uuid
from contextlib import closing
from datetime import datetime

from app.db import get_conn
from app.reportes import ZONA_REPORTE, registrar_compra


class BultosNoDisponibles(Exception):
    """Algún bulto del carrito no existe o ya no está disponible: no se vende nada."""

    def __init__(self, ids: list[str]):
        self.ids = ids
        super().__init__(f"Bultos no disponibles: {', '.join(ids)}")


def vender(bulto_ids: list[str], titular: str, *, ahora: datetime | None = None) -> dict:
    ids = list(dict.fromkeys(str(i).strip() for i in bulto_ids if str(i).strip()))
    if not ids:
        raise ValueError("El carrito está vacío.")
    titular = (titular or "").strip()
    if not titular:
        raise ValueError("Falta el titular del carrito.")
    ahora = ahora or datetime.now(ZONA_REPORTE)
    ahora_ms = int(ahora.timestamp() * 1000)

    with closing(get_conn()) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")      # bloquea escrituras: nadie vende el mismo bulto a la vez
            marcas = ",".join("?" * len(ids))
            filas = {f["id"]: dict(f) for f in conn.execute(f"SELECT * FROM bultos WHERE id IN ({marcas})", ids)}
            mias = {f[0] for f in conn.execute(                 # reservas vigentes del titular (venta estricta)
                f"SELECT bulto_id FROM reservas WHERE bulto_id IN ({marcas}) AND titular = ? AND expira_en_ms > ?",
                [*ids, titular, ahora_ms])}
            no_disponibles = [i for i in ids
                              if i not in filas or filas[i]["estado"] != "disponible" or i not in mias]
            if no_disponibles:
                raise BultosNoDisponibles(no_disponibles)

            compras = []
            for i in ids:
                bulto = filas[i]
                compra_id = uuid.uuid4().hex
                registrar_compra(conn, compra_id=compra_id, bulto=bulto, cantidad=bulto["peso_kg"],
                                 unidad="kg", comprada_en=ahora)
                conn.execute("UPDATE bultos SET estado = 'vendido' WHERE id = ?", (i,))
                compras.append({"compra_id": compra_id, "bulto_id": i,
                                "cantidad": {"valor": bulto["peso_kg"], "unidad": "kg"}})
            conn.execute(f"DELETE FROM reservas WHERE bulto_id IN ({marcas})", ids)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return {"vendidos": ids, "compras": compras}
