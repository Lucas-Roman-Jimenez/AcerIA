"""Validación con Pydantic de todo lo que entra en la API (tarea 6).

Mismo enfoque que llm/modelos.py (tarea 3, salida del LLM): forma, tipos y límites con Pydantic.
La diferencia es qué se hace con lo que no cumple: la salida del LLM se limpia campo a campo para no
romper la conversación; una petición a la API mal formada se rechaza con 422 y no se busca nada.

Qué NO se valida aquí, a propósito: que el grado o el acabado existan. Un grado que no hay no es una
petición mal formada sino una petición sin stock, y el frontend lo necesita así (pregunta a
/stock/valores y, si da 0 bultos, marca el dato «sin stock» y ofrece otros). Lo que existe lo decide
el código con el inventario y el catálogo (RNF-02), como hasta ahora.

Los límites están en config.py.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app import config

Formato = Literal["chapa", "bobina", "fleje"]
CampoStock = Literal["grado", "acabado", "formato", "espesor_mm", "ancho_mm"]   # = buscador.CAMPOS_VALORES

Valor = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.MAX_LONGITUD_VALOR)]
IdBulto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.MAX_LONGITUD_ID)]
Espesor = Annotated[float, Field(gt=0, le=config.MAX_ESPESOR_MM)]
Ancho = Annotated[float, Field(gt=0, le=config.MAX_ANCHO_MM)]
Largo = Annotated[float, Field(gt=0, le=config.MAX_LARGO_MM)]

# Cabecera X-Carrito: ID aleatorio del carrito que genera el frontend (k- y 32 hexadecimales).
PATRON_CARRITO = r"^[A-Za-z0-9_-]*$"


class Especificacion(BaseModel):
    """Entrada de POST /buscar: lo que ya se sabe de la petición.

    Los campos que no conoce se ignoran (extra="ignore"): el frontend, la evaluación de Lucas o la
    especificación completa de Nacho (con uso, avisos, cantidad…) siguen funcionando.
    """
    model_config = ConfigDict(extra="ignore")

    grado: Optional[Valor] = None
    acabado: Optional[Valor] = None
    formato: Optional[Formato] = None
    espesor_mm: Optional[Espesor] = None
    ancho_mm: Optional[Ancho] = None
    largo_mm: Optional[Largo] = None
    opciones: dict[Annotated[str, StringConstraints(max_length=20)],
                   Annotated[list[Valor], Field(max_length=config.MAX_OPCIONES)]] = Field(default_factory=dict)

    @field_validator("formato", mode="before")
    @classmethod
    def _formato_en_minusculas(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("opciones")
    @classmethod
    def _pocos_campos(cls, v):
        if len(v) > 6:
            raise ValueError("como mucho 6 campos con opciones")
        return v


class ListaBultos(BaseModel):
    """Entrada de POST /reservas y POST /compras: los IDs del carrito."""
    bultos: Annotated[list[IdBulto], Field(min_length=1, max_length=config.MAX_BULTOS_CARRITO)]


class MensajeChat(BaseModel):
    """Entrada de POST /chat. Acepta «mensaje» (evaluación de Lucas) o «texto» (frontend de Stanis)."""
    conversacion_id: Optional[Annotated[str, StringConstraints(max_length=100, pattern=PATRON_CARRITO)]] = None
    mensaje: Optional[str] = Field(None, max_length=config.MAX_LONGITUD_MENSAJE)
    texto: Optional[str] = Field(None, max_length=config.MAX_LONGITUD_MENSAJE)

    @model_validator(mode="after")
    def _con_texto(self):
        # Sin texto no se llama al LLM (es de pago): una petición vacía no es un mensaje.
        if not (self.mensaje or self.texto or "").strip():
            raise ValueError("falta el mensaje")
        return self

    @property
    def contenido(self) -> str:
        return self.mensaje or self.texto or ""


# ---------- Errores 422: claros, en español y sin repetir lo que se ha enviado ----------

MENSAJE_GENERAL = "Datos no válidos."
_ORIGENES = {"body", "query", "header", "path", "cookie"}
_CABECERAS = {"x-carrito": "X-Carrito"}


def _num(v) -> str:
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def _campo(loc) -> str:
    """('body', 'bultos', 3) -> 'bultos[3]';  ('header', 'x-carrito') -> 'X-Carrito';  ('body',) -> 'cuerpo'."""
    partes = list(loc[1:] if loc and loc[0] in _ORIGENES else loc)
    if loc and loc[0] == "body" and partes and isinstance(partes[0], int):
        return "cuerpo"                                            # JSON mal formado: la posición no es un campo
    texto = ""
    for p in partes:
        texto += f"[{p}]" if isinstance(p, int) else (f".{p}" if texto else str(p))
    return _CABECERAS.get(texto, texto) or "cuerpo"


def _mensaje(error: dict) -> str:
    tipo, ctx = error.get("type", ""), error.get("ctx") or {}
    if tipo == "missing":
        return "es obligatorio"
    if tipo in ("float_parsing", "float_type", "int_parsing", "int_type", "int_from_float", "finite_number"):
        return "debe ser un número"
    if tipo == "greater_than":
        return f"debe ser mayor que {_num(ctx.get('gt'))}"
    if tipo == "greater_than_equal":
        return f"debe ser como mínimo {_num(ctx.get('ge'))}"
    if tipo == "less_than":
        return f"debe ser menor que {_num(ctx.get('lt'))}"
    if tipo == "less_than_equal":
        return f"debe ser como máximo {_num(ctx.get('le'))}"
    if tipo == "string_too_short":
        return "no puede estar vacío"
    if tipo == "string_too_long":
        return f"como mucho {ctx.get('max_length')} caracteres"
    if tipo == "too_short":
        return "no puede estar vacío" if ctx.get("min_length") == 1 else f"como mínimo {ctx.get('min_length')} elementos"
    if tipo == "too_long":
        return f"como mucho {ctx.get('max_length')} elementos"
    if tipo == "literal_error":
        return f"debe ser uno de: {str(ctx.get('expected', '')).replace(' or ', ', ')}"
    if tipo == "string_pattern_mismatch":
        return "solo admite letras, números, guiones y guiones bajos"
    if tipo == "string_type":
        return "debe ser un texto"
    if tipo == "list_type":
        return "debe ser una lista"
    if tipo in ("dict_type", "model_type", "model_attributes_type"):
        return "debe ser un objeto JSON"
    if tipo == "json_invalid":
        return "el JSON no es válido"
    if tipo == "value_error" and ctx.get("error"):
        return str(ctx["error"])                                   # nuestros propios mensajes (p. ej. «falta el mensaje»)
    return "no es válido"


def errores_legibles(errores: list[dict]) -> list[dict]:
    """Errores de Pydantic -> [{campo, mensaje}]. Nunca incluye el valor recibido ni enlaces internos."""
    vistos, salida = set(), []
    for e in errores:
        par = (_campo(tuple(e.get("loc", ()))), _mensaje(e))
        if par not in vistos:
            vistos.add(par)
            salida.append({"campo": par[0], "mensaje": par[1]})
    return salida
