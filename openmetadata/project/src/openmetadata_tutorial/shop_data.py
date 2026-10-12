"""The running example: Brightcup, a small online coffee-bean shop.

`python -m openmetadata_tutorial.shop_data` regenerates the CSV seed files in
data/shop/ (deterministic, seed 42). The shopdb container loads them on its
first start (shopdb/init/*.sql). Chapters only read them through the loaders.

Planted defects (the data-quality chapter must find exactly these):
  raw.customers   12 rows with a NULL email
  raw.orders       3 duplicated order_id values (1,000 rows, 997 distinct ids)
                   5 rows with a negative total_amount
                   4 rows with the misspelled status 'shiped'
"""

import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from openmetadata_tutorial.config import project_root

SEED = 42
N_CUSTOMERS = 200
N_PRODUCTS = 30
N_ORDERS = 1000
FIRST_DAY = date(2026, 7, 1)
LAST_DAY = date(2026, 9, 30)  # 92 days of orders
STATUSES = ["placed", "shipped", "delivered", "cancelled", "returned"]
STATUS_WEIGHTS = [10, 20, 60, 6, 4]
COUNTRIES = ["DE", "FR", "NL", "PL", "UA", "ES", "IT", "SE"]
ORIGINS = ["Ethiopia", "Colombia", "Brazil", "Kenya", "Guatemala", "Vietnam"]
ROASTS = ["light", "medium", "dark"]

DEFECTS = {
    "customers_null_email": 12,
    "orders_duplicate_ids": 3,
    "orders_negative_amount": 5,
    "orders_bad_status": 4,
}

FIRST_NAMES = ["Anna", "Ben", "Chloe", "Dmytro", "Eva", "Felix", "Greta", "Hugo", "Iris", "Jonas",
               "Kasia", "Luca", "Mila", "Nils", "Olga", "Pablo", "Rosa", "Sven", "Tara", "Yuri"]
LAST_NAMES = ["Novak", "Schmidt", "Dubois", "Kowalski", "Rossi", "Garcia", "Jansen", "Lind",
              "Shevchenko", "Weber"]


def shop_dir(root: Path | None = None) -> Path:
    return (root or project_root()) / "data" / "shop"


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def generate(root: Path | None = None) -> dict[str, int]:
    """Write customers/products/orders/order_items CSVs; return row counts."""
    rnd = random.Random(SEED)
    out = shop_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    days = (LAST_DAY - FIRST_DAY).days + 1

    customers = []
    for cid in range(1, N_CUSTOMERS + 1):
        first, last = rnd.choice(FIRST_NAMES), rnd.choice(LAST_NAMES)
        email = f"{first}.{last}{cid}@example.com".lower()
        phone = f"+49 30 {rnd.randint(1000000, 9999999)}"
        signup = FIRST_DAY - timedelta(days=rnd.randint(0, 365))
        customers.append([cid, f"{first} {last}", email, phone, rnd.choice(COUNTRIES), signup.isoformat()])
    for row in rnd.sample(customers, DEFECTS["customers_null_email"]):
        row[2] = ""  # empty CSV field -> NULL in Postgres

    products = []
    for pid in range(1, N_PRODUCTS + 1):
        origin, roast = rnd.choice(ORIGINS), rnd.choice(ROASTS)
        price = round(rnd.uniform(8, 32), 2)
        products.append([pid, f"BC-{pid:03d}", f"{origin} {roast.title()} {pid}", roast, origin, f"{price:.2f}"])
    price_of = {p[0]: float(p[5]) for p in products}

    orders, items = [], []
    for oid in range(1, N_ORDERS + 1):
        day = FIRST_DAY + timedelta(days=rnd.randrange(days))
        ts = datetime(day.year, day.month, day.day, rnd.randint(7, 22), rnd.randint(0, 59), rnd.randint(0, 59))
        total = 0.0
        for pid in rnd.sample(range(1, N_PRODUCTS + 1), rnd.choice([1, 2, 2, 3, 3, 4])):
            qty = rnd.randint(1, 3)
            items.append([oid, pid, qty, f"{price_of[pid]:.2f}"])
            total += qty * price_of[pid]
        status = rnd.choices(STATUSES, STATUS_WEIGHTS)[0]
        orders.append([oid, rnd.randint(1, N_CUSTOMERS), ts.isoformat(sep=" "), status, f"{total:.2f}", "EUR"])

    # defects, each on distinct rows so the counts stay exact
    victims = rnd.sample(range(10, N_ORDERS), sum(DEFECTS[k] for k in DEFECTS if k.startswith("orders")))
    dup, neg, bad = victims[:3], victims[3:8], victims[8:12]
    for i in dup:
        orders[i][0] = orders[i - 1][0]  # reuse the previous order's id
    for i in neg:
        orders[i][4] = f"{-float(orders[i][4]):.2f}"
    for i in bad:
        orders[i][3] = "shiped"

    _write(out / "customers.csv", ["customer_id", "full_name", "email", "phone", "country", "signup_date"], customers)
    _write(out / "products.csv", ["product_id", "sku", "name", "roast", "origin", "price_eur"], products)
    _write(out / "orders.csv", ["order_id", "customer_id", "order_ts", "status", "total_amount", "currency"], orders)
    _write(out / "order_items.csv", ["order_id", "product_id", "quantity", "unit_price"], items)
    return {"customers": len(customers), "products": len(products), "orders": len(orders), "order_items": len(items)}


def load(table: str, root: Path | None = None) -> pd.DataFrame:
    """Load one seed table (customers, products, orders, order_items) as a DataFrame."""
    return pd.read_csv(shop_dir(root) / f"{table}.csv")


def load_all(root: Path | None = None) -> dict[str, pd.DataFrame]:
    return {t: load(t, root) for t in ["customers", "products", "orders", "order_items"]}


if __name__ == "__main__":
    for name, n in generate().items():
        print(f"{name:12s} {n:5d} rows")
