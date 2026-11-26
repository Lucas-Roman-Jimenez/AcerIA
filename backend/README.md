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
domingo en `Europe/Madrid` y una fila por bulto comprado durante esa semana.
Cada fila incluye el formato en el título y muestra el ID del bulto, grado
(AISI o Euronorma), acabado, espesor, ancho, largo cuando consta y peso.
Las cantidades sustraídas se suman por bulto y unidad. Si hay varios
movimientos del mismo bulto, se muestran las características del más reciente.

El flujo de baja debe llamar a `app.reportes.registrar_compra` dentro de la
misma transacción que actualiza el stock, pasando el bulto original antes
de la baja, un ID único por movimiento, la cantidad realmente descontada,
la unidad y una fecha con zona horaria. Si una compra agrupa varios bultos,
cada movimiento debe tener un ID distinto. La función usa la conexión
recibida y el llamador controla el commit o rollback. El registro de compras
se conserva cuando se vuelve a cargar la muestra de inventario.
