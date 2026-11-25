from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import crear_db, disponibles
from app.buscador import CAMPOS_VALORES, buscar_bultos, construir_objetivo, valores_disponibles


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_db()          # crea la base de datos al arrancar (RNF-12)
    yield


app = FastAPI(title="Asistente de inventario AcerIA", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class MensajeChat(BaseModel):
    conversacion_id: str | None = None
    mensaje: str | None = None      # formato de Alonso y de la evaluación de Lucas
    texto: str | None = None        # formato del frontend de Stanis (docs/contrato.md §6)


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


# ---------- respuestas FALSAS para que Stanis monte el frontend ----------
EXACTO = {"id": "1312", "grado": "304L/304", "acabado": "2B", "formato": "chapa",
          "espesor_mm": 2.0, "ancho_mm": 1250, "largo_mm": 2500, "peso_kg": 1118}

TRANSFORMABLE = {
    "bulto": {"id": "334", "grado": "304L/304", "acabado": "2B", "formato": "bobina",
              "espesor_mm": 2.0, "ancho_mm": 1500, "largo_mm": None, "peso_kg": 745},
    "acciones": ["Cortar bobina 2 × 1500 mm a chapa 2 × 1250 × 2500 mm"],
    "resultado": {"formato": "chapa", "acabado": "2B", "espesor_mm": 2.0,
                  "ancho_mm": 1250, "largo_mm": 2500, "piezas": 12},
    "merma_kg": 152.5, "merma_pct": 20.5, "num_operaciones": 1, "merma_estimada": True, "avisos": [],
}


def respuesta_base(conv_id: str | None) -> dict:
    return {
        "conversacion_id": conv_id or "demo-1",
        "estado": "resultados",
        "especificacion": {"grado": "304", "acabado": None, "formato": "chapa",
                           "espesor_mm": 2.0, "ancho_mm": 1250, "largo_mm": 2500, "faltan": []},
        "exactos": [], "transformables": [], "alternativas": [],
        "pregunta": None, "opciones": [],
        "texto": "", "criterio_orden": "exactos > % de merma > nº de operaciones",
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
def chat(m: MensajeChat):
    r = respuesta_base(m.conversacion_id)
    texto = (m.mensaje or m.texto or "").lower()

    if "error" in texto:
        r["estado"] = "error"
        r["texto"] = "No he podido procesar la petición. Inténtalo de nuevo o escríbela."
    elif "sin stock" in texto:
        r["estado"] = "sin_stock"
        r["texto"] = "No hay bultos disponibles ni transformables para esa petición."
    elif "2b" in texto:
        r["especificacion"]["acabado"] = "2B"
        r["exactos"] = [EXACTO]
        r["transformables"] = [TRANSFORMABLE]
        r["texto"] = "Tengo 1 bulto que cumple y 1 bobina que se puede cortar a medida."
    elif texto.strip() == "ba":
        r["estado"] = "sin_stock"
        r["especificacion"]["acabado"] = "BA"
        r["texto"] = "No hay 304 BA de 2 × 1250 × 2500 disponible ni transformable."
    else:
        r["estado"] = "pregunta"
        r["especificacion"]["faltan"] = ["acabado"]
        r["pregunta"] = "Tengo 304 de 2 mm en 2B y en BA, ¿cuál necesitas?"
        r["opciones"] = ["2B", "BA"]
        r["texto"] = r["pregunta"]
    return compatibilizar(r)

@app.post("/buscar")
def buscar(espec: dict):
    objetivo = construir_objetivo(espec)
    exactos, transformables = buscar_bultos(objetivo)
    return {
        "estado": "resultados" if exactos or transformables else "sin_stock",
        "objetivo": objetivo,
        "exactos": exactos, "transformables": transformables, "alternativas": [],
        "criterio_orden": "exactos > % de merma > nº de operaciones",
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
