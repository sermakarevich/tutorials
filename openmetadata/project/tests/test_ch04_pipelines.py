"""Chapter 04 checks against the running stack (marker `stack`)."""

import pytest

from openmetadata_tutorial import ch04_pipelines as P
from openmetadata_tutorial import client

pytestmark = pytest.mark.stack


def test_sandbox_pipeline_exists_and_is_idempotent():
    first = P.ensure_pipeline()
    second = P.ensure_pipeline()
    assert first["id"] == second["id"]
    assert second["how"] == "already there"
    assert first["fqn"] == "brightcup_sandbox.ch04_sandbox_metadata"


def test_cli_runs_leave_no_pipeline_but_scheduled_one_exists():
    assert P.pipeline_count("brightcup_sandbox") >= 1


def test_promotions_gained_channel_column():
    t = client.get("/v1/tables/name/brightcup_sandbox.brightcup.sandbox.promotions")
    assert {c["name"] for c in t["columns"]} >= {"promo_code", "discount_pct", "valid_until", "channel"}
    assert t["version"] >= 0.2


def test_dropped_table_is_soft_deleted():
    t = client.get("/v1/tables/name/brightcup_sandbox.brightcup.sandbox.old_coupons", include="all")
    assert t["deleted"] is True


def test_usage_wrote_summaries():
    t = client.get("/v1/tables/name/brightcup_pg.brightcup.analytics.customer_ltv", fields="usageSummary")
    assert t["usageSummary"]["dailyStats"]["count"] >= 1
