-- =====================================================================
--  Bertie Sweet Online Shop  |  03_views.sql
--  Reporting layer: the derived figures that are deliberately NOT stored
--  in the 3NF tables (totals, sequences, segments) live here.
--  These views are the data sources for the Tableau dashboard.
-- =====================================================================
SET search_path TO bertie;

-- ---------------------------------------------------------------------
-- vw_order_line_sales : one row per order line (grain = order_item)
-- Unifies single sweets and multi-packs into a single "product" dimension.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_order_line_sales AS
SELECT
    oi.order_item_id,
    o.order_id,
    o.order_date,
    DATE_TRUNC('month', o.order_date)::DATE                   AS order_month,
    o.order_status,
    o.customer_id,
    r.region_name,
    dc.dc_name,
    CASE WHEN oi.sweet_code IS NOT NULL THEN 'Single sweet' ELSE 'Multi-pack' END AS product_type,
    COALESCE(oi.sweet_code, 'MP' || LPAD(oi.multi_pack_id::TEXT, 3, '0'))       AS product_code,
    COALESCE(s.sweet_name, mp.multi_pack_name)                AS product_name,
    COALESCE(sc.category_name, 'Multi-Packs')                 AS category_name,
    oi.quantity,
    oi.unit_price,
    oi.discount_pct,
    CASE WHEN oi.discount_pct > 0 THEN 'On offer' ELSE 'Full price' END AS price_status,
    ROUND(oi.quantity * oi.unit_price, 2)                     AS gross_revenue,
    ROUND(oi.quantity * oi.unit_price * oi.discount_pct / 100, 2) AS discount_amount,
    ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100), 2) AS net_revenue
FROM order_item              oi
JOIN customer_order          o   ON o.order_id        = oi.order_id
JOIN delivery_address        da  ON da.address_id     = o.address_id
JOIN region                  r   ON r.region_id       = da.region_id
JOIN distribution_centre     dc  ON dc.dc_id          = o.dc_id
LEFT JOIN sweet              s   ON s.sweet_code      = oi.sweet_code
LEFT JOIN sweet_category     sc  ON sc.category_id    = s.category_id
LEFT JOIN multi_pack         mp  ON mp.multi_pack_id  = oi.multi_pack_id;


-- ---------------------------------------------------------------------
-- vw_order_summary : one row per order with derived totals and the
-- customer's order sequence (1st, 2nd, 3rd ...) -> repeat purchase flags
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_order_summary AS
WITH order_totals AS (
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        o.order_status,
        o.delivery_charge,
        r.region_name,
        COUNT(oi.order_item_id)                                        AS line_count,
        SUM(oi.quantity)                                               AS units,
        SUM(oi.quantity * oi.unit_price)                               AS gross_subtotal,
        SUM(oi.quantity * oi.unit_price * oi.discount_pct / 100)       AS discount_total
    FROM customer_order   o
    JOIN order_item       oi ON oi.order_id   = o.order_id
    JOIN delivery_address da ON da.address_id = o.address_id
    JOIN region           r  ON r.region_id   = da.region_id
    GROUP BY o.order_id, o.customer_id, o.order_date, o.order_status, o.delivery_charge, r.region_name
)
SELECT
    order_id,
    customer_id,
    order_date,
    DATE_TRUNC('month', order_date)::DATE                                AS order_month,
    order_status,
    region_name,
    line_count,
    units,
    ROUND(gross_subtotal, 2)                                             AS gross_subtotal,
    ROUND(discount_total, 2)                                             AS discount_total,
    delivery_charge,
    ROUND(gross_subtotal - discount_total + delivery_charge, 2)          AS order_total,
    ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS customer_order_seq,
    order_date - LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, order_id)
                                                                         AS days_since_prev_order,
    CASE WHEN ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) = 1
         THEN 'New' ELSE 'Repeat' END                                    AS new_vs_repeat
FROM order_totals;


-- ---------------------------------------------------------------------
-- vw_customer_summary : customer lifetime value & behavioural segment
-- (cancelled orders excluded from value metrics)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_customer_summary AS
SELECT
    c.customer_id,
    c.username,
    c.registered_on,
    r.region_name,
    MIN(os.order_date)                                   AS first_order_date,
    MAX(os.order_date)                                   AS last_order_date,
    DATE_TRUNC('month', MIN(os.order_date))::DATE        AS cohort_month,
    COUNT(os.order_id)                                   AS order_count,
    COALESCE(SUM(os.order_total), 0)                     AS lifetime_value,
    ROUND(AVG(os.order_total), 2)                        AS avg_order_value,
    ROUND(AVG(os.days_since_prev_order), 1)              AS avg_days_between_orders,
    CASE
        WHEN COUNT(os.order_id) = 0  THEN 'No purchase'
        WHEN COUNT(os.order_id) = 1  THEN 'One-off'
        WHEN COUNT(os.order_id) <= 4 THEN 'Occasional (2-4)'
        WHEN COUNT(os.order_id) <= 12 THEN 'Loyal (5-12)'
        ELSE 'Super-fan (13+)'
    END                                                  AS customer_segment
