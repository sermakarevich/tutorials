"""Chapter 10 checks: helpers behind the wrap-up inventory.

Offline tests use canned API responses (no stack needed); the live test
(marker `stack`) pins the numbers the chapter prose relies on.
"""

import pytest

from openmetadata_tutorial import ch10_inventory as I


def _patch_get(monkeypatch, payload):
    monkeypatch.setattr(I, "get", lambda path, **params: payload)


def test_tables_per_service_groups_by_service_prefix(monkeypatch):
    _patch_get(monkeypatch, {"data": [
        {"fullyQualifiedName": "brightcup_pg.brightcup.raw.orders"},
        {"fullyQualifiedName": "brightcup_pg.brightcup.raw.customers"},
        {"fullyQualifiedName": "brightcup_sandbox.sandbox.orders_fixed"},
    ]})
    # Offline: drop the stack marker's effect by calling the helper directly.
    out = I.tables_per_service()
    assert sorted(out) == ["brightcup_pg", "brightcup_sandbox"]
    assert sorted(out["brightcup_pg"]) == [
        "brightcup_pg.brightcup.raw.customers",
        "brightcup_pg.brightcup.raw.orders",
    ]
    assert out["brightcup_sandbox"] == ["brightcup_sandbox.sandbox.orders_fixed"]


def test_summary_parses_status_and_table(monkeypatch):
    _patch_get(monkeypatch, {"data": [
        {"name": "orders_status_in_set",
         "testCaseResult": {"testCaseStatus": "Failed"},
         "entityLink": "<#E::table::brightcup_pg.brightcup.raw.orders::columns::status>"},
        {"name": "orders_row_count_between",
         "testCaseResult": {"testCaseStatus": "Success"},
         "entityLink": "<#E::table::brightcup_pg.brightcup.raw.orders>"},
        {"name": "no_result_case",
         "entityLink": "<#E::table::brightcup_pg.brightcup.raw.products>"},
    ]})
    out = I.test_summary()
    assert len(out) == 3
    by_name = {name: (status, table) for name, status, table in out}
    # Column-level links parse to the column name; table-level to the FQN.
    assert by_name["orders_status_in_set"] == ("Failed", "status")
    assert by_name["orders_row_count_between"] == (
        "Success", "brightcup_pg.brightcup.raw.orders")
    # A case with no result yet reports exactly that (the prose relies on it).
    assert by_name["no_result_case"][0] == "No result yet"
    # The failed-test count the chapter prints is derived from this list.
    assert sum(1 for _, s, _ in out if s == "Failed") == 1


def test_lineage_downstream_names_edges(monkeypatch):
    _patch_get(monkeypatch, {
        "entity": {"id": "e0",
                   "fullyQualifiedName": "brightcup_pg.brightcup.raw.orders"},
        "nodes": [{"id": "n1", "fullyQualifiedName":
                   "brightcup_pg.brightcup.analytics.fct_orders"}],
        "downstreamEdges": [
            {"fromEntity": "e0", "toEntity": "n1",
             "lineageDetails": {"source": "ViewLineage"}},
            {"fromEntity": "n1", "toEntity": "missing"},
        ],
    })
    out = I.lineage_downstream()
    assert out[0] == ("brightcup_pg.brightcup.raw.orders",
                      "brightcup_pg.brightcup.analytics.fct_orders",
                      "ViewLineage")
    # Unknown nodes and missing details degrade to "?", never crash.
    assert out[1][1] == "?"
    assert out[1][2] == "?"


def test_pii_columns_needs_tags_field_and_parses_pii(monkeypatch):
    seen = {}

    def fake_get(path, **params):
        seen.update(params)
        return {"columns": [
            {"name": "email", "tags": [{"tagFQN": "PII.Sensitive"}]},
            {"name": "signup_date", "tags": []},
            {"name": "note", "tags": [{"tagFQN": "Tier.Tier1"}]},
        ]}

    monkeypatch.setattr(I, "get", fake_get)
    out = I.pii_columns(["brightcup_pg.brightcup.raw.customers"])
    # Column tags are only returned when "tags" is requested alongside
    # "columns" (observed against the live server); the helper must ask.
    assert "tags" in seen.get("fields", "")
    assert out == [("brightcup_pg.brightcup.raw.customers", "email",
                    "PII.Sensitive")]


@pytest.mark.stack
def test_live_inventory_matches_chapter_prose():
    tables = I.tables_per_service()
    assert sum(len(v) for v in tables.values()) == 9
    assert tables["brightcup_pg"] and len(tables["brightcup_pg"]) == 8
    assert tables["brightcup_sandbox"] == [
        "brightcup_sandbox.brightcup.sandbox.promotions"]
    assert len(I.lineage_downstream()) == 5
    tests = I.test_summary()
    assert len(tests) == 8
    assert sum(1 for _, s, _ in tests if s == "Failed") == 5
    assert {n for n, _, _ in tests} >= {
        "customers_country_in_set", "customers_email_not_null",
        "customers_email_unique", "daily_revenue_has_rows",
        "orders_no_negative_amounts", "orders_order_id_unique",
        "orders_row_count_between", "orders_status_in_set"}
    pii = I.pii_columns()
    assert len(pii) == 5
    assert {(c, t) for _, c, t in pii} == {
        ("full_name", "PII.Sensitive"), ("email", "PII.Sensitive"),
        ("phone", "PII.NonSensitive"), ("origin", "PII.NonSensitive"),
        ("order_ts", "PII.NonSensitive")}
    assert sorted(I.glossary_terms()) == [
        "Customer", "Lifetime value", "Order", "Revenue"]
    assert len(I.alert_subscriptions()) == 3
    assert len(I.contracts()) == 1
    assert len(I.installed_apps()) == 7
