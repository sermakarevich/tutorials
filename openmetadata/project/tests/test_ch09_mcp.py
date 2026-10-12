"""Chapter 09 checks against the running stack (marker `stack`)."""

import pytest

from openmetadata_tutorial import client

pytestmark = pytest.mark.stack


def test_mcp_tools_list_contains_search_metadata():
    from openmetadata_tutorial.ch09_mcp import MCP

    mcp = MCP()
    tools = mcp.call("tools/list", {})
    names = [t["name"] for t in tools["tools"]]
    assert "search_metadata" in names
    assert "get_entity_lineage" in names


def test_contract_validates_success():
    table = client.get("/v1/tables/name/brightcup_pg.brightcup.analytics.daily_revenue")
    contracts = client.get("/v1/dataContracts?limit=100").get("data", [])
    contract = next(
        (c for c in contracts if c.get("entity", {}).get("id") == table["id"]), None)
    assert contract is not None
    full = client.get(f"/v1/dataContracts/{contract['id']}")
    assert len(full.get("schema", [])) == 3
    assert len(full.get("semantics", [])) == 2
    assert len(full.get("qualityExpectations", [])) == 1
    latest = client.get(f"/v1/dataContracts/{contract['id']}/results/latest")
    assert latest.get("contractExecutionStatus") == "Success"


def test_finance_editor_role_has_both_policies():
    role = client.get("/v1/roles/name/FinanceEditor?fields=policies")
    assert {p["name"] for p in role.get("policies", [])} >= {
        "FinanceEditRevenue", "NoPIIForConsumers"}


def test_alert_subscription_exists():
    sub = client.get("/v1/events/subscriptions/name/ch09_quality_to_webhook")
    assert sub["destinations"][0]["config"]["endpoint"] == "http://webhook:8000/om"


def test_mcp_lineage_counts_three_upstream_one_downstream():
    from openmetadata_tutorial.ch09_mcp import MCP, lineage_counts

    counts = lineage_counts(MCP())
    assert len(counts["upstream"]) == 3
    assert len(counts["downstream"]) == 1
    assert ("brightcup_pg.brightcup.analytics.fct_orders",
            "brightcup_pg.brightcup.analytics.daily_revenue") in counts["upstream"]


def test_mcp_search_finds_daily_revenue():
    from openmetadata_tutorial.ch09_mcp import MCP, search_revenue

    d = search_revenue(MCP())
    fqns = [h.get("fullyQualifiedName") for h in d.get("results", [])]
    assert "brightcup_pg.brightcup.analytics.daily_revenue" in fqns


def test_contract_upstream_failures_are_real():
    from openmetadata_tutorial.ch09_contract import upstream_failures

    rows = {(r["table"], r["test"]): r for r in upstream_failures()}
    assert ("orders", "orders_order_id_unique") in rows
    assert ("orders", "orders_no_negative_amounts") in rows
    assert ("orders", "orders_status_in_set") in rows
    assert all(r["definition"] for r in rows.values())
