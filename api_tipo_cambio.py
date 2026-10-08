"""
Cliente de API: tipo de cambio USD/MXN diario.

Consulta la API pública Frankfurter (datos del Banco Central Europeo, sin
token) para enriquecer las ventas con su equivalente en dólares. Útil para
comparar contra costos de productos importados (herramienta eléctrica).

Si no hay conexión, usa la última respuesta guardada en caché y, si tampoco
existe, el pipeline continúa sin la columna en USD.

Alternativa oficial en México: API SIE de Banxico (serie SF43718, requiere
token gratuito): https://www.banxico.org.mx/SieAPIRest/

Uso:
    python src/api_tipo_cambio.py 2024-07-01 2026-06-30
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
CACHE = RAIZ / "data" / "processed" / "tipo_cambio_usd_mxn.csv"
URL = "https://api.frankfurter.app/{inicio}..{fin}"


def descargar(inicio: str, fin: str) -> pd.DataFrame:
    resp = requests.get(URL.format(inicio=inicio, fin=fin),
                        params={"from": "USD", "to": "MXN"}, timeout=20)
    resp.raise_for_status()
    datos = resp.json()["rates"]           # {"2024-07-01": {"MXN": 18.3}, ...}
    df = pd.DataFrame(
        [(fecha, valores["MXN"]) for fecha, valores in datos.items()],
        columns=["fecha", "usd_mxn"],
    )
    df["fecha"] = pd.to_datetime(df["fecha"])
    # la API solo publica días hábiles: rellenamos fines de semana con el último valor
    calendario = pd.DataFrame({"fecha": pd.date_range(inicio, fin, freq="D")})
    return calendario.merge(df, on="fecha", how="left").ffill().bfill()


def obtener_tipo_cambio(inicio: str, fin: str) -> pd.DataFrame | None:
    try:
        df = descargar(inicio, fin)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE, index=False)
        print(f"[API] Tipo de cambio descargado: {len(df)} días")
        return df
    except (requests.RequestException, KeyError, ValueError) as err:
        if CACHE.exists():
            print(f"[API] Sin conexión ({type(err).__name__}); usando caché local.")
            return pd.read_csv(CACHE, parse_dates=["fecha"])
        print(f"[API] Sin conexión ({type(err).__name__}) y sin caché: se omite la conversión a USD.")
        return None


if __name__ == "__main__":
    ini, fin = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("2024-07-01", "2026-06-30")
    tc = obtener_tipo_cambio(ini, fin)
    if tc is not None:
        print(tc.tail())
