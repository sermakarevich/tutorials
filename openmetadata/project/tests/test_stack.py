"""Smoke tests against the running stack (`just up`, `just token`, `just ingest metadata`)."""

import pytest

from openmetadata_tutorial.client import get

pytestmark = pytest.mark.stack


def test_server_version():
    assert get("/v1/system/version")["version"].startswith("2.0.5")


def test_orders_table_is_cataloged():
    t = get("/v1/tables/name/brightcup_pg.brightcup.raw.orders", fields="columns")
    assert [c["name"] for c in t["columns"]] == ["order_id", "customer_id", "order_ts", "status", "total_amount", "currency"]


def test_sdk_reads_the_orders_table():
    from metadata.generated.schema.entity.data.table import Table

    from openmetadata_tutorial.client import sdk

    t = sdk().get_by_name(entity=Table, fqn="brightcup_pg.brightcup.raw.orders")
    assert t is not None and t.name.root == "orders"