FROM customer c
JOIN delivery_address da ON da.customer_id = c.customer_id AND da.is_default
JOIN region           r  ON r.region_id    = da.region_id
LEFT JOIN vw_order_summary os
       ON os.customer_id = c.customer_id AND os.order_status <> 'cancelled'
GROUP BY c.customer_id, c.username, c.registered_on, r.region_name;


-- ---------------------------------------------------------------------
-- vw_monthly_category_revenue : revenue trend by category with
-- month-over-month and year-over-year growth (window functions)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_monthly_category_revenue AS
WITH monthly AS (
    SELECT order_month, category_name,
           SUM(net_revenue) AS revenue,
           SUM(quantity)    AS units
    FROM vw_order_line_sales
    WHERE order_status <> 'cancelled'
    GROUP BY order_month, category_name
)
SELECT
    order_month,
    category_name,
    revenue,
    units,
    ROUND(100.0 * revenue / SUM(revenue) OVER (PARTITION BY order_month), 1)        AS pct_of_month,
    LAG(revenue)     OVER (PARTITION BY category_name ORDER BY order_month)          AS prev_month_revenue,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (PARTITION BY category_name ORDER BY order_month))
          / NULLIF(LAG(revenue) OVER (PARTITION BY category_name ORDER BY order_month), 0), 1) AS mom_growth_pct,
    LAG(revenue, 12) OVER (PARTITION BY category_name ORDER BY order_month)          AS same_month_last_year,
    ROUND(100.0 * (revenue - LAG(revenue, 12) OVER (PARTITION BY category_name ORDER BY order_month))
          / NULLIF(LAG(revenue, 12) OVER (PARTITION BY category_name ORDER BY order_month), 0), 1) AS yoy_growth_pct
FROM monthly;


-- ---------------------------------------------------------------------
-- vw_product_performance : product league table incl. repeat-buy rate
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_product_performance AS
WITH per_customer AS (
    SELECT product_code, customer_id, COUNT(DISTINCT order_id) AS times_bought
    FROM vw_order_line_sales
    WHERE order_status <> 'cancelled'
    GROUP BY product_code, customer_id
),
repeat_rate AS (
    SELECT product_code,
           COUNT(*)                                   AS buyers,
           COUNT(*) FILTER (WHERE times_bought >= 2)  AS repeat_buyers
    FROM per_customer
    GROUP BY product_code
)
SELECT
    ls.product_code,
    ls.product_name,
    ls.category_name,
    ls.product_type,
    SUM(ls.quantity)                                          AS units_sold,
    COUNT(DISTINCT ls.order_id)                               AS orders,
    SUM(ls.net_revenue)                                       AS net_revenue,
    rr.buyers,
    rr.repeat_buyers,
    ROUND(100.0 * rr.repeat_buyers / rr.buyers, 1)            AS repeat_buyer_pct,
    RANK() OVER (ORDER BY SUM(ls.net_revenue) DESC)           AS overall_rank,
    RANK() OVER (PARTITION BY ls.category_name ORDER BY SUM(ls.net_revenue) DESC) AS rank_in_category
FROM vw_order_line_sales ls
JOIN repeat_rate rr ON rr.product_code = ls.product_code
WHERE ls.order_status <> 'cancelled'
GROUP BY ls.product_code, ls.product_name, ls.category_name, ls.product_type, rr.buyers, rr.repeat_buyers;


-- ---------------------------------------------------------------------
-- vw_cohort_retention : % of each first-purchase cohort ordering again
-- N months later (classic retention heat-map source)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_cohort_retention AS
WITH firsts AS (
    SELECT customer_id, MIN(order_month) AS cohort_month
    FROM vw_order_summary
    WHERE order_status <> 'cancelled'
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT f.cohort_month, os.customer_id,
           ((EXTRACT(YEAR FROM os.order_month) - EXTRACT(YEAR FROM f.cohort_month)) * 12
            + EXTRACT(MONTH FROM os.order_month) - EXTRACT(MONTH FROM f.cohort_month))::INT AS months_since_first
    FROM vw_order_summary os
    JOIN firsts f ON f.customer_id = os.customer_id
    WHERE os.order_status <> 'cancelled'
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS cohort_customers FROM firsts GROUP BY cohort_month
)
SELECT
    a.cohort_month,
    a.months_since_first,
    cs.cohort_customers,
    COUNT(*)                                            AS active_customers,
    ROUND(100.0 * COUNT(*) / cs.cohort_customers, 1)    AS retention_pct
FROM activity a
JOIN cohort_size cs ON cs.cohort_month = a.cohort_month
GROUP BY a.cohort_month, a.months_since_first, cs.cohort_customers;
