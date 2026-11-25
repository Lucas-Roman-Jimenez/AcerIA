# tests/

Todo se ejecuta desde la raíz del repo con `python -m pytest -q`.

- `test_llm.py`: tests del módulo `llm/` (Nacho), sin conexión ni clave.
- Tests unitarios de cada regla de transformación (Lucas, RF-28, RNF-15).
- Tests de integración del buscador con el motor de reglas (Alonso).
- Conjunto de pruebas de 30–40 peticiones con su resultado esperado y script de evaluación (Lucas, RF-24). El conjunto se fija antes de ajustar los prompts y no se modifica para que salgan mejor.

[`casos_evaluacion.json`](casos_evaluacion.json) reúne 32 peticiones:

- 16 exactas, con un ID de referencia de la hoja `DATA` y los valores
  literales del Excel. El ID acredita una coincidencia en la muestra y las
  medidas se conservan sin asignar unidades.
- 8 de aclaración, con el campo que falta o es ambiguo. La ambigüedad de
  «brillante» viene de «Tareas de Lucas».
- 4 transformaciones con los ejemplos del Word y 4 peticiones imposibles
  derivadas de sus restricciones y del ejemplo de corte imposible del PDF.
  Cada una fija el bulto de origen en la propia petición. El resultado
  esperado se refiere a esa operación, sin asociarla a un ID de stock.

## Evaluación de la API

Con la API de Alonso en marcha, ejecuta desde la raíz del proyecto:

```bash
python -m tests.evaluar_api --base-url http://127.0.0.1:8000 > informe_evaluacion.json
```

El informe JSON incluye el porcentaje y los fallos de cada métrica:

- **Resultados** (`POST /buscar`): busca el ID de referencia entre las
  coincidencias exactas de los 16 casos de stock. Comprueba que los
  transformables estén ordenados por `merma_pct` ascendente y, en caso de
  empate, por `num_operaciones` ascendente. El conjunto aporta una
  coincidencia exacta comprobada por caso, sin fijar todas las coincidencias
  exactas ni su orden.
- **Interpretación** (`POST /chat`): comprueba los campos de la especificación
  o el campo que requiere aclaración en 24 peticiones, cada una con su propia
  conversación.
- **Reglas locales**: ejecuta los 8 casos referidos a una operación y un
  bulto de origen del Word o del PDF. Estos casos carecen de un ID de stock
  asociado y se comprueban de forma local.

El comando devuelve un código de error si alguna métrica de la API queda por
debajo del 85 % o falla alguna comprobación local.
