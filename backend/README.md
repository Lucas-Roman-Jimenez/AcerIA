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

## Reporte semanal de compras

`GET /reportes/compras/semanal` devuelve el título, la semana de lunes a
domingo en `Europe/Madrid` y una fila por movimiento de compra confirmado.
Cada fila conserva las características del bulto y la cantidad sustraída
con su unidad explícita.

El flujo de baja debe llamar a `app.reportes.registrar_compra` dentro de la
misma transacción que actualiza el stock, pasando el bulto original antes
de la baja, un ID único por movimiento, la cantidad realmente descontada,
la unidad y una fecha con zona horaria. Si una compra agrupa varios bultos,
cada movimiento debe tener un ID distinto. La función usa la conexión
recibida y el llamador controla el commit o rollback. El registro de compras
se vacía en cada arranque (modo demo, ver «Venta simulada del carrito»).

## Venta simulada del carrito

`POST /compras` con `{"bultos": ["334", "23"]}` vende los bultos del carrito
(simulación para la demo: no toca los sistemas de AcerIA). En una sola
transacción, cada bulto se registra con `registrar_compra()` (aparece en el
reporte semanal, con su peso en kg) y pasa a estado `vendido`, así deja de
salir en `/buscar`, `/chat` y `/stock`. Si alguno no existe o ya no está
disponible responde `409` con `no_disponibles` y no vende ninguno.

**Modo demo:** al arrancar se recarga el Excel y se vacía `compras`, así que
cada demo empieza con el inventario completo y el reporte vacío. Lo vendido
solo dura hasta que se reinicia el backend.
