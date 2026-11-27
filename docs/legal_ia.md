# Uso de IA: transparencia, normativa europea y datos

> Documento del prototipo original. La rama principal actual usa el intérprete local y el inventario sintético. Consulta el README para arrancar la versión actual.

Responsable: Nacho (P2). Describe cómo usa la IA el asistente comercial y qué obligaciones legales le afectan. **No es asesoramiento jurídico:** antes de llevarlo a producción, lo tiene que revisar el equipo legal de AcerIA.

---

## 1. Qué hace la IA y qué no

| Lo hace un LLM (Claude, por el AI Gateway de Databricks) | Lo hace el código, sin IA |
| --- | --- |
| Entender lo que escribe o dicta el comercial y pasarlo a una especificación (grado, acabado, medidas…) | Validar esa especificación contra el catálogo de AcerIA |
| | Buscar los bultos en el inventario |
| | Decidir qué transformaciones se pueden hacer (motor de reglas) y calcular la merma |
| | Decidir qué preguntar y redactar las respuestas (plantillas) |
| | Recomendar una opción cuando al comercial le da igual un dato (por stock) |

- El LLM **no decide** qué existe, qué hay en stock ni qué se puede hacer (RNF-02). Si devuelve un valor que no está en el catálogo, el código lo descarta.
- Las respuestas salen de plantillas con datos del inventario. Si algún día se activa la redacción por LLM (`usar_llm=True`), el texto pasa por `control.no_inventa` y, si añade cifras, valores o bultos que no están en los datos, se sustituye por la plantilla (RNF-01).
- **Hay siempre un humano que decide.** El asistente propone; el comercial revisa y confirma la venta. En la demo, la venta es una simulación que no toca los sistemas de AcerIA.

---

## 2. Reglamento de IA de la UE (Reglamento (UE) 2024/1689, «AI Act»)

### Clasificación del sistema

- **No es una práctica prohibida** (art. 5).
- **No es de alto riesgo** (art. 6 y anexo III): no decide sobre personas (empleo, crédito, servicios esenciales…), solo ayuda a encontrar material en stock.
- **Le aplican las obligaciones de transparencia del art. 50**, porque interactúa con personas y genera texto.

### Papeles

- **Proveedor del sistema:** quien lo desarrolla y lo pone en servicio (el equipo; en producción, AcerIA o quien lo desarrolle).
- **Responsable del despliegue:** AcerIA, que lo usa con sus comerciales.
- **Proveedor del modelo de uso general (GPAI):** Anthropic (Claude), con sus propias obligaciones (art. 53).

### Obligaciones y cómo se cumplen

| Obligación | Qué pide | Cómo lo cumplimos |
| --- | --- | --- |
| Art. 50.1: informar de que se interactúa con una IA | Que la persona sepa que habla con un sistema de IA, salvo que sea evidente | Aviso al abrir el chat y nota en cada respuesta (sección 3) |
| Art. 50.2: marcar el contenido generado | Que el texto generado se pueda identificar como generado por IA, también de forma legible por máquina | Nota visible en cada respuesta y campo `aviso_ia.generado_por_ia: true` en cada respuesta de `POST /chat` (`docs/contrato.md` §6) |
| Art. 4: alfabetización en IA | Que quien usa el sistema sepa cómo funciona y sus límites | Esta guía y una formación breve a los comerciales: el asistente puede equivocarse al interpretar y hay que revisar antes de confirmar |
| Art. 50.4: texto publicado para informar al público | Solo para textos de interés público | No aplica: las respuestas son internas |

**Fechas:** el reglamento está en vigor desde el 1 de agosto de 2024. La alfabetización (art. 4) se aplica desde el 2 de febrero de 2025 y la transparencia (art. 50), desde el 2 de agosto de 2026.

**Ómnibus Digital sobre IA (Reglamento (UE) 2026/1744, en vigor desde el 27 de julio de 2026)**, comprobado el 26/11/2026:

