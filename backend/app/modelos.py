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
    bultos: Annotated[list[IdBulto], Field(max_length=config.MAX_BULTOS_CARRITO)]


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
