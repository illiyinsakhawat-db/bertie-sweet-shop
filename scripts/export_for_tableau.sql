-- =====================================================================
--  Export the reporting views to CSV for Tableau (Public or Desktop).
--  Run from the repo root with psql:
--      psql -d bertie_sweets -f scripts/export_for_tableau.sql
--  (Tableau Desktop users can instead connect live to PostgreSQL.)
-- =====================================================================
-- Cancelled orders are excluded so every dashboard figure is "valid sales".
SET search_path TO bertie;
\copy (SELECT * FROM vw_order_line_sales WHERE order_status <> 'cancelled' ORDER BY order_item_id)                 TO 'tableau/data/order_line_sales.csv'         WITH CSV HEADER
\copy (SELECT * FROM vw_order_summary WHERE order_status <> 'cancelled' ORDER BY order_id)                      TO 'tableau/data/order_summary.csv'            WITH CSV HEADER
\copy (SELECT customer_id, region_name, registered_on, first_order_date, last_order_date, cohort_month, order_count, lifetime_value, avg_order_value, avg_days_between_orders, customer_segment FROM vw_customer_summary WHERE order_count > 0 ORDER BY customer_id) TO 'tableau/data/customer_summary.csv' WITH CSV HEADER
\copy (SELECT * FROM vw_monthly_category_revenue ORDER BY category_name, order_month)    TO 'tableau/data/monthly_category_revenue.csv' WITH CSV HEADER
\copy (SELECT * FROM vw_product_performance      ORDER BY overall_rank)                  TO 'tableau/data/product_performance.csv'      WITH CSV HEADER
\copy (SELECT * FROM vw_cohort_retention         ORDER BY cohort_month, months_since_first) TO 'tableau/data/cohort_retention.csv'      WITH CSV HEADER
