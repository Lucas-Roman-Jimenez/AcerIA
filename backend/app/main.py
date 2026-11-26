import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import config
from app.db import crear_db, disponibles
from app.buscador import CAMPOS_VALORES, CRITERIO_ORDEN, buscar_alternativas, buscar_bultos, construir_objetivo, valores_disponibles
from app.conversacion import cargar_env, responder_chat
from app.ventas import BultosNoDisponibles, vender
from app.reportes import reporte_semanal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea la base de datos al arrancar (RNF-12). Conserva ventas y reporte salvo que se pida
    # reiniciar la demo (python arrancar.py --reiniciar-demo pone ACERIA_REINICIAR_DEMO=1).
    crear_db(reiniciar_ventas=os.getenv("ACERIA_REINICIAR_DEMO") == "1")
    cargar_env()        # clave y modelo del LLM desde el .env de la raíz (RNF-13)
    yield


log = logging.getLogger("aceria")

app = FastAPI(title="Asistente de inventario AcerIA", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGENES,   # nunca "*": otra web podría vender bultos
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class MensajeChat(BaseModel):
    conversacion_id: str | None = Field(None, max_length=100)
    mensaje: str | None = Field(None, max_length=config.MAX_LONGITUD_MENSAJE)   # formato de Alonso y de la evaluación de Lucas
    texto: str | None = Field(None, max_length=config.MAX_LONGITUD_MENSAJE)     # formato del frontend de Stanis (docs/contrato.md §6)


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


class Venta(BaseModel):
    bultos: list[str]               # IDs de los bultos del carrito


@app.post("/compras")
def comprar(v: Venta):
    """Vende (simulado) los bultos del carrito: pasan a «vendido» y aparecen en el reporte semanal."""
    try:
        return vender(v.bultos)
    except BultosNoDisponibles as e:
        raise HTTPException(409, {"mensaje": "Algún bulto ya no está disponible; no se ha vendido nada.",
                                  "no_disponibles": e.ids})
    except ValueError as e:
        log.info("Venta rechazada: %s", e)                 # el detalle, al log; al cliente, un texto fijo
        raise HTTPException(422, "El carrito está vacío o no es válido.")


@app.post("/chat")
def chat(m: MensajeChat):
    """Conversación real: módulo LLM + buscar_bultos() (exactos y transformables), en app/conversacion.py."""
    return compatibilizar(responder_chat(m.conversacion_id, m.mensaje or m.texto or ""))


@app.post("/buscar")
def buscar(espec: dict):
    objetivo = construir_objetivo(espec)
    exactos, transformables = buscar_bultos(objetivo)
    alternativas = [] if exactos or transformables else buscar_alternativas(objetivo)   # RF-29
    return {
        "estado": "resultados" if exactos or transformables else "sin_stock",
        "objetivo": objetivo,
        "exactos": exactos, "transformables": transformables, "alternativas": alternativas,
        "criterio_orden": CRITERIO_ORDEN,
    }


@app.get("/stock/valores")
def stock_valores(campo: str, grado: str | None = None, acabado: str | None = None,
                  formato: str | None = None, espesor_mm: float | None = None, ancho_mm: float | None = None):
    """Valores reales de un campo en el stock disponible, filtrado por lo que ya se sabe.
    Ejemplo: /stock/valores?campo=espesor_mm&grado=304 -> grosores de 304 que hay ahora."""
    if campo not in CAMPOS_VALORES:
        raise HTTPException(422, f"campo debe ser uno de: {', '.join(CAMPOS_VALORES)}")
    filtros = {k: v for k, v in {"grado": grado, "acabado": acabado, "formato": formato,
                                 "espesor_mm": espesor_mm, "ancho_mm": ancho_mm}.items() if v is not None}
    valores = valores_disponibles(campo, filtros)
    return {"campo": campo, "filtros": filtros, "valores": valores,
            "total_bultos": sum(v["bultos"] for v in valores)}


@app.get("/stock/resumen")
def stock_resumen(limite: int = 12):
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
