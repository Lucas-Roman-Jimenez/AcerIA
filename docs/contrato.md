# Contrato JSON del módulo LLM

Responsable: Nacho (P2). Afecta a Alonso (P1), que llama a estas funciones, y a Stanis (P3), que pinta la especificación y los bultos.

**Norma de equipo:** el contrato no se cambia sin avisar a los cuatro. **Estado (26/11/2026):** todo lo que describe este documento está implementado en `main`; las antiguas propuestas (`resultado`, `criterio_orden`, respuesta de `/chat`) ya están acordadas.

Los ejemplos usan los datos inventados de `datos_ejemplo/` (IDs como `B-1023`). En el inventario real los IDs son números (`"1343"`).

---

## 1. Flujo de llamadas

```python
from llm import interpretar, pregunta_tras_busqueda, responder, ErrorLLM

try:
    r = interpretar(historial)
except ErrorLLM:
    ...  # mostrar error y permitir reintentar o escribir (RNF-14)

if r.tipo == "pregunta":                     # 1.er momento: antes de buscar
    devolver(pregunta=r.pregunta, especificacion=r.especificacion)
else:
    resultado = buscar(r.especificacion)     # Alonso + motor de reglas de Lucas
    p = pregunta_tras_busqueda(r.especificacion, resultado["exactos"], historial=historial)
    if p:                                    # 2.º momento: el stock real se distingue por un dato no dado (RF-07)
        devolver(pregunta=p, especificacion=r.especificacion)
    else:
        devolver(texto=responder(resultado, r.especificacion), especificacion=r.especificacion)
```

- `interpretar()` puede lanzar `ErrorLLM`. Es el único caso en que el módulo lanza una excepción.
- `pregunta_tras_busqueda()` no usa el LLM: devuelve siempre una plantilla, rápida y sin errores posibles.
  El parámetro `historial` es opcional pero **recomendado**: si la última pregunta del asistente ya era la misma
  (el comercial no la ha resuelto, p. ej. «el brillante» ante «¿2R o BA?»), no se repite y se muestran todos los bultos.
- `responder()` nunca lanza excepción. Por defecto usa una plantilla (instantánea y sin riesgo de inventar); con `usar_llm=True` redacta el LLM y, si falla o inventa algo, vuelve a la plantilla.

---

## 2. Entrada de `interpretar()`: el historial

Lo guarda Alonso por conversación (RF-08) y se envía completo en cada mensaje, incluidas las preguntas del asistente.

```json
[
  {"rol": "comercial", "texto": "Necesito 304 de 2 mm"},
  {"rol": "asistente", "texto": "Tengo 304 de 2 mm en BA y en 2R. ¿Cuál prefieres?"},
  {"rol": "comercial", "texto": "BA"}
]
```

`rol` solo puede valer `"comercial"` o `"asistente"`. En una conversación nueva (RF-22), el historial se vacía.

---

## 3. Salida de `interpretar()`

```json
{
  "tipo": "especificacion",
  "especificacion": { ... },
  "pregunta": null
}
```

| `tipo` | Qué significa | Qué hace el backend |
| --- | --- | --- |
| `"especificacion"` | Hay datos suficientes y válidos para buscar | Buscar con `especificacion` |
| `"pregunta"` | Faltan datos, hay un valor inválido, una combinación imposible o una contradicción. También cuando el mensaje no es un pedido: saludo, agradecimiento, precio, plazo, reserva, consulta técnica o fuera de tema (RF-09), y cuando se pide consejo para una obra sin grado («un edificio donde llueve mucho»): se cita lo que documenta AcerIA y se pregunta lo que falta (`orientaciones_obra` del catálogo, de Lucas) | Devolver `pregunta` al comercial sin buscar |

En los dos casos se devuelve la especificación, para que el panel «Lo que he entendido» (RF-18) la muestre siempre.

---

## 4. La especificación

