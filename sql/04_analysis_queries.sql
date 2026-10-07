-- =====================================================================
--  Bertie Sweet Online Shop  |  04_analysis_queries.sql
--  Business questions answered with SQL.
--  Techniques: multi-table JOINs, correlated & non-correlated subqueries,
--  CTEs, window functions, FILTER, ROLLUP, CASE, date arithmetic.
-- =====================================================================
SET search_path TO bertie;


-- ---------------------------------------------------------------------
-- Q1. Headline KPIs by year
--     Revenue, orders, active customers, AOV, and share of repeat orders.
--     [CTE + aggregation + conditional aggregate]
-- ---------------------------------------------------------------------
WITH valid_orders AS (
    SELECT * FROM vw_order_summary WHERE order_status <> 'cancelled'
)
SELECT
    EXTRACT(YEAR FROM order_date)::INT                                AS year,
    ROUND(SUM(order_total), 2)                                        AS revenue_incl_delivery,
    COUNT(*)                                                          AS orders,
    COUNT(DISTINCT customer_id)                                       AS active_customers,
    ROUND(AVG(order_total), 2)                                        AS avg_order_value,
    ROUND(100.0 * COUNT(*) FILTER (WHERE new_vs_repeat = 'Repeat') / COUNT(*), 1) AS repeat_order_pct
FROM valid_orders
GROUP BY ROLLUP (EXTRACT(YEAR FROM order_date))
ORDER BY year NULLS LAST;            -- NULL row = all-time total


-- ---------------------------------------------------------------------
-- Q2. Top 10 products by net revenue, with category and units
--     [6-table JOIN across order, line, sweet, category, address, region]
-- ---------------------------------------------------------------------
SELECT
    s.sweet_code,
    s.sweet_name,
    sc.category_name,
    SUM(oi.quantity)                                                    AS units_sold,
    SUM(ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct/100), 2)) AS net_revenue,
    COUNT(DISTINCT r.region_id)                                         AS regions_sold_in
FROM order_item        oi
JOIN customer_order    o   ON o.order_id     = oi.order_id
JOIN sweet             s   ON s.sweet_code   = oi.sweet_code
JOIN sweet_category    sc  ON sc.category_id = s.category_id
JOIN delivery_address  da  ON da.address_id  = o.address_id
JOIN region            r   ON r.region_id    = da.region_id
WHERE o.order_status <> 'cancelled'
GROUP BY s.sweet_code, s.sweet_name, sc.category_name
ORDER BY net_revenue DESC
LIMIT 10;


-- ---------------------------------------------------------------------
-- Q3. Best-selling product in EACH category
--     [window function RANK() inside a CTE, filtered in outer query]
-- ---------------------------------------------------------------------
WITH ranked AS (
    SELECT
        category_name,
        product_name,
        SUM(net_revenue) AS revenue,
        RANK() OVER (PARTITION BY category_name ORDER BY SUM(net_revenue) DESC) AS rnk
    FROM vw_order_line_sales
    WHERE order_status <> 'cancelled'
    GROUP BY category_name, product_name
)
SELECT category_name, product_name, revenue
FROM ranked
WHERE rnk = 1
ORDER BY revenue DESC;


-- ---------------------------------------------------------------------
-- Q4. Category revenue trend: monthly revenue, running total and
--     3-month moving average per category
--     [window frames: ROWS BETWEEN ... ]
-- ---------------------------------------------------------------------
SELECT
    category_name,
    order_month,
    revenue,
    SUM(revenue) OVER (PARTITION BY category_name ORDER BY order_month)                   AS running_total,
    ROUND(AVG(revenue) OVER (PARTITION BY category_name ORDER BY order_month
                             ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2)                AS moving_avg_3m
FROM vw_monthly_category_revenue
ORDER BY category_name, order_month;


-- ---------------------------------------------------------------------
-- Q5. Year-over-year category growth (2025 vs 2024)
--     [conditional aggregation pivot]
-- ---------------------------------------------------------------------
SELECT
    category_name,
    SUM(net_revenue) FILTER (WHERE EXTRACT(YEAR FROM order_date) = 2024) AS revenue_2024,
    SUM(net_revenue) FILTER (WHERE EXTRACT(YEAR FROM order_date) = 2025) AS revenue_2025,
    ROUND(100.0 * (SUM(net_revenue) FILTER (WHERE EXTRACT(YEAR FROM order_date) = 2025)
                 - SUM(net_revenue) FILTER (WHERE EXTRACT(YEAR FROM order_date) = 2024))
          / NULLIF(SUM(net_revenue) FILTER (WHERE EXTRACT(YEAR FROM order_date) = 2024), 0), 1) AS yoy_growth_pct
FROM vw_order_line_sales
WHERE order_status <> 'cancelled'
GROUP BY category_name
ORDER BY yoy_growth_pct DESC;


-- ---------------------------------------------------------------------
-- Q6. Repeat purchasing: how quickly do customers come back?
--     Median & average days between orders, per customer segment
--     [ordered-set aggregate PERCENTILE_CONT + join to view]
-- ---------------------------------------------------------------------
SELECT
    cs.customer_segment,
    COUNT(DISTINCT cs.customer_id)                                          AS customers,
    ROUND(AVG(os.days_since_prev_order), 1)                                 AS avg_days_between_orders,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY os.days_since_prev_order)   AS median_days_between_orders
