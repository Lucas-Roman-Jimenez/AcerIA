"""Genera compras simuladas y arranca una instancia aislada de AcerIA."""

import argparse
from contextlib import closing
from datetime import datetime, time, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parent
SALIDA = CARPETA / "generados"
BASE_DEMO = SALIDA / "inventario-demo.db"

sys.path.insert(0, str(RAIZ / "backend"))

from app import config
from app.db import crear_db, get_conn
from app.reportes import ZONA_REPORTE, reporte_diario_inventario, reporte_semanal
from app.reservas import reservar
from app.tendencias import tendencias_compras
from app.ventas import vender


def simular_compras(ahora: datetime) -> None:
    plan = json.loads((CARPETA / "plan_compras.json").read_text(encoding="utf-8"))
    lunes_actual = ahora.date() - timedelta(days=ahora.weekday())

    # Publicar la base solo si se completaron todas las ventas.
    with TemporaryDirectory(dir=SALIDA) as temporal:
        config.DB_PATH = Path(temporal) / BASE_DEMO.name
        crear_db()
        for posicion, ids in enumerate(plan):
            fecha = lunes_actual - timedelta(weeks=len(plan) - 1 - posicion)
            inicio = min(datetime.combine(fecha, time(9), ZONA_REPORTE), ahora)
            fin = min(inicio + timedelta(days=4, hours=7), ahora)
            for orden, bulto_id in enumerate(ids, 1):
                momento = inicio + (fin - inicio) * orden / (len(ids) + 1)
                reservar([bulto_id], "demo-reportes", ahora=momento)
                vender([bulto_id], "demo-reportes", ahora=momento)
        config.DB_PATH.replace(BASE_DEMO)


def guardar_json(nombre: str, datos: dict) -> None:
    (SALIDA / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preparar_demo() -> None:
    ahora = datetime.now(ZONA_REPORTE)
    SALIDA.mkdir(exist_ok=True)
    if not BASE_DEMO.exists():
        simular_compras(ahora)
    config.DB_PATH = BASE_DEMO
    with closing(get_conn()) as conexion:
        filas = conexion.execute(
            "SELECT comprada_en_ms, material_json, cantidad, unidad FROM compras ORDER BY comprada_en_ms, id",
        ).fetchall()
    guardar_json("compras-simuladas.json", {
        "simulacion": True,
        "compras": [
            {"fecha": datetime.fromtimestamp(fila["comprada_en_ms"] / 1000, ZONA_REPORTE).isoformat(),
             "material": json.loads(fila["material_json"]), "cantidad": fila["cantidad"], "unidad": fila["unidad"]}
            for fila in filas
        ],
    })
    guardar_json("reporte-diario.json", {"simulacion": True, **reporte_diario_inventario(ahora=ahora)})
    guardar_json("reporte-semanal.json", {"simulacion": True, **reporte_semanal(ahora=ahora)})
    guardar_json("tendencias-compras.json", {"simulacion": True, **tendencias_compras(8, "kg", ahora=ahora)})
    print(f"Demo de reportes: {len(filas)} compras simuladas en {SALIDA}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solo-generar", action="store_true", help="generar la base y los archivos JSON")
    parser.add_argument("--sin-navegador", action="store_true")
    args = parser.parse_args()
    preparar_demo()
    if args.solo_generar:
        return 0
    comando = [sys.executable, str(RAIZ / "arrancar.py"), "--puerto-backend", "8011", "--puerto-frontend", "5174"]
    if args.sin_navegador:
        comando.append("--sin-navegador")
    return subprocess.call(comando, cwd=RAIZ, env={**os.environ, "ACERIA_DB_PATH": str(BASE_DEMO)})


if __name__ == "__main__":
    raise SystemExit(main())
