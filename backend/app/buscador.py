"""Buscador de bultos que cumplen la petición SIN transformar (RF-10).

Flujo: especificación de Nacho -> construir_objetivo() -> buscar_exactos(objetivo)
La función cumple() es la pieza clave: se reutiliza para verificar los transformables
de Lucas (RF-12) y en la verificación final anti-invención (RNF-01, RNF-02).
"""
from app import config
from app.db import disponibles, grados

EPS = 1e-9                                       # margen para comparar decimales (2.0 vs 1.9999999)
MEDIDAS = ["espesor_mm", "ancho_mm", "largo_mm"]


def _valores_aceptados(espec: dict, campo: str) -> list[str] | None:
    """Une el valor del campo y sus 'opciones' (p. ej. brillante -> BA o 2R). None = vale cualquiera."""
    valores = []
    if espec.get(campo):
        valores.append(espec[campo])
    valores += (espec.get("opciones") or {}).get(campo, [])
    limpios = sorted({str(v).strip().upper() for v in valores if v})
    return limpios or None


def construir_objetivo(espec: dict) -> dict:
    """Especificación de Nacho -> objetivo (el formato pactado con el motor de reglas de Lucas)."""
    return {
        "grados": _valores_aceptados(espec, "grado"),
        "acabados": _valores_aceptados(espec, "acabado"),
        "formato": espec.get("formato"),
        "espesor_mm": espec.get("espesor_mm"),
        "ancho_mm": espec.get("ancho_mm"),
        "largo_mm": espec.get("largo_mm"),
        "tolerancias": {
            "espesor_mm": config.TOL_ESPESOR_MM,
            "ancho_mm": config.TOL_ANCHO_MM,
            "largo_mm": config.TOL_LARGO_MM,
        },
    }


def cumple(bulto: dict, objetivo: dict) -> bool:
    """¿El bulto (o el resultado de una transformación) cumple el objetivo? Un campo None = no pedido."""
    if objetivo["grados"]:
        if not {g.upper() for g in grados(bulto)} & set(objetivo["grados"]):
            return False

    if objetivo["acabados"]:
        if (bulto.get("acabado") or "").upper() not in objetivo["acabados"]:
            return False

    if objetivo["formato"] and bulto.get("formato") != objetivo["formato"]:
        return False

    for campo in MEDIDAS:
        pedido = objetivo.get(campo)
        if pedido is None:                       # el comercial no lo ha pedido
            continue
        real = bulto.get(campo)
        if real is None:                         # lo ha pedido y el bulto no lo tiene (p. ej. largo en bobina)
            return False
        if abs(real - pedido) > objetivo["tolerancias"].get(campo, 0.0) + EPS:
            return False

    return True


def a_respuesta(bulto: dict) -> dict:
    """Bulto de la BD -> bulto para la API. Añade 'grado' porque es lo que espera responder() de Nacho."""
    return {**bulto, "grado": bulto.get("aisi") or bulto.get("euronorma")}


def buscar_exactos(objetivo: dict) -> list[dict]:
    """Bultos DISPONIBLES que cumplen sin transformar."""
    return [a_respuesta(b) for b in disponibles() if cumple(b, objetivo)]


CAMPOS_VALORES = ("grado", "acabado", "formato", "espesor_mm", "ancho_mm")


def valores_disponibles(campo: str, espec: dict, bultos: list[dict] | None = None) -> list[dict]:
    """Qué valores de un campo hay en stock disponible que cumpla lo ya pedido («¿qué grosores hay de 304?»).

    Devuelve [{valor, bultos, toneladas}]; las medidas de menor a mayor y el resto de más a menos toneladas.
    """
    if campo not in CAMPOS_VALORES:
        raise ValueError(f"Campo no consultable: {campo}")
    objetivo = construir_objetivo(espec)
    grupos: dict = {}
    for b in disponibles() if bultos is None else bultos:
        if not cumple(b, objetivo):
            continue
        valor = a_respuesta(b)["grado"] if campo == "grado" else b.get(campo)
        if valor is None:
            continue
        g = grupos.setdefault(valor, {"valor": valor, "bultos": 0, "toneladas": 0.0})
        g["bultos"] += 1
        g["toneladas"] += b["peso_kg"] / 1000
    for g in grupos.values():
        g["toneladas"] = round(g["toneladas"], 1)
    if campo in MEDIDAS:
        return sorted(grupos.values(), key=lambda g: g["valor"])
    return sorted(grupos.values(), key=lambda g: -g["toneladas"])