| Campo | Tipo | Origen | Descripción |
| --- | --- | --- | --- |
| `grado` | texto o `null` | Original | Valor exacto del catálogo, p. ej. `"304"` |
| `acabado` | texto o `null` | Original | Valor exacto del catálogo, p. ej. `"BA"` |
| `formato` | texto o `null` | Original | `"chapa"`, `"bobina"` o `"fleje"` |
| `espesor_mm` | número o `null` | Original | Siempre en milímetros |
| `ancho_mm` | número o `null` | Original | Siempre en milímetros |
| `faltan` | lista de textos | Original | Campos mínimos que aún no se conocen |
| `largo_mm` | número o `null` | **Nuevo** | Siempre en milímetros (RF-04) |
| `cantidad` | objeto o `null` | **Nuevo** | `{"valor": 500, "unidad": "kg"}`; la unidad es `"kg"`, `"t"` o `"bultos"` (RF-04) |
| `opciones` | objeto | **Nuevo** | Valores posibles de un término ambiguo, p. ej. `{"acabado": ["BA", "2R"]}` (RF-05) |
| `uso` | texto o `null` | **Nuevo** | Uso reconocido por el catálogo, p. ej. `"ambiente marino"` (RF-26) |
| `fuente_uso` | texto o `null` | **Nuevo** | Fuente del catálogo que respalda el uso, para citarla (RF-26) |
| `avisos` | lista de textos | **Nuevo** | Mensajes para el usuario: valores descartados, combinaciones que no existen o usos que el catálogo no respalda (RF-06). Los avisos sobre el uso se dicen también en el texto de la pregunta o la respuesta |
| `indiferentes` | lista de textos | **Nuevo** | Campos que al comercial le dan igual («me da igual el acabado»). No se preguntan ni cuentan en `faltan`; el buscador no filtra por ellos |

**Garantías del módulo:**
- Todos los valores de `grado`, `acabado` y `formato`, y también los de `opciones`, existen en `catalogo.json`. El LLM nunca pasa un valor sin validar (RNF-01, RNF-02).
- Un campo no tiene valor y opciones a la vez: si `acabado` tiene valor, no aparece en `opciones`.

**Regla para el buscador (Alonso):** si un campo es `null` pero tiene `opciones`, el bulto cumple con **cualquiera** de esos valores. Si el stock real se distingue por ese campo, `pregunta_tras_busqueda()` pregunta después de buscar.

Ejemplo para «chapa brillante 304 de 2 mm, unos 500 kg»:

```json
{
  "grado": "304",
  "acabado": null,
  "formato": "chapa",
  "espesor_mm": 2.0,
  "ancho_mm": null,
  "largo_mm": null,
  "cantidad": {"valor": 500, "unidad": "kg"},
  "uso": null,
  "opciones": {"acabado": ["BA", "2R"]},
  "fuente_uso": null,
  "faltan": [],
  "avisos": [],
  "indiferentes": []
}
```

---

## 5. Resultado de búsqueda que espera `responder()`

Lo construye Alonso. El acordado era `exactos` y `transformables`; se añaden campos opcionales.

```json
{
  "exactos": [
    {"id": "B-1023", "grado": "304", "acabado": "BA", "formato": "chapa",
     "espesor_mm": 2.0, "ancho_mm": 1250, "peso_kg": 520, "ubicacion": "Nave 3"}
  ],
  "transformables": [
    {"id": "B-1030",
     "acciones": ["Cortar ancho 1500 → 1250 mm"],
     "merma_kg": 150,
     "resultado": {"grado": "304", "acabado": "2B", "formato": "chapa",
                   "espesor_mm": 3.0, "ancho_mm": 1250}}
  ],
  "alternativas": []
}
```

