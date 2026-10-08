-- ============================================================================
-- Consultas de negocio - Ferretería (SQLite)
-- Cada bloque responde una pregunta del negocio. Los nombres "-- name:" los usa
-- src/analisis.py para ejecutar cada consulta y guardar el resultado.
-- ============================================================================


-- name: kpis_generales
-- ¿Cuánto vendimos, cuánto ganamos y cuál es el ticket promedio por año?
SELECT
    strftime('%Y', v.fecha)                                   AS anio,
    COUNT(DISTINCT v.ticket_id)                               AS tickets,
    ROUND(SUM(v.importe), 2)                                  AS ventas_netas,
    ROUND(SUM(v.utilidad), 2)                                 AS utilidad_bruta,
    ROUND(100.0 * SUM(v.utilidad) / SUM(v.importe), 2)        AS margen_pct,
    ROUND(SUM(v.importe) / COUNT(DISTINCT v.ticket_id), 2)    AS ticket_promedio
FROM fact_ventas v
GROUP BY anio
ORDER BY anio;


-- name: ventas_mensuales
-- Tendencia mensual de ventas y margen (base para detectar estacionalidad).
SELECT
    f.anio_mes,
    ROUND(SUM(v.importe), 2)                                  AS ventas_netas,
    ROUND(SUM(v.utilidad), 2)                                 AS utilidad_bruta,
    ROUND(100.0 * SUM(v.utilidad) / SUM(v.importe), 2)        AS margen_pct,
    COUNT(DISTINCT v.ticket_id)                               AS tickets
FROM fact_ventas v
JOIN dim_fecha f ON f.fecha = v.fecha_dia
GROUP BY f.anio_mes
ORDER BY f.anio_mes;


-- name: ventas_por_categoria
-- ¿Qué categorías generan más venta y más utilidad?
SELECT
    p.categoria,
    ROUND(SUM(v.importe), 2)                                  AS ventas_netas,
    ROUND(SUM(v.utilidad), 2)                                 AS utilidad_bruta,
    ROUND(100.0 * SUM(v.utilidad) / SUM(v.importe), 2)        AS margen_pct,
    ROUND(100.0 * SUM(v.importe) / (SELECT SUM(importe) FROM fact_ventas), 2) AS participacion_pct
FROM fact_ventas v
JOIN dim_producto p ON p.sku = v.sku
GROUP BY p.categoria
ORDER BY ventas_netas DESC;


-- name: ventas_por_canal
-- Mostrador vs marketplaces: ventas, margen y crecimiento año contra año.
WITH por_anio AS (
    SELECT v.canal,
           strftime('%Y', v.fecha) AS anio,
           SUM(v.importe)          AS ventas,
           SUM(v.utilidad)         AS utilidad
    FROM fact_ventas v
    WHERE v.fecha >= '2025-01-01'
    GROUP BY v.canal, anio
)
SELECT
    canal,
    ROUND(SUM(CASE WHEN anio = '2025' THEN ventas END), 2)                         AS ventas_2025,
    ROUND(SUM(CASE WHEN anio = '2026' THEN ventas END), 2)                         AS ventas_ene_jun_2026,
    ROUND(100.0 * SUM(utilidad) / SUM(ventas), 2)                                  AS margen_pct
FROM por_anio
GROUP BY canal
ORDER BY ventas_2025 DESC;


-- name: crecimiento_semestral_canal
-- Crecimiento ene-jun 2026 vs ene-jun 2025 por canal (periodos comparables).
SELECT
    canal,
    ROUND(SUM(CASE WHEN fecha BETWEEN '2025-01-01' AND '2025-06-30 23:59:59' THEN importe END), 2) AS ene_jun_2025,
    ROUND(SUM(CASE WHEN fecha BETWEEN '2026-01-01' AND '2026-06-30 23:59:59' THEN importe END), 2) AS ene_jun_2026,
    ROUND(100.0 * (
        SUM(CASE WHEN fecha BETWEEN '2026-01-01' AND '2026-06-30 23:59:59' THEN importe END) /
        SUM(CASE WHEN fecha BETWEEN '2025-01-01' AND '2025-06-30 23:59:59' THEN importe END) - 1), 2) AS crecimiento_pct
FROM fact_ventas
GROUP BY canal
ORDER BY crecimiento_pct DESC;


-- name: top_productos
-- Top 15 productos por utilidad bruta (últimos 12 meses).
SELECT
    p.sku,
    p.descripcion,
    p.categoria,
    SUM(v.cantidad)                                           AS unidades,
    ROUND(SUM(v.importe), 2)                                  AS ventas_netas,
    ROUND(SUM(v.utilidad), 2)                                 AS utilidad_bruta,
    ROUND(100.0 * SUM(v.utilidad) / SUM(v.importe), 2)        AS margen_pct
FROM fact_ventas v
JOIN dim_producto p ON p.sku = v.sku
WHERE v.fecha >= '2025-07-01'
GROUP BY p.sku, p.descripcion, p.categoria
ORDER BY utilidad_bruta DESC
LIMIT 15;


-- name: clasificacion_abc
-- Clasificación ABC (Pareto): ¿qué SKUs concentran el 80% de la venta?
WITH ventas_sku AS (
    SELECT sku, SUM(importe) AS ventas
    FROM fact_ventas
    WHERE fecha >= '2025-07-01'
    GROUP BY sku
),
acumulado AS (
    SELECT sku, ventas,
           SUM(ventas) OVER (ORDER BY ventas DESC ROWS UNBOUNDED PRECEDING)
               / SUM(ventas) OVER ()                          AS pct_acumulado
    FROM ventas_sku
)
SELECT
    CASE WHEN pct_acumulado <= 0.80 THEN 'A'
         WHEN pct_acumulado <= 0.95 THEN 'B'
         ELSE 'C' END                                         AS clase,
    COUNT(*)                                                  AS num_skus,
    ROUND(SUM(ventas), 2)                                     AS ventas,
    ROUND(100.0 * SUM(ventas) / (SELECT SUM(ventas) FROM ventas_sku), 2) AS pct_ventas
