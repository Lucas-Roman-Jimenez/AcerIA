"""Normaliza la hoja DATA conservando los encabezados y textos del Excel."""

import argparse
import json
import math
import re
from pathlib import Path

from openpyxl import load_workbook


COLUMNAS_NUMERICAS = (
    "ID", "Weight", "Gauge", "Gauge Min", "Gauge Max", "Width", "Quantity",
    "Lenght (Solo para chapas)",
)
NUMERO_LOCAL = re.compile(r"[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")


def normalizar_numero(valor):
    if isinstance(valor, str):
        valor = valor.strip()
        if valor in ("", "-"):
            return None
        if not NUMERO_LOCAL.fullmatch(valor):
            raise ValueError(f"Número con formato inesperado: {valor!r}")
        valor = float(valor.replace(".", "").replace(",", "."))
    if valor is None:
        return None
    if type(valor) not in (int, float) or not math.isfinite(valor):
        raise ValueError(f"Número no válido: {valor!r}")
    return int(valor) if valor == int(valor) else valor


def leer_inventario(origen):
    libro = load_workbook(origen, read_only=True, data_only=True)
    try:
        filas = libro["DATA"].values
        encabezados = next(filas, ())
        faltantes = set(COLUMNAS_NUMERICAS).difference(encabezados)
        if faltantes:
            raise ValueError(f"Faltan columnas en DATA: {', '.join(sorted(faltantes))}")
        ids = set()
        bultos = []
        for indice, fila in enumerate(filas, start=2):
            if all(valor is None for valor in fila):
                continue
            registro = dict(zip(encabezados, fila, strict=True))
            try:
                for columna in COLUMNAS_NUMERICAS:
                    registro[columna] = normalizar_numero(registro[columna])
                identificador = registro["ID"]
                if type(identificador) is not int or identificador <= 0:
                    raise ValueError(f"ID no válido: {identificador!r}")
                if identificador in ids:
                    raise ValueError(f"ID duplicado: {identificador}")
            except ValueError as error:
                raise ValueError(f"DATA, fila {indice}: {error}") from error
            ids.add(identificador)
            bultos.append(registro)
        return {"bultos": bultos}
    finally:
        libro.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origen", type=Path, help="Excel de stock con hoja DATA")
    parser.add_argument("destino", type=Path, help="Ruta de salida JSON")
    args = parser.parse_args()
    if args.origen.resolve() == args.destino.resolve():
        parser.error("La ruta de salida debe ser distinta del Excel de origen.")
    inventario = leer_inventario(args.origen)
    args.destino.write_text(
        json.dumps(inventario, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"{len(inventario['bultos'])} registros en {args.destino}")


if __name__ == "__main__":
    main()
