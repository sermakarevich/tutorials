"""Chapter 07 checks against the running stack (marker `stack`)."""

import pytest

from openmetadata_tutorial import ch07_quality as Q

pytestmark = pytest.mark.stack

EMAIL_FQN = "brightcup_pg.brightcup.raw.customers.email.customers_email_not_null"
UNIQUE_FQN = "brightcup_pg.brightcup.raw.customers.email.customers_email_unique"


def test_email_not_null_catches_planted_nulls():
    df = Q.results(Q.CUSTOMERS)
    row = df[df["test"] == "customers_email_not_null"].iloc[0]
    assert row["status"] == "Failed"
    assert "nullCount=12" in row["message"]


def test_orders_profile_shows_planted_defects():
    df = Q.profile(Q.ORDERS)
    order_id = df[df["column"] == "order_id"].iloc[0]
    assert order_id["distinctCount"] == 997.0
    assert order_id["uniqueCount"] == 994.0
    assert Q.table_summary(Q.ORDERS)["rowCount"] == 1000.0


def test_definitions_catalogue_has_25_entries():
    df = Q.definitions()
    assert len(df) == 25
    between = df[df["name"] == "columnValuesToBeBetween"].iloc[0]
    assert "NUMERIC" not in between["supportedDataTypes"]


def test_history_email_is_a_wall_of_identical_failures():
    h = Q.history(EMAIL_FQN)
    assert len(h) >= 2
    assert set(h["status"]) == {"Failed"}
    assert "failedRows" in h.columns
    assert h["failedRows"].isna().all()  # this definition reports via the message
    assert h["message"].nunique() == 1
    assert "nullCount=12" in h["message"].iloc[-1]


def test_history_unique_reports_zero_failed_rows():
    h = Q.history(UNIQUE_FQN)
    assert len(h) >= 2
    assert set(h["status"]) == {"Success"}
    assert (h["failedRows"] == 0).all()


def test_history_trend_summarizes_counts_and_recent():
    counts, recent = Q.history_trend(EMAIL_FQN)
    assert counts[counts["status"] == "Failed"]["runs"].iloc[0] == len(Q.history(EMAIL_FQN))
    assert len(recent) <= 5
    assert recent["timestamp"].is_monotonic_increasing


def test_current_incidents_show_email_assigned():
    cur = Q.current_incidents()
    assert set(cur["test"]) >= {"customers_email_not_null", "customers_country_in_set"}
    email = cur[cur["test"] == "customers_email_not_null"].iloc[0]
    assert email["status"] == "Assigned"


def test_set_incident_assigned_is_idempotent():
    r = Q.set_incident(EMAIL_FQN, "Assigned", assignee="admin")
    assert r["testCaseResolutionStatusType"] == "Assigned"
    cur = Q.current_incidents()
    email = cur[cur["test"] == "customers_email_not_null"].iloc[0]
    assert email["status"] == "Assigned"
    assert email["assignee"] == "admin"


def test_run_workflow_prints_a_success_tail():
    tail = Q.run_workflow()
    assert "Workflow Success %: 100.0" in tail


def test_yaml_params_come_from_the_file_not_memory():
    params = Q.yaml_case_params("ch07_customers_quality.yaml", "customers_country_in_set")
    assert params["forceUpdate"] is True
    assert params["params"]["matchEnum"] == "true"
    assert "DE" in params["params"]["allowedValues"]


def test_create_and_delete_test_case_via_api():
    created = Q.create_test_case(
        "ch07_test_probe",
        "<#E::table::brightcup_pg.brightcup.raw.products>",
        "tableRowCountToBeBetween",
        {"minValue": "0", "maxValue": "1000"},
    )
    try:
        found = Q.test_case("ch07_test_probe", Q.PRODUCTS)
        assert found["id"] == created["id"]
    finally:
        Q.delete_test_case(created["id"])
    with pytest.raises(KeyError):
        Q.test_case("ch07_test_probe", Q.PRODUCTS)


def test_suites_lists_basic_and_logical():
    df = Q.suites()
    assert set(df["basic"]) == {True, False}
    assert (df["suite"] == "Data Contract - daily_revenue-contract").any()
    assert (df["suite"].str.contains("raw.customers").any())


def test_deleted_throwaways_leave_no_traces():
    for fqn in (
        "brightcup_pg.brightcup.raw.customers.ch07_row_count_demo",
        "brightcup_pg.brightcup.raw.customers.email.ch07_email_sampled",
    ):
        traces = Q.deleted_case_traces(fqn)
        assert traces["history"].startswith("gone")
        assert traces["incident_rows"] == 0


def test_status_plot_svg_draws_one_dot_per_run():
    h = Q.history(EMAIL_FQN)
    svg = Q.status_plot_svg(EMAIL_FQN)
    assert svg.startswith("<svg")
    assert svg.count("<circle") == len(h)
    assert f"{len(h)} runs" in svg
