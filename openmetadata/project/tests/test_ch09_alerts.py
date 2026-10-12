"""Chapter 09 alert checks against the running stack (marker `stack`).

Covers the helper numbers the prose relies on: the subscription filter
(matches Failed test results, delivers to the in-Docker webhook) and the
trimmed event parsing (failing test case FQN + Failed status).
"""

import pytest

from openmetadata_tutorial import ch09_alerts, client

pytestmark = pytest.mark.stack


def test_alert_filter_matches_failed_results_to_webhook():
    sub = client.get("/v1/events/subscriptions/name/ch09_quality_to_webhook")
    assert "Failed" in ch09_alerts.filter_summary(sub)
    assert sub["destinations"][0]["config"]["endpoint"] == "http://webhook:8000/om"


def test_trim_event_parses_failing_test_case():
    trimmed = ch09_alerts.trim_event({
        "path": "/om",
        "body": {
            "eventType": "entityUpdated",
            "entityType": "testCase",
            "entityFullyQualifiedName":
                "brightcup_pg.brightcup.raw.customers.country.customers_country_in_set",
            "changeDescription": {"fieldsUpdated": [
                {"name": "testCaseResult", "newValue": {
                    "testCaseStatus": "Failed",
                    "result": "Found countInSet=148."}}]},
            "timestamp": 1791804476617,
        },
    })
    assert trimmed["path"] == "/om"
    assert trimmed["eventType"] == "entityUpdated"
    assert trimmed["entityFullyQualifiedName"] == (
        "brightcup_pg.brightcup.raw.customers.country.customers_country_in_set")
    assert trimmed["testCaseStatus"] == "Failed"
    assert trimmed["timestamp"] == 1791804476617


def test_trim_event_parses_plain_status_string():
    trimmed = ch09_alerts.trim_event({
        "path": "/om",
        "body": {
            "eventType": "entityUpdated",
            "entityType": "testCase",
            "entityFullyQualifiedName":
                "brightcup_pg.brightcup.raw.products.ch07_products_row_count",
            "changeDescription": {"fieldsUpdated": [
                {"name": "testCaseStatus", "newValue": "Failed"}]},
            "timestamp": 1791806225037,
        },
    })
    assert trimmed["testCaseStatus"] == "Failed"
    assert trimmed["entityFullyQualifiedName"] == (
        "brightcup_pg.brightcup.raw.products.ch07_products_row_count")


def test_show_event_prefers_our_trigger():
    import io
    from contextlib import redirect_stdout

    other = {"path": "/om", "body": {
        "eventType": "entityUpdated", "entityType": "testCase",
        "entityFullyQualifiedName": "brightcup_pg.brightcup.raw.products.ch07_products_row_count",
        "changeDescription": {"fieldsUpdated": [
            {"name": "testCaseStatus", "newValue": "Failed"}]},
        "timestamp": 1}}
    ours = {"path": "/om", "body": {
        "eventType": "entityUpdated", "entityType": "testCase",
        "entityFullyQualifiedName":
            "brightcup_pg.brightcup.raw.customers.country.customers_country_in_set",
        "changeDescription": {"fieldsUpdated": [
            {"name": "testCaseResult", "newValue": {"testCaseStatus": "Failed"}}]},
        "timestamp": 2}}
    buf = io.StringIO()
    with redirect_stdout(buf):
        ch09_alerts.show_event([other, ours])
    assert "customers_country_in_set" in buf.getvalue()


def test_alert_delivery_has_no_failures():
    # failedEventsCount is the stable property on this shared live catalog
    # (pendingEventsCount fluctuates as parallel chapters keep emitting).
    rec = client.get(
        "/v1/events/subscriptions/name/ch09_quality_to_webhook/eventsRecord")
    assert rec.get("failedEventsCount") == 0
    assert rec.get("successfulEventsCount", 0) > 0
