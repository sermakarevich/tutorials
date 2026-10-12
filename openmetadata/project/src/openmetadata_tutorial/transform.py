"""The Brightcup "nightly job": rebuild analytics.customer_ltv with CREATE TABLE AS.

It runs as shop_admin, so the statement lands in pg_stat_statements, where the
OpenMetadata lineage workflow can find it and draw query lineage (chapter 06).
`python -m openmetadata_tutorial.transform`
"""

import psycopg

from openmetadata_tutorial.config import settings

CUSTOMER_LTV_SQL = """
CREATE TABLE analytics.customer_ltv AS
SELECT c.customer_id,
       c.email,
       c.country,
       count(f.order_id)               AS orders,
       coalesce(sum(f.total_amount), 0) AS lifetime_value
FROM raw.customers c
LEFT JOIN analytics.fct_orders f ON f.customer_id = c.customer_id
GROUP BY c.customer_id, c.email, c.country
"""


def rebuild_customer_ltv() -> int:
    """Drop and recreate analytics.customer_ltv; return its row count."""
    s = settings()
    dsn = f"host={s.shop_host} port={s.shop_port} dbname={s.shop_db} user={s.shop_admin_user} password={s.shop_admin_password}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS analytics.customer_ltv")
        conn.execute(CUSTOMER_LTV_SQL)
        conn.execute("GRANT SELECT ON analytics.customer_ltv TO om_reader")
        return conn.execute("SELECT count(*) FROM analytics.customer_ltv").fetchone()[0]


if __name__ == "__main__":
    print(f"analytics.customer_ltv rebuilt: {rebuild_customer_ltv()} rows")
