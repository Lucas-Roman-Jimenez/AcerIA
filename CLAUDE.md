# Contexto del proyecto para Claude Code

Hackathon IndesIAHack 2026, reto de AcerIA: asistente comercial por voz y texto que interpreta peticiones de acero inoxidable, busca bultos reales en el inventario y propone transformaciones permitidas por las reglas de AcerIA.

## Equipo
- Alonso (P1): backend (FastAPI + SQLite), buscador, transformables, ranking, orquestación de la conversación y log.
- Nacho (P2): este módulo `llm/`. Interpreta la petición, valida contra el catálogo, decide las preguntas y redacta la respuesta.
- Stanis (P3): frontend (chat, tarjetas, panel «Lo que he entendido», lectura en voz alta).
- Lucas (P4): `catalogo.json`, `glosario.json`, motor de reglas del TXT, entrada por voz, conjunto de pruebas y script de evaluación.

## Reglas que no se pueden romper
- El LLM solo traduce lenguaje. Qué valores existen, qué bultos hay y qué transformaciones son posibles lo decide el código, nunca el LLM (RNF-02).
- El bot no inventa productos, propiedades, cifras ni bultos (RNF-01). Todo texto del LLM pasa por `control.no_inventa`; si falla, se usa la plantilla.
- Se pregunta en dos momentos: antes de buscar, si faltan datos mínimos o hay valores inválidos; después de buscar, solo por el dato que distingue entre el stock real (RF-07).
- Preguntas en modo mixto: el código decide qué preguntar y el LLM solo lo redacta.
- El conjunto de pruebas de Lucas no se modifica para que los prompts salgan mejor.
- Las claves van en `.env`, que nunca se sube al repositorio.

## Decisiones tomadas
- Python, proveedor de LLM intercambiable (`LLM_PROVEEDOR=anthropic|openai`).
- Contrato ampliado con `largo_mm`, `cantidad`, `opciones`, `uso`, `fuente_uso` y `avisos` (ver README).

## Pendiente
- Confirmar con el mentor `CAMPOS_MINIMOS` (ahora grado + espesor) y las tolerancias.
- Sustituir `datos_ejemplo/` por los datos reales de Lucas.
- Probar los prompts con el LLM real usando `demo_consola.py`.

## Forma de trabajar
- Antes de cualquier decisión importante (cambiar el contrato, añadir dependencias, cambiar la arquitectura), preguntar a Nacho.
- Ejecutar `python -m pytest -q` después de cada cambio.
- Responder en español.

## Estructura del repositorio
- Raíz: `llm/` (módulo de Nacho), `tests/`, `demo_consola.py`, `datos_ejemplo/`.
- Carpetas de cada miembro: `backend/` (Alonso), `frontend/` (Stanis), `datos/`, `reglas/`, `voz/`, `evaluacion/` (Lucas), `docs/`.
- Comandos desde la raíz del repo: `python -m pytest -q`, `python demo_consola.py`.
