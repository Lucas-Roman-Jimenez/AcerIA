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
- El código decide qué preguntar. Por defecto la pregunta sale de una plantilla; el LLM solo la redacta si se activa `redactar_con_llm=True`, y aun así se valida con `no_inventa` y `conserva_datos`.
- El conjunto de pruebas de Lucas no se modifica para que los prompts salgan mejor.
- Las claves van en `.env`, que nunca se sube al repositorio.

## Decisiones tomadas
- Python, proveedor de LLM intercambiable (`LLM_PROVEEDOR=anthropic|openai`).
- Contrato ampliado con `largo_mm`, `cantidad`, `opciones`, `uso`, `fuente_uso`, `avisos` e `indiferentes`, y `aviso_ia` en `/chat` (ver `docs/contrato.md`).
- La salida del LLM se valida en dos capas: forma y tipos con Pydantic (`llm/modelos.py`) y valores contra el catálogo en `interprete._validar()`.
- Si al comercial le da igual un dato, `responder()` recomienda el valor con más stock (por kg si el pedido es en kg o t). Lo calcula el código.
- El LLM solo hace la extracción (una llamada por mensaje). Las preguntas y las respuestas salen de plantillas por defecto, por velocidad (RNF-05) y para que no inventen (RNF-01). `pregunta_tras_busqueda()` no usa nunca el LLM. No cambiar esto sin preguntar a Nacho.
- LLM del hackathon: Claude por el AI Gateway de Databricks. El modelo se llama `system.ai.claude-sonnet-5-5` (sin el prefijo `system.ai.` da 403).
- Los mensajes que no son un pedido (saludo, gracias, precio, plazo, reserva, consulta técnica, fuera de tema) tienen respuesta fija, sin LLM.

## Pendiente
Estado a 26/11/2026: catálogo y glosario reales en `datos/`, `/chat` conectado, evaluación de Lucas al 100 % y batería de 53 escenarios sin fallos (`docs/evaluacion.md`). Queda:
- Confirmar con el mentor `CAMPOS_MINIMOS` (ahora grado + espesor), las tolerancias y si la merma del orden RF-14 va en % o en kg.
- Stanis: pintar la nota de IA desde `aviso_ia` de `/chat` (`docs/legal_ia.md` §3), `indiferentes` («Cualquiera») y unificar los títulos de los grados (EN y AISI se mezclan en las tarjetas).
- Formato de las opciones para botones en `/chat` (`opciones` va vacío).
- Antes de presentar: `python arrancar.py --reiniciar-demo` y el guion de `docs/guion_demo.md`.

## Normas de equipo
- Carpetas acordadas: `backend/`, `llm/`, `frontend/`, `voz/` y `tests/`. Cada persona en su rama, con merge frecuente a `main`.
- El contrato JSON no se cambia sin avisar a los cuatro.
- Los fallos van a issues, asignados a quien le toque.
- A partir de las 12:00 del día 3, nada de funcionalidades nuevas: solo arreglar fallos.
- Requisitos, análisis y reparto: ver `docs/README.md`.

## Forma de trabajar
- Antes de cualquier decisión importante (cambiar el contrato, añadir dependencias, cambiar la arquitectura), preguntar a Nacho.
- Ejecutar `python -m pytest -q` después de cada cambio.
- Responder en español.

## Estructura del repositorio
- Raíz: `llm/` (módulo de Nacho), `tests/`, `arrancar.py`, `datos/` (catálogo real) y `datos_ejemplo/` (solo tests y frontend sin backend).
- Carpetas de cada miembro: `backend/` (Alonso), `frontend/` (Stanis), `datos/`, `reglas/`, `voz/` (Lucas), `docs/`. `tests/` es común: tests de cada pieza, conjunto de pruebas y script de evaluación.
- Comandos desde la raíz del repo: `python -m pytest -q`, `python arrancar.py` (`--reiniciar-demo` para empezar sin ventas) y `python tests/bateria_llm.py`.
