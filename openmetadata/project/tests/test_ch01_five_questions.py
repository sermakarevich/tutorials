"""Tests for chapter 01 helpers (need the running, bootstrapped stack)."""

import pytest

from openmetadata_tutorial.ch01_five_questions import (
    CUSTOMERS,
    DAILY_REVENUE,
    ORDERS,
    describe,
    downstream,
    find,
    governance,
    quality,
)

pytestmark = pytest.mark.stack


def test_find_revenue_includes_daily_revenue():
    rows = find("revenue")
    assert any(fqn == DAILY_REVENUE for fqn, _ in rows)


def test_describe_daily_revenue_has_three_columns():
    assert [c for c, _, _ in describe(DAILY_REVENUE)] == ["order_date", "orders", "revenue"]


def test_downstream_orders_includes_fct_orders():
    edges = downstream(ORDERS)
    assert any("fct_orders" in to for _, to, _ in edges)


def test_quality_orders_is_one_success_three_failed():
    rows = quality(ORDERS)
    assert len(rows) == 4
    by_status = sorted(s for _, s, _ in rows)
    assert by_status == ["Failed", "Failed", "Failed", "Success"]


def test_governance_customers_flags_pii():
    cols, owners = governance(CUSTOMERS)
    tags = dict(cols)
    assert tags["full_name"] == ["PII.Sensitive"]
    assert tags["email"] == ["PII.Sensitive"]
    # Owners are a human decision: chapter 08 sets team `Data Engineering`
    # here, so on the shared stack this is non-empty. Only check the shape.
    assert isinstance(owners, list) and all(isinstance(o, str) for o in owners)
    # `signup_date` carries the recognizer's false positive (`PII.NonSensitive`)
    # on a freshly bootstrapped catalog; chapter 08 removes it. Accept both,
    # so the test passes regardless of which chapter ran last.
    assert tags["signup_date"] in ([], ["PII.NonSensitive"])
