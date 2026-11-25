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

El JSON recoge las expectativas de la evaluación. Adaptar su ejecución al
contrato de la API queda pendiente.
