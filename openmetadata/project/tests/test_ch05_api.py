"""Chapter 05 checks against the running stack (marker `stack`)."""

import pytest

from openmetadata_tutorial import ch05_api as A

pytestmark = pytest.mark.stack

SEED = {
    "brightcup_pg.brightcup.raw.orders",
    "brightcup_pg.brightcup.raw.order_items",
    "brightcup_pg.brightcup.raw.customers",
    "brightcup_pg.brightcup.raw.products",
    "brightcup_pg.brightcup.analytics.fct_orders",
    "brightcup_pg.brightcup.analytics.daily_revenue",
    "brightcup_pg.brightcup.analytics.customer_ltv",
}


def test_list_all_covers_seed_tables():
    fqns = {e["fullyQualifiedName"] for e in A.list_all("/v1/tables", database="brightcup_pg.brightcup")}
    assert len(fqns) >= 7
    assert SEED <= fqns


def test_column_index_finds_quantity():
    table = A.get_table(fields="columns")
    assert A.column_index(table, "quantity") == 2


def test_versions_frame_is_an_audit_log():
    df = A.versions_frame(A.get_table()["id"])
    assert list(df.columns) == ["version", "updatedBy", "updatedAt", "previousVersion", "changed"]
    assert len(df) >= 2
    assert (df["updatedBy"] == "ingestion-bot").all()
    row03 = df[df["version"] == 0.3].iloc[0]
    assert row03["previousVersion"] == 0.2
    assert "added:tags" in row03["changed"] and "updated:description" in row03["changed"]


def test_change_detail_prints_previous_version():
    t = A.get_table()
    d = A.change_detail(t)
    assert d["previousVersion"] == 0.2
    assert "added:tags" in d["summary"] and "updated:description" in d["summary"]


def test_set_description_is_idempotent():
    eid = A.get_table()["id"]
    before = A.get_table()["version"]
    t = A.set_description(eid, A.TABLE_DESCRIPTION)
    assert t.get("description") == A.TABLE_DESCRIPTION
    assert t.get("version") == before
    again = A.set_description(eid, A.TABLE_DESCRIPTION)
    assert again.get("version") == before  # no-op patch mints no new version


def test_set_column_description_writes_quantity():
    eid = A.get_table()["id"]
    t = A.set_column_description(eid, "quantity", A.QUANTITY_DESCRIPTION)
    assert t["columns"][A.column_index(t, "quantity")].get("description") == A.QUANTITY_DESCRIPTION


def test_ensure_tier_tag_does_not_duplicate():
    eid = A.get_table()["id"]
    t = A.ensure_tier_tag(eid)
    full = A.get_table(fields="tags")
    tiers = [g["tagFQN"] for g in full.get("tags", [])]
    assert tiers.count("Tier.Tier3") == 1


def test_patch_noop_keeps_version():
    eid = A.get_table()["id"]
    before = A.get_table()["version"]
    t = A.patch(f"/v1/tables/{eid}", [{"op": "add", "path": "/description", "value": A.TABLE_DESCRIPTION}])
    assert t.get("version") == before


def test_ensure_scratch_delete_cycle():
    scratch = A.ensure_scratch()
    eid = scratch["id"]
    assert A.get_status(eid)["status"] == 200
    from openmetadata_tutorial import client as _client

    assert _client.api("DELETE", f"/v1/tables/{eid}").status_code == 200
    assert A.get_status(eid, include="deleted")["deleted"] is True
    assert _client.api("PUT", "/v1/tables/restore", json={"id": eid}).status_code == 200
    assert A.get_status(eid)["status"] == 200
    assert _client.api("DELETE", f"/v1/tables/{eid}?hardDelete=true&recursive=true").status_code == 200
    assert A.get_status(eid, include="all")["status"] == 404


def test_snapshot_column_shows_nested_edit_without_own_entry():
    eid = A.get_table()["id"]
    snap02 = A.snapshot_column(eid, "0.2", "quantity")
    assert snap02["description"] == A.QUANTITY_DESCRIPTION
    assert snap02["summary"] == "added:tableConstraints"  # 0.2 lists only the FK constraint
    assert snap02["previousVersion"] == 0.1


def test_payload_size_grows_with_fields():
    plain = A.get_table()
    full = A.get_table(fields="columns,owners,tags")
    assert A.payload_size(full) > A.payload_size(plain) > 0


def test_change_summary_formats_added_updated_deleted():
    entity = {
        "changeDescription": {
            "fieldsAdded": [{"name": "tags"}],
            "fieldsUpdated": [{"name": "description"}],
            "fieldsDeleted": [],
        }
    }
    assert A.change_summary(entity) == "added:tags; updated:description"
    assert A.change_summary({}) == ""


def test_search_frame_revenue_finds_daily_revenue():
    hits = A.search_frame("revenue", index="table_search_index")
    assert list(hits.columns) == ["entity", "fqn", "kind", "description"]
    assert hits.attrs["total"] >= 1
    assert "brightcup_pg.brightcup.analytics.daily_revenue" in set(hits["fqn"])


def test_search_frame_all_and_from_paging_partition_hits():
    first = A.search_frame("revenue", index="all", size=5, frm=0)
    total = first.attrs["total"]
    assert total > 5  # more hits than one page: paging is needed
    rest = A.search_frame("revenue", index="all", size=total, frm=5)
    assert len(rest) == total - 5
    assert not set(first["fqn"]) & set(rest["fqn"])
    whole = A.search_frame("revenue", index="all", size=total)
    assert len(whole) == total


def test_probe_error_bad_fields_is_400():
    e = A.probe_error("bad-fields")
    assert e["status"] == 400
    assert "BOGUS_FIELD" in e["message"]


def test_sdk_release_matches_server():
    rel = A.sdk_release()
    assert rel["server"] == "2.0.5"
    assert rel["pkg"].startswith(rel["server"])
