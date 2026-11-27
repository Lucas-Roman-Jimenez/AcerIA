"""Interpreta peticiones de inventario con el catálogo y patrones locales."""
import re
import unicodedata
from collections.abc import Sequence

from voz.normalizacion import normalizar_transcripcion

from .catalogo import Catalogo
from .contrato import CAMPOS_TEXTO

NUMERO = r"\d+(?:[.,]\d+)?"
MEDIDAS = {
    "espesor_mm": r"espesor|grosor|galga",
    "ancho_mm": r"ancho|anchura",
    "largo_mm": r"largo|longitud",
}


def _texto(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", normalizar_transcripcion(texto).casefold())
        if not unicodedata.combining(c)
    )


def _buscar(texto, termino):
    return re.search(rf"(?<!\w){re.escape(_texto(termino))}(?!\w)", texto)


def extraer_local(historial: Sequence[dict[str, str]], catalogo: Catalogo) -> dict:
    datos = {}
    texto = pregunta = ""
    for mensaje in historial:
        if mensaje.get("rol") == "asistente":
            pregunta = _texto(mensaje["texto"])
            continue
        if mensaje.get("rol") != "comercial":
            continue
        texto = _texto(mensaje["texto"])
        for campo in CAMPOS_TEXTO:
            candidatos = [
                (valor, [valor]) for valor in catalogo.valores(campo)
                if not valor.isdigit() or campo == "grado"
            ]
            candidatos.extend((t["termino"], t["valores"]) for t in catalogo.terminos if t["campo"] == campo)
            if campo == "grado":
                candidatos.extend((valor, [valor]) for valor in catalogo.grados_en_por_comercial)
            for termino, valores in sorted(candidatos, key=lambda item: -len(item[0])):
                if not termino or not _buscar(texto, termino):
                    continue
                if campo != "grado":
                    valores = [valor for valor in valores if catalogo.normalizar(campo, valor)]
                elif len(valores) == 1 and not catalogo.normalizar(campo, valores[0]):
                    valores = sorted(catalogo.grados_en_por_comercial.get(valores[0].upper(), ()))
                if valores:
                    datos[campo] = valores[0] if len(valores) == 1 else valores
                    break

        dimensiones = re.search(rf"(?<![\d.])({NUMERO})\s*[x×]\s*({NUMERO})(?:\s*[x×]\s*({NUMERO}))?", texto)
        if dimensiones:
            datos.update({campo: valor for campo, valor in zip(MEDIDAS, dimensiones.groups()) if valor})
        for campo, palabras in MEDIDAS.items():
            medida = re.search(rf"\b(?:{palabras})\s*(?:de\s+)?({NUMERO})(?![\d.,])|({NUMERO})\s*mm\s*(?:de\s+)?(?:{palabras})\b", texto)
            if medida:
                datos[campo] = medida[1] or medida[2]
        respuesta = re.fullmatch(rf"({NUMERO})\s*(mm|cm)?", texto.strip())
        campo_preguntado = next((
            campo for campo, palabras in MEDIDAS.items()
            if re.search(rf"\b(?:{palabras})\b", pregunta)
        ), None)
        if respuesta and campo_preguntado:
            factor = 10 if respuesta[2] == "cm" else 1
            datos[campo_preguntado] = float(respuesta[1].replace(",", ".")) * factor
        elif not dimensiones and not re.search(r"\b(?:ancho|anchura|largo|longitud)\b", texto):
            espesor = re.search(rf"(?<![\d.])({NUMERO})\s*(mm|cm|milimetros?)\b", texto)
            if espesor:
                factor = 10 if espesor[2] == "cm" else 1
                datos["espesor_mm"] = float(espesor[1].replace(",", ".")) * factor

        cantidad = re.search(rf"(?<![\d.])({NUMERO})\s*(kg|t|toneladas?|bultos?)\b", texto)
        if cantidad:
            unidad = "bultos" if cantidad[2].startswith("bulto") else "t" if cantidad[2].startswith("t") else "kg"
            datos["cantidad"] = {"valor": cantidad[1], "unidad": unidad}

        for uso in catalogo.usos:
            if any(_buscar(texto, alias) for alias in [uso["uso"], *uso.get("alias", [])] if alias):
                datos["uso"] = uso["uso"]
                break

    intenciones = {
        "saludo": r"^[¿¡ ]*(hola|buenos dias|buenas tardes)[!. ]*$",
        "agradecimiento": r"^[¿¡ ]*(muchas gracias|gracias)[!. ]*$",
        "precio": r"\b(precio|cuanto cuesta)\b",
        "plazo": r"\b(plazo|cuando llega)\b",
        "reserva": r"\b(reserva|reservar|reservame)\b",
        "consulta_tecnica": r"\b(recomiend\w*|aconsej\w*|que grado|que acero)\b",
    }
    datos["intencion"] = next(
        (intencion for intencion, patron in intenciones.items() if re.search(patron, texto)), "pedido"
    )
    return datos
