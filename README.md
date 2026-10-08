# Análisis de Datos y BI para una Ferretería

Proyecto de análisis de datos de punta a punta para una ferretería mediana que vende en mostrador y en marketplaces. Extrae datos de varias fuentes, los limpia y valida, los carga a una base SQL, detecta anomalías y entrega reportes listos para tomar decisiones.

> **Nota sobre los datos:** los datos son **simulados**, generados con `src/generate_data.py` a partir de mi experiencia operando una ferretería (catálogo, inventario, precios de proveedor y venta en marketplaces). Reproducen los problemas reales de calidad de datos y los patrones de temporada del negocio, sin exponer información de ninguna empresa.

![Ventas mensuales](reports/figures/01_ventas_mensuales.png)

---

## Preguntas de negocio que responde

1. ¿Cómo evolucionan las ventas y el margen, y qué los está moviendo?
2. ¿Qué categorías y productos concentran la venta y la utilidad? (análisis ABC)
3. ¿Qué canal crece más y cuánto margen deja cada uno después de comisiones?
4. ¿Qué productos hay que reabastecer ya, según demanda y días de entrega del proveedor?
5. ¿Dónde hay diferencias entre el inventario del sistema y el conteo físico?
6. ¿Qué aumentos de costo del proveedor ponen en riesgo el margen?
7. ¿Qué días se comportaron de forma atípica y por qué?

## Hallazgos principales

| # | Hallazgo | Recomendación |
|---|---|---|
| 1 | El margen bruto bajó de **23.7% (2024) a 22.5% (2026)** aunque la venta crece. La causa es la mezcla: los marketplaces crecen más rápido y dejan **17.9%** de margen tras la comisión del 15%, contra **24.5%** en mostrador. | Revisar precios publicados en Mercado Libre y Amazon, o empujar los productos de mayor margen en esos canales. |
| 2 | WhatsApp creció **69%** (ene–jun 2026 vs 2025) y Mercado Libre **25%**; mostrador solo **3%**. | Formalizar el canal de WhatsApp (catálogo y cotizaciones) porque no paga comisión y concentra pedidos de obra. |
| 3 | **97 de 352 SKUs (28%) generan el 80% de la venta** (clase A). | Prioridad de inventario y conteos cíclicos semanales en clase A. |
| 4 | **22 productos** están bajo mínimo y se agotan antes de que llegue el pedido del proveedor. | Lista de compras urgente generada por la consulta `reabastecimiento`. |
| 5 | El conteo físico detectó **46 SKUs con faltante por $116,897** frente al sistema. Un solo producto concentra la mitad. | Auditar recepción y salidas de impermeabilizantes y membranas. |
| 6 | La nueva lista del proveedor (obtenida por scraping) sube costos **7.2% en promedio**; **18 productos** quedan con margen menor a 15%. | Aplicar el precio sugerido que calcula la consulta para recuperar 30% de margen. |
| 7 | **7 productos** tienen precio capturado por debajo del costo. Con el volumen de los últimos 12 meses representarían una pérdida de **$280,106**. | Corregir el catálogo antes de la siguiente venta. |
| 8 | De 730 días, el detector marcó **10 días atípicos**. Destacan **3 caídas de operación** con tickets −80% (compatibles con caída del POS o corte de luz) y **2 pedidos de obra** que hicieron vender casi 5 veces lo normal ese día. | Separar pedidos de obra en los pronósticos para no inflar la demanda normal. |

![Participación de canales](reports/figures/03_participacion_canales.png)

![Anomalías](reports/figures/06_anomalias_ventas.png)

---

## Tecnologías

| Área | Herramientas |
|---|---|
| Extracción | **Python** (pandas), **web scraping** (requests + BeautifulSoup), **API** REST de tipo de cambio |
| Transformación (ETL) | pandas: limpieza, validación, normalización, imputación, reporte de calidad |
| Base de datos | **SQL** (SQLite): modelo estrella, JOINs, agregaciones, CTEs, funciones de ventana |
| Análisis | Clasificación ABC, índice estacional, detección de anomalías con z-score robusto (mediana/MAD) |
| Visualización | **Power BI** (modelo + medidas DAX), **Grafana** (dashboard en Docker), matplotlib |
| Reportes | **Excel** con tablas dinámicas, formato condicional, validación de datos y fórmulas INDEX/MATCH |

