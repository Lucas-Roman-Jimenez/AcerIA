"""Parámetros de negocio. Todo lo que hay que confirmar con el mentor está aquí, no en la lógica."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

INVENTARIO = DATA / "inventario.xlsx"
ESTADOS_DEMO = DATA / "estados_demo.csv"   # opcional: id;estado para simular reservados/bloqueados
DB_PATH = DATA / "aceria.db"


# Orígenes que pueden llamar a la API desde el navegador (CORS). arrancar.py pasa el del frontend;
# para otro despliegue: ACERIA_CORS_ORIGENES="https://mi-frontend,https://otro".
CORS_ORIGENES = [o.strip() for o in os.environ.get(
    "ACERIA_CORS_ORIGENES", "http://127.0.0.1:5173,http://localhost:5173").split(",") if o.strip()]

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
