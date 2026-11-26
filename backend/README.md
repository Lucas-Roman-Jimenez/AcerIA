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

## Reporte diario de inventario

`GET /reportes/inventario/diario` devuelve el título, la fecha en
`Europe/Madrid` y las combinaciones de `datos/catalogo.json` sin bultos
físicos en inventario. El identificador combina formato, grado, acabado,
espesor y ancho. La fecha de agotamiento se obtiene de la última baja
registrada en compras y es `null` cuando el historial no la acredita.
Los bultos reservados o bloqueados siguen contando como stock físico.

## Reporte semanal de compras

`GET /reportes/compras/semanal` devuelve el título, la semana de lunes a
domingo en `Europe/Madrid` y una fila por bulto comprado durante esa semana.
Cada fila incluye el formato en el título y muestra el ID del bulto, grado
(AISI o Euronorma), acabado, espesor, ancho, largo cuando consta y peso.
Las cantidades sustraídas se suman por bulto y unidad. Si hay varios
movimientos del mismo bulto, se muestran las características del más reciente.

`GET /reportes/compras/tendencias?semanas=8&unidad=kg` reconstruye el reporte
consolidado de cada semana y usa sus compras como fuente de las barras.
Devuelve barras por semana y formato y ordena los materiales por cantidad.
Cada material se identifica por formato, grado, acabado y medidas. El peso
en toneladas se convierte a kg. Las vistas de bultos y piezas son separadas.
El comparativo con stock actual se ofrece en kg o bultos.

La semana en curso y la primera con movimientos se marcan aparte. El
porcentaje compara semanas cerradas consecutivas y queda en `null` cuando
falta una base comparable o el valor anterior es cero. El periodo anterior
al primer movimiento se devuelve como `sin_historial`, con barras nulas.

## Reposición

`GET /reportes/reposicion` usa las ventas de las últimas 4 semanas completas
(lunes a domingo en `Europe/Madrid`, sin la semana en curso) y el stock
disponible en el momento de la consulta. Agrupa por la misma referencia que
Tendencias. Las ventas en t se pasan a kg y un bulto entero cuenta con su peso
si no hay kg ni t registrados; las piezas no cuentan. La cobertura es
`stock ÷ (kg vendidos ÷ 28)` y los umbrales se evalúan antes de redondear:

- `reponer`: ventas en 2 semanas o más y cobertura < 7 días.
- `vigilar`: ventas en 2 semanas o más y cobertura de 7 a 14 días.
- `puntual`: ventas en una sola semana y menos de 2 t disponibles.

Devuelve `periodo`, `stock_a` (fecha y hora del stock), `umbrales`, `filtro` y
`secciones` con las tres listas ordenadas por menor cobertura y mayor venta.
Cada fila trae la referencia, `vendido_t`, `disponible_t`, `semanas_con_ventas`,
`cobertura_dias` y `cumple_filtro` (más de 2 t vendidas y menos de 2 t
disponibles). Las referencias que no entran en ninguna sección no se devuelven.

Para que se vea con datos, cada arranque crea ventas simuladas
(`app/ventas_demo.py`) de las 4 semanas completas anteriores a partir del stock
real, con filas en las tres secciones. Ninguna cae en la semana en curso, así
que el reporte semanal solo muestra ventas reales. Sus IDs empiezan por `demo-`
y sus bultos no existen, así que no quitan stock. Se recrean en cada arranque;
`python arrancar.py --sin-ventas-demo` las borra. Las ventas reales no se tocan.

El flujo de baja debe llamar a `app.reportes.registrar_compra` dentro de la
misma transacción que actualiza el stock, pasando el bulto original antes
de la baja, un ID único por movimiento, la cantidad realmente descontada,
la unidad y una fecha con zona horaria. Si una compra agrupa varios bultos,
cada movimiento debe tener un ID distinto. La función usa la conexión
recibida y el llamador controla el commit o rollback. El registro de compras
se conserva al reiniciar, salvo que se reinicie la demo (ver «Venta simulada del carrito»).

## Venta simulada del carrito

`POST /compras` con `{"bultos": ["334", "23"]}` vende los bultos del carrito
(simulación para la demo: no toca los sistemas de AcerIA). En una sola
transacción, cada bulto se registra con `registrar_compra()` (aparece en el
reporte semanal, con su peso en kg) y pasa a estado `vendido`, así deja de
salir en `/buscar`, `/chat` y `/stock`. Si alguno no existe o ya no está
disponible responde `409` con `no_disponibles` y no vende ninguno.

**Al reiniciar se conserva todo:** se recarga el Excel, pero los bultos que ya
están en `compras` se vuelven a marcar como `vendido` y el reporte mantiene su
historial. **Para empezar la demo de cero:** `python arrancar.py --reiniciar-demo`
(o arrancar el backend con `ACERIA_REINICIAR_DEMO=1`): vacía `compras` y el
inventario vuelve a estar completo.
