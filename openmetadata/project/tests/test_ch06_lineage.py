"""Chapter 06 checks against the running stack (marker `stack`)."""

import pandas as pd
import pytest

from openmetadata_tutorial import ch06_lineage as L

pytestmark = pytest.mark.stack


def test_downstream_of_orders_includes_daily_revenue():
    df = L.edges(L.ORDERS, up=1, down=3)
    assert not df.empty
    assert (df["to"] == L.DAILY_REVENUE).any()
    assert set(df["source"]) <= {"ViewLineage", "QueryLineage", "Manual"}


def test_amount_column_feeds_revenue():
    path = L.column_path(L.AMOUNT_COLUMN)
    assert not path.empty
    assert (path["to_column"] == f"{L.DAILY_REVENUE}.revenue").any()


def test_mermaid_mentions_every_node():
    text = L.to_mermaid(L.brightcup_graph())
    assert text.startswith("flowchart LR")
    for short in ("orders", "fct_orders", "daily_revenue", "customer_ltv", "customers"):
        assert short in text


def test_column_impact_reaches_both_money_metrics():
    imp = L.impact(L.ORDERS, column=L.AMOUNT_COLUMN)
    assert not imp.empty
    assert (imp["via_column"] == "revenue").any()  # daily_revenue.revenue
    assert (imp["via_column"] == "lifetime_value").any()  # customer_ltv.lifetime_value
    assert (imp["fqn"] == L.DAILY_REVENUE).any()
    assert (imp["fqn"] == L.CUSTOMER_LTV).any()


def test_table_impact_reaches_dashboard():
    L.ensure_dashboard()
    L.add_edge(
        L.DAILY_REVENUE, "table",
        "brightcup_metabase.finance_overview", "dashboard",
        "Finance overview reads daily_revenue nightly",
    )
    imp = L.impact(L.ORDERS)
    assert not imp.empty
    dash = imp[imp["kind"] == "dashboard"]
    assert (dash["fqn"] == "brightcup_metabase.finance_overview").any()
    assert int(dash["level"].max()) == 3


def test_quality_status_names_the_failing_test():
    qs = L.quality_status(L.ORDERS)
    assert not qs.empty
    row = qs[qs["test"] == "orders_no_negative_amounts"]
    assert not row.empty
    assert row["status"].iloc[0] == "Failed"


def test_negative_amount_count_matches_planted_defect():
    assert L.negative_amount_count()["rows"] == 5


def test_nightly_job_sql_is_the_customer_ltv_ctas():
    sql = L.nightly_job_sql()
    assert "CREATE TABLE analytics.customer_ltv AS" in sql
    assert "lifetime_value" in sql


def test_queries_for_finds_the_logged_ctas():
    qs = L.queries_for(L.CUSTOMER_LTV)
    assert not qs.empty
    ctas = qs[qs["query"].str.contains("CREATE TABLE analytics.customer_ltv", na=False)]
    assert not ctas.empty
    logged = ctas["query"].iloc[0]
    assert "coalesce(sum(f.total_amount), $1)" in logged  # pg_stat_statements normalises 0 to $1
    assert "raw.customers" in logged and "fct_orders" in logged


def test_exclude_hides_the_late_parser_test_view():
    df = L.edges(L.ORDERS, up=1, down=3, exclude=[L.DYNAMIC_VIEW])
    assert not (df == L.DYNAMIC_VIEW).any().any()
    assert (df["to"] == L.DAILY_REVENUE).any()
    path = L.column_path(L.AMOUNT_COLUMN, exclude=[L.DYNAMIC_VIEW])
    assert not (path == L.DYNAMIC_VIEW + ".amount").any().any()
    assert (path["to_column"] == f"{L.DAILY_REVENUE}.revenue").any()
    imp = L.impact(L.ORDERS, column=L.AMOUNT_COLUMN, exclude=[L.DYNAMIC_VIEW])
    assert not (imp["fqn"] == L.DYNAMIC_VIEW).any()


def test_walks_hide_the_late_view_by_default():
    df = L.edges(L.ORDERS, up=1, down=3)
    assert not (df == L.DYNAMIC_VIEW).any().any()
    assert (df["to"] == L.DAILY_REVENUE).any()
    path = L.column_path(L.AMOUNT_COLUMN)
    assert not (path == L.DYNAMIC_VIEW + ".amount").any().any()
    assert (path["to_column"] == f"{L.DAILY_REVENUE}.revenue").any()


def test_limits_section_opts_back_in():
    df = L.edges(L.DYNAMIC_VIEW, up=3, down=0, exclude=[])
    assert len(df) == 2
    assert set(df["from"]) == {L.ORDERS, "brightcup_pg.brightcup.raw.order_items"}
    cols = L.column_edges(L.DYNAMIC_VIEW, up=3, down=0, exclude=[])
    assert len(cols) == 7
