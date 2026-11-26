"""Parámetros de negocio. Todo lo que hay que confirmar con el mentor está aquí, no en la lógica."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

INVENTARIO = DATA / "inventario.xlsx"
ESTADOS_DEMO = DATA / "estados_demo.csv"   # opcional: id;estado para simular reservados/bloqueados
DB_PATH = Path(os.environ.get("ACERIA_DB_PATH") or (DATA / "aceria.db"))

# Fichas técnicas en PDF (app/fichas.py): catálogo de Lucas, carpeta del workspace de Databricks donde
# están los PDF y caché local (los PDF no se suben a git: **/*.pdf en .gitignore).
CATALOGO = BASE.parent / "datos" / "catalogo.json"
DATABRICKS_FICHAS = os.environ.get("DATABRICKS_FICHAS") or "/Shared/Dataset-aceria"
FICHAS_DIR = DATA / "fichas"
FICHAS_TIMEOUT_S = 30


# Orígenes que pueden llamar a la API desde el navegador (CORS). arrancar.py pasa el del frontend;
# para otro despliegue: ACERIA_CORS_ORIGENES="https://mi-frontend,https://otro".
CORS_ORIGENES = [o.strip() for o in os.environ.get(
    "ACERIA_CORS_ORIGENES", "http://127.0.0.1:5173,http://localhost:5173").split(",") if o.strip()]

# Nombres con los que se puede llamar a la API (cabecera Host). Frena el «DNS rebinding»: una web maliciosa
# que hace apuntar su dominio a 127.0.0.1 llega con su propio Host y recibe 400. «testserver» es el Host del
# TestClient de los tests (no es un dominio público). Otro despliegue: ACERIA_HOSTS="mi-dominio,otro".
HOSTS_PERMITIDOS = [h.strip() for h in os.environ.get(
    "ACERIA_HOSTS", "127.0.0.1,localhost,testserver").split(",") if h.strip()]

# Longitud máxima de un mensaje de chat: cada uno va al LLM de pago junto con el historial.
MAX_LONGITUD_MENSAJE = 2000

# Sin largo -> bobina o fleje. Por debajo de este ancho se considera fleje. POR CONFIRMAR.
UMBRAL_FLEJE_MM = 600

# Densidad para estimar el largo de una bobina a partir de su peso (kg/dm³). POR CONFIRMAR.
DENSIDAD_KG_DM3 = 7.9

# Permite laminar y después cortar. POR CONFIRMAR.
MAX_OPERACIONES = 2

# Tolerancias de búsqueda. POR CONFIRMAR.
TOL_ESPESOR_MM = 0.0
TOL_ANCHO_MM = 0.0
TOL_LARGO_MM = 0.0

# RF-14. Orden de los transformables. POR CONFIRMAR con el mentor: el PDF pide operaciones > merma > ID.
ORDEN_TRANSFORMABLES = ("num_operaciones", "merma_pct", "id")

# RF-29. Máximo de alternativas cercanas cuando no hay stock.
MAX_ALTERNATIVAS = 3

# Tarea 4. Minutos que dura la reserva de un bulto en el carrito; al caducar vuelve a estar disponible.
RESERVA_MINUTOS = 15

# Tarea 6. Límites de lo que entra en la API (validación con Pydantic en app/modelos.py). POR CONFIRMAR.
# Las medidas dejan margen sobre el inventario real (espesor 0,3-45 mm, ancho 101-1566, largo 648-4727).
MAX_ESPESOR_MM = 100
MAX_ANCHO_MM = 5000
MAX_LARGO_MM = 20000
MAX_BULTOS_CARRITO = 200      # IDs por reserva o venta (también evita pasar el límite de variables de SQLite)
MAX_RESERVAS_CARRITO = 50     # bultos reservados a la vez por un carrito: nadie bloquea todo el stock
MAX_LONGITUD_ID = 50          # ID de bulto (los del inventario tienen hasta 4 caracteres)
MAX_LONGITUD_VALOR = 50       # grado, acabado y cada opción (el acabado más largo tiene 17)
MAX_OPCIONES = 10             # valores por campo en «opciones» (p. ej. brillante -> BA o 2R)
MAX_LIMITE_RESUMEN = 50       # grupos en /stock/resumen
