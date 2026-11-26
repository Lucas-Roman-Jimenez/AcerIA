"""Contrato de datos entre el módulo LLM (Nacho) y el backend (Alonso).

Cualquier cambio aquí se avisa a los cuatro antes de tocar código.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# Campos de la especificación, en el orden en que se muestran y se preguntan.
CAMPOS_TEXTO = ("grado", "acabado", "formato")
CAMPOS_NUMERO = ("espesor_mm", "ancho_mm", "largo_mm")
CAMPOS = CAMPOS_TEXTO + CAMPOS_NUMERO + ("cantidad", "uso")


@dataclass
class Cantidad:
    valor: float
    unidad: str  # "kg", "t" o "bultos"


@dataclass
class Especificacion:
    grado: Optional[str] = None
    acabado: Optional[str] = None
    formato: Optional[str] = None
    espesor_mm: Optional[float] = None
    ancho_mm: Optional[float] = None
    largo_mm: Optional[float] = None
    cantidad: Optional[Cantidad] = None
    uso: Optional[str] = None
    # Valores posibles cuando un término es ambiguo: {"acabado": ["BA", "2R"]}.
    # El backend puede buscar con cualquiera de ellos; si el stock real
    # distingue entre ellos, se pregunta después de buscar (RF-05, RF-07).
    opciones: dict[str, list[str]] = field(default_factory=dict)
    # Fuente del catálogo que respalda una traducción por uso (RF-26).
    fuente_uso: Optional[str] = None
    # Campos mínimos para buscar que aún no se conocen.
    faltan: list[str] = field(default_factory=list)
    # Avisos para el usuario: valores descartados, combinaciones inexistentes...
    avisos: list[str] = field(default_factory=list)
    # Campos que el comercial ha dicho que le dan igual («me da igual el acabado»):
    # no se preguntan ni cuentan como «faltan».
    indiferentes: list[str] = field(default_factory=list)

    def tiene(self, campo: str) -> bool:
        """True si el campo tiene valor o hay opciones para él."""
        return getattr(self, campo) is not None or bool(self.opciones.get(campo))

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def desde_dict(cls, d: dict[str, Any]) -> "Especificacion":
        d = dict(d or {})
        cant = d.get("cantidad")
        if isinstance(cant, dict) and cant.get("valor") is not None:
            d["cantidad"] = Cantidad(float(cant["valor"]), str(cant.get("unidad", "kg")))
        else:
            d["cantidad"] = None
        conocidos = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in conocidos})


@dataclass
class ResultadoInterpretacion:
    """Lo que devuelve interpretar().

    tipo = "especificacion": se puede buscar con `especificacion`.
    tipo = "pregunta": hay que mostrar `pregunta` al comercial y esperar su respuesta.
    """
    tipo: str
    especificacion: Especificacion
    pregunta: Optional[str] = None

    def a_dict(self) -> dict[str, Any]:
        return {"tipo": self.tipo, "especificacion": self.especificacion.a_dict(), "pregunta": self.pregunta}
