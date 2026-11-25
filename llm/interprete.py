"""interpretar(): conversación -> especificación validada o pregunta (RF-04 a RF-09, RF-26).
pregunta_tras_busqueda(): pregunta solo por el dato que distingue el stock real (RF-07).

Reparto de responsabilidades:
- El LLM interpreta la petición y elige qué dato aclarar cuando hay varias opciones.
- El código valida los datos y genera las preguntas a partir del catálogo y del stock.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Optional, Sequence

from . import prompts
from .catalogo import Catalogo
from .contrato import CAMPOS_NUMERO, CAMPOS_TEXTO, Cantidad, Especificacion, ResultadoInterpretacion
from .control import fmt_num, lista_y, no_inventa
from .proveedores import ClienteLLM, ErrorLLM, crear_cliente

# Datos mínimos para poder buscar. PENDIENTE DE CONFIRMAR CON EL MENTOR.
CAMPOS_MINIMOS: tuple[str, ...] = ("grado", "espesor_mm")

NOMBRE_CAMPO = {"grado": "grado", "acabado": "acabado", "formato": "formato", "espesor_mm": "espesor",
                "ancho_mm": "ancho", "largo_mm": "largo"}

_cliente: Optional[ClienteLLM] = None
_catalogo: Optional[Catalogo] = None


def _cliente_defecto() -> ClienteLLM:
    global _cliente
    _cliente = _cliente or crear_cliente()
    return _cliente


def _catalogo_defecto() -> Catalogo:
    global _catalogo
    _catalogo = _catalogo or Catalogo.cargar()
    return _catalogo


# ------------------------------------------------------------------ extracción

def _conversacion(historial: Sequence[dict[str, str]]) -> str:
    rol = {"comercial": "Comercial", "asistente": "Asistente"}
    return "\n".join(f'{rol.get(m.get("rol"), m.get("rol"))}: {m.get("texto", "")}' for m in historial)


def _parsear_json(texto: str) -> dict[str, Any]:
    texto = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.M).strip()
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini < 0 or fin < 0:
        raise ValueError("no hay JSON")
    return json.loads(texto[ini:fin + 1])


def _extraer(historial, cliente: ClienteLLM, catalogo: Catalogo, minimos: Sequence[str]) -> dict[str, Any]:
    sistema = prompts.SISTEMA_EXTRACCION.format(
        catalogo=catalogo.resumen_para_prompt(), minimos=", ".join(minimos) or "ninguno",
    )
    usuario = prompts.USUARIO_EXTRACCION.format(conversacion=_conversacion(historial))
    ultimo_error = None
    for _ in range(2):  # un reintento si el JSON llega mal formado
        texto = cliente.completar(sistema, usuario, json=True)
        try:
            return _parsear_json(texto)
        except (ValueError, json.JSONDecodeError) as e:
            ultimo_error = e
            usuario += "\n\nTu respuesta anterior no era un JSON válido. Devuelve solo el JSON."
    raise ErrorLLM(f"El LLM no devolvió un JSON válido: {ultimo_error}")


# ------------------------------------------------------------------ validación

def _num(v) -> Optional[float]:
    try:
        x = float(str(v).replace(",", "."))
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def _validar(bruto: dict[str, Any], catalogo: Catalogo) -> tuple[Especificacion, dict[str, Any]]:
    """Devuelve la especificación limpia y los problemas detectados (para decidir la pregunta)."""
    esp = Especificacion()
    problemas: dict[str, Any] = {"invalidos": [], "contradiccion": None, "combinacion": None,
                                 "uso_desconocido": None, "opciones_dudosas": None,
                                 "fuera_de_tema": bool(bruto.get("fuera_de_tema"))}

    for campo in CAMPOS_TEXTO:
        v = bruto.get(campo)
        if v in (None, ""):
            continue
        norm = catalogo.normalizar(campo, v)
        if norm:
            setattr(esp, campo, norm)
        else:
            problemas["invalidos"].append((campo, str(v)))
            esp.avisos.append(f"«{v}» no es un {NOMBRE_CAMPO[campo]} del catálogo.")

    for campo in CAMPOS_NUMERO:
        x = _num(bruto.get(campo))
        if x is not None:
            setattr(esp, campo, x)

    cant = bruto.get("cantidad")
    if isinstance(cant, dict) and _num(cant.get("valor")) and cant.get("unidad") in ("kg", "t", "bultos"):
        esp.cantidad = Cantidad(_num(cant["valor"]), cant["unidad"])

    for campo, valores in (bruto.get("opciones") or {}).items():
        if campo not in CAMPOS_TEXTO or getattr(esp, campo) is not None:
            continue
        validos = [n for n in dict.fromkeys(catalogo.normalizar(campo, v) for v in valores or []) if n]
        for v in valores or []:
            if not catalogo.normalizar(campo, v):
                esp.avisos.append(f"«{v}» no es un {NOMBRE_CAMPO[campo]} del catálogo.")
        # La ambigüedad tiene que venir del glosario, no del LLM (RF-05).
        if len(validos) > 1 and not catalogo.ambiguedad_valida(campo, validos):
            problemas["opciones_dudosas"] = (campo, validos)
            esp.avisos.append(f"No tengo claro qué {NOMBRE_CAMPO[campo]} necesitas.")
            continue
        if len(validos) == 1:
            setattr(esp, campo, validos[0])
        elif validos:
            esp.opciones[campo] = validos

    # Uso (RF-26): solo se traduce a grados si el catálogo lo respalda.
    uso_txt = bruto.get("uso")
    if uso_txt:
        uso = catalogo.uso(uso_txt)
        if uso:
            esp.uso = uso["uso"]
            esp.fuente_uso = uso.get("fuente")
            if esp.grado and not catalogo.grado_indicado_para_uso(esp.grado, uso["grados"]):
                esp.avisos.append(f"Según el catálogo, para {uso['uso']} se indican {lista_y(uso['grados'])}.")
            if esp.grado is None and "grado" not in esp.opciones:
                grados = [g for g in uso["grados"] if g in catalogo.grados]
                if len(grados) == 1:
                    esp.grado = grados[0]
                elif grados:
                    esp.opciones["grado"] = grados
        else:
            problemas["uso_desconocido"] = str(uso_txt)
            esp.avisos.append(f"El catálogo no indica qué grado es adecuado para «{uso_txt}».")

    contr = [c for c in (bruto.get("contradicciones") or []) if isinstance(c, dict) and c.get("campo")]
    if contr:
        problemas["contradiccion"] = contr[0]
        if contr[0]["campo"] in CAMPOS_TEXTO + CAMPOS_NUMERO:
            setattr(esp, contr[0]["campo"], None)

    if catalogo.validar_combinaciones and not problemas["invalidos"]:
        _recortar_opciones(esp, catalogo)
        problemas["combinacion"] = _comprobar_combinacion(esp, catalogo)
        if problemas["combinacion"]:
            esp.avisos.append(problemas["combinacion"]["aviso"])
    return esp, problemas


def _candidatos(esp: Especificacion, campo: str) -> list[Optional[str]]:
    if getattr(esp, campo) is not None:
        return [getattr(esp, campo)]
    return list(esp.opciones.get(campo) or [None])


def _hay_combinacion(esp: Especificacion, catalogo: Catalogo, ignorar: str = "") -> bool:
    for g in ([None] if ignorar == "grado" else _candidatos(esp, "grado")):
        for a in ([None] if ignorar == "acabado" else _candidatos(esp, "acabado")):
            for f in ([None] if ignorar == "formato" else _candidatos(esp, "formato")):
                if catalogo.productos_compatibles(
                        g, a, f,
                        None if ignorar == "espesor_mm" else esp.espesor_mm,
                        None if ignorar == "ancho_mm" else esp.ancho_mm):
                    return True
    return False


def _fijar(esp: Especificacion, campo: str, valor: str) -> Especificacion:
    """Copia de la especificación con `campo` fijado a `valor` y sin opciones para él."""
    opciones = {c: v for c, v in esp.opciones.items() if c != campo}
    return replace(esp, opciones=opciones, **{campo: valor})


def _recortar_opciones(esp: Especificacion, catalogo: Catalogo) -> None:
    """Quita de opciones los valores que no forman ninguna combinación del catálogo con el resto de datos."""
    for campo in list(esp.opciones):
        posibles = [v for v in esp.opciones[campo] if _hay_combinacion(_fijar(esp, campo, v), catalogo)]
        if not posibles:
            continue  # lo detecta y lo explica _comprobar_combinacion
        descartados = [v for v in esp.opciones[campo] if v not in posibles]
        if descartados:
            esp.avisos.append(f"Descarto {lista_y(descartados)}: no existe en el catálogo con el resto de datos.")
        if len(posibles) == 1:
            setattr(esp, campo, posibles[0])
            del esp.opciones[campo]
        else:
            esp.opciones[campo] = posibles


def _comprobar_combinacion(esp: Especificacion, catalogo: Catalogo) -> Optional[dict[str, Any]]:
    """None si la combinación existe. Si no, indica qué campo la hace imposible y qué hay disponible."""
    if _hay_combinacion(esp, catalogo):
        return None
    for campo in ("espesor_mm", "ancho_mm", "acabado", "formato", "grado"):
        if not esp.tiene(campo) or not _hay_combinacion(esp, catalogo, ignorar=campo):
            continue
        prods = [p for p in catalogo.productos
                 if all(getattr(esp, c) in (None, p.get(c)) or c == campo for c in CAMPOS_TEXTO)]
        if campo in CAMPOS_NUMERO:
            rangos = [p[campo] for p in prods if campo in p]
            if not rangos:
                continue
            lo, hi = min(r[0] for r in rangos), max(r[1] for r in rangos)
            disp = f"entre {fmt_num(lo)} y {fmt_num(hi)} mm"
        else:
            disponibles = sorted({p[campo] for p in prods})
            if not disponibles:
                continue
            disp = lista_y(disponibles)
        actual = getattr(esp, campo)
        actual_txt = f"{fmt_num(actual)} mm" if campo in CAMPOS_NUMERO else (actual or lista_y(esp.opciones[campo]))
        return {"campo": campo, "disponible": disp,
                "aviso": f"Con esos datos no hay {NOMBRE_CAMPO[campo]} {actual_txt} en el catálogo; "
                         f"existe {disp}."}
    return {"campo": None, "disponible": "", "aviso": "Esa combinación no existe en el catálogo."}


# ------------------------------------------------------------------ preguntas

def _describir(esp: Especificacion, sin: str = "") -> str:
    partes = []
    if esp.formato and sin != "formato":
        partes.append(esp.formato)
    if esp.grado and sin != "grado":
        partes.append(esp.grado)
    if esp.espesor_mm and sin != "espesor_mm":
        partes.append(f"de {fmt_num(esp.espesor_mm)} mm")
    if esp.acabado and sin != "acabado":
        partes.append(f"en {esp.acabado}")
    return " ".join(partes) or "material"


def _plantilla_previa(esp: Especificacion, problemas: dict[str, Any], catalogo: Catalogo,
                      minimos: Sequence[str], campo_aclaracion: object) -> Optional[str]:
    """Pregunta ANTES de buscar, o None si ya se puede buscar."""
    # Se calcula siempre, aunque se pregunte por otra cosa, para el panel del frontend (RF-18).
    esp.faltan = [c for c in minimos if not esp.tiene(c)]
    if problemas["fuera_de_tema"]:
        return "Solo puedo ayudarte a buscar material en el inventario. ¿Qué necesita tu cliente?"
    if problemas["contradiccion"]:
        c = problemas["contradiccion"]
        vals = [fmt_num(v) + " mm" if c["campo"] in CAMPOS_NUMERO else str(v) for v in c.get("valores", [])]
        return f"Has indicado {lista_y(vals)} de {NOMBRE_CAMPO.get(c['campo'], c['campo'])}. ¿Cuál de los dos necesitas?"
    if problemas["invalidos"]:
        campo, valor = problemas["invalidos"][0]
        ejemplos = lista_y(catalogo.valores(campo)[:4], "")
        return f"No encuentro «{valor}» como {NOMBRE_CAMPO[campo]} en el catálogo. ¿Te refieres a alguno de estos: {ejemplos}?"
    if problemas["opciones_dudosas"]:
        campo, vals = problemas["opciones_dudosas"]
        return f"No tengo claro qué {NOMBRE_CAMPO[campo]} necesitas. ¿Es {', '.join(vals[:-1])} o {vals[-1]}?"
    if problemas["combinacion"]:
        comb = problemas["combinacion"]
        if comb["campo"]:
            return f"{comb['aviso']} ¿Qué {NOMBRE_CAMPO[comb['campo']]} necesitas?"
        return "Esa combinación no existe en el catálogo. ¿Puedes revisar el grado, el acabado o el espesor?"
    if problemas["uso_desconocido"] and not esp.tiene("grado"):
        return (f"El catálogo no indica qué grado es adecuado para «{problemas['uso_desconocido']}». "
                f"¿Qué grado necesitas? Por ejemplo: {lista_y(catalogo.grados[:3])}.")
    faltan = esp.faltan
    if faltan:
        sugerido = isinstance(campo_aclaracion, str) and campo_aclaracion in faltan
        c = campo_aclaracion if sugerido else faltan[0]
        if c in CAMPOS_TEXTO:
            return f"¿Qué {NOMBRE_CAMPO[c]} necesitas? Por ejemplo: {lista_y(catalogo.valores(c)[:3])}."
        return f"¿Qué {NOMBRE_CAMPO[c]} necesitas, en milímetros?"
    return None


def _redactar(plantilla: str, cliente: Optional[ClienteLLM], catalogo: Catalogo) -> str:
    """Modo mixto: el LLM solo reescribe la pregunta; si añade algo, se usa la plantilla."""
    if cliente is None:
        return plantilla
    try:
        texto = cliente.completar(prompts.SISTEMA_REDACTAR_PREGUNTA, plantilla, max_tokens=150).strip()
    except ErrorLLM:
        return plantilla
    if (not texto or "?" not in texto or len(texto) > 2 * len(plantilla) + 60
            or not no_inventa(texto, plantilla, catalogo, conteos_permitidos=0)):
        return plantilla
    return texto


# ------------------------------------------------------------------ API pública

def interpretar(historial: Sequence[dict[str, str]], *, cliente: Optional[ClienteLLM] = None,
                catalogo: Optional[Catalogo] = None, redactar_con_llm: bool = True,
                minimos: Sequence[str] = CAMPOS_MINIMOS) -> ResultadoInterpretacion:
    """historial: [{"rol": "comercial" | "asistente", "texto": "..."}], en orden.

    Lanza ErrorLLM si el proveedor falla; el backend debe capturarlo y mostrar
    un error con opción de reintentar (RNF-14).
    """
    cliente = cliente or _cliente_defecto()
    catalogo = catalogo or _catalogo_defecto()
    bruto = _extraer(historial, cliente, catalogo, minimos)
    esp, problemas = _validar(bruto, catalogo)
    plantilla = _plantilla_previa(esp, problemas, catalogo, minimos, bruto.get("campo_aclaracion"))
    if plantilla is None:
        return ResultadoInterpretacion("especificacion", esp)
    pregunta = _redactar(plantilla, cliente if redactar_con_llm else None, catalogo)
    return ResultadoInterpretacion("pregunta", esp, pregunta)


ORDEN_DISTINGUIR = ("acabado", "grado", "formato", "espesor_mm", "ancho_mm", "largo_mm")


def _elegir_campo_stock(opciones: dict[str, list], historial: Optional[Sequence[dict[str, str]]],
                        cliente: Optional[ClienteLLM]) -> str:
    primero = next(iter(opciones))
    usuario = json.dumps({
        "conversacion": _conversacion(historial or []),
        "opciones_por_campo": opciones,
    }, ensure_ascii=False)
    try:
        modelo = cliente or _cliente_defecto()
        texto = modelo.completar(prompts.SISTEMA_ELEGIR_ACLARACION, usuario, json=True, max_tokens=500)
        campo = _parsear_json(texto).get("campo")
    except (ErrorLLM, ValueError):
        return primero
    return campo if isinstance(campo, str) and campo in opciones else primero


def pregunta_tras_busqueda(especificacion: Especificacion | dict, bultos: Sequence[dict[str, Any]], *,
                           cliente: Optional[ClienteLLM] = None, catalogo: Optional[Catalogo] = None,
                           redactar_con_llm: bool = True, max_opciones: int = 4,
                           historial: Optional[Sequence[dict[str, str]]] = None) -> Optional[str]:
    """Llamar DESPUÉS de buscar con los bultos que cumplen (los «exactos»).

    Devuelve la pregunta por el dato que el comercial no ha dado y que distingue
    entre los bultos encontrados, o None si no hace falta preguntar.
    Si hay varios candidatos, el historial permite que el LLM elija cuál aclarar.
    """
    esp = especificacion if isinstance(especificacion, Especificacion) else Especificacion.desde_dict(especificacion)
    if len(bultos) < 2:
        return None
    campos = [c for c in esp.opciones] + [c for c in ORDEN_DISTINGUIR if c not in esp.opciones]
    opciones = {}
    plantillas = {}
    for campo in campos:
        if getattr(esp, campo, None) is not None:
            continue
        valores = sorted({b.get(campo) for b in bultos if b.get(campo) is not None},
                         key=lambda v: (isinstance(v, str), v))
        if not 2 <= len(valores) <= max_opciones:
            continue
        if campo in CAMPOS_NUMERO:
            plantilla = (f"Tengo {_describir(esp, sin=campo)} con {NOMBRE_CAMPO[campo]} de "
                         f"{lista_y([fmt_num(v) for v in valores])} mm. ¿Cuál prefieres?")
        else:
            plantilla = f"Tengo {_describir(esp, sin=campo)} {lista_y(valores, 'en ')}. ¿Cuál prefieres?"
        opciones[campo] = valores
        plantillas[campo] = plantilla
    ultima = next((m.get("texto") for m in reversed(historial or []) if m.get("rol") == "asistente"), None)
    if not plantillas or ultima in plantillas.values():
        return None
    if redactar_con_llm and len(opciones) > 1 and (historial or cliente is not None):
        return plantillas[_elegir_campo_stock(opciones, historial, cliente)]

    plantilla = next(iter(plantillas.values()))
    if not redactar_con_llm:
        return plantilla
    try:
        cliente = cliente or _cliente_defecto()
    except ErrorLLM:
        return plantilla
    return _redactar(plantilla, cliente, catalogo or _catalogo_defecto())
