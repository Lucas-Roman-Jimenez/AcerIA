import os
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import Literal
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.db import crear_db, disponibles
from app.buscador import CAMPOS_VALORES, CRITERIO_ORDEN, buscar_alternativas, buscar_bultos, construir_objetivo, valores_disponibles
from app.conversacion import cargar_env, responder_chat
from app.ventas import BultosNoDisponibles, vender
from app.reservas import liberar, liberar_todas, mis_reservas, reservar
from app.reportes import reporte_diario_inventario, reporte_semanal
from app.modelos import (MENSAJE_GENERAL, PATRON_CARRITO, CampoStock, Especificacion, Formato, ListaBultos,
                         MensajeChat, errores_legibles)
from app.tendencias import recomendaciones_reposicion, tendencias_compras
from app.ventas_demo import preparar_ventas_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea la base de datos al arrancar (RNF-12). Conserva ventas y reporte salvo que se pida
    # reiniciar la demo (python arrancar.py --reiniciar-demo pone ACERIA_REINICIAR_DEMO=1).
    crear_db(reiniciar_ventas=os.getenv("ACERIA_REINICIAR_DEMO") == "1")
    # Ventas simuladas para los reportes; python arrancar.py --sin-ventas-demo pone ACERIA_VENTAS_DEMO=0.
    if creadas := preparar_ventas_demo(os.getenv("ACERIA_VENTAS_DEMO", "1") != "0"):
        print(f"✔ {creadas} ventas simuladas (demo-*) para los reportes")
    cargar_env()        # clave y modelo del LLM desde el .env de la raíz (RNF-13)
    yield


log = logging.getLogger("aceria")

