"""The running example's data matches what plan.md promises (offline)."""

from openmetadata_tutorial import shop_data as S


def test_row_counts():
    d = S.load_all()
    assert len(d["customers"]) == 200
    assert len(d["products"]) == 30
    assert len(d["orders"]) == 1000
    assert len(d["order_items"]) == 2550


def test_planted_defects_are_exact():
    d = S.load_all()
    o, c = d["orders"], d["customers"]
    assert c["email"].isna().sum() == S.DEFECTS["customers_null_email"]
    assert o["order_id"].nunique() == 1000 - S.DEFECTS["orders_duplicate_ids"]
    assert (o["total_amount"] < 0).sum() == S.DEFECTS["orders_negative_amount"]
    assert (o["status"] == "shiped").sum() == S.DEFECTS["orders_bad_status"]


def test_generation_is_deterministic(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    S.generate(tmp_path)
    for t in ["customers", "products", "orders", "order_items"]:
        assert (tmp_path / "data/shop" / f"{t}.csv").read_text() == (S.shop_dir() / f"{t}.csv").read_text()
