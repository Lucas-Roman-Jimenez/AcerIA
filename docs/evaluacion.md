# Evaluación con el LLM real

Resultado de `tests/evaluar_api.py` (el evaluador de Lucas) **contra el servidor real**: `/chat` con el módulo LLM, el buscador de Alonso con el motor de reglas, la base de datos de 2411 bultos y el **catálogo y glosario reales** de `datos/`.

- **Fecha:** 26 de noviembre de 2026 · **código:** `main` en `4b16d37`
- **LLM:** `system.ai.claude-sonnet-5-5` por el AI Gateway de Databricks
- **Duración:** 49 s para los 32 casos · el script termina con `exit 0`

| Métrica | Requisito | Resultado | Umbral 85 % |
| --- | --- | --- | --- |
| Interpretación (por `/chat`) | RNF-03 | **25/26 = 96,2 %** | ✅ |
| Resultados (por `/buscar`) | RNF-04 | **16/16 = 100 %** | ✅ |
| Transformables (por `/buscar`) | RF-11 a RF-14 | **2/2 = 100 %** | ✅ |
| Reglas locales | RF-28 | **8/8 = 100 %** | ✅ |

## El único fallo: CL-08

*«Quiero una chapa 304 brillante de 2 mm.»* El caso espera que el asistente pregunte por el acabado (RF-05). No lo hace porque el glosario real todavía no da ninguna equivalencia para «brillante»: está en `pendientes_de_confirmacion` (el inventario tiene BA y no tiene 2R). En cuanto el mentor confirme sus valores y Lucas los añada al glosario, el intérprete los usará sin cambiar código.

Queda además una diferencia de criterio por cerrar entre Nacho y Lucas: con un término ambiguo, el módulo busca con todas las opciones y solo pregunta si el stock se distingue por ese dato (RF-07); el caso espera que se pregunte siempre (RF-05).

## Cómo repetirla

Desde la raíz del repositorio, con el `.env` del gateway:

```bash
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# en otra terminal:
python -m tests.evaluar_api --base-url http://127.0.0.1:8000
```

`python -m tests.evaluar_api` (como módulo) para que encuentre `reglas/`. Llama al LLM real: gasta tokens.

## Lo que esta evaluación no mide todavía

- **Casos sin solución (RF-15).** La métrica de resultados solo puntúa casos con solución. Falta añadir casos sin stock al evaluador (Lucas).
- **Alternativas cercanas (RF-29): hecho en el buscador, sin métrica.** Si no hay exactos ni transformables, `buscador.buscar_alternativas()` propone hasta 3 chapas reales del mismo grado, acabado y espesor con otra medida (regla de sustitución de `reglas/sustitucion.py`), las más cercanas primero. Lo cubre `tests/test_alternativas.py`; el evaluador todavía no lo puntúa.
- **Criterio de orden (RF-14): hecho.** El buscador y el evaluador ordenan los transformables por nº de operaciones, luego % de merma y luego ID (como número), como pide el PDF del reto. El orden está en `config.ORDEN_TRANSFORMABLES`; queda confirmarlo con el mentor (¿merma en % o en kg?).

## Otras pruebas del módulo LLM

- `python -m pytest -q`: tests sin conexión (153 en `main`).
- `python tests/bateria_llm.py`: 42 escenarios de conversación contra el LLM real (búsqueda simulada sobre `datos_ejemplo/`), con mediana de 1,3 s por mensaje en las últimas ejecuciones.