app = FastAPI(title="Asistente de inventario AcerIA", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGENES,   # nunca "*": otra web podría vender bultos
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-Carrito"])


@app.exception_handler(RequestValidationError)
async def datos_no_validos(request: Request, exc: RequestValidationError):
    """Tarea 6: todo 422 de validación con el mismo formato, en español y sin repetir lo enviado.
    {"detail": "Datos no válidos.", "errores": [{"campo": "espesor_mm", "mensaje": "debe ser mayor que 0"}]}"""
    return JSONResponse(status_code=422,
                        content={"detail": MENSAJE_GENERAL, "errores": errores_legibles(exc.errors())})


def compatibilizar(r: dict) -> dict:
    """Añade los campos que usa el frontend de Stanis sin quitar los que usa la evaluación de Lucas.
    estado (pregunta | resultados | sin_stock | error)  ->  tipo (pregunta | respuesta | error) + error."""
    r["tipo"] = {"pregunta": "pregunta", "error": "error"}.get(r["estado"], "respuesta")
    r["error"] = r["texto"] if r["estado"] == "error" else None
    for t in r.get("transformables", []):
        t.setdefault("id", t["bulto"]["id"])           # Stanis usa la clave id
        t.setdefault("bulto_id", t["bulto"]["id"])     # el motor de Lucas usa bulto_id
        t.setdefault("origen", t["bulto"])             # Stanis pinta el «antes» desde origen
    return r


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/reportes/compras/semanal")
def obtener_reporte_semanal():
    return reporte_semanal()


@app.get("/reportes/inventario/diario")
def obtener_reporte_diario_inventario():
    return reporte_diario_inventario()


@app.get("/reportes/compras/tendencias")
def obtener_tendencias_compras(
    semanas: int = Query(default=8, ge=1, le=52),
    unidad: Literal["kg", "bultos", "piezas"] = "kg",
):
    return tendencias_compras(semanas, unidad)


@app.get("/reportes/reposicion")
def obtener_reposicion():
    return recomendaciones_reposicion()


def titular_actual(x_carrito: str = Header("", max_length=100, pattern=PATRON_CARRITO)) -> str:
    """Quién reserva y vende: el ID aleatorio de carrito que el frontend manda en la cabecera X-Carrito.
    No hay login (la tarea 5 no se hace); si algún día lo hay, solo cambia esta función."""
    return x_carrito.strip()


@app.post("/compras")
def comprar(v: ListaBultos, titular: str = Depends(titular_actual)):
    """Vende (simulado) los bultos del carrito: pasan a «vendido» y aparecen en el reporte semanal.
    Solo se venden los bultos reservados por el titular (tarea 4)."""
    try:
        return vender(v.bultos, titular)
    except BultosNoDisponibles as e:
        raise HTTPException(409, {"mensaje": "Algún bulto no está reservado a tu nombre o ya no está disponible; "
                                             "no se ha vendido nada.",
                                  "no_disponibles": e.ids})
    except ValueError as e:
        log.info("Venta rechazada: %s", e)                 # el detalle, al log; al cliente, un texto fijo
        raise HTTPException(422, "El carrito está vacío o no es válido.")


# ---------- Reservas del carrito (tarea 4): que dos comerciales no cojan el mismo bulto ----------

def _sin_titular() -> HTTPException:
    return HTTPException(422, "Falta la cabecera X-Carrito.")


@app.post("/reservas")
def crear_reserva(r: ListaBultos, titular: str = Depends(titular_actual)):
    """Al añadir al carrito: reserva los bultos (todos o ninguno) durante config.RESERVA_MINUTOS.
    Si ya eran del titular, renueva la caducidad. 409 si alguno lo tiene otro o ya no está disponible."""
    if not titular:
        raise _sin_titular()
    try:
        return {"reservas": reservar(r.bultos, titular), "minutos": config.RESERVA_MINUTOS}
    except BultosNoDisponibles as e:
        raise HTTPException(409, {"mensaje": "Algún bulto ya está reservado o no está disponible; "
                                             "no se ha reservado nada.", "no_disponibles": e.ids})
    except ValueError as e:
        log.info("Reserva rechazada: %s", e)
        raise HTTPException(422, "No hay bultos que reservar.")


@app.get("/reservas")
def listar_reservas(titular: str = Depends(titular_actual)):
    """Reservas vigentes del titular, para rehacer el carrito si se recarga la página."""
    if not titular:
        raise _sin_titular()
    return {"reservas": mis_reservas(titular), "minutos": config.RESERVA_MINUTOS}


@app.delete("/reservas/{bulto_id}", status_code=204)
def quitar_reserva(bulto_id: str = Path(min_length=1, max_length=config.MAX_LONGITUD_ID), titular: str = Depends(titular_actual)):
    """Al quitar un bulto del carrito: vuelve a estar disponible. 404 si no es una reserva del titular."""
    if not titular:
        raise _sin_titular()
    if not liberar(bulto_id, titular):
        raise HTTPException(404, "Ese bulto no está en tu carrito.")


@app.delete("/reservas")
def vaciar_reservas(titular: str = Depends(titular_actual)):
    """Vaciar el carrito: libera todas las reservas del titular (las de otros no se tocan)."""
    if not titular:
        raise _sin_titular()
    return {"liberadas": liberar_todas(titular)}


@app.post("/chat")
def chat(m: MensajeChat):
    """Conversación real: módulo LLM + buscar_bultos() (exactos y transformables), en app/conversacion.py."""
    return compatibilizar(responder_chat(m.conversacion_id, m.contenido))


@app.post("/buscar")
def buscar(espec: Especificacion):
    """Exactos, transformables y, si no hay ninguno, alternativas (RF-29). La entrada se valida con
    Pydantic (app/modelos.py): medidas positivas y con límite, formato permitido, textos acotados."""
    if isinstance(espec, dict):                       # llamada directa (tests y evaluación): misma validación
        espec = Especificacion.model_validate(espec)
    objetivo = construir_objetivo(espec.model_dump())
    exactos, transformables = buscar_bultos(objetivo)
    alternativas = [] if exactos or transformables else buscar_alternativas(objetivo)   # RF-29
    return {
        "estado": "resultados" if exactos or transformables else "sin_stock",
        "objetivo": objetivo,
        "exactos": exactos, "transformables": transformables, "alternativas": alternativas,
        "criterio_orden": CRITERIO_ORDEN,
    }


@app.get("/stock/valores")
def stock_valores(campo: CampoStock,
                  grado: str | None = Query(None, min_length=1, max_length=config.MAX_LONGITUD_VALOR),
                  acabado: str | None = Query(None, min_length=1, max_length=config.MAX_LONGITUD_VALOR),
                  formato: Formato | None = None,
                  espesor_mm: float | None = Query(None, gt=0, le=config.MAX_ESPESOR_MM),
                  ancho_mm: float | None = Query(None, gt=0, le=config.MAX_ANCHO_MM)):
    """Valores reales de un campo en el stock disponible, filtrado por lo que ya se sabe.
    Ejemplo: /stock/valores?campo=espesor_mm&grado=304 -> grosores de 304 que hay ahora.
    Un grado o acabado que no existe no es un error: da 0 bultos (el frontend lo marca «sin stock»)."""
    filtros = {k: v for k, v in {"grado": grado, "acabado": acabado, "formato": formato,
                                 "espesor_mm": espesor_mm, "ancho_mm": ancho_mm}.items() if v is not None}
    valores = valores_disponibles(campo, filtros)
    return {"campo": campo, "filtros": filtros, "valores": valores,
            "total_bultos": sum(v["bultos"] for v in valores)}


@app.get("/stock/resumen")
def stock_resumen(limite: int = Query(12, ge=1, le=config.MAX_LIMITE_RESUMEN)):
    """Cinta de stock de la cabecera del frontend: grupos de bultos disponibles por grado, acabado y formato."""
    grupos: dict[str, dict] = {}
    for b in disponibles():
        etiqueta = f"{b['aisi'] or b['euronorma']} {b['acabado']} · {b['formato']}"
        g = grupos.setdefault(etiqueta, {"etiqueta": etiqueta, "bultos": 0, "toneladas": 0.0})
        g["bultos"] += 1
        g["toneladas"] += b["peso_kg"] / 1000
    resumen = sorted(grupos.values(), key=lambda g: g["toneladas"], reverse=True)[:limite]
    for g in resumen:
        g["toneladas"] = round(g["toneladas"], 1)
    return resumen
