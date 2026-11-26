"""Creación y acceso a la base de datos del inventario.

Uso manual (desde backend/):  python -m app.db
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

from app import config

SCHEMA = Path(__file__).resolve().parent / "schema.sql"

# Nombre de columna en el Excel de AcerIA -> nuestro nombre
MAPEO = {
    "ID": "id",
    "Weight": "peso_kg",
    "AISI": "aisi",
    "Euronorma": "euronorma",
    "Euronorma Sup.Finish": "acabado",
    "Euronorma Inf.Finish": "acabado_inf",
    "Inf. Finish": "codigo_acabado_inf",
    "Paper": "papel",
    "Gauge": "espesor_mm",
    "Gauge Min": "espesor_min_mm",
    "Gauge Max": "espesor_max_mm",
    "Width": "ancho_mm",
    "Quantity": "cantidad",
    "Lenght (Solo para chapas)": "largo_mm",
}

COLUMNAS = ["id", "peso_kg", "aisi", "euronorma", "acabado", "acabado_inf",
            "codigo_acabado_inf", "papel", "espesor_mm", "espesor_min_mm",
            "espesor_max_mm", "ancho_mm", "largo_mm", "cantidad", "formato", "estado"]

NUMERICAS = ["peso_kg", "espesor_mm", "espesor_min_mm", "espesor_max_mm", "ancho_mm", "largo_mm"]
OBLIGATORIAS = ["id", "peso_kg", "acabado", "espesor_mm", "ancho_mm"]
ESTADOS_VALIDOS = {"disponible", "reservado", "bloqueado"}

_MILES = re.compile(r"^\d{1,3}(\.\d{3})+$")   # '3.000', '1.500.000'


def numero_es(valor) -> float | None:
    """Convierte números con formato español: '1.500,0' -> 1500.0, '3.000' -> 3000.0, '0,70' -> 0.7."""
    if valor is None or pd.isna(valor):
        return None
    s = str(valor).strip()
    if s in ("", "-"):
        return None
    if "," in s:                                  # coma decimal: los puntos son de miles
        s = s.replace(".", "").replace(",", ".")
    elif _MILES.match(s):                         # solo puntos de miles
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def texto(valor) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    s = re.sub(r"\s+", " ", str(valor)).strip()
    return None if s in ("", "-") else s


def normalizar_euronorma(valor: str | None) -> str | None:
    """'4301/4307' -> '1.4301/1.4307'; '1.4310Mo' se deja igual."""
    if not valor:
        return None
    partes = [p if p.startswith("1.") else f"1.{p}" for p in valor.split("/")]
    return "/".join(partes)


def deducir_formato(largo_mm, ancho_mm) -> str:
    if pd.notna(largo_mm):                        # ojo: pandas guarda los vacíos como NaN, no None
        return "chapa"
    return "fleje" if ancho_mm < config.UMBRAL_FLEJE_MM else "bobina"


def leer_inventario(ruta: Path) -> pd.DataFrame:
    # dtype=str: pandas no reinterpreta nada; convertimos nosotros
    df = pd.read_excel(ruta, dtype=str)
    sin_mapear = [c for c in df.columns if c not in MAPEO]
    if sin_mapear:
        print(f"⚠ Columnas del Excel sin mapear (avisa al equipo): {sin_mapear}")
    return df.rename(columns=MAPEO)


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["id", "aisi", "euronorma", "acabado", "acabado_inf", "codigo_acabado_inf"]:
        df[col] = df[col].map(texto)

    df["id"] = df["id"].str.replace(r"\.0$", "", regex=True)       # '12.0' -> '12'
    df["aisi"] = df["aisi"].str.upper()                             # '316Ti' -> '316TI'
    df["euronorma"] = df["euronorma"].map(normalizar_euronorma)
    df["acabado"] = df["acabado"].str.upper()
    df["acabado_inf"] = df["acabado_inf"].str.upper()
    df["papel"] = df["papel"].map(lambda v: {"Y": 1, "N": 0}.get(texto(v)))

    for col in NUMERICAS:
        df[col] = df[col].map(numero_es)
    df["cantidad"] = df["cantidad"].map(numero_es).astype("Int64")

    invalidas = df[df[OBLIGATORIAS].isna().any(axis=1)]
    if not invalidas.empty:
        print(f"⚠ {len(invalidas)} filas descartadas por datos obligatorios vacíos:\n{invalidas}")
        df = df.drop(invalidas.index)

    df["formato"] = [deducir_formato(l, a) for l, a in zip(df["largo_mm"], df["ancho_mm"])]
    df["estado"] = "disponible"   # el Excel no trae estado: supuesto POR CONFIRMAR
    return df[COLUMNAS]


def aplicar_estados_demo(conn: sqlite3.Connection) -> None:
    """Si existe data/estados_demo.csv (id;estado), sobrescribe el estado de esos bultos."""
    if not config.ESTADOS_DEMO.exists():
        return
    estados = pd.read_csv(config.ESTADOS_DEMO, sep=";", dtype=str)
    for _, fila in estados.iterrows():
        estado = fila["estado"].strip().lower()
        if estado not in ESTADOS_VALIDOS:
            print(f"⚠ Estado no válido para {fila['id']}: {estado}")
            continue
        conn.execute("UPDATE bultos SET estado = ? WHERE id = ?", (estado, fila["id"].strip()))
    print(f"✔ Estados de demo aplicados: {len(estados)}")


def crear_db(ruta_inventario: Path = config.INVENTARIO) -> int:
    df = normalizar(leer_inventario(ruta_inventario))
    df = df.astype(object).where(df.notna(), None)                  # NaN/NA -> NULL
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.executemany(
            f"INSERT INTO bultos ({', '.join(COLUMNAS)}) VALUES ({', '.join('?' * len(COLUMNAS))})",
            df.itertuples(index=False, name=None),
        )
        aplicar_estados_demo(conn)
        conn.execute("DELETE FROM compras")     # modo demo: cada arranque empieza sin ventas (POST /compras)
    print(f"✔ {len(df)} bultos cargados en {config.DB_PATH.name}")
    return len(df)


# ---------- acceso para el resto del backend ----------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def disponibles() -> list[dict]:
    with get_conn() as conn:
        return [dict(f) for f in conn.execute("SELECT * FROM bultos WHERE estado = 'disponible'")]


def obtener_bulto(bulto_id: str) -> dict | None:
    with get_conn() as conn:
        fila = conn.execute("SELECT * FROM bultos WHERE id = ?", (bulto_id,)).fetchone()
        return dict(fila) if fila else None


def grados(bulto: dict) -> set[str]:
    """Grados que cumple un bulto. '304L/304' (doble certificado) -> {'304L', '304'}."""
    aisi = {g.strip() for g in (bulto["aisi"] or "").split("/") if g.strip()}
    en = {e.strip() for e in (bulto["euronorma"] or "").split("/") if e.strip()}
    return aisi | en   # permite buscar por AISI (304) o por Euronorma (1.4301)


if __name__ == "__main__":
    crear_db()