| Campo | Origen | Descripción |
| --- | --- | --- |
| `exactos[]` | Original | Bultos que cumplen sin transformar. `id` obligatorio |
| `exactos[].peso_kg`, `.ubicacion` | **Nuevo**, opcional | Se mencionan solo si vienen (RF-17) |
| `transformables[].acciones` | Original | Lista de acciones del motor de reglas. El motor de Lucas las devuelve como objetos `{"regla", "descripcion", "parametros", …}`; `responder()` usa `descripcion` |
| `transformables[].bulto` | Acordado | El backend manda el bulto de origen en `bulto` (con su `id`) y además copia el `id` arriba para el frontend |
| `transformables[].merma_kg`, `.merma_pct` | **Nuevo**, opcional | Merma estimada en kg y en % (RF-13) |
| `transformables[].resultado` | Acordado | Cómo queda el bulto tras transformar (RF-13, RF-20). Ver sección 7 |
| `criterio` / `criterio_orden` | Acordado, opcional | Texto con el criterio de ordenación del ranking (RF-14). El backend lo manda como `criterio_orden`: `"exactos > nº de operaciones > % de merma > ID"` (sale de `config.ORDEN_TRANSFORMABLES`). `responder()` acepta las dos claves y lo añade como «Orden: …» (RNF-09). Si no viene, no se dice nada |
| `alternativas[]` | **Nuevo**, opcional | Bultos reales cercanos que **no** cumplen (RF-29). Solo se rellena cuando no hay `exactos` ni `transformables`. Cada elemento es un bulto con el mismo formato que `exactos[]` más `diferencias: list[str]` (p. ej. `"ancho 1000 mm (pedido 1250 mm)"`). Con la regla de sustitución de AcerIA: chapa del mismo grado, acabado y espesor con otra medida (ancho × largo), como mucho `config.MAX_ALTERNATIVAS` (3), las más cercanas primero. Siempre se presentan como alternativa, y `estado` sigue siendo `"sin_stock"` |

`responder()` solo menciona datos de este JSON. Si no hay `exactos` ni `transformables`, dice claramente que no hay stock (RF-15).

---

## 6. Respuesta de `POST /chat` para el frontend

Implementada por Alonso en `backend/app/conversacion.py` y `main.py`. Stanis tiene en una sola respuesta todo lo que pinta.

```json
{
  "conversacion_id": "c-001",
  "estado": "resultados",
  "tipo": "respuesta",
  "texto": "Hay 1 bulto que cumple la petición: B-1023 (304 BA, 2 × 1250 mm, 520 kg, Nave 3).",
  "pregunta": null,
  "especificacion": { ... },
  "exactos": [ ... ],
  "transformables": [ ... ],
  "alternativas": [],
  "opciones": [],
  "criterio_orden": "exactos > nº de operaciones > % de merma > ID",
  "error": null,
  "aviso_ia": {
    "generado_por_ia": true,
    "texto": "Respuesta generada por IA. Los bultos y las transformaciones salen del inventario y las reglas de AcerIA; revísalos antes de confirmar.",
    "texto_voz": "Respuesta generada por inteligencia artificial.",
    "inicio": "Estás hablando con un asistente de inteligencia artificial. …"
  }
}
```

- `estado`: `"pregunta"`, `"resultados"`, `"sin_stock"` o `"error"`. `tipo` es la versión corta para el frontend: `"pregunta"`, `"respuesta"` o `"error"`.
- `criterio_orden`: criterio con el que vienen ordenadas las tarjetas (RF-14, RNF-09). `opciones` queda vacío (botones sin acordar).
- `texto` o `pregunta`: lo que se muestra en el chat y se lee en voz alta (RF-21).
- `especificacion`: siempre presente, para el panel «Lo que he entendido» (RF-18) y para marcar `faltan`.
- `exactos`, `transformables` y `alternativas`: para las tarjetas (RF-17), con distinto color para cada tipo.
- `error`: mensaje claro si falló el LLM, para mostrar el botón de reintentar (RNF-14).
- `aviso_ia` (Reglamento de IA de la UE, art. 50; ver `docs/legal_ia.md`): `generado_por_ia` es la marca legible por máquina. El frontend pinta `texto` en cada respuesta del asistente, lee `texto_voz` en la lectura en voz alta y muestra `inicio` una vez al abrir el chat. Es `null` cuando `tipo` es `"error"`. Los textos salen de `llm/aviso.py`.

