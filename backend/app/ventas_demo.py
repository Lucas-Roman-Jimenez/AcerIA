"""Ventas simuladas para enseñar los reportes (Reposición y Tendencias) sin vender en la demo.

Se crean en cada arranque del backend (salvo `python arrancar.py --sin-ventas-demo`, que pone
ACERIA_VENTAS_DEMO=0): se borran las anteriores y se vuelven a crear con fechas relativas a hoy, así
siempre caen en las últimas 4 semanas completas. Ninguna cae en la semana en curso, de modo que el
reporte semanal solo enseña las ventas reales de la demo. Se reconocen por el prefijo `demo-` en el ID
de la compra y del bulto: los bultos no existen en el inventario, así que `marcar_vendidos` no quita
stock real, y las ventas reales no se tocan.

Las cantidades se calculan a partir del stock disponible de cada referencia para que haya filas en
las tres secciones de Reposición, alguna que pasa el filtro de 2 t y casos que deben quedar fuera.
"""
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta

from app.db import get_conn
from app.reportes import ZONA_REPORTE, registrar_compra
from app.tendencias import DIAS_REPOSICION, _lunes, _material

PREFIJO = "demo-"

# (grupo, posición en el grupo, semanas atrás con ventas (0 = la última completa), cobertura objetivo en días)
# grupo «medio»: 5-20 t de stock; «pequeño»: 1-1,9 t.
ESCENARIOS = [
    ("medio", 0, (0, 1, 2, 3), 2.5),    # reponer
    ("medio", 1, (0, 2), 5),            # reponer, con una venta en toneladas
    ("pequeno", 0, (0, 1, 3), 4),       # reponer y pasa el filtro (> 2 t vendidas, < 2 t de stock)
    ("medio", 3, (0, 1, 2), 8),         # vigilar
    ("medio", 4, (1, 3), 12),           # vigilar
    ("pequeno", 1, (0, 1), 10),         # vigilar y pasa el filtro
    ("medio", 5, (0, 1), 30),           # fuera: cobertura alta
]
PESOS = (1.0, 0.8, 1.2, 0.9)            # reparto entre semanas para que no salgan todas iguales


def quitar_ventas_demo(conexion) -> int:
    return conexion.execute("DELETE FROM compras WHERE id LIKE ?", (f"{PREFIJO}%",)).rowcount


def preparar_ventas_demo(activar: bool) -> int:
    """Al arrancar: las crea de nuevo; con --sin-ventas-demo borra las que quedasen de otra vez."""
    if activar:
        return sembrar_ventas_demo()
    with closing(get_conn()) as conexion, conexion:
        quitar_ventas_demo(conexion)
    return 0


def sembrar_ventas_demo(*, ahora: datetime | None = None) -> int:
    """Sustituye las ventas de demo por unas nuevas relativas a `ahora`. Devuelve cuántas ha creado."""
    ahora = (ahora or datetime.now(ZONA_REPORTE)).astimezone(ZONA_REPORTE)
    lunes_actual = datetime.combine(_lunes(ahora.date()), datetime.min.time(), ZONA_REPORTE)

    with closing(get_conn()) as conexion, conexion:
        quitar_ventas_demo(conexion)
        por_material = defaultdict(list)
        for fila in conexion.execute("SELECT * FROM bultos WHERE estado = 'disponible' ORDER BY id"):
            por_material[_material(dict(fila))].append(dict(fila))
        stock = {m: sum(b["peso_kg"] for b in bultos) for m, bultos in por_material.items()}
        orden = sorted(stock, key=lambda m: (-stock[m], str(m)))
        grupos = {"medio": [m for m in orden if 5000 <= stock[m] <= 20000],
                  "pequeno": [m for m in orden if 1000 <= stock[m] < 1900]}

        contador = 0

        def vender(material, kg, fecha, *, unidad="kg", cantidad=None, **cambios):
            nonlocal contador
            contador += 1
            ident = f"{PREFIJO}{contador}"
            bulto = dict(por_material[material][0], id=ident, peso_kg=round(kg, 1), **cambios)
            registrar_compra(conexion, compra_id=ident, bulto=bulto, comprada_en=fecha, unidad=unidad,
                             cantidad=cantidad if cantidad is not None else round(kg, 1))

        def fecha(semanas_atras, n):
            return lunes_actual - timedelta(weeks=semanas_atras + 1) + timedelta(days=1 + n % 3, hours=9 + n % 6)

        for grupo, posicion, semanas, cobertura in ESCENARIOS:
            if posicion >= len(grupos[grupo]):
                continue
            material = grupos[grupo][posicion]
            total = stock[material] * DIAS_REPOSICION / cobertura
            pesos = PESOS[:len(semanas)]
            for n, (semana, peso) in enumerate(zip(semanas, pesos)):
                kg = total * peso / sum(pesos)
                if grupo == "medio" and posicion == 1 and n == 1:
                    vender(material, kg, fecha(semana, n), unidad="t", cantidad=round(kg / 1000, 3))
                else:
                    vender(material, kg, fecha(semana, n))

        pequenos = grupos["pequeno"]
        if len(pequenos) > 4:
            vender(pequenos[2], 3200, fecha(1, 0))                       # salida puntual, pasa el filtro
            vender(pequenos[3], 800, fecha(2, 1))                        # salida puntual
            vender(pequenos[4], 900, fecha(0, 2), unidad="piezas", cantidad=12)   # piezas: no cuenta
        medios = grupos["medio"]
        if len(medios) > 2:
            # Sin stock: la misma ficha con un ancho que no hay en inventario.
            base = medios[2]
            anchos = {m[4] for m in stock if m[:4] == base[:4]}
            ancho = next(a for a in range(1000, 2100, 10) if float(a) not in anchos)
            for n, semana in enumerate((0, 2)):
                vender(base, 2400, fecha(semana, n), ancho_mm=float(ancho))
    return contador
