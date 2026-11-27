"""Arranca la aplicación completa en modo real con un solo comando (RNF-12).

    python arrancar.py                 # backend + frontend y abre el navegador
    python arrancar.py --sin-navegador
    python arrancar.py --sin-ventas-demo   # sin las ventas simuladas de Reposición y Tendencias

Levanta el backend (FastAPI, desde la raíz para que encuentre llm/ y reglas/) y, cuando responde,
el frontend (Vite) conectado a él. Usa 127.0.0.1 y no «localhost»: en algunas redes (p. ej. la
de la URJC) «localhost» acaba en el proxy. Ctrl+C para los dos.

Requisitos: pip install -r requirements.txt -r backend/requirements.txt, Node.js.
"""
from __future__ import annotations

import argparse
import getpass
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
HOST = "127.0.0.1"


def esperar(url: str, segundos: float, proceso: subprocess.Popen) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        if proceso.poll() is not None:          # el proceso ha terminado: no tiene sentido esperar más
            return False
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def parar(*procesos: subprocess.Popen) -> None:
    for p in procesos:
        if p and p.poll() is None:
            p.terminate()
    for p in procesos:
        if p:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modos = parser.add_mutually_exclusive_group()
    modos.add_argument("--claude", action="store_true", help="usar la API de Claude Sonnet 5.5 con una clave personal")
    modos.add_argument("--ollama", metavar="MODELO", help="interpretar el chat con un modelo de Ollama instalado en este equipo")
    parser.add_argument("--puerto-backend", type=int, default=8000)
    parser.add_argument("--puerto-frontend", type=int, default=5173)
    parser.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador")
    parser.add_argument("--reiniciar-demo", action="store_true",
                        help="vaciar las ventas de la demo y el reporte semanal (si no, se conservan)")
    parser.add_argument("--sin-ventas-demo", action="store_true",
                        help="no crear las ventas simuladas (demo-*) de las últimas 4 semanas que usan los reportes")
    args = parser.parse_args()

    clave_claude = ""
    if args.claude:
        if not sys.stdin.isatty():
            parser.error("--claude necesita una terminal interactiva para introducir la clave personal.")
        clave_claude = getpass.getpass("Clave personal de Anthropic (las consultas se facturan a su cuenta): ").strip()
        if not clave_claude:
            parser.error("Introduce una clave personal para activar Claude.")
    npm = shutil.which("npm")
    if not npm:
        print("Falta Node.js (npm) para el frontend: https://nodejs.org")
        return 1
    frontend = RAIZ / "frontend"
    if not (frontend / "node_modules").exists():
        print("Instalando las dependencias del frontend (npm install)...")
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=frontend, check=True)

    api = f"http://{HOST}:{args.puerto_backend}"
    web = f"http://{HOST}:{args.puerto_frontend}"
    backend = front = None
    try:
        print(f"Backend en {api} ...")
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", "backend",
             "--host", HOST, "--port", str(args.puerto_backend)], cwd=RAIZ,
            env={**os.environ, "ACERIA_OLLAMA_MODELO": args.ollama or "",
                 "ACERIA_CLAUDE_KEY": clave_claude,
                 "ACERIA_REINICIAR_DEMO": "1" if args.reiniciar_demo else "0",
                 # Una base propia (ACERIA_DB_PATH, p. ej. python -m demo_reportes) trae ya sus compras.
                 "ACERIA_VENTAS_DEMO": "0" if args.sin_ventas_demo or os.environ.get("ACERIA_DB_PATH") else "1",
                 "ACERIA_CORS_ORIGENES": web})
        if not esperar(f"{api}/health", 90, backend):
            print("El backend no ha arrancado. Revisa el error de arriba "
                  "(¿pip install -r backend/requirements.txt? ¿puerto ocupado?).")
            return 1

        print(f"Frontend en {web} (modo real, VITE_API_URL={api}) ...")
        front = subprocess.Popen(
            [npm, "run", "dev", "--", "--host", HOST, "--port", str(args.puerto_frontend), "--strictPort"],
            cwd=frontend, env={**os.environ, "VITE_API_URL": api})
        if not esperar(web, 60, front):
            print("El frontend no ha arrancado. Revisa el error de arriba (¿puerto ocupado?).")
            return 1

        print(f"\nListo: abre {web}   (Ctrl+C para parar)\n")
        if not args.sin_navegador:
            webbrowser.open(web)
        while backend.poll() is None and front.poll() is None:
            time.sleep(1)
        print("Uno de los dos procesos se ha parado; cierro el otro.")
        return 1
    except KeyboardInterrupt:
        print("\nParando...")
        return 0
    finally:
        parar(front, backend)


if __name__ == "__main__":
    sys.exit(main())
