"""
Scraper de la lista de precios del proveedor.

Lee la página HTML de precios a distribuidor (desde un archivo local o una URL)
y devuelve un DataFrame limpio con SKU, costo nuevo y disponibilidad.
Se usa para detectar aumentos de costo que erosionan el margen.

Uso:
    python src/scraper_proveedor.py                      # archivo de ejemplo
    python src/scraper_proveedor.py https://proveedor.mx/lista-precios
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVO_EJEMPLO = RAIZ / "data" / "raw" / "lista_precios_proveedor.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (portafolio-analisis-datos)"}


def obtener_html(origen: str | Path) -> str:
    """Descarga la página si es URL; si no, la lee del disco."""
    origen = str(origen)
    if origen.startswith(("http://", "https://")):
        resp = requests.get(origen, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return resp.text
    return Path(origen).read_text(encoding="utf-8")


def _a_numero(texto: str) -> float | None:
    limpio = re.sub(r"[^\d.]", "", texto or "")
    return float(limpio) if limpio else None


def parsear_lista(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "html.parser")
    vigencia = soup.select_one(".vigencia")
    fecha = None
    if vigencia:
        m = re.search(r"(\d{2}/\d{2}/\d{4})", vigencia.get_text())
        fecha = pd.to_datetime(m.group(1), dayfirst=True).date().isoformat() if m else None

    filas = []
    for tr in soup.select("table#lista-precios tr.producto"):
        filas.append({
            "sku": tr.select_one(".sku").get_text(strip=True).upper(),
            "descripcion_proveedor": tr.select_one(".desc").get_text(strip=True),
            "costo_nuevo": _a_numero(tr.select_one(".precio").get_text()),
            "disponible": tr.select_one(".disp").get_text(strip=True) == "Disponible",
            "vigencia": fecha,
        })
    df = pd.DataFrame(filas)
    if df.empty:
        raise ValueError("No se encontraron productos: revisa los selectores CSS.")
    return df.dropna(subset=["costo_nuevo"]).drop_duplicates("sku")


def scrapear(origen: str | Path = ARCHIVO_EJEMPLO) -> pd.DataFrame:
    return parsear_lista(obtener_html(origen))


if __name__ == "__main__":
    origen = sys.argv[1] if len(sys.argv) > 1 else ARCHIVO_EJEMPLO
    df = scrapear(origen)
    print(df.head(10).to_string(index=False))
    print(f"\n{len(df)} productos extraídos (vigencia {df['vigencia'].iloc[0]})")
