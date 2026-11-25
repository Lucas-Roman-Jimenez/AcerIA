"""Demo por consola para probar los prompts con el LLM real antes de tener el backend.

    python demo_consola.py

Necesita un fichero .env (ver .env.example). La búsqueda es una SIMULACIÓN muy simple
sobre datos_ejemplo/inventario.json: el buscador de verdad y las transformaciones son de Alonso y Lucas.
"""
import json
import os
from pathlib import Path

from llm import ErrorLLM, interpretar, pregunta_tras_busqueda, responder
from llm.catalogo import Catalogo

RAIZ = Path(__file__).resolve().parent


def cargar_env():
    f = RAIZ / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def buscar_simulado(esp):
    bultos = json.loads((RAIZ / "datos_ejemplo" / "inventario.json").read_text(encoding="utf-8"))["bultos"]

    def encaja(b, campo):
        if getattr(esp, campo) is not None:
            return b.get(campo) == getattr(esp, campo)
        return not esp.opciones.get(campo) or b.get(campo) in esp.opciones[campo]

    res = [b for b in bultos if b["estado"] == "disponible"
           and all(encaja(b, c) for c in ("grado", "acabado", "formato"))
           and (esp.espesor_mm is None or abs(b["espesor_mm"] - esp.espesor_mm) <= 0.05)
           and (esp.ancho_mm is None or b["ancho_mm"] == esp.ancho_mm)]
    return {"exactos": res, "transformables": [], "alternativas": []}


def main():
    cargar_env()
    catalogo = Catalogo.cargar(RAIZ / "datos_ejemplo")
    historial = []
    print("Asistente AcerIA (demo). Escribe tu petición; 'nueva' reinicia, 'salir' termina.\n")
    while True:
        texto = input("Comercial> ").strip()
        if texto.lower() == "salir":
            break
        if texto.lower() == "nueva":
            historial = []
            print("-- conversación nueva --\n")
            continue
        historial.append({"rol": "comercial", "texto": texto})
        try:
            r = interpretar(historial, catalogo=catalogo)
        except ErrorLLM as e:
            print(f"[Error del LLM: {e}. Inténtalo de nuevo.]\n")
            historial.pop()
            continue
        print(f"  (entendido: {json.dumps(r.especificacion.a_dict(), ensure_ascii=False)})")
        if r.tipo == "pregunta":
            salida = r.pregunta
        else:
            resultado = buscar_simulado(r.especificacion)
            salida = (pregunta_tras_busqueda(
                r.especificacion, resultado["exactos"], historial=historial, catalogo=catalogo,
            ) or responder(resultado, r.especificacion, catalogo=catalogo))
        historial.append({"rol": "asistente", "texto": salida})
        print(f"Asistente> {salida}\n")


if __name__ == "__main__":
    main()