FROM vw_customer_summary cs
JOIN vw_order_summary    os ON os.customer_id = cs.customer_id
WHERE os.days_since_prev_order IS NOT NULL
  AND os.order_status <> 'cancelled'
  AND cs.customer_segment <> 'One-off'
GROUP BY cs.customer_segment
ORDER BY avg_days_between_orders;


-- ---------------------------------------------------------------------
-- Q7. Customer segments: size and share of revenue
--     ("what % of revenue comes from our loyal customers?")
-- ---------------------------------------------------------------------
SELECT
    customer_segment,
    COUNT(*)                                                         AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)               AS pct_customers,
    ROUND(SUM(lifetime_value), 2)                                    AS revenue,
    ROUND(100.0 * SUM(lifetime_value) / SUM(SUM(lifetime_value)) OVER (), 1) AS pct_revenue,
    ROUND(AVG(lifetime_value), 2)                                    AS avg_lifetime_value
FROM vw_customer_summary
WHERE customer_segment <> 'No purchase'
GROUP BY customer_segment
ORDER BY avg_lifetime_value DESC;


-- ---------------------------------------------------------------------
-- Q8. Customers who spent more than the average customer
--     [non-correlated scalar subquery in HAVING]
-- ---------------------------------------------------------------------
SELECT
    c.customer_id,
    c.full_name,
    COUNT(o.order_id)          AS orders,
    ROUND(SUM(os.order_total), 2) AS total_spent
FROM customer          c
JOIN customer_order    o  ON o.customer_id = c.customer_id
JOIN vw_order_summary  os ON os.order_id   = o.order_id
WHERE o.order_status <> 'cancelled'
GROUP BY c.customer_id, c.full_name
HAVING SUM(os.order_total) > (
        SELECT AVG(customer_total)
        FROM (SELECT customer_id, SUM(order_total) AS customer_total
              FROM vw_order_summary
              WHERE order_status <> 'cancelled'
              GROUP BY customer_id) t
)
ORDER BY total_spent DESC
LIMIT 20;


-- ---------------------------------------------------------------------
-- Q9. Each customer's favourite category (most units bought)
--     [correlated subquery]
-- ---------------------------------------------------------------------
SELECT
    cs.customer_id,
    cs.username,
    cs.order_count,
    (SELECT ls.category_name
       FROM vw_order_line_sales ls
      WHERE ls.customer_id = cs.customer_id
        AND ls.order_status <> 'cancelled'
      GROUP BY ls.category_name
      ORDER BY SUM(ls.quantity) DESC, ls.category_name
      LIMIT 1)                                AS favourite_category
FROM vw_customer_summary cs
WHERE cs.customer_segment IN ('Loyal (5-12)', 'Super-fan (13+)')
ORDER BY cs.order_count DESC
LIMIT 20;


-- ---------------------------------------------------------------------
-- Q10. Products frequently bought together (market-basket pairs)
--      [self-join on order_item]
-- ---------------------------------------------------------------------
SELECT
    a.sweet_code                        AS product_a,
    sa.sweet_name                       AS product_a_name,
    b.sweet_code                        AS product_b,
    sb.sweet_name                       AS product_b_name,
    COUNT(*)                            AS orders_together
FROM order_item a
JOIN order_item b   ON b.order_id = a.order_id
                   AND a.sweet_code < b.sweet_code       -- avoid duplicates & self-pairs
JOIN sweet      sa  ON sa.sweet_code = a.sweet_code
JOIN sweet      sb  ON sb.sweet_code = b.sweet_code
GROUP BY a.sweet_code, sa.sweet_name, b.sweet_code, sb.sweet_name
HAVING COUNT(*) >= 10
ORDER BY orders_together DESC
LIMIT 15;


-- ---------------------------------------------------------------------
-- Q11. Promotion effectiveness: units/day for sweets ON offer vs OFF offer
--      [EXISTS subquery against time-boxed sweet_offer]
-- ---------------------------------------------------------------------
WITH line_flags AS (
    SELECT
        oi.sweet_code,
        oi.quantity,
        o.order_date,
        EXISTS (SELECT 1
                  FROM sweet_offer so
                 WHERE so.sweet_code = oi.sweet_code
                   AND o.order_date BETWEEN so.offer_start_date AND so.offer_end_date) AS during_offer
    FROM order_item oi
    JOIN customer_order o ON o.order_id = oi.order_id
    WHERE oi.sweet_code IS NOT NULL AND o.order_status <> 'cancelled'
)
SELECT
    sc.category_name,
    CASE WHEN during_offer THEN 'On offer' ELSE 'Full price' END AS price_status,
    SUM(lf.quantity)                                              AS units,
    COUNT(DISTINCT lf.order_date)                                 AS trading_days,
    ROUND(SUM(lf.quantity)::NUMERIC / COUNT(DISTINCT lf.order_date), 2) AS units_per_trading_day