FROM acumulado
GROUP BY clase
ORDER BY clase;


-- name: estacionalidad_categoria
-- Índice estacional: venta promedio de cada mes vs promedio anual, por categoría.
WITH mensual AS (
    SELECT p.categoria,
           CAST(strftime('%m', v.fecha) AS INTEGER) AS mes,
           SUM(v.importe) / COUNT(DISTINCT strftime('%Y', v.fecha)) AS venta_prom_mes
    FROM fact_ventas v
    JOIN dim_producto p ON p.sku = v.sku
    GROUP BY p.categoria, mes
)
SELECT categoria, mes,
       ROUND(venta_prom_mes / AVG(venta_prom_mes) OVER (PARTITION BY categoria), 2) AS indice_estacional
FROM mensual
ORDER BY categoria, mes;


-- name: diferencias_inventario
-- Conciliación sistema vs conteo físico: faltantes con mayor impacto económico.
SELECT
    i.sku,
    p.descripcion,
    p.categoria,
    i.existencia_sistema,
    i.existencia_fisica,
    i.diferencia,
    i.valor_diferencia
FROM inventario i
JOIN dim_producto p ON p.sku = i.sku
WHERE i.diferencia <> 0
ORDER BY i.valor_diferencia ASC
LIMIT 20;


-- name: reabastecimiento
-- Productos bajo stock mínimo con su venta promedio diaria y días de cobertura.
WITH demanda AS (
    SELECT sku, SUM(cantidad) / 90.0 AS venta_diaria
    FROM fact_ventas
    WHERE fecha >= date('2026-06-30', '-90 day')
    GROUP BY sku
)
SELECT
    i.sku,
    p.descripcion,
    pr.nombre                                                 AS proveedor,
    pr.dias_entrega,
    i.existencia_fisica,
    p.stock_minimo,
    ROUND(d.venta_diaria, 2)                                  AS venta_diaria,
    ROUND(i.existencia_fisica / NULLIF(d.venta_diaria, 0), 1) AS dias_cobertura,
    CASE WHEN i.existencia_fisica / NULLIF(d.venta_diaria, 0) < pr.dias_entrega
         THEN 'URGENTE' ELSE 'Programar' END                  AS prioridad
FROM inventario i
JOIN dim_producto  p  ON p.sku = i.sku
JOIN dim_proveedor pr ON pr.proveedor_id = p.proveedor_id
LEFT JOIN demanda d   ON d.sku = i.sku
WHERE i.bajo_minimo = 1
ORDER BY dias_cobertura ASC NULLS LAST
LIMIT 25;


-- name: erosion_margen_proveedor
-- Aumentos de costo del proveedor (scraping) que dejan el margen por debajo del 15%.
SELECT
    pp.sku,
    p.descripcion,
    pr.nombre                                                 AS proveedor,
    pp.costo                                                  AS costo_actual,
    pp.costo_nuevo,
    ROUND(100 * pp.aumento_costo_pct, 1)                      AS aumento_pct,
    pp.precio_venta,
    ROUND(100 * pp.margen_actual_pct, 1)                      AS margen_actual_pct,
    ROUND(100 * pp.margen_con_costo_nuevo_pct, 1)             AS margen_nuevo_pct,
    ROUND(pp.costo_nuevo / (1 - 0.30), 0) - 0.10              AS precio_sugerido_margen_30
FROM precios_proveedor pp
JOIN dim_producto  p  ON p.sku = pp.sku
JOIN dim_proveedor pr ON pr.proveedor_id = p.proveedor_id
WHERE pp.margen_con_costo_nuevo_pct < 0.15
ORDER BY pp.margen_con_costo_nuevo_pct ASC;


-- name: productos_precio_bajo_costo
-- Errores de catálogo: productos cuyo precio capturado quedó por debajo del costo.
-- Se estima la pérdida si se vendiera el volumen de los últimos 12 meses a ese precio.
SELECT p.sku, p.descripcion, p.categoria, p.costo, p.precio_venta,
       ROUND(100.0 * p.margen_pct, 1)                              AS margen_pct,
       COALESCE(SUM(v.cantidad), 0)                                AS unidades_vendidas_12m,
       ROUND(COALESCE(SUM(v.cantidad), 0) * (p.precio_venta - p.costo), 2) AS perdida_potencial_12m
FROM dim_producto p
LEFT JOIN fact_ventas v ON v.sku = p.sku AND v.fecha >= '2025-07-01'
WHERE p.alerta_precio_bajo_costo = 1
GROUP BY p.sku, p.descripcion, p.categoria, p.costo, p.precio_venta, p.margen_pct
ORDER BY perdida_potencial_12m ASC;


-- name: ventas_por_dia_hora
-- Mapa de calor: ¿en qué día y hora se vende más en mostrador? (para turnos)
SELECT
    f.dia_semana,
    CAST(strftime('%H', v.fecha) AS INTEGER)                  AS hora,
    ROUND(SUM(v.importe) / COUNT(DISTINCT v.fecha_dia), 2)  AS venta_promedio
FROM fact_ventas v
JOIN dim_fecha f ON f.fecha = v.fecha_dia
WHERE v.canal = 'Mostrador'
GROUP BY f.dia_semana, hora;
