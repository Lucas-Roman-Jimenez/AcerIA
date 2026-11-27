# AcerIA

Asistente de inventario de acero inoxidable por texto y voz. Consulta stock de ejemplo, propone transformaciones y gestiona reservas, ventas y reportes de demostración.

## Equipo y propiedad

La propiedad del proyecto AcerIA corresponde a los cuatro integrantes del equipo. La cuenta `Lucas-Roman-Jimenez` es la titular administrativa del repositorio privado en GitHub. La propiedad compartida del proyecto y la titularidad de esa cuenta son independientes.

| Integrante | Aportaciones |
| --- | --- |
| Lucas Román Jiménez (`@Lucas-Roman-Jimenez`) | Catálogo y glosario, motor de reglas de transformación, normalización de voz, escenarios de evaluación y reportes de inventario. |
| Ignacio de Diego Valera (`@Ignacioddv`) | Interpretación de consultas, validación y preguntas de aclaración, plantillas de respuesta, fichas técnicas, documentación de arquitectura e integración de Telegram. |
| Alonso (`@alonsoo-cmd`) | Backend en FastAPI y SQLite, búsqueda y clasificación de alternativas, integración del motor de transformación, reservas, ventas, reposición y seguridad de la API. |
| Stanis (`@stann15`) | Interfaz en React, chat, tarjetas de materiales, panel de interpretación, navegación, reproducción por voz e interfaz de demostración. |

## Arranque local sin claves de IA

Con Python y Node.js instalados, ejecuta desde la raíz:

```bash
python -m pip install -r requirements.txt -r backend/requirements.txt
python arrancar.py
```

El frontend abre en `http://127.0.0.1:5173` y el backend escucha en `http://127.0.0.1:8000`. El backend carga el inventario sintético de `datos_ejemplo/`. Prueba, por ejemplo, «chapa 304 BA de 2 × 1250 × 2000 mm».

La rama principal interpreta el chat con reglas locales, consulta el catálogo y redacta con plantillas. No necesita un `.env` para arrancar ni llama a proveedores de IA. Las expresiones flexibles dependen de los patrones y del glosario. Si la consulta queda incompleta, indica el grado, el espesor y, si procede, el formato y el acabado.

Las fichas PDF solo se sirven si están instaladas en `backend/data/fichas/`. El bot opcional de Telegram usa `TELEGRAM_BOT_TOKEN` desde el entorno o desde un `.env` local ignorado por Git. La interpretación de sus consultas pasa por el mismo backend local.

## Código y pruebas

- `frontend/` contiene la interfaz React.
- `backend/` contiene la API, la búsqueda, el inventario y los reportes.
- `llm/`, `reglas/` y `voz/` contienen la interpretación local, la validación, las transformaciones y la normalización de voz.
- `python -m pytest -q` ejecuta las pruebas. Parte de la batería histórica espera identificadores y cantidades del inventario original.
- `python tests/bateria_llm.py` recorre escenarios de chat con el motor local. La documentación del prototipo original está en `docs/`.
