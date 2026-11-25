from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import crear_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_db()          # crea la base de datos al arrancar (RNF-12)
    yield


app = FastAPI(title="Asistente de inventario AcerIA", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class MensajeChat(BaseModel):
    conversacion_id: str | None = None
    mensaje: str


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
    texto = m.mensaje.lower()

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
    return r