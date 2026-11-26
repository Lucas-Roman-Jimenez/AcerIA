"""Reservas del carrito (tarea 4): que dos comerciales no cojan el mismo bulto.

Al añadir un bulto al carrito se reserva para su titular durante config.RESERVA_MINUTOS. Mientras la
reserva esté vigente nadie más puede reservarlo ni venderlo; al quitarlo del carrito o al caducar vuelve
a estar disponible. Las reservas caducadas no se borran con un proceso aparte: se ignoran al leer
(expira_en_ms > ahora) y se borran en la siguiente escritura.

Todo en BEGIN IMMEDIATE, como ventas.py: si dos peticiones reservan el mismo bulto a la vez, la segunda
espera a que termine la primera y ve su reserva. Además, bulto_id es la clave de la tabla reservas.

El titular es la cabecera X-Carrito (un ID aleatorio que genera el frontend; no hay login). Si algún
día lo hay, el titular será el usuario y este módulo no cambia.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta

from app import config
from app.db import get_conn
from app.reportes import ZONA_REPORTE
from app.ventas import BultosNoDisponibles


class DemasiadasReservas(Exception):
    """El carrito pasaría de config.MAX_RESERVAS_CARRITO bultos reservados: no se reserva nada."""


def _ms(momento: datetime) -> int:
    return int(momento.timestamp() * 1000)


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, ZONA_REPORTE).isoformat(timespec="seconds")


def _limpiar_ids(bulto_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(str(i).strip() for i in bulto_ids if str(i).strip()))


def _comprobar_titular(titular: str) -> str:
    titular = (titular or "").strip()
    if not titular:
        raise ValueError("Falta el titular de la reserva.")
    return titular


def reservar(bulto_ids: list[str], titular: str, *, ahora: datetime | None = None) -> list[dict]:
    """Reserva los bultos para el titular: o todos o ninguno.

    Si un bulto ya es del titular, renueva la caducidad. Lanza BultosNoDisponibles con los que no
    existen, no están disponibles o tienen una reserva vigente de otro titular, y DemasiadasReservas si el
    carrito pasaría de config.MAX_RESERVAS_CARRITO bultos reservados.
    """
    titular = _comprobar_titular(titular)
    ids = _limpiar_ids(bulto_ids)
    if not ids:
        raise ValueError("No hay bultos que reservar.")
    ahora_ms = _ms(ahora or datetime.now(ZONA_REPORTE))
    expira_ms = ahora_ms + config.RESERVA_MINUTOS * 60_000
    marcas = ",".join("?" * len(ids))

    with closing(get_conn()) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")   # bloquea escrituras: dos reservas del mismo bulto no se cruzan
            conn.execute("DELETE FROM reservas WHERE expira_en_ms <= ?", (ahora_ms,))
            estados = dict(conn.execute(f"SELECT id, estado FROM bultos WHERE id IN ({marcas})", ids).fetchall())
            de_otros = {f[0] for f in conn.execute(
                f"SELECT bulto_id FROM reservas WHERE bulto_id IN ({marcas}) AND titular <> ?", [*ids, titular])}
            no_disponibles = [i for i in ids if estados.get(i) != "disponible" or i in de_otros]
            if no_disponibles:
                raise BultosNoDisponibles(no_disponibles)
            # Límite por carrito: las que ya tiene más las nuevas (renovar las propias no suma).
            mias = {f[0] for f in conn.execute("SELECT bulto_id FROM reservas WHERE titular = ?", (titular,))}
            if len(mias | set(ids)) > config.MAX_RESERVAS_CARRITO:
                raise DemasiadasReservas()

            conn.executemany(
                "INSERT INTO reservas (bulto_id, titular, creada_en_ms, expira_en_ms) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (bulto_id) DO UPDATE SET expira_en_ms = excluded.expira_en_ms",
                [(i, titular, ahora_ms, expira_ms) for i in ids],
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return [{"bulto_id": i, "expira_en": _iso(expira_ms)} for i in ids]


def liberar(bulto_id: str, titular: str) -> bool:
    """Quita un bulto del carrito. Solo el titular puede liberar su reserva; False si no era suya."""
    titular = _comprobar_titular(titular)
    with closing(get_conn()) as conn, conn:
        borradas = conn.execute("DELETE FROM reservas WHERE bulto_id = ? AND titular = ?",
                                (str(bulto_id).strip(), titular)).rowcount
    return borradas > 0


def liberar_todas(titular: str) -> int:
    """Vacía el carrito del titular. Devuelve cuántas reservas se han liberado."""
    titular = _comprobar_titular(titular)
    with closing(get_conn()) as conn, conn:
        return conn.execute("DELETE FROM reservas WHERE titular = ?", (titular,)).rowcount


def mis_reservas(titular: str, *, ahora: datetime | None = None) -> list[dict]:
    """Reservas vigentes del titular, en el orden en que se añadieron (para rehacer el carrito)."""
    titular = _comprobar_titular(titular)
    ahora_ms = _ms(ahora or datetime.now(ZONA_REPORTE))
    with closing(get_conn()) as conn:
        filas = conn.execute(
            "SELECT bulto_id, expira_en_ms FROM reservas WHERE titular = ? AND expira_en_ms > ? "
            "ORDER BY creada_en_ms, rowid", (titular, ahora_ms)).fetchall()
    return [{"bulto_id": f["bulto_id"], "expira_en": _iso(f["expira_en_ms"])} for f in filas]
