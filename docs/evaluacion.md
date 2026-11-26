# Evaluación con el LLM real

Resultado de `tests/evaluar_api.py` (el evaluador de Lucas) **contra el servidor real**: `/chat` con el módulo LLM, el buscador de Alonso con el motor de reglas, la base de datos de 2411 bultos y el **catálogo y glosario reales** de `datos/`.

- **Fecha:** 26 de noviembre de 2026 · **código:** `main` en `fe4a607` (con la venta del carrito) más esta rama
- **LLM:** `system.ai.claude-sonnet-5-5` por el AI Gateway de Databricks
- **Duración:** 45 s para los 34 casos · el script termina con `exit 0`

| Métrica | Requisito | Resultado | Umbral 85 % |
| --- | --- | --- | --- |
| Interpretación (por `/chat`) | RNF-03 | **26/26 = 100 %** | ✅ |
| Resultados (por `/buscar`, incluido un caso sin stock) | RNF-04, RF-15 | **17/17 = 100 %** | ✅ |
| Transformables (por `/buscar`) | RF-11 a RF-14 | **2/2 = 100 %** | ✅ |
| Reglas locales | RF-28 | **8/8 = 100 %** | ✅ |

## CL-08: «brillante»

*«Quiero una chapa 304 brillante de 2 mm.»* Antes era el único fallo (96,2 %). Lucas añadió al glosario «brillante» → BA con fuente de AcerIA («2R (BA), brillante»), y el caso pasó a comprobar que se interpreta como BA y que se comunica que no hay stock. **Ojo:** es un cambio en el conjunto de evaluación; está justificado por un dato nuevo con fuente, no por ajustar los prompts.

## Cómo repetirla

Desde la raíz del repositorio, con el `.env` del gateway:

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# en otra terminal:
python -m tests.evaluar_api --base-url http://127.0.0.1:8000
```

`python -m tests.evaluar_api` (como módulo) para que encuentre `reglas/`. Llama al LLM real: gasta tokens.

## Lo que esta evaluación no mide todavía

- **Alternativas cercanas (RF-29): hecho en el buscador, sin métrica.** El evaluador ya puntúa un caso sin stock (CL-08), pero todavía no puntúa las alternativas. Si no hay exactos ni transformables, `buscador.buscar_alternativas()` propone hasta 3 chapas reales del mismo grado, acabado y espesor con otra medida (regla de sustitución de `reglas/sustitucion.py`), las más cercanas primero. Lo cubre `tests/test_alternativas.py`.
- **Criterio de orden (RF-14): hecho.** El buscador y el evaluador ordenan los transformables por nº de operaciones, luego % de merma y luego ID (como número), como pide el PDF del reto. El orden está en `config.ORDEN_TRANSFORMABLES`; queda confirmarlo con el mentor (¿merma en % o en kg?).

## Otras pruebas del módulo LLM

- `python -m pytest -q`: tests sin conexión (165).
- `python tests/bateria_llm.py`: 48 escenarios de conversación con el LLM real y los datos reales, por el mismo camino que `POST /chat`. Última ejecución (26/11): 0 fallos, mediana de 1,4 s por mensaje.
