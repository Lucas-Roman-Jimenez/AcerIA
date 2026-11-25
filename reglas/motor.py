"""Interfaz de transformación para el backend de inventario."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from reglas.configuracion import REGLAS
from reglas.corte import cumple_condiciones_corte
from reglas.laminacion import LAMINACION, permite_laminacion


_MEDIDAS = ("espesor_mm", "ancho_mm", "largo_mm")
_DENSIDAD = Decimal(str(REGLAS["densidad_kg_mm3"]))
_DECIMA = Decimal("0.1")
_DENSIDAD_KG_DM3 = f"{(_DENSIDAD * 10**6).normalize():f}".replace(".", ",")
_AVISO_LARGO = (
    f"Largo de la bobina estimado a partir del peso (densidad {_DENSIDAD_KG_DM3} kg/dm³)"
)


def _redondear(valor: Decimal) -> float:
    return float(valor.quantize(_DECIMA, rounding=ROUND_HALF_UP))


def _cumple(resultado: dict, objetivo: dict) -> bool:
    formato = objetivo.get("formato")
    if formato is not None and formato != resultado["formato"]:
        return False
    if objetivo.get("largo_mm") is not None and resultado["formato"] != "chapa":
        return False
    acabados = objetivo.get("acabados")
    if acabados and resultado["acabado"] not in acabados:
        return False
    tolerancias = objetivo.get("tolerancias") or {}
    for campo in _MEDIDAS:
        pedido = objetivo.get(campo)
        if pedido is None:
            continue
        actual = resultado[campo]
        if actual is None or abs(Decimal(str(actual)) - Decimal(str(pedido))) > Decimal(
            str(tolerancias.get(campo, 0))
        ):
            return False
    return True


def _laminar(origen: dict, espesor: float | None) -> tuple[dict, dict] | None:
    acabado = LAMINACION["acabado_destino"]
    if espesor is None or not permite_laminacion(
        formato_origen=origen["formato"],
        acabado_origen=origen["acabado"],
        espesor_origen=origen["espesor_mm"],
        acabado_destino=acabado,
        espesor_destino=espesor,
    ):
        return None

    anterior = origen["espesor_mm"]
    merma = LAMINACION["merma_kg"]
    resultado = dict(
        origen, acabado=acabado, espesor_mm=espesor,
        peso_util_kg=origen["peso_util_kg"] - merma,
    )
    accion = {
        "regla": LAMINACION["id"],
        "descripcion": f"Laminar de {anterior:g} a {espesor:g} mm con acabado {acabado}",
        "parametros": {"espesor_mm": espesor, "acabado": acabado},
        "merma_kg": merma,
    }
    return resultado, accion


def _cortar(origen: dict, objetivo: dict, formato: str) -> tuple[dict, dict, bool] | None:
    formato_origen = origen["formato"]
    ancho_origen = origen["ancho_mm"]
    largo_origen = origen["largo_mm"]
    ancho = objetivo.get("ancho_mm")
    if ancho is None:
        ancho = ancho_origen
    largo = objetivo.get("largo_mm") if formato == "chapa" else largo_origen
    if formato == "chapa" and largo is None:
        largo = largo_origen
    if formato == formato_origen and ancho == ancho_origen and largo == largo_origen:
        return None
    if not cumple_condiciones_corte(
        formato_origen=formato_origen, formato_destino=formato,
        ancho_origen=ancho_origen, ancho_destino=ancho,
        largo_origen=largo_origen, largo_destino=largo,
    ):
        return None

    peso = Decimal(str(origen["peso_util_kg"]))
    ancho_original = Decimal(str(ancho_origen))
    ancho_pieza = Decimal(str(ancho))
    piezas = int(ancho_original // ancho_pieza)
    proporcion = piezas * ancho_pieza / ancho_original
    estimada = formato_origen == "bobina" and formato == "chapa"
    espesor = origen["espesor_mm"]
    if formato == "chapa":
        largo_pieza = Decimal(str(largo))
        if estimada:
            largo_original = peso / (_DENSIDAD * Decimal(str(espesor)) * ancho_original)
        else:
            largo_original = Decimal(str(largo_origen))
        filas = int(largo_original // largo_pieza)
        if filas == 0:
            return None
        piezas *= filas
        proporcion *= filas * largo_pieza / largo_original

    peso_util = peso * proporcion
    parametros = {"ancho_mm": ancho, "largo_mm": largo, "piezas": piezas}
    medida = f"{espesor:g} × {ancho:g}"
    if largo is not None:
        medida += f" × {largo:g}"
    accion = {
        "regla": REGLAS["cortes"][formato_origen][formato],
        "descripcion": f"Cortar {formato_origen} a {formato} {medida} mm",
        "parametros": parametros,
        "merma_kg": _redondear(peso - peso_util),
    }
    resultado = dict(origen, **parametros, formato=formato, peso_util_kg=_redondear(peso_util))
    return resultado, accion, estimada


def _transformacion(bulto_id: str, peso: float, resultado: dict,
                    acciones: list[dict], estimada: bool) -> dict:
    merma = sum(Decimal(str(accion["merma_kg"])) for accion in acciones)
    return {
        "bulto_id": bulto_id,
        "acciones": [dict(accion, orden=i) for i, accion in enumerate(acciones, start=1)],
        "resultado": resultado,
        "merma_kg": _redondear(merma),
        "merma_pct": _redondear(100 * merma / Decimal(str(peso))),
        "num_operaciones": len(acciones),
        "merma_estimada": estimada,
        "avisos": [_AVISO_LARGO] if estimada else [],
    }


def aplicar_reglas(bulto: dict, objetivo: dict, max_operaciones: int = 2) -> list[dict]:
    """Devuelve las rutas de corte y laminación que cumplen el objetivo."""
    if max_operaciones < 1:
        return []
    grados = objetivo.get("grados")
    certificados = {
        grado.strip()
        for campo in ("aisi", "euronorma")
        for grado in (bulto.get(campo) or "").split("/")
        if grado.strip()
    }
    if grados and certificados.isdisjoint(grados):
        return []
    peso = bulto["peso_kg"]
    if not all(0 < bulto[campo] < float("inf") for campo in ("peso_kg", "espesor_mm", "ancho_mm")):
        return []
    origen = {
        campo: bulto.get(campo)
        for campo in ("formato", "aisi", "euronorma", "acabado", *_MEDIDAS)
    }
    if _cumple(origen, objetivo):
        return []
    origen.update(piezas=1, peso_util_kg=peso)

    laminado = _laminar(origen, objetivo.get("espesor_mm"))
    candidatos = [(origen, [])]
    if laminado is not None:
        resultado, accion = laminado
        candidatos.append((resultado, [accion]))

    transformaciones = []
    for material, acciones in candidatos:
        if acciones and _cumple(material, objetivo):
            transformaciones.append(_transformacion(bulto["id"], peso, material, acciones, False))
        if len(acciones) >= max_operaciones:
            continue
        formato_pedido = objetivo.get("formato")
        cortes = REGLAS["cortes"].get(material["formato"], {})
        destinos = (formato_pedido,) if formato_pedido in cortes else ()
        if formato_pedido is None:
            destinos = cortes
        for formato in destinos:
            corte = _cortar(material, objetivo, formato)
            if corte is None:
                continue
            resultado, accion, estimada = corte
            if _cumple(resultado, objetivo):
                transformaciones.append(
                    _transformacion(bulto["id"], peso, resultado, [*acciones, accion], estimada)
                )
    return transformaciones