---

## 7. Campo `resultado` en cada transformable (acordado)

RF-13 pide indicar «las acciones necesarias, el resultado final y la merma», y RF-20 el «antes y después». El contrato original solo traía `id` y `acciones`.

El motor de reglas de Lucas devuelve, y Alonso pasa tal cual, un objeto `resultado` con los mismos campos que un bulto (`grado`, `acabado`, `formato`, `espesor_mm`, `ancho_mm`, `largo_mm`, `peso_kg`) tal como quedaría tras transformarlo.

`responder()` lo usa si viene: «B-1030 (Cortar ancho 1500 → 1250 mm; merma 150 kg; queda 304 2B, 3 × 1250 mm)». Si no viene, sigue funcionando sin él.


---

## 8. Reservas del carrito (tarea 4)

**Nuevo.** Sirve para que dos comerciales no cojan el mismo bulto. Al añadir un bulto al carrito se reserva para quien lo añade durante `config.RESERVA_MINUTOS` (15). Mientras la reserva está vigente:

- el bulto **no sale** en `/buscar`, `/chat`, `/stock/valores` ni `/stock/resumen`, ni siquiera para quien lo reservó, porque ya lo tiene en el carrito;
- nadie más puede reservarlo ni venderlo.

Al quitarlo del carrito, o cuando caduca la reserva, vuelve a estar disponible. Las reservas se vacían cada vez que arranca el backend.

**Quién reserva:** se identifica con la cabecera `X-Carrito`, que lleva un ID aleatorio del carrito (128 bits, generado en el frontend, de 100 caracteres como mucho). La lleva **cada** llamada de esta sección y también `POST /compras`. Es provisional: cuando haya login (tarea 5), el titular saldrá del token.

| Llamada | Cuándo | Respuesta |
| --- | --- | --- |
| `POST /reservas` con `{"bultos": ["334"]}` | Al añadir al carrito | 200 `{"reservas": [{"bulto_id": "334", "expira_en": "2026-11-26T10:15:00+01:00"}], "minutos": 15}`. Se reservan todos o ninguno. Si un bulto ya era tuyo, se renueva su caducidad. 409 `{"detail": {"mensaje": ..., "no_disponibles": ["334"]}}` si alguno lo tiene otro o no está disponible. |
| `DELETE /reservas/{bulto_id}` | Al quitar un bulto del carrito | 204. Si no está en tu carrito, 404. |
| `DELETE /reservas` | Al vaciar el carrito | 200 `{"liberadas": 2}`. Solo libera las tuyas. |
| `GET /reservas` | Al recargar la página | 200 `{"reservas": [...], "minutos": 15}`: tus reservas vigentes, en el orden en que se añadieron. |
| `POST /compras` con `{"bultos": [...]}` | Al confirmar la venta | **Cambia:** solo vende los bultos con reserva vigente **tuya**. Si no, 409 con `no_disponibles` y no se vende nada. Al vender se borran esas reservas. |

Sin la cabecera `X-Carrito`, todas responden 422 con `"Falta la cabecera X-Carrito."`. En `/compras`, el texto es `"El carrito está vacío o no es válido."`.

---

## Pendiente de confirmar con el mentor

- Campos mínimos para buscar (`CAMPOS_MINIMOS` en `llm/interprete.py`; ahora `grado` y `espesor_mm`).
- Tolerancias de espesor y ancho (las aplica el buscador de Alonso, no este módulo).
- Criterio RF-14: si la merma se ordena en % o en kg (ahora en %).
