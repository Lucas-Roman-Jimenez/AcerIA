# tests/

Todo se ejecuta desde la raíz del repo con `python -m pytest -q`.

- `test_llm.py`: tests del módulo `llm/` (Nacho), sin conexión ni clave.
- Tests unitarios de cada regla de transformación (Lucas, RF-28, RNF-15).
- Tests de integración del buscador con el motor de reglas (Alonso).
- Conjunto de pruebas de 30–40 peticiones con su resultado esperado y script de evaluación (Lucas, RF-24). El conjunto se fija antes de ajustar los prompts y no se modifica para que salgan mejor.
