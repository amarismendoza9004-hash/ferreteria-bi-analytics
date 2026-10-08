# Dashboard en Power BI — guía de armado

Los CSV limpios que genera el pipeline están en `powerbi/datos/`. Con esta guía se arma el dashboard en unos 30 minutos y se guarda como `powerbi/Ferreteria_BI.pbix`.

## 1. Cargar los datos

**Inicio → Obtener datos → Texto/CSV** y carga los seis archivos de `powerbi/datos/`:
`fact_ventas`, `dim_producto`, `dim_proveedor`, `dim_fecha`, `inventario`, `precios_proveedor`.

En Power Query revisa los tipos: `fecha` como Fecha/hora, `fecha_dia` y `dim_fecha[fecha]` como Fecha, importes como Número decimal.

## 2. Modelo (esquema estrella)

| Desde | Hacia | Cardinalidad |
|---|---|---|
| `fact_ventas[sku]` | `dim_producto[sku]` | Muchos a uno |
| `fact_ventas[fecha_dia]` | `dim_fecha[fecha]` | Muchos a uno |
| `dim_producto[proveedor_id]` | `dim_proveedor[proveedor_id]` | Muchos a uno |
| `inventario[sku]` | `dim_producto[sku]` | Uno a uno |
| `precios_proveedor[sku]` | `dim_producto[sku]` | Uno a uno |

Marca `dim_fecha` como **tabla de fechas** (Herramientas de tabla → Marcar como tabla de fechas).

## 3. Medidas DAX

Crea una tabla vacía llamada `_Medidas` y agrega:

```dax
Ventas Netas = SUM ( fact_ventas[importe] )

Utilidad Bruta = SUM ( fact_ventas[utilidad] )

Margen % = DIVIDE ( [Utilidad Bruta], [Ventas Netas] )

Tickets = DISTINCTCOUNT ( fact_ventas[ticket_id] )

Ticket Promedio = DIVIDE ( [Ventas Netas], [Tickets] )

Unidades = SUM ( fact_ventas[cantidad] )

Ventas Año Anterior =
CALCULATE ( [Ventas Netas], SAMEPERIODLASTYEAR ( dim_fecha[fecha] ) )

Crecimiento % vs AA =
DIVIDE ( [Ventas Netas] - [Ventas Año Anterior], [Ventas Año Anterior] )

Ventas Acumuladas Año = TOTALYTD ( [Ventas Netas], dim_fecha[fecha] )

Ventas Promedio Móvil 3M =
AVERAGEX (
    DATESINPERIOD ( dim_fecha[fecha], MAX ( dim_fecha[fecha] ), -3, MONTH ),
    [Ventas Netas]
) * 30

Participación Canal % =
DIVIDE ( [Ventas Netas], CALCULATE ( [Ventas Netas], ALL ( fact_ventas[canal] ) ) )

Comisiones Marketplace = SUM ( fact_ventas[comision] )

Tasa Devolución % =
DIVIDE (
    CALCULATE ( ABS ( [Unidades] ), fact_ventas[es_devolucion] = TRUE () ),
    CALCULATE ( [Unidades], fact_ventas[es_devolucion] = FALSE () )
)

Valor Faltante Inventario =
CALCULATE ( SUM ( inventario[valor_diferencia] ), inventario[diferencia] < 0 )

SKUs Bajo Mínimo =
CALCULATE ( COUNTROWS ( inventario ), inventario[bajo_minimo] = TRUE () )

SKUs Margen en Riesgo =
CALCULATE ( COUNTROWS ( precios_proveedor ), precios_proveedor[margen_con_costo_nuevo_pct] < 0.15 )

Clase ABC =
VAR VentasSku = [Ventas Netas]
VAR Total = CALCULATE ( [Ventas Netas], ALL ( dim_producto ) )
VAR Acumulado =
    SUMX (
        FILTER (
            ALL ( dim_producto[sku] ),
            CALCULATE ( [Ventas Netas] ) >= VentasSku
        ),
        CALCULATE ( [Ventas Netas] )
    )
RETURN
    SWITCH ( TRUE (),
        DIVIDE ( Acumulado, Total ) <= 0.80, "A",
        DIVIDE ( Acumulado, Total ) <= 0.95, "B",
        "C" )
```

## 4. Páginas sugeridas

**Página 1 · Resumen ejecutivo**
- Tarjetas: Ventas Netas, Utilidad Bruta, Margen %, Ticket Promedio, Crecimiento % vs AA.
- Gráfico de líneas: Ventas Netas por `dim_fecha[anio_mes]` con Ventas Año Anterior.
- Barras: Ventas Netas por `dim_producto[categoria]`, con Margen % en la información sobre herramientas.
- Segmentadores en una fila arriba: año, canal, categoría.

**Página 2 · Canales**
- Líneas: Participación Canal % por mes.
- Tabla: canal, Ventas Netas, Comisiones Marketplace, Margen %.

**Página 3 · Inventario**
- Tarjetas: Valor Faltante Inventario, SKUs Bajo Mínimo.
- Tabla con formato condicional: sku, descripción, existencia_sistema, existencia_fisica, diferencia, valor_diferencia.

**Página 4 · Precios y proveedores**
- Tarjeta: SKUs Margen en Riesgo.
- Dispersión: `aumento_costo_pct` (X) vs `margen_con_costo_nuevo_pct` (Y), con una línea de referencia en 15%.
- Tabla de productos a revisar, ordenada por margen nuevo.

## 5. Storytelling

Pon un título con la conclusión en cada página, no solo el nombre del dato. Por ejemplo: "El margen bajó 1.2 puntos porque crecen los marketplaces, que pagan 15% de comisión", en lugar de "Margen por canal".

Al terminar, exporta capturas de cada página a `reports/figures/powerbi_*.png` y agrégalas al README.
