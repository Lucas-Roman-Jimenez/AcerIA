# backend/ — Alonso (P1)

FastAPI + SQLite: buscador, transformables, ranking, orquestación de la conversación y log.

Usa el módulo `llm/` así (ver el README raíz):

```python
from llm import interpretar, pregunta_tras_busqueda, responder, ErrorLLM
```

## Buscar con el motor de reglas

Ejecuta desde la raíz del repositorio para que el backend pueda importar
`reglas.motor`.

```bash
python -m uvicorn app.main:app --app-dir backend
```

`POST /buscar` devuelve coincidencias exactas y transformaciones de bultos
disponibles. El backend comprueba cada resultado del motor y ordena por
porcentaje de merma y número de operaciones.
