"""Chapter 09: alerts. A failing test case notifies the webhook receiver.

Idempotent: the subscription is created once, then updated in place.
Run from project/: ``uv run python -m openmetadata_tutorial.ch09_alerts <step>``
steps: ensure | clear | wait | status
"""

import json
import sys
import time

import requests

from openmetadata_tutorial import client
from openmetadata_tutorial.config import settings

ALERT = "ch09_quality_to_webhook"
WEBHOOK_ENDPOINT = "http://webhook:8000/om"  # the server calls this address (inside Docker)


def get_or_none(path: str):
    try:
        return client.get(path)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


def ensure_alert() -> dict:
    """Create (or refresh) the failed-test-case -> webhook subscription.

    alertType Observability: Notification subscriptions cannot filter on
    testCase resources (only Observability/ActivityFeed/Custom can).
    """
    body = {
        "name": ALERT,
        "displayName": ALERT,
        "description": "Chapter 09 demo: failed test cases go to the local webhook receiver.",
        "alertType": "Observability",
        "resources": ["testCase"],
        "trigger": {"triggerType": "RealTime"},
        "destinations": [{
            "category": "External",
            "type": "Webhook",
            "config": {"endpoint": WEBHOOK_ENDPOINT},
        }],
        "input": {"filters": [], "actions": [{
            "name": "GetTestCaseStatusUpdates",
            "effect": "include",
            "prefixCondition": "OR",
            "arguments": [{"name": "testResultList", "input": ["Failed"]}],
        }]},
    }
    existing = get_or_none(f"/v1/events/subscriptions/name/{ALERT}")
    if existing is None:
        sub = client.api("POST", "/v1/events/subscriptions", json=body).json()
        print(f"alert {ALERT}: created ({sub['id']})")
    else:
        sub = client.api("PUT", "/v1/events/subscriptions", json=body).json()
        print(f"alert {ALERT}: updated ({sub['id']})")
    dest = sub["destinations"][0]
    print(f"  destination: {dest['type']} -> {dest['config'].get('endpoint')}")
    print(f"  action: {sub['filteringRules']['actions'][0]['condition']}")
    return sub


def filter_summary(sub: dict | None = None) -> str:
    """The match condition of our subscription, e.g. ``matchTestResult({'Failed'})``."""
    sub = sub if sub is not None else client.get(f"/v1/events/subscriptions/name/{ALERT}")
    return sub["filteringRules"]["actions"][0]["condition"]


def trim_event(event: dict) -> dict:
    """The trimmed view the chapter prints for one receiver event.

    Pure function (no I/O) so tests can check the exact numbers the prose
    relies on: the failing test case's FQN and its Failed status.

    The status hides in different places depending on the update: either a
    `{"name": "testCaseStatus", "newValue": "Failed"}` entry (plain string)
    or inside a `{"name": "testCaseResult", "newValue": {...}}` entry (dict).
    """
    body = event.get("body", event)
    status = None
    for field in (body.get("changeDescription", {}) or {}).get("fieldsUpdated", []) or []:
        new_value = field.get("newValue")
        if isinstance(new_value, dict) and new_value.get("testCaseStatus"):
            status = new_value["testCaseStatus"]
            break
        if field.get("name") == "testCaseStatus" and isinstance(new_value, str):
            status = status or new_value
    return {
        "path": event.get("path"),
        "eventType": body.get("eventType"),
        "entityType": body.get("entityType"),
        "entityFullyQualifiedName": body.get("entityFullyQualifiedName"),
        "testCaseStatus": status,
        "timestamp": body.get("timestamp"),
    }


def clear_events() -> None:
    s = settings()
    r = requests.delete(f"{s.webhook_url}/events", timeout=30)
    r.raise_for_status()
    print("receiver: cleared")


def wait_for_events(timeout: int = 60) -> list:
    """Poll the receiver until something arrives; print which path ran."""
    s = settings()
    deadline = time.time() + timeout
    while time.time() < deadline:
        events = requests.get(f"{s.webhook_url}/events", timeout=30).json()
        if events:
            print(f"receiver: live, got {len(events)} event(s)")
            return events
        time.sleep(5)
    print("receiver: live, got 0 events (nothing arrived in time)")
    return []


def show_event(events: list, match: str = "customers") -> None:
    """Print the trimmed view of our trigger event.

    Other chapters share this catalog and their failing tests can land in the
    receiver too, so this shows the first event for `match` (default: the
    customers suite this chapter re-ran) instead of blindly taking events[0].
    """
    if not events:
        return
    bodies = [(e.get("body", e) or {}).get("entityFullyQualifiedName", "") for e in events]
    pick = next((e for e, fqn in zip(events, bodies) if match in fqn), events[0])
    print(json.dumps(trim_event(pick), indent=1))


def delivery_status() -> None:
    rec = client.get(f"/v1/events/subscriptions/name/{ALERT}/eventsRecord")
    print(json.dumps({k: rec.get(k) for k in
                      ("totalEventsCount", "pendingEventsCount",
                       "successfulEventsCount", "failedEventsCount")}, indent=1))


def main(argv: list[str]) -> None:
    step = argv[1] if len(argv) > 1 else "ensure"
    if step == "ensure":
        ensure_alert()
    elif step == "clear":
        clear_events()
    elif step == "wait":
        show_event(wait_for_events())
    elif step == "status":
        delivery_status()
    else:
        raise SystemExit(f"unknown step {step!r}: ensure|clear|wait|status")


if __name__ == "__main__":
    main(sys.argv)
