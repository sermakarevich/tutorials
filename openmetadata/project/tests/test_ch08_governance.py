"""Chapter 08 checks against the running stack (marker `stack`)."""

import pytest

from openmetadata_tutorial import ch08_governance as G
from openmetadata_tutorial import client

pytestmark = pytest.mark.stack


def test_daily_revenue_owner_is_finance():
    assert "Finance" in G.owners_of(G.DAILY_REVENUE)


def test_daily_revenue_tier_certification_domain():
    assert G.tier_of(G.DAILY_REVENUE) == "Tier.Tier1"
    t = client.get(f"/v1/tables/name/{G.DAILY_REVENUE}", fields="certification,domains")
    assert t["certification"]["tagLabel"]["tagFQN"] == "Certification.Gold"
    assert [d["name"] for d in t.get("domains", [])] == ["Sales"]


def test_revenue_term_exists_with_synonyms():
    term = client.get("/v1/glossaryTerms/name/Brightcup.Revenue")
    assert term["description"].startswith("Sum of total_amount")
    assert set(term.get("synonyms", [])) >= {"sales", "turnover"}


def test_false_positive_removed_and_email_confirmed():
    # The classify workflow re-adds Generated tags on every run, so the
    # correction is re-applied here first: that is the standing procedure,
    # not a one-off (see chapter 08, section 3).
    G.remove_tag(G.CUSTOMERS, "PII.NonSensitive", column="signup_date")
    G.confirm_tag(G.CUSTOMERS, "PII.Sensitive", column="email")
    assert G.column_tags(G.CUSTOMERS, "signup_date") == []
    (email_tag,) = G.column_tags(G.CUSTOMERS, "email")
    assert (email_tag["tagFQN"], email_tag["labelType"], email_tag["state"]) == (
        "PII.Sensitive", "Manual", "Confirmed")


def test_report_covers_all_assets():
    df = G.report()
    assert list(df["fqn"]) == G.ALL_ASSETS
    row = df.set_index("fqn").loc[G.DAILY_REVENUE]
    assert row["owners"] == "Finance"
    assert row["domain"] == "Sales"


def test_report_empty_cells_are_the_backlog():
    # The prose names these gaps explicitly: products has no owner and no
    # domain; fct_orders and customer_ltv have no tier yet.
    df = G.report().set_index("fqn")
    assert df.loc[f"{G.RAW}.products", "owners"] == ""
    assert df.loc[f"{G.RAW}.products", "domain"] == ""
    assert df.loc[f"{G.ANALYTICS}.fct_orders", "tier"] == ""
    assert df.loc[f"{G.ANALYTICS}.customer_ltv", "tier"] == ""


def test_report_pii_and_product_columns():
    # The prose relies on these: customers carries the three PII columns
    # (email human-confirmed), daily_revenue has no PII but is published in
    # the product with its glossary term; customer_ltv links Lifetime value.
    df = G.report().set_index("fqn")
    pii = df.loc[G.CUSTOMERS, "PII columns"]
    assert "full_name" in pii and "email" in pii and "phone" in pii
    assert "Manual" in pii  # email was confirmed by a human (section 3)
    assert df.loc[G.DAILY_REVENUE, "PII columns"] == ""
    assert df.loc[G.DAILY_REVENUE, "glossary terms"] == "revenue←Revenue"
    assert "Revenue Reporting" in df.loc[G.DAILY_REVENUE, "data products"]
    assert "lifetime_value←Lifetime value" in df.loc[
        f"{G.ANALYTICS}.customer_ltv", "glossary terms"]


def test_governed_screenshot_exists():
    # The artifact cell 43 points at: captured after the notebook ran, with
    # the Revenue glossary pill scrolled into view (see ch08_shot).
    import struct
    from pathlib import Path

    from openmetadata_tutorial.config import project_root

    png = project_root().parent / "assets" / "08_daily_revenue_governed.png"
    assert png.stat().st_size > 0
    with open(png, "rb") as f:
        head = f.read(33)
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", head[16:24])
    assert (w, h) == (1440, 900)
