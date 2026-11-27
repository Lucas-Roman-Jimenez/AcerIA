"""Bot de Telegram de acerIA: hacer un pedido de acero inoxidable desde el móvil.

Es otro cliente del mismo backend que usa la web: no decide nada por su cuenta (RNF-01, RNF-02).
- Cada mensaje va a POST /chat y se contesta con el texto del backend y la nota de IA (aviso_ia).
- Los bultos que devuelve el backend salen como botones «Reservar»: POST /reservas.
- /carrito enseña lo reservado y permite confirmar el pedido: POST /compras.

Solo usa la biblioteca estándar (sin dependencias nuevas). Se arranca con:
    python telegram/bot.py
y necesita TELEGRAM_TOKEN en el .env de la raíz (el token que da @BotFather). Ver telegram/README.md.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MAX_TARJETAS = 5          # bultos que se ofrecen como botones en cada respuesta
ESPERA_SONDEO = 30        # segundos de long polling en getUpdates


def cargar_env() -> None:
    """Lee el .env de la raíz sin pisar lo que ya esté en el entorno."""
    env = RAIZ / ".env"
    if not env.exists():
        return
    for linea in env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


cargar_env()
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"https://api.telegram.org/bot{TOKEN}"

AVISO_INICIO = ("Estás hablando con un asistente de inteligencia artificial. Interpreta tu petición y busca en el "
                "inventario real de AcerIA, pero puede equivocarse: revisa los bultos antes de confirmar.")
AYUDA = ("Escríbeme lo que necesitas, por ejemplo:\n"
         "• chapa 304 2B de 2 mm\n"
         "• bobina 316L BA de 0,6 mm\n"
         "• fleje 430 BA de 0,5 mm de 300 de ancho\n\n"
         "Te enseño los bultos que hay y los reservas con un botón.\n"
         "/carrito — ver lo reservado y confirmar el pedido\n"
         "/nueva — empezar una petición nueva\n"
         "/vaciar — liberar todo lo reservado")

# Número de conversación por chat: /nueva empieza otra en el backend (memoria del proceso; basta para la demo).
conversaciones: dict[int, int] = {}


# ---------- HTTP ----------

def _peticion(metodo: str, url: str, cuerpo=None, cabeceras=None, espera=60):
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo,
                                 headers={"Content-Type": "application/json", **(cabeceras or {})})
    try:
        with urllib.request.urlopen(req, timeout=espera) as r:
            texto = r.read().decode("utf-8")
            return r.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as e:
        texto = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(texto)
        except ValueError:
            return e.code, {"detail": texto}


def telegram(metodo: str, **params):
    _, r = _peticion("POST", f"{API}/{metodo}", params, espera=ESPERA_SONDEO + 10)
    return r or {}


def backend(metodo: str, ruta: str, cuerpo=None, carrito: str | None = None):
    cab = {"X-Carrito": carrito} if carrito else {}
    return _peticion(metodo, f"{BACKEND}{ruta}", cuerpo, cab)


# ---------- Formato ----------

def num(v) -> str:
    if v is None:
        return "—"
    v = float(v)
    return (f"{v:.0f}" if v.is_integer() else f"{v:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


def carrito_de(chat_id: int) -> str:
    return f"tg{chat_id}".replace("-", "n")          # cumple el patrón de X-Carrito (letras, números, _ y -)


def conversacion_de(chat_id: int) -> str:
    return f"{carrito_de(chat_id)}-{conversaciones.get(chat_id, 0)}"


def describir(b: dict) -> str:
    medidas = " × ".join(num(x) for x in (b.get("espesor_mm"), b.get("ancho_mm"), b.get("largo_mm")) if x is not None)
    return f"{b.get('grado') or b.get('aisi')} {b.get('acabado')} · {b.get('formato')} · {medidas} mm · {num(b.get('peso_kg'))} kg"


def botones_bultos(r: dict) -> list[list[dict]]:
    """Un botón por bulto propuesto: exactos primero y luego transformables (el orden lo da el backend)."""
    filas = []
    for b in (r.get("exactos") or [])[:MAX_TARJETAS]:
        filas.append([{"text": f"🛒 {b['id']} · {describir(b)}", "callback_data": f"res:{b['id']}"}])
    hueco = MAX_TARJETAS - len(filas)
    for t in (r.get("transformables") or [])[:max(hueco, 0)]:
        b = t.get("bulto") or {}
        filas.append([{"text": f"🛠 {t['id']} · transformable · {describir(b)}", "callback_data": f"res:{t['id']}"}])
    return filas


# ---------- Acciones ----------

def responder_mensaje(chat_id: int, texto: str) -> None:
    telegram("sendChatAction", chat_id=chat_id, action="typing")
    estado, r = backend("POST", "/chat", {"conversacion_id": conversacion_de(chat_id), "texto": texto})
    if estado != 200 or not r:
        telegram("sendMessage", chat_id=chat_id, text="No he podido consultar el inventario ahora mismo. Inténtalo de nuevo en un momento.")
        return
    if r.get("tipo") == "error":
        telegram("sendMessage", chat_id=chat_id, text=r.get("error") or "No he podido entender la petición. ¿Puedes reformularla?")
        return
    cuerpo = r.get("pregunta") or r.get("texto") or ""
    aviso = (r.get("aviso_ia") or {}).get("texto")
    if aviso:
        cuerpo += f"\n\nℹ️ {aviso}"
    filas = botones_bultos(r)
    params = {"chat_id": chat_id, "text": cuerpo[:4000]}
    if filas:
        params["reply_markup"] = {"inline_keyboard": filas}
    telegram("sendMessage", **params)


def reservar(chat_id: int, bulto_id: str) -> str:
    estado, r = backend("POST", "/reservas", {"bultos": [bulto_id]}, carrito_de(chat_id))
    if estado == 200:
        return f"✅ Bulto {bulto_id} reservado durante {r.get('minutos', 15)} minutos. Míralo con /carrito."
    detalle = (r or {}).get("detail")
    return f"⚠️ {detalle.get('mensaje') if isinstance(detalle, dict) else detalle or 'No se ha podido reservar.'}"


def enviar_carrito(chat_id: int) -> None:
    estado, r = backend("GET", "/reservas", carrito=carrito_de(chat_id))
    reservas = (r or {}).get("reservas") or [] if estado == 200 else []
    if not reservas:
        telegram("sendMessage", chat_id=chat_id, text="Tu carrito está vacío. Pídeme un material y reserva un bulto.")
        return
    lineas, filas = [], []
    for x in reservas:
        bid = str(x.get("bulto_id") or x.get("id") or x)
        lineas.append(f"• Bulto {bid}")
        filas.append([{"text": f"✕ Quitar {bid}", "callback_data": f"quitar:{bid}"}])
    filas.append([{"text": "✅ Confirmar pedido", "callback_data": "comprar"}])
    telegram("sendMessage", chat_id=chat_id, text="🛒 Tu carrito (reservado a tu nombre):\n" + "\n".join(lineas),
             reply_markup={"inline_keyboard": filas})


def comprar(chat_id: int) -> str:
    estado, r = backend("GET", "/reservas", carrito=carrito_de(chat_id))
    ids = [str(x.get("bulto_id") or x.get("id") or x) for x in ((r or {}).get("reservas") or [])] if estado == 200 else []
    if not ids:
        return "No hay nada reservado que confirmar."
    estado, r = backend("POST", "/compras", {"bultos": ids}, carrito_de(chat_id))
    if estado == 200:
        return f"🎉 Pedido confirmado: {', '.join(ids)}. Aparecerá en el reporte semanal de compras."
    detalle = (r or {}).get("detail")
    return f"⚠️ {detalle.get('mensaje') if isinstance(detalle, dict) else detalle or 'No se ha podido confirmar el pedido.'}"


def atender(u: dict) -> None:
    if "callback_query" in u:
        q = u["callback_query"]
        chat_id, dato = q["message"]["chat"]["id"], q.get("data", "")
        telegram("answerCallbackQuery", callback_query_id=q["id"])
        if dato.startswith("res:"):
            texto = reservar(chat_id, dato[4:])
        elif dato.startswith("quitar:"):
            estado, _ = backend("DELETE", f"/reservas/{dato[7:]}", carrito=carrito_de(chat_id))
            texto = f"Bulto {dato[7:]} quitado del carrito." if estado == 204 else "Ese bulto ya no estaba en tu carrito."
        elif dato == "comprar":
            texto = comprar(chat_id)
        else:
            return
        telegram("sendMessage", chat_id=chat_id, text=texto)
        return

    m = u.get("message") or {}
    chat_id, texto = (m.get("chat") or {}).get("id"), (m.get("text") or "").strip()
    if not chat_id:
        return
    if not texto:
        telegram("sendMessage", chat_id=chat_id, text="De momento solo entiendo mensajes de texto. Escríbeme lo que necesitas.")
        return
    orden = texto.split()[0].split("@")[0].lower()
    if orden in ("/start", "/ayuda", "/help"):
        telegram("sendMessage", chat_id=chat_id, text=f"Hola, soy acerIA.\n\n{AVISO_INICIO}\n\n{AYUDA}")
    elif orden == "/carrito":
        enviar_carrito(chat_id)
    elif orden == "/nueva":
        conversaciones[chat_id] = conversaciones.get(chat_id, 0) + 1
        telegram("sendMessage", chat_id=chat_id, text="Petición nueva. ¿Qué necesitas?")
    elif orden == "/vaciar":
        backend("DELETE", "/reservas", carrito=carrito_de(chat_id))
        telegram("sendMessage", chat_id=chat_id, text="He liberado todo lo que tenías reservado.")
    else:
        responder_mensaje(chat_id, texto)


def main() -> None:
    if not TOKEN:
        sys.exit("Falta TELEGRAM_TOKEN en el .env (pídeselo a @BotFather). Ver telegram/README.md.")
    yo = telegram("getMe")
    if not yo.get("ok"):
        sys.exit(f"Telegram no acepta el token: {yo.get('description', 'sin respuesta')}")
    telegram("setMyCommands", commands=[
        {"command": "carrito", "description": "Ver lo reservado y confirmar el pedido"},
        {"command": "nueva", "description": "Empezar una petición nueva"},
        {"command": "vaciar", "description": "Liberar todo lo reservado"},
        {"command": "ayuda", "description": "Ejemplos de peticiones"},
    ])
    print(f"Bot @{yo['result']['username']} escuchando · backend {BACKEND}")
    siguiente = 0
    while True:
        try:
            r = telegram("getUpdates", offset=siguiente, timeout=ESPERA_SONDEO, allowed_updates=["message", "callback_query"])
            for u in r.get("result", []):
                siguiente = u["update_id"] + 1
                try:
                    atender(u)
                except Exception as e:                    # un mensaje raro no tumba el bot
                    print("Error atendiendo un mensaje:", e)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print("Sin conexión con Telegram, reintento:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
