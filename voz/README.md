# voz/ — Lucas (P4)

La entrada por voz transcribe lo que dice el comercial en lenguaje natural.
La integración envía la transcripción completa por el mismo flujo que una
petición escrita, con el contexto de la conversación. El LLM debe decidir
qué información es útil y qué aclaración pedir. La validación contra el
catálogo, el inventario y las reglas de transformación sigue a cargo del
código. En el intérprete actual, la selección de la pregunta todavía se
hace en código.

## Micrófono en el navegador

`microfono.mjs` usa la [Web Speech API](https://wicg.github.io/speech-api/).
El chat puede llamar a `microfonoDisponible()` para comprobar si el
navegador ofrece reconocimiento. Desde el botón de micrófono, llama a
`transcribirVoz()`, que devuelve `{ texto, detener, cancelar }`. `texto` es una
promesa con la transcripción final en español. Si el navegador no reconoce
voz, la promesa puede resolverse con una cadena vacía. Si ocurre un error
de permisos o del servicio, la promesa se rechaza.

El punto de entrada del frontend en `frontend/src/voz.js` conecta el botón
del chat con este adaptador. Puedes detener la escucha pulsando el mismo
botón. El chat añade el dictado a la caja de texto para revisarlo o
editarlo antes de enviarlo. Cambiar de conversación descarta el dictado
en curso.

El navegador aplica las equivalencias de RF-27 documentadas en «Tareas de
Lucas» («dos be» → `2B` y «trescientos dieciséis ele» → `316L`). La tabla
`equivalencias.json` se comparte con el normalizador de Python.

Pruebas desde la raíz del proyecto.

```bash
python -m pytest tests/test_normalizacion.py -q
node --test tests/test_microfono.mjs
```

## Medir reconocimiento con micrófono

Dicta cada frase de `tests/casos_voz.json` en el chat. Copia lo que aparece
en la caja de texto antes de editarlo y guárdalo como JSON por ID
(`{"VOZ-01": "Necesito acabado 2B."}`). Usa `""` si el dictado acaba sin
texto. Omite un ID únicamente si todavía no has intentado ese dictado.

```bash
node tests/evaluar_voz.mjs transcripciones.json
node --test tests/test_evaluar_voz.mjs
```

Se cuenta un acierto si aparecen todos los códigos esperados del dictado.
El objetivo deseable de RNF-08 es el 90 %. El informe da el porcentaje al
completar los diez dictados e identifica los códigos que se perdieron.
