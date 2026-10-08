"""
Generador de datos SIMULADOS para el proyecto.

Crea un escenario realista de una ferretería mediana con venta en mostrador
y en marketplaces, incluyendo los errores típicos que aparecen en datos
reales (SKUs duplicados, unidades inconsistentes, fechas en distintos
formatos, precios por debajo del costo, diferencias de inventario).

Los datos NO pertenecen a ningún negocio real; se generan con semilla fija
para que el análisis sea reproducible.

Uso:
    python src/generate_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

FECHA_INICIO = "2024-07-01"
FECHA_FIN = "2026-06-30"

CATEGORIAS = {
    # categoria: (prefijo, rango_costo, margen_objetivo, peso_ventas, estacionalidad)
    "Herramientas": ("HER", (80, 2500), 0.35, 1.0, "diciembre"),
    "Plomería": ("PLO", (15, 900), 0.40, 1.3, "lluvias"),
    "Eléctrico": ("ELE", (10, 1200), 0.38, 1.2, "plana"),
    "Pinturas": ("PIN", (60, 1800), 0.32, 0.9, "secas"),
    "Tornillería": ("TOR", (1, 120), 0.55, 2.2, "plana"),
    "Construcción": ("CON", (40, 650), 0.22, 1.1, "secas"),
    "Jardinería": ("JAR", (25, 1500), 0.37, 0.6, "lluvias"),
    "Seguridad": ("SEG", (20, 800), 0.45, 0.5, "plana"),
    "Impermeabilizantes": ("IMP", (250, 2200), 0.30, 0.7, "pre_lluvias"),
}

NOMBRES = {
    "Herramientas": ["Martillo", "Desarmador", "Pinza", "Llave Stilson", "Taladro", "Esmeriladora",
                     "Flexómetro", "Nivel", "Serrucho", "Juego de llaves", "Rotomartillo", "Caladora"],
    "Plomería": ["Codo PVC", "Tee PVC", "Tubo PVC", "Llave de paso", "Cespol", "Manguera",
                 "Teflón", "Válvula esfera", "Cople cobre", "Regadera", "Flotador", "Conector flexible"],
    "Eléctrico": ["Cable THW", "Apagador", "Contacto", "Foco LED", "Centro de carga", "Pastilla térmica",
                  "Cinta aislar", "Extensión", "Clavija", "Chalupa", "Tubo conduit", "Lámpara LED"],
    "Pinturas": ["Pintura vinílica", "Esmalte", "Thinner", "Brocha", "Rodillo", "Sellador",
                 "Primario", "Charola", "Aerosol", "Barniz"],
    "Tornillería": ["Tornillo", "Taquete", "Pija", "Clavo", "Tuerca", "Rondana", "Ancla", "Remache"],
    "Construcción": ["Cemento", "Mortero", "Varilla", "Alambre recocido", "Block", "Pegazulejo",
                     "Yeso", "Arena (bulto)", "Malla electrosoldada"],
    "Jardinería": ["Pala", "Rastrillo", "Tijera podar", "Carretilla", "Aspersor", "Machete", "Azadón"],
    "Seguridad": ["Guantes", "Lentes seguridad", "Casco", "Candado", "Cubrebocas", "Chaleco"],
    "Impermeabilizantes": ["Impermeabilizante acrílico 19L", "Impermeabilizante 5 años", "Membrana refuerzo",
                           "Impermeabilizante 10 años", "Sellador elastomérico"],
}

MARCAS = {
    "Herramientas": ["Truper", "Pretul", "Urrea", "Surtek", "Hermex"],
    "Plomería": ["Coflex", "Rotoplas", "Foset", "Dica"],
    "Eléctrico": ["Volteck", "Bticino", "Argos", "Iusa"],
    "Pinturas": ["Comex", "Berel", "Pintumex"],
    "Tornillería": ["Fiero", "Hermex", "Fischer"],
    "Construcción": ["Cemex", "Holcim", "Cruz Azul", "Deacero"],
    "Jardinería": ["Truper", "Pretul", "Rugo"],
    "Seguridad": ["Truper", "3M", "Hermex"],
    "Impermeabilizantes": ["Fester", "Comex", "Thermotek"],
}
MEDIDAS = {
    "Herramientas": ["", "16 oz", "1/2\"", "3/8\"", "5 m", "8 m", "24\""],
    "Plomería": ['1/2"', '3/4"', '1"', "2\"", "15 m"],
    "Eléctrico": ["cal. 12", "cal. 14", "9 W", "15 A", "20 A", ""],
    "Pinturas": ["1 L", "4 L", "19 L", '2"', '4"', "9\""],
    "Tornillería": ["1/4\" x 1\"", "#8 x 1\"", "#10 x 1 1/2\"", "1/4\"", "2 1/2\""],
    "Construcción": ["50 kg", "25 kg", '3/8"', "20 kg", ""],
    "Jardinería": ["", "Mango largo", "8\"", "5 pies3"],
    "Seguridad": ["Talla M", "Talla G", "", "50 mm"],
    "Impermeabilizantes": ["19 L", "4 L", ""],
}

UNIDADES_BUENAS = ["PZA", "MT", "KG", "LT", "CAJA", "BULTO"]
UNIDADES_SUCIAS = {"PZA": ["pza", "Pieza", "pz", "PZA "], "MT": ["mt", "Metro", "m"],
                   "KG": ["kg", "Kilo"], "LT": ["lt", "Litro", "L"],
                   "CAJA": ["caja", "Cja"], "BULTO": ["bulto", "Bto"]}

CANALES = {"Mostrador": 0.68, "Mercado Libre": 0.17, "Amazon": 0.07, "WhatsApp": 0.08}

PROVEEDORES = [
    (1, "Distribuidora Truper Occidente", "Guadalajara", 5),
    (2, "Coflex Bajío", "León", 7),
    (3, "Eléctricos del Centro", "Morelia", 3),
    (4, "Pinturas y Recubrimientos MX", "CDMX", 6),
    (5, "Tornillos y Fijaciones SA", "Querétaro", 4),
    (6, "Materiales La Huerta", "Uruapan", 2),
    (7, "AgroJardín Michoacán", "Zamora", 4),
    (8, "Impermeabilizantes del Pacífico", "Guadalajara", 6),
]
PROV_POR_CAT = {"Herramientas": [1], "Plomería": [2], "Eléctrico": [3], "Pinturas": [4],
                "Tornillería": [5, 1], "Construcción": [6], "Jardinería": [7, 1],
                "Seguridad": [1, 5], "Impermeabilizantes": [8, 4]}


def factor_estacional(mes: np.ndarray, tipo: str) -> np.ndarray:
    """Multiplicador de demanda por mes según el tipo de estacionalidad."""
    base = np.ones_like(mes, dtype=float)
    if tipo == "lluvias":          # jun-sep (temporada de lluvias en Michoacán)
        base = np.where(np.isin(mes, [6, 7, 8, 9]), 1.7, 0.85)
    elif tipo == "pre_lluvias":    # impermeabilizantes: abr-jun
        base = np.where(np.isin(mes, [4, 5, 6]), 2.6, np.where(np.isin(mes, [7, 8]), 1.2, 0.55))
    elif tipo == "secas":          # obra y pintura: nov-may
        base = np.where(np.isin(mes, [11, 12, 1, 2, 3, 4, 5]), 1.25, 0.8)
    elif tipo == "diciembre":      # regalos / aguinaldo
        base = np.where(mes == 12, 1.9, np.where(mes == 11, 1.2, 1.0))
    return base


def generar_proveedores() -> pd.DataFrame:
    return pd.DataFrame(PROVEEDORES, columns=["proveedor_id", "nombre", "ciudad", "dias_entrega"])


def generar_productos(rng: np.random.Generator) -> pd.DataFrame:
    filas = []
    for cat, (pref, (cmin, cmax), margen, peso, est) in CATEGORIAS.items():
        n = int(28 * peso) + 10
        for i in range(1, n + 1):
            nombre = rng.choice(NOMBRES[cat])
            marca = rng.choice(MARCAS[cat])
            medida = rng.choice(MEDIDAS[cat])
            costo = float(np.round(np.exp(rng.uniform(np.log(cmin), np.log(cmax))), 2))
            m = max(0.08, rng.normal(margen, 0.06))
            precio = float(np.round(costo * (1 + m), 0) - 0.10)
            unidad = {"Construcción": "BULTO", "Eléctrico": "MT" if "Cable" in nombre else "PZA",
                      "Tornillería": "CAJA"}.get(cat, "PZA")
            if "Manguera" in nombre or "Tubo" in nombre:
                unidad = "MT"
            filas.append({
                "sku": f"{pref}-{i:04d}",
                "descripcion": f"{nombre} {marca} {medida}".strip(),
                "categoria": cat,
                "marca": marca,
                "unidad": unidad,
                "costo": costo,
                "precio_venta": precio,
                "proveedor_id": int(rng.choice(PROV_POR_CAT[cat])),
                "stock_minimo": int(rng.integers(3, 40)),
                "popularidad": float(rng.lognormal(0, 0.9) * peso),
                "estacionalidad": est,
            })
    df = pd.DataFrame(filas)
    return df


def ensuciar_productos(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Introduce errores típicos de un catálogo capturado a mano."""
    sucio = df.drop(columns=["popularidad", "estacionalidad"]).copy()
    n = len(sucio)
    # unidades escritas de muchas formas
    idx = rng.choice(n, size=int(n * 0.25), replace=False)
    sucio.loc[idx, "unidad"] = [rng.choice(UNIDADES_SUCIAS[u]) for u in sucio.loc[idx, "unidad"]]
    # SKUs con espacios / minúsculas
    idx = rng.choice(n, size=12, replace=False)
    sucio.loc[idx, "sku"] = [f" {s.lower()} " if k % 2 else f"{s} " for k, s in enumerate(sucio.loc[idx, "sku"])]
    # descripciones vacías
    idx = rng.choice(n, size=9, replace=False)
    sucio.loc[idx, "descripcion"] = np.nan
    # precio por debajo del costo (error de captura)
    idx = rng.choice(n, size=7, replace=False)
    sucio.loc[idx, "precio_venta"] = np.round(sucio.loc[idx, "costo"] * rng.uniform(0.6, 0.95, size=7), 2)
    # costos con formato de texto "$1,234.50"
    idx = rng.choice(n, size=15, replace=False)
    sucio["costo"] = sucio["costo"].astype(object)
    sucio.loc[idx, "costo"] = [f"${c:,.2f}" for c in sucio.loc[idx, "costo"]]
    # duplicados exactos (doble alta del mismo producto)
    dup = sucio.sample(6, random_state=SEED)
    sucio = pd.concat([sucio, dup], ignore_index=True)
    return sucio.sample(frac=1, random_state=SEED).reset_index(drop=True)


