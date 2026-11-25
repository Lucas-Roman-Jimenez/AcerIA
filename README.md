# AcerIA · Asistente de inventario AcerIA

IndesIAHack 2026, reto de AcerIA: asistente comercial por voz y texto que interpreta peticiones de acero inoxidable, busca bultos reales en el inventario y propone transformaciones permitidas por las reglas de AcerIA.

## Estructura del repositorio

```
llm/             Nacho (P2)  interpretación, validación contra catálogo, preguntas y respuesta
tests/           tests de llm, reglas y buscador; conjunto de pruebas y evaluación (Lucas)
demo_consola.py  prueba real del módulo llm con búsqueda simulada
datos_ejemplo/   catálogo, glosario e inventario inventados para desarrollar
backend/         Alonso (P1) FastAPI + SQLite, buscador, transformables, ranking, orquestación
frontend/        Stanis (P3) chat, tarjetas, panel «Lo que he entendido», voz alta
datos/           Lucas (P4)  catalogo.json y glosario.json reales
reglas/          Lucas (P4)  motor de reglas del TXT (determinista, sin LLM)
voz/             Lucas (P4)  entrada por voz
docs/            documentación del proyecto
```

---

## Módulo LLM (Nacho)

Convierte lo que dice el comercial en una especificación validada contra el catálogo, decide si hay que preguntar algo y redacta la respuesta final. **El LLM solo traduce: qué valores existen y qué hay que preguntar lo decide el código.**

### Puesta en marcha

```bash
pip install -r requirements.txt
cp .env.example .env        # y rellena la clave del proveedor
python -m pytest -q         # 31 tests, sin conexión ni clave
python demo_consola.py      # prueba real con el LLM (búsqueda simulada)
```

El proveedor se elige con `LLM_PROVEEDOR=anthropic|openai` en el `.env`.

### Cómo lo usa el backend (Alonso)

```python
from llm import interpretar, pregunta_tras_busqueda, responder, ErrorLLM

try:
    r = interpretar(historial)          # [{"rol": "comercial"|"asistente", "texto": "..."}]
except ErrorLLM:
    ...                                 # mostrar error y permitir reintentar (RNF-14)

if r.tipo == "pregunta":                # 1.er momento: faltan datos, valor inválido, combinación imposible...
    devolver(r.pregunta, r.especificacion)
else:
    resultado = buscar(r.especificacion)                       # Alonso + motor de reglas de Lucas
    p = pregunta_tras_busqueda(r.especificacion, resultado["exactos"])
    if p:                               # 2.º momento: las opciones reales se distinguen por un dato no dado
        devolver(p, r.especificacion)
    else:
        devolver(responder(resultado, r.especificacion), r.especificacion)
```

`responder()` nunca lanza excepción: si el LLM falla o su texto añade algo que no está en el resultado, usa una plantilla.

### Contrato ampliado (avisar a Alonso y Stanis)
La especificación añade estos campos al contrato original:

| Campo | Para qué | Requisito |
| --- | --- | --- |
| `largo_mm` | Medida que faltaba | RF-04 |
| `cantidad` | `{"valor": 500, "unidad": "kg" \| "t" \| "bultos"}` | RF-04 |
| `opciones` | Valores posibles de un término ambiguo, p. ej. `{"acabado": ["BA", "2R"]}`. **El buscador debe aceptar cualquiera de ellos.** | RF-05 |
| `uso` y `fuente_uso` | Uso reconocido por el catálogo y su fuente, para citarla | RF-26 |
| `avisos` | Mensajes para el usuario (valores descartados, combinaciones inexistentes). Stanis puede mostrarlos en el panel | RF-06 |

El resultado de búsqueda que espera `responder()` admite en cada bulto `peso_kg` y `ubicacion`, en cada transformable `merma_kg`, y una lista opcional `alternativas` (RF-29).

### Decisiones pendientes

- `CAMPOS_MINIMOS` en `llm/interprete.py`: ahora es grado + espesor. **Confirmar con el mentor** qué datos son imprescindibles para buscar.
- Los ficheros de `datos_ejemplo/` son inventados para desarrollar. Lucas los sustituye por los reales (`catalogo.json`, `glosario.json`) con el mismo formato.

### Estructura

```
llm/
  contrato.py     Especificacion, Cantidad, ResultadoInterpretacion
  catalogo.py     valores válidos, combinaciones, usos y glosario
  prompts.py      prompts de extracción, redacción de preguntas y respuesta
  interprete.py   interpretar() y pregunta_tras_busqueda()
  respuesta.py    responder() con plantilla de respaldo
  control.py      control anti-invención de cifras, valores y bultos
  proveedores.py  Anthropic, OpenAI y ClienteFalso para tests
tests/test_llm.py
demo_consola.py
```
