-- Brightcup source database: the data OpenMetadata catalogs in this tutorial.
-- Runs once, on the first start of the om-tutorial-shopdb container.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE SCHEMA raw;        -- landing tables, copied from the shop application
CREATE SCHEMA analytics;  -- derived views and tables for reporting

COMMENT ON SCHEMA raw IS 'Landing tables copied nightly from the Brightcup web shop.';
COMMENT ON SCHEMA analytics IS 'Derived reporting views and tables built from raw.';

CREATE TABLE raw.customers (
    customer_id  integer PRIMARY KEY,
    full_name    text NOT NULL,
    email        text,
    phone        text,
    country      char(2) NOT NULL,
    signup_date  date NOT NULL
);
COMMENT ON TABLE raw.customers IS 'One row per registered shop customer.';

CREATE TABLE raw.products (
    product_id integer PRIMARY KEY,
    sku        text NOT NULL,
    name       text NOT NULL,
    roast      text NOT NULL,
    origin     text NOT NULL,
    price_eur  numeric(8,2) NOT NULL
);

-- No primary key on purpose: the shop export can duplicate orders (a planted defect).
CREATE TABLE raw.orders (
    order_id      integer NOT NULL,
    customer_id   integer NOT NULL,
    order_ts      timestamp NOT NULL,
    status        text NOT NULL,
    total_amount  numeric(10,2) NOT NULL,
    currency      char(3) NOT NULL
);
COMMENT ON TABLE raw.orders IS 'One row per web-shop order.';

CREATE TABLE raw.order_items (
    order_id    integer NOT NULL,
    product_id  integer NOT NULL REFERENCES raw.products(product_id),
    quantity    integer NOT NULL,
    unit_price  numeric(8,2) NOT NULL
);
