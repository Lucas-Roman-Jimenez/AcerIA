# telegram/

Bot de Telegram de acerIA para hacer un pedido desde el móvil. Es otro cliente del mismo backend que la web: manda cada mensaje a `POST /chat`, ofrece los bultos como botones «Reservar» (`POST /reservas`) y confirma el pedido con `POST /compras`. No decide nada por su cuenta (RNF-01, RNF-02) y cada respuesta lleva la nota de IA (`aviso_ia`).

Solo usa la biblioteca estándar de Python: no añade dependencias.

## Ponerlo en marcha

1. En Telegram, habla con **@BotFather**, envía `/newbot`, elige nombre y usuario, y copia el token que te da.
2. Añade al `.env` de la raíz (nunca se sube al repositorio):
   ```
   TELEGRAM_TOKEN=123456:ABC...
   # Opcional, si el backend no está en local:
   # BACKEND_URL=http://127.0.0.1:8000
   ```
3. Arranca el backend (`python arrancar.py`) y, en otra terminal:
   ```
   python telegram/bot.py
   ```
4. Abre el bot en Telegram y envía `/start`.

## Qué hace

- Mensaje de texto → respuesta del backend (preguntas antes y después de buscar, bultos, transformaciones).
- Botón **🛒 / 🛠** bajo la respuesta → reserva ese bulto 15 minutos a nombre del chat.
- `/carrito` → lo reservado, con **✕ Quitar** y **✅ Confirmar pedido** (la venta sale en el reporte semanal).
- `/nueva` → empieza una petición nueva · `/vaciar` → libera lo reservado · `/ayuda` → ejemplos.

Cada chat de Telegram es un carrito distinto (`X-Carrito: tg<id del chat>`), así que dos comerciales no se quitan los bultos.
Funciona por *long polling* (no necesita URL pública ni webhook). De momento solo entiende texto; las notas de voz no.