## Arquitectura

```
 Fuentes                     ETL (Python)                     Destino              Consumo
 ─────────                   ────────────                     ───────              ───────
 POS / ERP (CSV) ──┐
 Lista proveedor ──┼──► limpieza ─► validación ─► métricas ──► SQLite (estrella) ──► SQL / análisis
   (scraping HTML) │                                       │                    ├──► Power BI
 API tipo cambio ──┘                                       └──► CSV limpios      ├──► Grafana
                                                                                 └──► Excel + gráficas
```

## Calidad de datos

El ETL encuentra y corrige los problemas típicos de un sistema de punto de venta. Todo queda registrado en `data/processed/calidad_datos.json`:

| Problema | Filas | Tratamiento |
|---|---:|---|
| Fechas en formato dd/mm/aaaa mezcladas con ISO | 7,529 | Se interpretan ambos formatos |
| Unidades escritas de forma distinta (pza, Pieza, PZA) | 88 | Se normalizan a un catálogo |
| Duplicados exactos de ventas (doble envío del POS) | 120 | Se eliminan |
| Precio nulo en la venta | 40 | Se imputa con el precio de catálogo |
| SKU vendido que no existe en catálogo | 25 | Se manda a `rechazos_ventas` |
| Costos guardados como texto ("$1,234.50") | 15 | Se convierten a número |
| Cantidades imposibles (código de barras capturado como cantidad) | 8 | Se manda a `rechazos_ventas` |
| SKUs duplicados en catálogo | 6 | Se deja uno |
| Precio de venta menor al costo | 7 | Se marca con alerta |

## Estructura del proyecto

```
ferreteria-bi-analytics/
├── run_pipeline.py              # Ejecuta todo de punta a punta
├── src/
│   ├── generate_data.py         # Datos simulados con errores realistas
│   ├── scraper_proveedor.py     # Web scraping de la lista de precios del proveedor
│   ├── api_tipo_cambio.py       # Cliente de API (USD/MXN) con caché
│   ├── etl.py                   # Limpieza, validación y carga a SQLite
│   └── analisis.py              # Consultas SQL, anomalías, gráficas y Excel
├── sql/consultas_negocio.sql    # 13 consultas de negocio comentadas
├── data/
│   ├── raw/                     # Datos de entrada (se regeneran con el pipeline)
│   └── processed/               # Base SQLite y reporte de calidad
├── reports/
│   ├── figures/                 # Gráficas
│   ├── resultados/              # Resultado de cada consulta en CSV
│   └── reporte_ferreteria.xlsx  # Reporte en Excel
├── powerbi/medidas_dax.md       # Modelo y medidas DAX para el dashboard
└── grafana/                     # Dashboard de monitoreo con Docker
```

## Cómo ejecutarlo

```bash
git clone https://github.com/amarismendoza9004-hash/ferreteria-bi-analytics.git
cd ferreteria-bi-analytics
pip install -r requirements.txt
python run_pipeline.py
```

Tarda menos de un minuto y genera la base de datos, los CSV para Power BI, las gráficas y el Excel.

**Grafana** (requiere Docker):

```bash
cd grafana
docker compose up -d
# Abrir http://localhost:3000  (usuario admin / contraseña admin)
```

**Power BI:** sigue la guía de `powerbi/medidas_dax.md` usando los CSV de `powerbi/datos/`.

## Más gráficas

| | |
|---|---|
| ![Categorías](reports/figures/02_ventas_categoria.png) | ![Estacionalidad](reports/figures/04_estacionalidad.png) |
| ![Mapa de calor](reports/figures/05_mapa_calor_horas.png) | ![Inventario](reports/figures/07_faltantes_inventario.png) |

## Autor

**Amaris Milagros Mendoza C.** — Analista de datos con experiencia en operación de retail, control de inventarios y e-commerce.

[GitHub](https://github.com/amarismendoza9004-hash) · [amarismendoza9004@gmail.com](mailto:amarismendoza9004@gmail.com)
