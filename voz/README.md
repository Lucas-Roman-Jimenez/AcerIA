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
`transcribirVoz()`, que devuelve `{ texto, detener }`. `texto` es una
promesa con la transcripción final en español. Si el navegador no reconoce
voz, la promesa puede resolverse con una cadena vacía. Si ocurre un error
de permisos o del servicio, la promesa se rechaza.

El adaptador devuelve el texto libre para mostrarlo en el compositor y
poder revisarlo o editarlo antes de enviarlo a la conversación.

`normalizacion.normalizar_transcripcion(texto)` aplica las equivalencias de
RF-27 documentadas en «Tareas de Lucas»: «dos be» → `2B` y «trescientos
dieciséis ele» → `316L`. Se puede aplicar a la transcripción en Python
antes de pasarla al intérprete.

Pruebas desde la raíz del proyecto.

```bash
python -m pytest tests/test_normalizacion.py -q
node --test tests/test_microfono.mjs
```
