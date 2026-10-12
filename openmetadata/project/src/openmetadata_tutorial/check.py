"""`just check`: is every piece of the stack up, and what versions are running?"""

import psycopg
import requests

from openmetadata_tutorial.client import get
from openmetadata_tutorial.config import settings


def check() -> list[tuple[str, bool, str]]:
    s = settings()
    results = []

    def probe(name, fn):
        try:
            results.append((name, True, fn()))
        except Exception as e:  # report, don't crash: the point is to see what is down
            results.append((name, False, f"{type(e).__name__}: {e}"[:120]))

    probe("openmetadata server", lambda: get("/v1/system/version")["version"])
    probe("search index", lambda: str(get("/v1/search/query", q="*", index="table_search_index", size=0)["hits"]["total"]["value"]) + " tables indexed")
    probe("ingestion (airflow)", lambda: requests.get("http://localhost:18080/api/v2/monitor/health", timeout=10).json()["metadatabase"]["status"])
    probe("shop database", lambda: _shop_counts(s))
    probe("webhook receiver", lambda: requests.get(s.webhook_url, timeout=5).json()["status"])
    probe("ingestion-bot token in .env", lambda: "set" if s.om_jwt_token else (_ for _ in ()).throw(RuntimeError("run `just token`")))
    return results


def _shop_counts(s) -> str:
    dsn = f"host={s.shop_host} port={s.shop_port} dbname={s.shop_db} user={s.shop_reader_user} password={s.shop_reader_password}"
    with psycopg.connect(dsn) as c:
        n = {t: c.execute(f"select count(*) from raw.{t}").fetchone()[0] for t in ["customers", "products", "orders", "order_items"]}
    return ", ".join(f"{k}={v}" for k, v in n.items())


if __name__ == "__main__":
    ok = True
    for name, good, detail in check():
        ok &= good
        print(f"{'OK  ' if good else 'FAIL'} {name:30s} {detail}")
    raise SystemExit(0 if ok else 1)
