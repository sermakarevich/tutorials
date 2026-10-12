"""Chapter 01: the five jobs of OpenMetadata, each as one question about Brightcup.

One function per job, each a thin wrapper over a single read-only API call
(`client.get` only). Run from project/ as, e.g.::

    uv run python -m openmetadata_tutorial.ch01_five_questions find revenue
    uv run python -m openmetadata_tutorial.ch01_five_questions describe
    uv run python -m openmetadata_tutorial.ch01_five_questions downstream
    uv run python -m openmetadata_tutorial.ch01_five_questions quality
    uv run python -m openmetadata_tutorial.ch01_five_questions governance
"""

import sys

from openmetadata_tutorial.client import get

DAILY_REVENUE = "brightcup_pg.brightcup.analytics.daily_revenue"
ORDERS = "brightcup_pg.brightcup.raw.orders"
CUSTOMERS = "brightcup_pg.brightcup.raw.customers"

#: The shop catalog this chapter was bootstrapped with: the database service
#: `brightcup_pg`. Later chapters add demo assets under their own names
#: (chapter 06's `analytics.ch06_dynamic` view, its stand-in dashboard
#: service); the two search/lineage helpers below skip those. Later chapters
#: also enrich these same shop assets in place — chapter 08 sets owners and
#: corrects tags, chapter 03's probe demo briefly rewords a description —
#: and that enrichment intentionally stays visible: on this shared stack the
#: helpers report the live catalog, never a frozen bootstrap copy.
SHOP_PREFIX = "brightcup_pg.brightcup."
LATER_DEMO_MARKERS = ("ch06_dynamic", "brightcup_metabase")


def _is_shop_asset(fqn: str) -> bool:
    return fqn.startswith(SHOP_PREFIX) and not any(m in fqn for m in LATER_DEMO_MARKERS)


def find(q: str) -> list[tuple[str, str]]:
    """Search the catalog; return [(FQN, description)] in ranking order.

    Only the bootstrapped shop assets (see SHOP_PREFIX) are returned.
    """
    r = get("/v1/search/query", q=q, index="table_search_index")
    return [
        (h["_source"].get("fullyQualifiedName", ""), h["_source"].get("description") or "")
        for h in r["hits"]["hits"]
        if _is_shop_asset(h["_source"].get("fullyQualifiedName", ""))
    ]


def describe(fqn: str) -> list[tuple[str, str, str]]:
    """Return [(column, type, description)] for one table or view."""
    t = get(f"/v1/tables/name/{fqn}", fields="columns")
    return [(c["name"], c.get("dataType", "?"), c.get("description") or "") for c in t["columns"]]


def downstream(fqn: str) -> list[tuple[str, str, str]]:
    """Return [(from FQN, to FQN, lineage source)] for every edge downstream of `fqn`.

    Only edges between bootstrapped shop assets are returned (see SHOP_PREFIX).
    """
    lin = get(f"/v1/lineage/table/name/{fqn}", upstreamDepth=0, downstreamDepth=3)
    names = {n["id"]: n.get("fullyQualifiedName", n.get("name", "?")) for n in lin.get("nodes", [])}
    names[lin["entity"]["id"]] = lin["entity"]["fullyQualifiedName"]
    out = []
    for e in lin.get("downstreamEdges", []):
        details = e.get("lineageDetails") or {}
        frm, to = names.get(e["fromEntity"], "?"), names.get(e["toEntity"], "?")
        if not (_is_shop_asset(frm) and _is_shop_asset(to)):
            continue
        out.append((frm, to, details.get("source", "?")))
    return out


def quality(fqn: str) -> list[tuple[str, str, str]]:
    """Return [(test name, status, result message)] for the test cases on one table."""
    link = f"<#E::table::{fqn}>"
    r = get("/v1/dataQuality/testCases", entityLink=link, includeAllTests="true", fields="testCaseResult")
    out = []
    for tc in r.get("data", []):
        res = tc.get("testCaseResult") or {}
        out.append((tc.get("name", "?"), res.get("testCaseStatus", "?"), res.get("result") or ""))
    return out


def governance(fqn: str) -> tuple[list[tuple[str, list[str]]], list[str]]:
    """Return ([(column, [tag FQNs])], [owner names]) for one table.

    Owners and tags are live state: on the shared stack they include later
    chapters' enrichment (chapter 08 sets owners and corrects auto-tags)."""
    t = get(f"/v1/tables/name/{fqn}", fields="columns,tags,owners")
    cols = [(c["name"], [g.get("tagFQN", "") for g in c.get("tags", [])]) for c in t["columns"]]
    owners = [o.get("fullyQualifiedName", o.get("name", "?")) for o in t.get("owners") or []]
    return cols, owners


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in ("find", "describe", "downstream", "quality", "governance"):
        print("usage: ch01_five_questions {find <q>|describe [fqn]|downstream [fqn]|quality [fqn]|governance [fqn]}")
        return 2
    cmd = argv[1]
    if cmd == "find":
        q = argv[2] if len(argv) > 2 else "revenue"
        rows = find(q)
        print(f"search {q!r}: {len(rows)} hit(s)")
        for fqn, desc in rows:
            print(f"  {fqn}\n    {desc or '(no description)'}")
    elif cmd == "describe":
        for col, typ, desc in describe(argv[2] if len(argv) > 2 else DAILY_REVENUE):
            print(f"  {col:15s} {typ:10s} {desc or '(no description)'}")
    elif cmd == "downstream":
        for frm, to, src in downstream(argv[2] if len(argv) > 2 else ORDERS):
            print(f"  {frm} -> {to}  [{src}]")
    elif cmd == "quality":
        for name, status, result in quality(argv[2] if len(argv) > 2 else ORDERS):
            print(f"  {status:8s} {name}\n           {result}")
    elif cmd == "governance":
        cols, owners = governance(argv[2] if len(argv) > 2 else CUSTOMERS)
        for col, tags in cols:
            print(f"  {col:15s} {', '.join(tags) if tags else '(no tags)'}")
        print(f"  owners: {', '.join(owners) if owners else '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