def generar_ventas(prod: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    fechas = pd.date_range(FECHA_INICIO, FECHA_FIN, freq="D")
    dow = fechas.dayofweek.values
    # domingo medio día, sábado fuerte
    f_dia = np.select([dow == 5, dow == 6], [1.35, 0.55], 1.0)
    tendencia = np.linspace(1.0, 1.18, len(fechas))   # crecimiento ~9% anual
    meses = fechas.month.values

    canales = np.array(list(CANALES))
    p_canal_base = np.array(list(CANALES.values()))

    filas = []
    ticket = 100000
    pop = prod["popularidad"].values
    registros = prod[["sku", "categoria", "unidad", "precio_venta"]].to_dict("records")
    for d, fecha in enumerate(fechas):
        n_tickets = rng.poisson(95 * f_dia[d] * tendencia[d])
        # eventos atípicos para el detector de anomalías
        if fecha.strftime("%Y-%m-%d") in ("2025-03-14", "2025-10-02", "2026-02-11"):
            n_tickets = int(n_tickets * 0.18)       # caída del sistema POS / corte de luz
        # el peso de cada producto depende de su estacionalidad este mes
        est = np.array([factor_estacional(np.array([meses[d]]), e)[0] for e in prod["estacionalidad"]])
        w = pop * est
        w = w / w.sum()
        # online crece con el tiempo
        shift = d / len(fechas) * 0.08
        p_canal = p_canal_base + np.array([-shift, shift * 0.6, shift * 0.25, shift * 0.15])
        p_canal = p_canal / p_canal.sum()
        for _ in range(n_tickets):
            ticket += 1
            canal = rng.choice(canales, p=p_canal)
            n_lineas = 1 + rng.poisson(1.4 if canal == "Mostrador" else 0.4)
            skus = rng.choice(len(prod), size=n_lineas, replace=False, p=w)
            hora = int(rng.choice(np.arange(8, 20), p=np.array([3, 6, 9, 10, 9, 7, 6, 7, 8, 9, 8, 6]) / 88))
            for s in skus:
                r = registros[s]
                if r["categoria"] == "Tornillería":
                    cant = int(rng.integers(1, 6))
                elif r["unidad"] == "MT":
                    cant = int(rng.integers(1, 12))
                elif r["categoria"] == "Construcción":
                    cant = int(rng.integers(1, 8))
                else:
                    cant = int(rng.choice([1, 1, 1, 2, 2, 3, 4]))
                precio = r["precio_venta"]
                # comisión de marketplace se refleja como precio más alto publicado
                if canal in ("Mercado Libre", "Amazon"):
                    precio = round(precio * 1.12, 2)
                # descuento ocasional en mostrador
                desc = 0.0
                if canal == "Mostrador" and rng.random() < 0.06:
                    desc = float(rng.choice([0.05, 0.10]))
                filas.append((ticket, fecha + pd.Timedelta(hours=hora, minutes=int(rng.integers(0, 60))),
                              r["sku"], cant, precio, desc, canal))
    # pedidos de obra grandes (contratistas): picos de venta en días específicos
    obra = prod[prod["categoria"] == "Construcción"].nlargest(3, "popularidad")
    for dia, mult in (("2025-08-21", 1.0), ("2026-05-07", 1.4)):
        ticket += 1
        for r in obra.itertuples():
            filas.append((ticket, pd.Timestamp(dia) + pd.Timedelta(hours=10), r.sku,
                          int(400 * mult), r.precio_venta, 0.08, "WhatsApp"))
    v = pd.DataFrame(filas, columns=["ticket_id", "fecha", "sku", "cantidad", "precio_unitario",
                                     "descuento", "canal"])
    return v


def ensuciar_ventas(v: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    v = v.copy()
    n = len(v)
    # devoluciones (cantidades negativas legítimas)
    idx = rng.choice(n, size=int(n * 0.006), replace=False)
    v.loc[idx, "cantidad"] = -v.loc[idx, "cantidad"].abs()
    # cantidades absurdas (error de captura: escanearon el código de barras en cantidad)
    idx = rng.choice(n, size=8, replace=False)
    v.loc[idx, "cantidad"] = rng.integers(7_500_000, 7_509_999, size=8)
    # fechas en formatos mezclados (export de distintos sistemas)
    v["fecha"] = v["fecha"].dt.strftime("%Y-%m-%d %H:%M:%S")
    idx = rng.choice(n, size=int(n * 0.05), replace=False)
    v.loc[idx, "fecha"] = pd.to_datetime(v.loc[idx, "fecha"]).dt.strftime("%d/%m/%Y %H:%M")
    # canal con mayúsculas/minúsculas
    idx = rng.choice(n, size=int(n * 0.03), replace=False)
    v.loc[idx, "canal"] = v.loc[idx, "canal"].str.upper()
    # nulos en precio
    idx = rng.choice(n, size=40, replace=False)
    v.loc[idx, "precio_unitario"] = np.nan
    # SKUs que no existen en catálogo (productos dados de baja)
    idx = rng.choice(n, size=25, replace=False)
    v.loc[idx, "sku"] = [f"XXX-{k:04d}" for k in range(25)]
    # filas duplicadas (doble envío del POS)
    v = pd.concat([v, v.sample(120, random_state=SEED)], ignore_index=True)
    return v


def generar_inventario(prod: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Existencias según sistema vs conteo físico del cierre de junio 2026."""
    sistema = np.maximum(0, (prod["stock_minimo"] * rng.uniform(0.2, 4.0, len(prod))).round()).astype(int)
    fisico = sistema.copy()
    # merma, robo hormiga y errores de recepción
    idx = rng.choice(len(prod), size=int(len(prod) * 0.18), replace=False)
    fisico[idx] = np.maximum(0, sistema[idx] + rng.integers(-8, 4, size=len(idx)))
    # algunos casos graves
    idx = rng.choice(len(prod), size=6, replace=False)
    fisico[idx] = np.maximum(0, sistema[idx] - rng.integers(20, 60, size=6))
    return pd.DataFrame({"sku": prod["sku"], "existencia_sistema": sistema,
                         "existencia_fisica": fisico, "fecha_conteo": "2026-06-30"})


def generar_lista_proveedor_html(prod: pd.DataFrame, rng: np.random.Generator) -> str:
    """Página HTML con la lista de precios vigente del proveedor (para el scraper)."""
    muestra = prod.sample(140, random_state=SEED).copy()
    # aumentos de proveedor: la mayoría 3-8%, algunos fuertes
    aum = rng.normal(0.055, 0.02, len(muestra))
    fuertes = rng.choice(len(muestra), size=12, replace=False)
    aum[fuertes] = rng.uniform(0.15, 0.32, size=12)
    muestra["costo_nuevo"] = (muestra["costo"] * (1 + aum)).round(2)
    filas = "\n".join(
        f'      <tr class="producto"><td class="sku">{r.sku}</td><td class="desc">{r.descripcion}</td>'
        f'<td class="unidad">{r.unidad}</td><td class="precio">${r.costo_nuevo:,.2f}</td>'
        f'<td class="disp">{"Disponible" if rng.random() > 0.08 else "Agotado"}</td></tr>'
        for r in muestra.itertuples()
    )
    return f"""<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Lista de precios mayoreo - Julio 2026</title></head>
<body>
  <h1>Lista de precios a distribuidor</h1>
  <p class="vigencia">Vigente a partir del 01/07/2026. Precios sin IVA.</p>
  <table id="lista-precios">
    <thead><tr><th>SKU</th><th>Descripción</th><th>Unidad</th><th>Precio distribuidor</th><th>Disponibilidad</th></tr></thead>
    <tbody>
{filas}
    </tbody>
  </table>
</body>
</html>
"""


def main() -> None:
    rng = np.random.default_rng(SEED)
    RAW.mkdir(parents=True, exist_ok=True)

    prov = generar_proveedores()
    prod = generar_productos(rng)
    ventas = generar_ventas(prod, rng)
    inv = generar_inventario(prod, rng)
    html = generar_lista_proveedor_html(prod, rng)

    prov.to_csv(RAW / "proveedores.csv", index=False)
    ensuciar_productos(prod, rng).to_csv(RAW / "productos.csv", index=False)
    ensuciar_ventas(ventas, rng).to_csv(RAW / "ventas.csv", index=False)
    inv.to_csv(RAW / "inventario_conteo.csv", index=False)
    (RAW / "lista_precios_proveedor.html").write_text(html, encoding="utf-8")

    print(f"Productos: {len(prod):,} | Líneas de venta: {len(ventas):,} | Proveedores: {len(prov)}")
    print(f"Archivos generados en {RAW}")


if __name__ == "__main__":
    main()
