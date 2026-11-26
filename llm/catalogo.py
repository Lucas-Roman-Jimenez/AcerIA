"""Acceso al catálogo estructurado y al glosario (los prepara Lucas).

Aquí se decide qué valores y combinaciones existen. El LLM nunca lo decide (RNF-02).
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any, Optional

RUTA_DATOS = Path(__file__).resolve().parent.parent / "datos"


def _norm_texto(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v)).strip()


class Catalogo:
    def __init__(self, catalogo: dict[str, Any], glosario: dict[str, Any]):
        self.grados: list[str] = catalogo["grados"]
        self.acabados: list[str] = catalogo["acabados"]
        self.formatos: list[str] = catalogo["formatos"]
        self.productos: list[dict[str, Any]] = catalogo.get("productos", [])
        self.usos: list[dict[str, Any]] = catalogo.get("usos", [])
        self.terminos: list[dict[str, Any]] = glosario.get("terminos", [])
        self.acabados_pendientes = [
            t["termino"] for t in glosario.get("pendientes_de_confirmacion", [])
            if t.get("campo") == "acabado"
        ]
        # Catálogo real (Lucas): se puede desactivar la validación de combinaciones y cada ficha
        # relaciona el grado comercial (AISI, p. ej. 304) con su designación EN (1.4301).
        self.validar_combinaciones: bool = catalogo.get("validar_combinaciones", True)
        self.grados_en_por_comercial: dict[str, set[str]] = {}
        for ficha in catalogo.get("fichas", []):
            grado = ficha.get("grado_comercial")
            if grado:
                self.grados_en_por_comercial.setdefault(grado, set()).add(ficha["en"])

    @classmethod
    def cargar(cls, carpeta: Path | str = RUTA_DATOS) -> "Catalogo":
        carpeta = Path(carpeta)
        cat = json.loads((carpeta / "catalogo.json").read_text(encoding="utf-8"))
        glo = json.loads((carpeta / "glosario.json").read_text(encoding="utf-8"))
        return cls(cat, glo)

    # ---------- valores sueltos ----------
    def valores(self, campo: str) -> list[str]:
        return {"grado": self.grados, "acabado": self.acabados, "formato": self.formatos}[campo]

    def normalizar(self, campo: str, valor: Any) -> Optional[str]:
        """Devuelve el valor tal como está en el catálogo, o None si no existe."""
        if valor is None:
            return None
        v = _norm_texto(valor)
        candidatos = [v]                       # primero el valor tal cual: «NR.1» y «N4-G-180» existen así
        if campo == "grado":
            candidatos.append(re.sub(r"^(aisi|en)[\s-]*", "", v, flags=re.I))
        if campo == "acabado":                 # «n.º 4», «nº 4», «no. 4» -> «4» (solo si sigue un número)
            candidatos.append(re.sub(r"^n(?:\.?\s*º|o\.)?\s*(?=\d)", "", v, flags=re.I))
        for c in candidatos:
            for permitido in self.valores(campo):
                if c.lower() == permitido.lower():
                    return permitido
        return None

    def parecidos(self, campo: str, valor: Any, n: int = 4) -> list[str]:
        """Valores del catálogo más parecidos a uno que no existe (316 -> 316L, 316TI), para sugerirlos."""
        v = _norm_texto(valor).lower()
        valores = self.valores(campo)
        prefijo = [p for p in valores if p.lower().startswith(v) or v.startswith(p.lower())]
        cercanos = difflib.get_close_matches(v, [p.lower() for p in valores], n=n, cutoff=0.6)
        por_minuscula = {p.lower(): p for p in valores}
        res = list(dict.fromkeys(prefijo + [por_minuscula[c] for c in cercanos]))[:n]
        return res or valores[:n]

    def termino(self, campo: str, valores: list[str]) -> Optional[str]:
        """Término coloquial del glosario que corresponde a esos valores (satinado -> ['4']), si lo hay."""
        for t in self.terminos:
            if t["campo"] == campo and set(t["valores"]) == set(valores):
                return t["termino"]
        return None

    # ---------- combinaciones ----------
    def productos_compatibles(self, grado=None, acabado=None, formato=None,
                              espesor_mm=None, ancho_mm=None) -> list[dict[str, Any]]:
        res = []
        for p in self.productos:
            if grado and p["grado"] != grado:
                continue
            if acabado and p["acabado"] != acabado:
                continue
            if formato and p["formato"] != formato:
                continue
            if espesor_mm is not None and "espesor_mm" in p:
                lo, hi = p["espesor_mm"]
                if not lo <= espesor_mm <= hi:
                    continue
            if ancho_mm is not None and "ancho_mm" in p:
                lo, hi = p["ancho_mm"]
                if not lo <= ancho_mm <= hi:
                    continue
            res.append(p)
        return res

    def ambiguedad_valida(self, campo: str, valores: list[str]) -> bool:
        """True si algún término del glosario admite todos esos valores para ese campo (RF-05)."""
        return any(t["campo"] == campo and set(valores) <= set(t["valores"]) for t in self.terminos)

    def grado_indicado_para_uso(self, grado: str, grados_del_uso: list[str]) -> bool:
        """True si el grado, o su designación EN, está entre los que el catálogo indica para un uso."""
        return grado in grados_del_uso or not self.grados_en_por_comercial.get(grado, set()).isdisjoint(grados_del_uso)

    # ---------- usos ----------
    def uso(self, nombre: Optional[str]) -> Optional[dict[str, Any]]:
        if not nombre:
            return None
        for u in self.usos:
            if u["uso"].lower() == _norm_texto(nombre).lower():
                return u
        return None

    # ---------- texto para el prompt ----------
    def resumen_para_prompt(self) -> str:
        glos = "\n".join(f'- «{t["termino"]}» → {t["campo"]}: {", ".join(t["valores"])}' for t in self.terminos)
        usos = "\n".join(f'- {u["uso"]}' for u in self.usos) or "- (ninguno)"
        pendientes = ", ".join(f"«{t}»" for t in self.acabados_pendientes) or "(ninguno)"
        return (
            f"Grados válidos: {', '.join(self.grados)}\n"
            f"Acabados válidos: {', '.join(self.acabados)}\n"
            f"Formatos válidos: {', '.join(self.formatos)}\n"
            f"Glosario (término coloquial → valores técnicos posibles):\n{glos}\n"
            f"Términos de acabado sin equivalencia confirmada: {pendientes}. Si no hay código explícito, deja el acabado pendiente.\n"
            f"Usos reconocidos por el catálogo:\n{usos}"
        )
