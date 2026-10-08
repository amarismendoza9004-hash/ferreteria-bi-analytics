"""
ETL: extracción, limpieza, validación y carga a SQLite.

Pasos
1. Extrae los CSV crudos del POS/ERP, la lista de precios del proveedor
   (scraping) y el tipo de cambio (API).
2. Limpia y valida: SKUs, unidades, costos con formato de texto, fechas en
   formatos mezclados, duplicados, cantidades imposibles, SKUs huérfanos.
3. Calcula importe, costo y margen por línea de venta.
4. Carga un modelo estrella en SQLite (data/processed/ferreteria.db) y
   exporta CSV limpios para Power BI.
5. Genera un reporte de calidad de datos (data/processed/calidad_datos.json).

Uso:
    python src/etl.py
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from api_tipo_cambio import obtener_tipo_cambio
from scraper_proveedor import scrapear

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
DB = PROC / "ferreteria.db"

MAPA_UNIDADES = {
    "PZA": "PZA", "PIEZA": "PZA", "PZ": "PZA",
    "MT": "MT", "METRO": "MT", "M": "MT",
    "KG": "KG", "KILO": "KG",
    "LT": "LT", "LITRO": "LT", "L": "LT",
    "CAJA": "CAJA", "CJA": "CAJA",
    "BULTO": "BULTO", "BTO": "BULTO",
}
CANTIDAD_MAXIMA_LINEA = 1_000   # más que esto en una línea = error de captura
# Comisión aproximada por venta en marketplace (referencia para el ejemplo; ajustar a la tarifa real)
COMISION_CANAL = {"Mercado Libre": 0.15, "Amazon": 0.15}

calidad: dict[str, dict] = {}


def registrar(tabla: str, regla: str, filas: int) -> None:
    calidad.setdefault(tabla, {})[regla] = int(filas)


# --------------------------------------------------------------------------- #
# Productos
# --------------------------------------------------------------------------- #
def limpiar_productos(df: pd.DataFrame) -> pd.DataFrame:
    registrar("productos", "filas_crudas", len(df))
    df = df.copy()

    df["sku"] = df["sku"].astype(str).str.strip().str.upper()

    u = df["unidad"].astype(str).str.strip().str.upper()
    registrar("productos", "unidades_normalizadas", (u != df["unidad"]).sum())
    df["unidad"] = u.map(MAPA_UNIDADES).fillna("PZA")

    costo_txt = df["costo"].astype(str)
    registrar("productos", "costos_con_formato_texto", costo_txt.str.contains(r"[$,]").sum())
    df["costo"] = pd.to_numeric(costo_txt.str.replace(r"[$,]", "", regex=True), errors="coerce")

    registrar("productos", "descripciones_vacias", df["descripcion"].isna().sum())
    df["descripcion"] = df["descripcion"].fillna("SIN DESCRIPCIÓN - REVISAR")

    antes = len(df)
    df = df.drop_duplicates(subset="sku", keep="first")
    registrar("productos", "skus_duplicados_eliminados", antes - len(df))

    df["alerta_precio_bajo_costo"] = df["precio_venta"] < df["costo"]
    registrar("productos", "precio_menor_a_costo", df["alerta_precio_bajo_costo"].sum())

    df["margen_pct"] = (df["precio_venta"] - df["costo"]) / df["precio_venta"]
    registrar("productos", "filas_limpias", len(df))
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Ventas
# --------------------------------------------------------------------------- #
def limpiar_ventas(df: pd.DataFrame, productos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    registrar("ventas", "filas_crudas", len(df))
    df = df.copy()

    antes = len(df)
    df = df.drop_duplicates()
    registrar("ventas", "duplicados_exactos_eliminados", antes - len(df))

    # Fechas: el POS exporta ISO y el módulo web dd/mm/aaaa
    iso = pd.to_datetime(df["fecha"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    dmy = pd.to_datetime(df["fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
    registrar("ventas", "fechas_formato_dd_mm_aaaa", (iso.isna() & dmy.notna()).sum())
    df["fecha"] = iso.fillna(dmy)
    registrar("ventas", "fechas_invalidas", df["fecha"].isna().sum())
    df = df.dropna(subset=["fecha"])

    df["sku"] = df["sku"].astype(str).str.strip().str.upper()
    df["canal"] = df["canal"].astype(str).str.strip().str.title().replace(
        {"Mercado Libre": "Mercado Libre", "Whatsapp": "WhatsApp"})

    # Cantidades imposibles -> rechazos
    absurdas = df["cantidad"].abs() > CANTIDAD_MAXIMA_LINEA
    registrar("ventas", "cantidades_imposibles", absurdas.sum())

    # SKUs que no existen en el catálogo -> rechazos
    huerfanos = ~df["sku"].isin(productos["sku"])
    registrar("ventas", "skus_sin_catalogo", huerfanos.sum())

    rechazos = df[absurdas | huerfanos].assign(
        motivo=np.where(absurdas[absurdas | huerfanos], "cantidad_imposible", "sku_sin_catalogo"))
    df = df[~(absurdas | huerfanos)]

    # Precio faltante -> se imputa con el precio de catálogo
    registrar("ventas", "precios_nulos_imputados", df["precio_unitario"].isna().sum())
    precio_cat = productos.set_index("sku")["precio_venta"]
    df["precio_unitario"] = df["precio_unitario"].fillna(df["sku"].map(precio_cat))

    df["fecha_dia"] = df["fecha"].dt.strftime("%Y-%m-%d")   # llave hacia dim_fecha
    df["es_devolucion"] = df["cantidad"] < 0
    registrar("ventas", "devoluciones", df["es_devolucion"].sum())

    costo_cat = productos.set_index("sku")["costo"]
    df["importe"] = (df["cantidad"] * df["precio_unitario"] * (1 - df["descuento"])).round(2)
    df["costo_total"] = (df["cantidad"] * df["sku"].map(costo_cat)).round(2)
    df["comision"] = (df["importe"] * df["canal"].map(COMISION_CANAL).fillna(0)).round(2)
    df["utilidad"] = (df["importe"] - df["costo_total"] - df["comision"]).round(2)

    registrar("ventas", "filas_limpias", len(df))
    return df.reset_index(drop=True), rechazos.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Inventario y precios de proveedor
# --------------------------------------------------------------------------- #
def preparar_inventario(df: pd.DataFrame, productos: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sku"] = df["sku"].str.strip().str.upper()
    df = df.merge(productos[["sku", "costo", "stock_minimo"]], on="sku", how="left")
    df["diferencia"] = df["existencia_fisica"] - df["existencia_sistema"]
    df["valor_diferencia"] = (df["diferencia"] * df["costo"]).round(2)
    df["bajo_minimo"] = df["existencia_fisica"] < df["stock_minimo"]
    registrar("inventario", "skus_con_diferencia", (df["diferencia"] != 0).sum())
    registrar("inventario", "skus_bajo_minimo", df["bajo_minimo"].sum())
    return df.drop(columns=["costo", "stock_minimo"])


def preparar_precios_proveedor(df: pd.DataFrame, productos: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(productos[["sku", "costo", "precio_venta"]], on="sku", how="inner")
    df["aumento_costo_pct"] = (df["costo_nuevo"] / df["costo"] - 1).round(4)
    df["margen_actual_pct"] = ((df["precio_venta"] - df["costo"]) / df["precio_venta"]).round(4)
    df["margen_con_costo_nuevo_pct"] = ((df["precio_venta"] - df["costo_nuevo"]) / df["precio_venta"]).round(4)
    registrar("precios_proveedor", "productos_scrapeados", len(df))
    return df


def dim_fecha(inicio: pd.Timestamp, fin: pd.Timestamp) -> pd.DataFrame:
    f = pd.DataFrame({"fecha": pd.date_range(inicio.normalize(), fin.normalize(), freq="D")})
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    f["anio"] = f["fecha"].dt.year
    f["mes"] = f["fecha"].dt.month
    f["nombre_mes"] = f["mes"].map(lambda m: meses[m - 1])
    f["anio_mes"] = f["fecha"].dt.strftime("%Y-%m")
    f["trimestre"] = "T" + f["fecha"].dt.quarter.astype(str)
    f["dia_semana"] = f["fecha"].dt.dayofweek.map(lambda d: dias[d])
    f["temporada_lluvias"] = f["mes"].isin([6, 7, 8, 9])
    f["fecha"] = f["fecha"].dt.strftime("%Y-%m-%d")
    return f


# --------------------------------------------------------------------------- #
# Carga
# --------------------------------------------------------------------------- #
def cargar_sqlite(tablas: dict[str, pd.DataFrame]) -> None:
    DB.unlink(missing_ok=True)
    with sqlite3.connect(DB) as con:
        for nombre, df in tablas.items():
            out = df.copy()
            for c in out.select_dtypes(include="datetime").columns:
                out[c] = out[c].dt.strftime("%Y-%m-%d %H:%M:%S")
            out.to_sql(nombre, con, index=False)
        con.executescript("""
            CREATE INDEX ix_ventas_sku   ON fact_ventas(sku);
            CREATE INDEX ix_ventas_fecha ON fact_ventas(fecha);
            CREATE INDEX ix_ventas_dia   ON fact_ventas(fecha_dia);
            CREATE UNIQUE INDEX ix_fecha ON dim_fecha(fecha);
            CREATE INDEX ix_prod_cat     ON dim_producto(categoria);
        """)


def main() -> dict:
    PROC.mkdir(parents=True, exist_ok=True)

    print("1/4 Extrayendo datos...")
    productos_raw = pd.read_csv(RAW / "productos.csv")
    ventas_raw = pd.read_csv(RAW / "ventas.csv")
    inventario_raw = pd.read_csv(RAW / "inventario_conteo.csv")
    proveedores = pd.read_csv(RAW / "proveedores.csv")
    lista_prov = scrapear()
    print(f"    [Scraping] {len(lista_prov)} precios de proveedor extraídos")

    print("2/4 Limpiando y validando...")
    productos = limpiar_productos(productos_raw)
    ventas, rechazos = limpiar_ventas(ventas_raw, productos)
    inventario = preparar_inventario(inventario_raw, productos)
    precios_prov = preparar_precios_proveedor(lista_prov, productos)

    print("3/4 Enriqueciendo con API de tipo de cambio...")
    inicio, fin = ventas["fecha"].min(), ventas["fecha"].max()
    tc = obtener_tipo_cambio(inicio.date().isoformat(), fin.date().isoformat())
    if tc is not None:
        ventas["dia"] = ventas["fecha"].dt.normalize()
        ventas = ventas.merge(tc.rename(columns={"fecha": "dia"}), on="dia", how="left")
        ventas["importe_usd"] = (ventas["importe"] / ventas["usd_mxn"]).round(2)
        ventas = ventas.drop(columns="dia")

    print("4/4 Cargando a SQLite y exportando CSV para Power BI...")
    fechas = dim_fecha(inicio, fin)
    tablas = {
        "dim_producto": productos,
        "dim_proveedor": proveedores,
        "dim_fecha": fechas,
        "fact_ventas": ventas,
        "inventario": inventario,
        "precios_proveedor": precios_prov,
        "rechazos_ventas": rechazos,
    }
    if tc is not None:
        tablas["tipo_cambio"] = tc
    cargar_sqlite(tablas)

    pbi = RAIZ / "powerbi" / "datos"
    pbi.mkdir(parents=True, exist_ok=True)
    for nombre in ["dim_producto", "dim_proveedor", "dim_fecha", "fact_ventas", "inventario", "precios_proveedor"]:
        tablas[nombre].to_csv(pbi / f"{nombre}.csv", index=False, encoding="utf-8-sig")

    (PROC / "calidad_datos.json").write_text(json.dumps(calidad, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nReporte de calidad de datos")
    for tabla, reglas in calidad.items():
        print(f"  {tabla}")
        for regla, n in reglas.items():
            print(f"    - {regla.replace('_', ' ')}: {n:,}")
    print(f"\nBase de datos: {DB.relative_to(RAIZ)}")
    return calidad


if __name__ == "__main__":
    main()
