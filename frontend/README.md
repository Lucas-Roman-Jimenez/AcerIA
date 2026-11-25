# frontend/ — Stanis (P3)

Chat, tarjetas de bultos, panel «Lo que he entendido», detalle del bulto y lectura en voz alta. React + Vite.

```bash
cd frontend
npm install
npm run dev                                       # http://localhost:5173 con la API falsa
VITE_API_URL=http://localhost:8000 npm run dev    # contra el backend de Alonso
```

## API
- `POST /chat` con `{"conversacion_id", "texto"}` → respuesta de `docs/contrato.md` §6.
- `GET /stock/valores?campo=espesor_mm&grado=304` → `{campo, filtros, valores: [{valor, bultos, toneladas}], total_bultos}`. Lo usan «¿qué grosores hay?», el asistente de uso, la corrección del panel y las alternativas cercanas.
- `GET /stock/resumen` → `[{"etiqueta": "304 BA · chapa", "bultos": 2, "toneladas": 1.0}]` (cinta de stock de la cabecera).

Sin `VITE_API_URL` se usa `src/mock.js`, que lee `datos_ejemplo/inventario.json`. Escribe «error» en el chat para probar el estado de fallo.

## Voz (Lucas)
`src/voz.js`: el micrófono llama a `window.vozLucas.escuchar(onTexto, onError)`. La transcripción va a la caja de texto para revisarla antes de enviar (RF-03).

## Pendiente de acordar
- Transformables: el detalle muestra el «antes» desde `origen` (datos del bulto original) y el «después» desde `resultado`. Ninguno de los dos está en el contrato acordado.
