-- Load the seed CSVs (project/data/shop, mounted at /seed).
COPY raw.customers   FROM '/seed/customers.csv'   WITH (FORMAT csv, HEADER true);
COPY raw.products    FROM '/seed/products.csv'    WITH (FORMAT csv, HEADER true);
COPY raw.orders      FROM '/seed/orders.csv'      WITH (FORMAT csv, HEADER true);
COPY raw.order_items FROM '/seed/order_items.csv' WITH (FORMAT csv, HEADER true);
ANALYZE;
