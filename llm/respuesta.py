"""responder(): resultado del backend -> texto para el comercial (RF-15, RF-16, RNF-01).

El texto del LLM se acepta solo si no añade cifras, valores del catálogo ni bultos
que no estén en el resultado. Si no, o si el LLM falla, se usa una plantilla.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from . import prompts
from .catalogo import Catalogo
from .contrato import CAMPOS_NUMERO, Especificacion
from .control import fmt_num, lista_y, no_inventa
from .proveedores import ClienteLLM, ErrorLLM

_ID = re.compile(r"\b[A-Z]{1,4}-\d{2,}\b")


def _id(b: dict[str, Any]) -> str:
    """ID del bulto. El backend de Alonso pone los transformables como {"bulto": {"id": ...}, ...}."""
    return str(b.get("id") or (b.get("bulto") or {}).get("id") or "?")


def _caracteristicas(b: dict[str, Any], con_formato: bool = False) -> list[str]:
    partes = []
    claves = ("formato", "grado", "acabado") if con_formato else ("grado", "acabado")
    tipo = " ".join(str(b[k]) for k in claves if b.get(k))
    if tipo:
        partes.append(tipo)
    medidas = [fmt_num(b[k]) for k in ("espesor_mm", "ancho_mm", "largo_mm") if b.get(k)]
    if medidas:
        partes.append(" × ".join(medidas) + " mm")
    if b.get("peso_kg"):
        partes.append(f"{fmt_num(b['peso_kg'])} kg")
    if b.get("piezas"):
        partes.append(f"{fmt_num(b['piezas'])} pieza{'' if b['piezas'] == 1 else 's'}")
    if b.get("ubicacion"):
        partes.append(str(b["ubicacion"]))
    return partes


def _describir_bulto(b: dict[str, Any]) -> str:
    partes = _caracteristicas(b)
    return f"{_id(b)} ({', '.join(partes)})" if partes else _id(b)


def _describir_transformable(t: dict[str, Any]) -> str:
    """Acepta {"id": ..., "acciones": ...} y el formato del backend {"bulto": {...}, "acciones": ...}."""
    detalle = []
    if isinstance(t.get("bulto"), dict) and _caracteristicas(t["bulto"], con_formato=True):
        detalle.append(", ".join(_caracteristicas(t["bulto"], con_formato=True)))  # antes (RF-20)
    # El motor de Lucas devuelve cada acción como {"regla", "descripcion", "parametros", ...}; antes eran textos.
    detalle += [a.get("descripcion") or a.get("regla") or "" if isinstance(a, dict) else str(a)
                for a in (t.get("acciones") or [])]
    if t.get("merma_kg") is not None:
        pct = f" ({fmt_num(t['merma_pct'])} %)" if t.get("merma_pct") is not None else ""
        detalle.append(f"merma {fmt_num(t['merma_kg'])} kg{pct}")
    if isinstance(t.get("resultado"), dict) and _caracteristicas(t["resultado"], con_formato=True):
        detalle.append("queda " + ", ".join(_caracteristicas(t["resultado"], con_formato=True)))  # RF-13
    return f"{_id(t)} ({'; '.join(detalle)})" if detalle else _id(t)


MAX_EN_TEXTO = 5  # el texto (y la lectura en voz alta) nombra como mucho 5; las tarjetas reciben todos


def _lista(items: list[dict[str, Any]], describir) -> str:
    texto = "; ".join(describir(b) for b in items[:MAX_EN_TEXTO])
    resto = len(items) - MAX_EN_TEXTO
    return texto + (f"; y {resto} más (ver las tarjetas)" if resto > 0 else "")


def plantilla(resultado: dict[str, Any]) -> str:
    exactos = resultado.get("exactos") or []
    transf = resultado.get("transformables") or []
    alts = resultado.get("alternativas") or []
    frases = []
    if exactos:
        n = len(exactos)
        frases.append(f"{'Hay 1 bulto que cumple' if n == 1 else f'Hay {n} bultos que cumplen'} la petición: "
                      + _lista(exactos, _describir_bulto) + ".")
    if transf:
        inicio = "También se pueden adaptar" if exactos else "No hay ningún bulto que cumpla directamente, pero se pueden adaptar"
        frases.append(f"{inicio}: " + _lista(transf, _describir_transformable) + ".")
    if not exactos and not transf:
        frases.append("No hay stock que cumpla la petición ni bultos que se puedan transformar para cumplirla.")
        if alts:
            frases.append("Como alternativa, sin cumplir exactamente lo pedido, hay: "
                          + _lista(alts, _describir_bulto) + ".")
    return " ".join(frases)


def _nota_cantidad(exactos: list[dict[str, Any]], especificacion: Especificacion | dict | None) -> str:
    """Frase calculada por el código si lo que cumple no llega a la cantidad pedida (RF-04)."""
    if not exactos or especificacion is None:
        return ""
    esp = especificacion if isinstance(especificacion, Especificacion) else Especificacion.desde_dict(especificacion)
    cant = esp.cantidad
    if cant is None:
        return ""
    if cant.unidad == "bultos":
        if len(exactos) < cant.valor:
            n = len(exactos)
            return f"Pides {fmt_num(cant.valor)} bultos y hay {n} que {'cumple' if n == 1 else 'cumplen'}."
    elif all(b.get("peso_kg") for b in exactos):
        pedido_kg = cant.valor * (1000 if cant.unidad == "t" else 1)
        total = sum(b["peso_kg"] for b in exactos)
        if total < pedido_kg:
            return f"Pides {fmt_num(cant.valor)} {cant.unidad} y lo que cumple suma {fmt_num(total)} kg."
    return ""


_NOMBRE = {"grado": "el grado", "acabado": "el acabado", "formato": "el formato",
           "espesor_mm": "el espesor", "ancho_mm": "el ancho", "largo_mm": "el largo"}


def _fmt_valor(campo: str, v: Any) -> str:
    return f"{fmt_num(v)} mm" if campo in CAMPOS_NUMERO else str(v)


def _stock(n: int, kg: float, por_kg: bool) -> str:
    bultos = f"{n} bulto{'s' if n != 1 else ''}"
    return f"{fmt_num(round(kg))} kg, {bultos}" if por_kg else (f"{bultos}, {fmt_num(round(kg))} kg" if kg else bultos)


def _nota_recomendacion(resultado: dict[str, Any], esp: Optional[Especificacion]) -> str:
    """Si al comercial le da igual un dato y el stock tiene varios valores, recomienda uno (calculado por el código).

    Criterio: por kg si el pedido viene en kg o t; si no, por número de bultos. El otro desempata.
    Se cuentan los exactos; si no hay, los transformables (el valor que queda tras transformar).
    No cambia el orden de las tarjetas (RF-14).
    """
    if esp is None or not esp.indiferentes:
        return ""
    bultos = resultado.get("exactos") or []
    if bultos:
        filas = [(b, b.get("peso_kg") or 0) for b in bultos]
    else:
        filas = [(t.get("resultado") or t.get("bulto") or t, (t.get("bulto") or t).get("peso_kg") or 0)
                 for t in resultado.get("transformables") or []]
    por_kg = esp.cantidad is not None and esp.cantidad.unidad in ("kg", "t")
    frases = []
    for campo in esp.indiferentes:
        if campo not in _NOMBRE:
            continue
        cuenta: dict[Any, list[float]] = {}
        for b, kg in filas:
            if b.get(campo) is not None:
                n_kg = cuenta.setdefault(b[campo], [0, 0.0])
                n_kg[0] += 1
                n_kg[1] += float(kg)
        if len(cuenta) < 2:
            continue
        orden = sorted(cuenta.items(), key=lambda it: ((-it[1][1], -it[1][0]) if por_kg else (-it[1][0], -it[1][1]),
                                                       str(it[0])))
        (mejor, (n, kg)), resto = orden[0], orden[1:]
        motivo = "más peso" if por_kg else "más stock"
        otros = [f"{_fmt_valor(campo, v)} ({_stock(o_n, o_kg, por_kg)})" for v, (o_n, o_kg) in resto[:3]]
        if len(resto) > 3:
            otros.append(f"{len(resto) - 3} más")
        frases.append(f"Te da igual {_NOMBRE[campo]}: te recomiendo {_fmt_valor(campo, mejor)}, el que {motivo} "
                      f"tiene ({_stock(n, kg, por_kg)}). También hay {lista_y(otros)}.")
    return " ".join(frases)


def _nota_uso(esp: Optional[Especificacion], catalogo: Optional[Catalogo]) -> str:
    """Cita el catálogo cuando la petición se tradujo por uso (RF-26). Nunca sale del LLM."""
    if esp is None or not esp.uso:
        return ""
    if catalogo is None:
        from .interprete import _catalogo_defecto  # evita import circular
        catalogo = _catalogo_defecto()
    uso = catalogo.uso(esp.uso)
    if not uso:
        return ""
    fuente = f" (fuente: {esp.fuente_uso})" if esp.fuente_uso else ""
    return f"Para {uso['uso']}, el catálogo indica {lista_y(uso['grados'])}{fuente}."


def _nota_uso_desconocido(esp: Optional[Especificacion]) -> str:
    """Si el comercial dio un uso que el catálogo no respalda, se dice en el texto (no solo en el panel).
    Si el uso sí está en el catálogo, ya lo cita _nota_uso."""
    if esp is None:
        return ""
    return " ".join(a for a in esp.avisos if a.startswith("El catálogo no indica qué grado"))


def _nota_criterio(resultado: dict[str, Any]) -> str:
    """Criterio de ordenación que manda el backend (RNF-09). Solo si hay 2 o más propuestas que ordenar."""
    if len(resultado.get("exactos") or []) + len(resultado.get("transformables") or []) < 2:
        return ""
    criterio = str(resultado.get("criterio") or resultado.get("criterio_orden") or "").strip().rstrip(".")
    return f"Orden: {criterio}." if criterio else ""


def _con_nota(texto: str, *notas: str) -> str:
    return " ".join([texto, *[n for n in notas if n]])


def _texto_valido(texto: str, resultado: dict[str, Any], fuente: Any, catalogo: Catalogo) -> bool:
    ids = {_id(b) for k in ("exactos", "transformables", "alternativas") for b in resultado.get(k) or []}
    if not texto or not no_inventa(texto, fuente, catalogo):
        return False
    # Los IDs reales son números («1343»): se buscan como palabra completa, no como trozo de otro número.
    if not all(re.search(rf"(?<![\w.,]){re.escape(i)}(?![\w]|[.,]\d)", texto) for i in ids):
        return False  # se ha dejado algún bulto
    if set(_ID.findall(texto)) - ids:
        return False  # ha inventado un identificador con letras (los números inventados los frena no_inventa)
    if resultado.get("alternativas") and not (resultado.get("exactos") or resultado.get("transformables")):
        if "alternativ" not in texto.lower():
            return False  # las alternativas deben presentarse como tales
    return True


def responder(resultado: dict[str, Any], especificacion: Especificacion | dict | None = None, *,
              cliente: Optional[ClienteLLM] = None, catalogo: Optional[Catalogo] = None,
              usar_llm: bool = False) -> str:
    """resultado: {"exactos": [...], "transformables": [...], "alternativas": [...], "criterio": "..."} del backend.

    Por defecto usa siempre la plantilla: instantánea, igual en cada demo y sin riesgo de inventar (RNF-01, RNF-05).
    Con usar_llm=True, si hay 2 o más bultos, el LLM redacta el texto y se valida; si falla, plantilla.
    Al final se añaden frases calculadas por el código: fuente del uso, criterio de orden y cantidad.
    Nunca lanza excepción.
    """
    texto_plantilla = plantilla(resultado)
    esp_obj = (especificacion if isinstance(especificacion, Especificacion)
               else Especificacion.desde_dict(especificacion) if especificacion else None)
    notas = (_nota_recomendacion(resultado, esp_obj), _nota_uso(esp_obj, catalogo), _nota_uso_desconocido(esp_obj),
             _nota_criterio(resultado),
             _nota_cantidad(resultado.get("exactos") or [], especificacion))
    total = sum(len(resultado.get(k) or []) for k in ("exactos", "transformables", "alternativas"))
    if not usar_llm or total <= 1:
        return _con_nota(texto_plantilla, *notas)

    from .interprete import _catalogo_defecto, _cliente_defecto  # evita import circular
    catalogo = catalogo or _catalogo_defecto()
    try:
        cliente = cliente or _cliente_defecto()
        if cliente is None:
            return _con_nota(texto_plantilla, *notas)
        esp = especificacion.a_dict() if isinstance(especificacion, Especificacion) else (especificacion or {})
        usuario = prompts.USUARIO_RESPUESTA.format(
            especificacion=json.dumps(esp, ensure_ascii=False),
            resultado=json.dumps(resultado, ensure_ascii=False))
        texto = cliente.completar(prompts.SISTEMA_RESPUESTA, usuario, max_tokens=400).strip()
    except ErrorLLM:
        return _con_nota(texto_plantilla, *notas)
    fuente = {"especificacion": esp, "resultado": resultado, "plantilla": texto_plantilla}
    return _con_nota(texto if _texto_valido(texto, resultado, fuente, catalogo) else texto_plantilla, *notas)
