"""Validación con Pydantic de la salida del LLM (la extracción en JSON).

Primera capa: forma y tipos. Lo que no tenga la forma esperada se descarta campo a campo y nunca
rompe la conversación (RNF-14): un campo mal formado no invalida los demás.
Segunda capa, en interprete._validar(): que los valores existan en el catálogo, combinaciones,
usos y ambigüedades. Esa necesita los datos de AcerIA y la decide el código (RNF-02).
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, ValidationError, field_validator

from .contrato import CAMPOS_NUMERO, CAMPOS_TEXTO

CampoEspecificacion = Literal["grado", "acabado", "formato", "espesor_mm", "ancho_mm", "largo_mm"]


def _numero(v: Any) -> Optional[float]:
    """'2,5' -> 2.5. None si no es un número positivo."""
    if isinstance(v, bool):
        return None
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def _textos(valores: Any) -> list[str]:
    """Lista de textos: los elementos que no son texto o número se descartan."""
    return [str(x) for x in valores if isinstance(x, (str, int, float)) and not isinstance(x, bool)]


class CantidadLLM(BaseModel):
    valor: PositiveFloat
    unidad: Literal["kg", "t", "bultos"]

    @field_validator("valor", mode="before")
    @classmethod
    def _valor(cls, v):
        return _numero(v)


class ContradiccionLLM(BaseModel):
    campo: str
    valores: list[Any] = Field(default_factory=list)


class Extraccion(BaseModel):
    """Lo que devuelve el LLM según prompts.ESQUEMA_EXTRACCION, ya con tipos seguros."""
    model_config = ConfigDict(extra="ignore")

    grado: Optional[str] = None
    acabado: Optional[str] = None
    formato: Optional[str] = None
    espesor_mm: Optional[PositiveFloat] = None
    ancho_mm: Optional[PositiveFloat] = None
    largo_mm: Optional[PositiveFloat] = None
    cantidad: Optional[CantidadLLM] = None
    uso: Optional[str] = None
    opciones: dict[str, list[str]] = Field(default_factory=dict)
    indiferentes: list[CampoEspecificacion] = Field(default_factory=list)
    contradicciones: list[ContradiccionLLM] = Field(default_factory=list)
    intencion: Optional[str] = None
    fuera_de_tema: bool = False
    campo_aclaracion: Optional[str] = None

    @classmethod
    def desde_llm(cls, bruto: Any) -> "Extraccion":
        """Valida el JSON del LLM. Los valores de texto que llegan como lista pasan a opciones."""
        bruto = dict(bruto) if isinstance(bruto, dict) else {}
        opciones = bruto.get("opciones") if isinstance(bruto.get("opciones"), dict) else {}
        opciones = {c: ([v] if isinstance(v, str) else v) for c, v in opciones.items() if isinstance(v, (list, str))}
        for campo in CAMPOS_TEXTO:
            if isinstance(bruto.get(campo), list):    # varios valores en el campo: se tratan como opciones
                opciones.setdefault(campo, bruto.pop(campo))
        bruto["opciones"] = {c: _textos(v) for c, v in opciones.items()}
        try:
            return cls.model_validate(bruto)
        except ValidationError:                        # no debería pasar: los validadores ya limpian
            return cls()

    @field_validator(*CAMPOS_TEXTO, mode="before")
    @classmethod
    def _texto(cls, v):
        if v in (None, "") or isinstance(v, bool) or not isinstance(v, (str, int, float)):
            return None
        return str(v)

    @field_validator(*CAMPOS_NUMERO, mode="before")
    @classmethod
    def _medida(cls, v):
        return _numero(v)

    @field_validator("cantidad", mode="before")
    @classmethod
    def _cantidad(cls, v):
        try:
            return CantidadLLM.model_validate(v) if isinstance(v, dict) else None
        except ValidationError:
            return None

    @field_validator("uso", "intencion", "campo_aclaracion", mode="before")
    @classmethod
    def _solo_texto(cls, v):
        return v if isinstance(v, str) else None

    @field_validator("fuera_de_tema", mode="before")
    @classmethod
    def _booleano(cls, v):
        return v is True

    @field_validator("indiferentes", mode="before")
    @classmethod
    def _indiferentes(cls, v):
        campos = CAMPOS_TEXTO + CAMPOS_NUMERO
        return [c for c in v if isinstance(c, str) and c in campos] if isinstance(v, list) else []

    @field_validator("contradicciones", mode="before")
    @classmethod
    def _contradicciones(cls, v):
        if not isinstance(v, list):
            return []
        return [c for c in v if isinstance(c, dict) and isinstance(c.get("campo"), str)
                and isinstance(c.get("valores", []), list)]
