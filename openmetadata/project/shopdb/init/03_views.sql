-- Reporting views. OpenMetadata reads their SQL and draws lineage from it.
CREATE VIEW analytics.fct_orders AS
SELECT o.order_id,
       o.order_ts::date AS order_date,
       o.customer_id,
       c.country,
       o.status,
       o.total_amount
FROM raw.orders o
JOIN raw.customers c ON c.customer_id = o.customer_id
WHERE o.status <> 'cancelled';
COMMENT ON VIEW analytics.fct_orders IS 'Orders that were not cancelled, with the customer country.';

CREATE VIEW analytics.daily_revenue AS
SELECT order_date,
       count(*)          AS orders,
       sum(total_amount) AS revenue
FROM analytics.fct_orders
GROUP BY order_date;
COMMENT ON VIEW analytics.daily_revenue IS 'Revenue and order count per day. Feeds the finance dashboard.';
