"""interpretar(): conversación -> especificación validada o pregunta (RF-04 a RF-09, RF-26).
pregunta_tras_busqueda(): pregunta solo por el dato que distingue el stock real (RF-07).

Reparto de responsabilidades:
- El LLM solo extrae lo que dice el comercial y, opcionalmente, redacta las preguntas.
- El código valida contra el catálogo y decide si hay que preguntar y qué.
"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any, Optional, Sequence

from . import prompts
from .catalogo import Catalogo
from .contrato import CAMPOS_NUMERO, CAMPOS_TEXTO, Cantidad, Especificacion, ResultadoInterpretacion
from .control import conserva_datos, fmt_num, lista_o, lista_y, no_inventa
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


def _extraer(historial, cliente: ClienteLLM, catalogo: Catalogo) -> dict[str, Any]:
    sistema = prompts.SISTEMA_EXTRACCION.format(catalogo=catalogo.resumen_para_prompt())
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
    intencion = bruto.get("intencion") or ("fuera_de_tema" if bruto.get("fuera_de_tema") else "pedido")
    problemas: dict[str, Any] = {"invalidos": [], "contradiccion": None, "combinacion": None,
                                 "uso_desconocido": None, "opciones_dudosas": None,
                                 "intencion": intencion if intencion in INTENCIONES else "pedido"}

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
        if valores and not validos:
            # Ninguno de los valores existe (p. ej. «satinado» -> «4» y no hay «4»): se pregunta, no se ignora.
            nombre = catalogo.termino(campo, [str(v) for v in valores]) or str(valores[0])
            problemas["invalidos"].append((campo, nombre))
            esp.avisos.append(f"«{nombre}» no corresponde a ningún {NOMBRE_CAMPO[campo]} del catálogo.")
            continue
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
            if esp.grado and esp.grado not in uso["grados"]:
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

    # Campos que al comercial le dan igual: no se preguntan ni cuentan como «faltan».
    indif = bruto.get("indiferentes") or []
    esp.indiferentes = [c for c in indif if isinstance(c, str)
                        and c in CAMPOS_TEXTO + CAMPOS_NUMERO and getattr(esp, c) is None]
    esp.opciones = {c: v for c, v in esp.opciones.items() if c not in esp.indiferentes}

    contr = [c for c in (bruto.get("contradicciones") or []) if isinstance(c, dict) and c.get("campo")]
    if contr:
        problemas["contradiccion"] = contr[0]
        if contr[0]["campo"] in CAMPOS_TEXTO + CAMPOS_NUMERO:
            setattr(esp, contr[0]["campo"], None)

    if not problemas["invalidos"]:
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
        # Lo que hay en el catálogo con el resto de datos (sin tener en cuenta `campo`).
        otros = {c: (None if c == campo else getattr(esp, c))
                 for c in ("grado", "acabado", "formato", "espesor_mm", "ancho_mm")}
        prods = catalogo.productos_compatibles(**otros)
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
        return {"campo": campo, "disponible": disp,
                "aviso": f"En el catálogo no existe {_describir(esp)}. "
                         f"Con el resto de datos hay {NOMBRE_CAMPO[campo]} {disp}."}
    return {"campo": None, "disponible": "", "aviso": "Esa combinación no existe en el catálogo."}


# ------------------------------------------------------------------ preguntas

def _valor_o_opciones(esp: Especificacion, campo: str) -> Optional[str]:
    if getattr(esp, campo):
        return getattr(esp, campo)
    return lista_o(esp.opciones[campo]) if esp.opciones.get(campo) else None


def _describir(esp: Especificacion, sin: str = "") -> str:
    partes = []
    formato, grado, acabado = (_valor_o_opciones(esp, c) for c in ("formato", "grado", "acabado"))
    if formato and sin != "formato":
        partes.append(formato)
    if grado and sin != "grado":
        partes.append(grado)
    if acabado and sin != "acabado":
        partes.append(acabado)
    if esp.espesor_mm and sin != "espesor_mm":
        partes.append(f"de {fmt_num(esp.espesor_mm)} mm")
    return " ".join(partes) or "material"


INTENCIONES = ("pedido", "saludo", "agradecimiento", "precio", "plazo", "reserva", "consulta_tecnica",
               "fuera_de_tema")


def _calcular_faltan(esp: Especificacion, minimos: Sequence[str]) -> None:
    """Se calcula siempre, aunque se pregunte por otra cosa, para el panel del frontend (RF-18)."""
    esp.faltan = [c for c in minimos if not esp.tiene(c) and c not in esp.indiferentes]


def _respuesta_intencion(esp: Especificacion, intencion: str, catalogo: Catalogo) -> Optional[str]:
    """Respuesta fija para mensajes que no son un pedido (RF-09). No pasa por el LLM."""
    hay_datos = _describir(esp) != "material"
    buscar = f"¿Quieres que busque {_describir(esp)}?" if hay_datos else "¿Qué material necesitas?"
    usos = [u["uso"] for u in catalogo.usos]
    ejemplo_usos = f" (por ejemplo, {lista_o(usos)})" if usos else ""
    return {
        "saludo": "¡Hola! ¿Qué material necesita tu cliente? Dime grado, acabado, espesor o para qué lo quiere.",
        "agradecimiento": "De nada. ¿Necesitas buscar algo más?",
        "precio": f"No tengo información de precios: solo puedo decirte qué stock hay disponible. {buscar}",
        "plazo": f"No tengo información de plazos de entrega: solo puedo decirte qué stock hay disponible. {buscar}",
        "reserva": ("No puedo reservar bultos: solo propongo los disponibles. "
                    "La reserva se hace en el sistema de AcerIA. ¿Necesitas algo más?"),
        "consulta_tecnica": ("No puedo comparar propiedades de los materiales: solo uso lo que indica el catálogo. "
                             f"Si me dices para qué es{ejemplo_usos}, te digo qué grados indica."),
        "fuera_de_tema": "Solo puedo ayudarte a buscar material en el inventario. ¿Qué necesita tu cliente?",
    }.get(intencion)


def _plantilla_previa(esp: Especificacion, problemas: dict[str, Any], catalogo: Catalogo,
                      minimos: Sequence[str]) -> Optional[str]:
    """Pregunta ANTES de buscar, o None si ya se puede buscar."""
    _calcular_faltan(esp, minimos)
    if problemas["contradiccion"]:
        c = problemas["contradiccion"]
        vals = [fmt_num(v) + " mm" if c["campo"] in CAMPOS_NUMERO else str(v) for v in c.get("valores", [])]
        return (f"Has indicado {lista_y(vals)} de {NOMBRE_CAMPO.get(c['campo'], c['campo'])}. "
                "Si son pedidos distintos, vamos de uno en uno: ¿con cuál empezamos?")
    if problemas["invalidos"]:
        campo, valor = problemas["invalidos"][0]
        ejemplos = lista_y(catalogo.parecidos(campo, valor), "")
        return f"No encuentro «{valor}» como {NOMBRE_CAMPO[campo]} en el catálogo. ¿Te refieres a alguno de estos: {ejemplos}?"
    if problemas["opciones_dudosas"]:
        campo, vals = problemas["opciones_dudosas"]
        return f"No tengo claro qué {NOMBRE_CAMPO[campo]} necesitas. ¿Es {lista_o(vals)}?"
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
        c = faltan[0]
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
            or texto.lower().startswith(("hola", "buenas", "buenos"))
            or not no_inventa(texto, plantilla, catalogo, conteos_permitidos=0)
            or not conserva_datos(texto, plantilla, catalogo)):
        return plantilla
    return texto


# ------------------------------------------------------------------ API pública

def interpretar(historial: Sequence[dict[str, str]], *, cliente: Optional[ClienteLLM] = None,
                catalogo: Optional[Catalogo] = None, redactar_con_llm: bool = False,
                minimos: Sequence[str] = CAMPOS_MINIMOS) -> ResultadoInterpretacion:
    """historial: [{"rol": "comercial" | "asistente", "texto": "..."}], en orden.

    Lanza ErrorLLM si el proveedor falla; el backend debe capturarlo y mostrar
    un error con opción de reintentar (RNF-14).

    Hace una sola llamada al LLM (la extracción). Las preguntas salen de plantillas;
    con redactar_con_llm=True el LLM las reescribe (una llamada más, ~1-4 s, RNF-05).
    """
    # Los mensajes vacíos del comercial no aportan nada; si no queda ninguno, no se llama al LLM.
    historial = [m for m in historial if m.get("rol") != "comercial" or str(m.get("texto") or "").strip()]
    if not any(m.get("rol") == "comercial" for m in historial):
        return ResultadoInterpretacion("pregunta", Especificacion(faltan=list(minimos)), "¿Qué material necesitas?")
    cliente = cliente or _cliente_defecto()
    catalogo = catalogo or _catalogo_defecto()
    bruto = _extraer(historial, cliente, catalogo)
    esp, problemas = _validar(bruto, catalogo)
    if problemas["intencion"] != "pedido":
        _calcular_faltan(esp, minimos)
        return ResultadoInterpretacion("pregunta", esp, _respuesta_intencion(esp, problemas["intencion"], catalogo))
    plantilla = _plantilla_previa(esp, problemas, catalogo, minimos)
    if plantilla is None:
        return ResultadoInterpretacion("especificacion", esp)
    pregunta = _redactar(plantilla, cliente if redactar_con_llm else None, catalogo)
    return ResultadoInterpretacion("pregunta", esp, pregunta)


ORDEN_DISTINGUIR = ("acabado", "grado", "formato", "espesor_mm", "ancho_mm", "largo_mm")


def pregunta_tras_busqueda(especificacion: Especificacion | dict, bultos: Sequence[dict[str, Any]], *,
                           historial: Optional[Sequence[dict[str, str]]] = None,
                           max_opciones: int = 4) -> Optional[str]:
    """Llamar DESPUÉS de buscar con los bultos que cumplen (los «exactos»).

    Devuelve la pregunta por el dato que el comercial no ha dado y que distingue
    entre los bultos encontrados, o None si no hace falta preguntar.
    No usa el LLM: es la pregunta de la demo (RF-07) y debe salir siempre igual y rápida.

    `historial` es opcional: si se pasa y la última pregunta del asistente ya era esta,
    no se repite (el comercial no la ha resuelto) y se devuelve None para mostrar todos los bultos.
    """
    esp = especificacion if isinstance(especificacion, Especificacion) else Especificacion.desde_dict(especificacion)
    if len(bultos) < 2:
        return None
    ultima = next((m.get("texto") for m in reversed(historial or []) if m.get("rol") == "asistente"), None)
    campos = [c for c in esp.opciones] + [c for c in ORDEN_DISTINGUIR if c not in esp.opciones]
    for campo in campos:
        if getattr(esp, campo, None) is not None or campo in esp.indiferentes:
            continue
        valores = sorted({b.get(campo) for b in bultos if b.get(campo) is not None},
                         key=lambda v: (isinstance(v, str), v))
        if not 2 <= len(valores) <= max_opciones:
            continue
        if campo in CAMPOS_NUMERO:
            plantilla = (f"Tengo {_describir(esp, sin=campo)} con {NOMBRE_CAMPO[campo]} de "
                         f"{lista_y([fmt_num(v) for v in valores])} mm. ¿Cuál prefieres?")
        elif campo == "formato":
            plantilla = f"Tengo {_describir(esp, sin=campo)} en {lista_y(valores)}. ¿Qué formato prefieres?"
        else:
            plantilla = f"Tengo {_describir(esp, sin=campo)} {lista_y(valores, 'en ')}. ¿Cuál prefieres?"
        return None if plantilla == ultima else plantilla
    return None
