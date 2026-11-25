"""Configuración que se carga una vez al importar el motor."""

import json
from pathlib import Path


with Path(__file__).with_name("reglas.json").open(encoding="utf-8") as archivo:
    REGLAS = json.load(archivo)
