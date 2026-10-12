"""Chapter 09 contract helpers that need no running stack (no `stack` marker).

Covers the numbers the prose relies on: the upstream-failure rows (filter +
sort order) and the per-section pass counts printed by `cmd_validate`.
"""

import yaml

from openmetadata_tutorial import ch09_contract


def _canned_test_cases():
    return {"data": [
        {"name": "orders_status_in_set",
         "fullyQualifiedName": "brightcup_pg.brightcup.raw.orders.status.orders_status_in_set",
         "testDefinition": {"name": "columnValuesToBeInSet"},
         "testCaseResult": {"testCaseStatus": "Failed", "result": "Found countInSet=996."}},
        {"name": "orders_order_id_unique",
         "fullyQualifiedName": "brightcup_pg.brightcup.raw.orders.order_id.orders_order_id_unique",
         "testDefinition": {"name": "columnValuesToBeUnique"},
         "testCaseResult": {"testCaseStatus": "Failed", "result": "Found valuesCount=1000."}},
        {"name": "daily_revenue_has_rows",
         "fullyQualifiedName": "brightcup_pg.brightcup.analytics.daily_revenue.daily_revenue_has_rows",
         "testDefinition": {"name": "tableRowCountToBeBetween"},
         "testCaseResult": {"testCaseStatus": "Success", "result": "ok"}},
        {"name": "orders_row_count_between",
         "fullyQualifiedName": "brightcup_pg.brightcup.raw.orders.orders_row_count_between",
         "testDefinition": {"name": "tableRowCountToBeBetween"},
         "testCaseResult": {"testCaseStatus": "Success", "result": "ok"}},
    ]}


def test_upstream_failures_keep_only_failed_upstream_sorted(monkeypatch):
    monkeypatch.setattr(ch09_contract.client, "get", lambda *a, **k: _canned_test_cases())
    rows = ch09_contract.upstream_failures()
    assert [(r["table"], r["test"]) for r in rows] == [
        ("orders", "orders_order_id_unique"),
        ("orders", "orders_status_in_set"),
    ]
    assert rows[0]["definition"] == "columnValuesToBeUnique"
    assert "valuesCount=1000" in rows[0]["message"]


def test_upstream_failures_empty_when_nothing_failed(monkeypatch):
    payload = {"data": [dict(t, testCaseResult={"testCaseStatus": "Success"}) for t in _canned_test_cases()["data"]]}
    monkeypatch.setattr(ch09_contract.client, "get", lambda *a, **k: payload)
    assert ch09_contract.upstream_failures() == []


def test_validation_summary_counts_success():
    summary = ch09_contract.validation_summary({
        "contractExecutionStatus": "Success",
        "schemaValidation": {"passed": 3, "total": 3},
        "semanticsValidation": {"passed": 2, "total": 2},
        "qualityValidation": {"passed": 1, "failed": 0, "total": 1, "qualityScore": 100.0},
    })
    assert summary["status"] == "Success"
    assert summary["schema"] == (3, 3)
    assert summary["semantics"] == (2, 2)
    assert summary["quality"] == {"passed": 1, "failed": 0, "total": 1, "qualityScore": 100.0}


def test_validation_summary_running_has_no_quality_yet():
    summary = ch09_contract.validation_summary({"contractExecutionStatus": "Running"})
    assert summary["status"] == "Running"
    assert summary["quality"] is None


def test_contract_yaml_is_the_document_sent():
    doc = yaml.safe_load(ch09_contract.CONTRACT_YAML)
    assert doc["kind"] == "DataContract"
    assert doc["name"] == "daily_revenue-contract"
    props = doc["schema"][0]["properties"]
    assert [c["name"] for c in props] == ["order_date", "orders", "revenue"]
    assert len(doc["schema"][0]["quality"]) == 1