FROM line_flags lf
JOIN sweet          s  ON s.sweet_code   = lf.sweet_code
JOIN sweet_category sc ON sc.category_id = s.category_id
WHERE sc.category_id IN (SELECT DISTINCT s2.category_id
                           FROM sweet_offer so2 JOIN sweet s2 ON s2.sweet_code = so2.sweet_code)
GROUP BY sc.category_name, price_status
ORDER BY sc.category_name, price_status;


-- ---------------------------------------------------------------------
-- Q12. Regional performance with region & grand totals
--      [GROUPING SETS / ROLLUP across region and category]
-- ---------------------------------------------------------------------
SELECT
    COALESCE(region_name,  'ALL REGIONS')    AS region,
    COALESCE(category_name, 'ALL CATEGORIES') AS category,
    ROUND(SUM(net_revenue), 2)               AS revenue,
    COUNT(DISTINCT order_id)                 AS orders
FROM vw_order_line_sales
WHERE order_status <> 'cancelled'
GROUP BY ROLLUP (region_name, category_name)
HAVING GROUPING(category_name) = 1           -- keep only the subtotal rows
ORDER BY revenue DESC;


-- ---------------------------------------------------------------------
-- Q13. Stock alert: sweets below re-order level at each distribution
--      centre, alongside last-90-day demand from that DC
--      [LEFT JOIN to an aggregated derived table]
-- ---------------------------------------------------------------------
SELECT
    dc.dc_name,
    s.sweet_name,
    st.quantity_on_hand,
    st.reorder_level,
    COALESCE(d.units_last_90d, 0)    AS units_last_90d
FROM stock st
JOIN distribution_centre dc ON dc.dc_id      = st.dc_id
JOIN sweet               s  ON s.sweet_code  = st.sweet_code
LEFT JOIN (
    SELECT o.dc_id, oi.sweet_code, SUM(oi.quantity) AS units_last_90d
    FROM order_item oi
    JOIN customer_order o ON o.order_id = oi.order_id
    WHERE o.order_date > (SELECT MAX(order_date) FROM customer_order) - INTERVAL '90 days'
      AND oi.sweet_code IS NOT NULL
    GROUP BY o.dc_id, oi.sweet_code
) d ON d.dc_id = st.dc_id AND d.sweet_code = st.sweet_code
WHERE st.quantity_on_hand < st.reorder_level
ORDER BY units_last_90d DESC, st.quantity_on_hand
LIMIT 20;


-- ---------------------------------------------------------------------
-- Q14. Basket abandonment rate by month
--      [LEFT JOIN anti-pattern check + FILTER]
-- ---------------------------------------------------------------------
SELECT
    DATE_TRUNC('month', b.created_at)::DATE                               AS month,
    COUNT(*)                                                               AS baskets,
    COUNT(*) FILTER (WHERE b.status = 'abandoned')                         AS abandoned,
    ROUND(100.0 * COUNT(*) FILTER (WHERE b.status = 'abandoned') / COUNT(*), 1) AS abandonment_rate_pct,
    COUNT(*) FILTER (WHERE b.status = 'checked_out' AND o.order_id IS NULL) AS data_quality_issues
FROM shopping_basket b
LEFT JOIN customer_order o ON o.basket_id = b.basket_id
GROUP BY 1
ORDER BY 1;


-- ---------------------------------------------------------------------
-- Q15. Cohort retention snapshot: % of each quarterly cohort that
--      returned within 1, 3 and 6 months
-- ---------------------------------------------------------------------
SELECT
    TO_CHAR(DATE_TRUNC('quarter', cohort_month), 'YYYY-"Q"Q')                     AS cohort_quarter,
    SUM(cohort_customers) FILTER (WHERE months_since_first = 0)                   AS new_customers,
    ROUND(100.0 * SUM(active_customers) FILTER (WHERE months_since_first = 1)
          / SUM(cohort_customers) FILTER (WHERE months_since_first = 0), 1)       AS m1_retention_pct,
    ROUND(100.0 * SUM(active_customers) FILTER (WHERE months_since_first = 3)
          / SUM(cohort_customers) FILTER (WHERE months_since_first = 0), 1)       AS m3_retention_pct,
    ROUND(100.0 * SUM(active_customers) FILTER (WHERE months_since_first = 6)
          / SUM(cohort_customers) FILTER (WHERE months_since_first = 0), 1)       AS m6_retention_pct
FROM vw_cohort_retention
GROUP BY 1
ORDER BY 1;