- **No aplaza el art. 50.** La transparencia se aplica desde el 2 de agosto de 2026, como estaba previsto.
- **Única transición:** los sistemas generativos que ya estaban en el mercado antes del 2 de agosto de 2026 tienen hasta el **2 de diciembre de 2026** para el marcado legible por máquina (art. 50.2). Un sistema nuevo, como este, tiene que cumplirlo desde que se pone en servicio. Por eso `aviso_ia` va ya en cada respuesta.
- **Lo que sí se aplaza** es el alto riesgo del anexo III, hasta el 2 de diciembre de 2027. A este asistente no le afecta, porque no es de alto riesgo.
- La Comisión publicó sus directrices sobre el art. 50 en julio de 2026.

Fuentes consultadas (secundarias; para producción, revisar el texto en el DOUE): [euai-act.com](https://www.euai-act.com/es/articles/eu-ai-act-digital-omnibus-2026), [Jones Walker](https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html), [Delvy](https://delvy.es/omnibus-digital-sobre-ia-articulo-50-ai-act/), [Economist & Jurist](https://www.economistjurist.es/articulos-juridicos-destacados/europa-reescribe-el-ai-act-el-omnibus-de-ia-ya-es-ley-y-la-transparencia-no-espera/).

---

## 3. Textos de aviso (para el frontend)

Llegan en cada respuesta de `POST /chat`, en el campo `aviso_ia` (`texto`, `texto_voz` e `inicio`), y salen de `llm/aviso.py`. Si hay que cambiarlos, se cambian solo ahí.

**Al abrir el chat (una vez por conversación):**

> Estás hablando con un asistente de inteligencia artificial. Interpreta tu petición y busca en el inventario real de AcerIA, pero puede equivocarse: revisa los bultos antes de confirmar.

**En cada respuesta del asistente** (al final o al lado del texto; no en los mensajes del comercial):

> Respuesta generada por IA. Los bultos y las transformaciones salen del inventario y las reglas de AcerIA; revísalos antes de confirmar.

**En la lectura en voz alta:** «Respuesta generada por inteligencia artificial», antes o después de leer el texto.

Requisitos: siempre visible, legible (contraste suficiente) y en el mismo idioma que la respuesta.

---

## 4. Datos y privacidad (RGPD)

| Dato | Dónde va | Cuánto tiempo |
| --- | --- | --- |
| Texto de la conversación (hasta 40 mensajes) | Al LLM por el AI Gateway de Databricks, en cada mensaje, con un resumen del catálogo | En memoria del backend; se pierde al reiniciar |
| Voz del comercial | Al servicio de reconocimiento de voz del navegador (Web Speech API; en Chrome, servidores de Google) | Según el proveedor del navegador. Solo vuelve el texto |
| Ventas simuladas | Base de datos local (SQLite): bulto, cantidad y fecha | Hasta `python arrancar.py --reiniciar-demo` |
| Registro (log) del backend | Errores técnicos y ventas rechazadas, sin el texto del chat | Mientras corre el servidor |

- **Por diseño no se tratan datos personales:** no hay usuarios, no se guarda quién pregunta y las peticiones son de material (grado, medidas, kg).
- **Riesgo:** si un comercial escribe el nombre de un cliente, ese texto llega al LLM. Indicar en la formación que no se escriban datos de clientes. En producción, valorar un filtro antes de enviar el texto.
- **Proveedores:** en producción, AcerIA necesita un contrato de encargado del tratamiento (art. 28 RGPD) con Databricks y con el proveedor del modelo, y comprobar dónde se procesan los datos (UE o con garantías adecuadas).
- **Claves:** solo en `.env`, que no se sube al repositorio.
- **Roles (comercial / administrador):** cuando existan usuarios, sus datos de acceso serán datos personales. Hay que guardarlos lo mínimo y protegidos.

---

## 5. Pendiente

- **Stanis:** pintar `aviso_ia` (sección 3) en el chat y en la lectura en voz alta.
- **Avisar a los cuatro** del campo nuevo `aviso_ia` en `POST /chat` (cambio del contrato, `docs/contrato.md` §6). Es un campo añadido: no rompe nada de lo que ya se usa.
- **Lucas:** resumir este documento en el apartado legal de `docs/arquitectura.md` y en la presentación.
- **Producción:** revisión del equipo legal de AcerIA, contratos con los proveedores y formación a los comerciales.
