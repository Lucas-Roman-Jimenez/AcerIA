# voz/ — Lucas (P4)

Entrada por voz: transcripción de lo que dice el comercial antes de pasarlo a `llm.interpretar()`.

`normalizacion.normalizar_transcripcion(texto)` aplica las equivalencias de
RF-27 documentadas en «Tareas de Lucas»: «dos be» → `2B` y «trescientos
dieciséis ele» → `316L`.

Desde la raíz del proyecto:

```bash
python -m unittest voz.test_normalizacion -v
```
