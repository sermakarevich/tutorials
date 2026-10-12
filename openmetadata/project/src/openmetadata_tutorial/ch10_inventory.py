"""Chapter 10: inventory of what the tutorial built, read from the live catalog.

Read-only: every function is a thin wrapper over GET calls (`client.get`).
Whatever the other chapters created shows here as observed; anything a
chapter has not created yet simply shows 0. Run from project/ as::

    uv run python -m openmetadata_tutorial.ch10_inventory
"""

from openmetadata_tutorial.client import get

ORDERS = "brightcup_pg.brightcup.raw.orders"

#: The 7 Brightcup assets every chapter shares (plan.md).
BRIGHTCUP_ASSETS = [
    "brightcup_pg.brightcup.raw.customers",
    "brightcup_pg.brightcup.raw.products",
    "brightcup_pg.brightcup.raw.orders",
    "brightcup_pg.brightcup.raw.order_items",
    "brightcup_pg.brightcup.analytics.fct_orders",
    "brightcup_pg.brightcup.analytics.daily_revenue",
    "brightcup_pg.brightcup.analytics.customer_ltv",
]


def tables_per_service(limit: int = 100) -> dict[str, list[str]]:
    """Return {service name: [table FQNs]} for every table in the catalog."""
    r = get("/v1/tables", limit=limit, fields="name")
    out: dict[str, list[str]] = {}
    for t in r.get("data", []):
        fqn = t.get("fullyQualifiedName", "?")
        out.setdefault(fqn.split(".")[0], []).append(fqn)
    return out


def lineage_downstream(fqn: str = ORDERS) -> list[tuple[str, str, str]]:
    """Return [(from FQN, to FQN, source)] downstream of one table."""
    lin = get(f"/v1/lineage/table/name/{fqn}", upstreamDepth=0, downstreamDepth=3)
    names = {n["id"]: n.get("fullyQualifiedName", n.get("name", "?")) for n in lin.get("nodes", [])}
    names[lin["entity"]["id"]] = lin["entity"]["fullyQualifiedName"]
    out = []
    for e in lin.get("downstreamEdges", []):
        details = e.get("lineageDetails") or {}
        out.append((names.get(e["fromEntity"], "?"), names.get(e["toEntity"], "?"), details.get("source", "?")))
    return out


def test_summary(limit: int = 100) -> list[tuple[str, str, str]]:
    """Return [(test name, status, table FQN)] for every test case in the catalog."""
    r = get("/v1/dataQuality/testCases", limit=limit, fields="testCaseResult", includeAllTests="true")
    out = []
    for tc in r.get("data", []):
        res = tc.get("testCaseResult") or {}
        link = tc.get("entityLink", "")
        table = link.split("::")[-1].rstrip(">") if "::" in link else "?"
        out.append((tc.get("name", "?"), res.get("testCaseStatus") or "No result yet", table))
    return out


def pii_columns(fqns: list[str] | None = None) -> list[tuple[str, str, str]]:
    """Return [(table FQN, column, tag FQN)] for columns tagged PII.*."""
    out = []
    for fqn in fqns or BRIGHTCUP_ASSETS:
        # NOTE: column tags are only returned when "tags" is requested too
        # (observed: fields="columns" alone yields empty tag lists).
        t = get(f"/v1/tables/name/{fqn}", fields="columns,tags")
        for c in t.get("columns", []):
            for g in c.get("tags", []):
                if g.get("tagFQN", "").startswith("PII."):
                    out.append((fqn, c["name"], g["tagFQN"]))
    return out


def glossary_terms(limit: int = 100) -> list[str]:
    """Return the names of all glossary terms (e.g. chapter 08's Brightcup terms)."""
    r = get("/v1/glossaryTerms", limit=limit)
    return [t.get("name", "?") for t in r.get("data", [])]


def owners_report(fqns: list[str] | None = None) -> list[tuple[str, str]]:
    """Return [(table FQN, owner names or '(none)')] for the Brightcup assets."""
    out = []
    for fqn in fqns or BRIGHTCUP_ASSETS:
        t = get(f"/v1/tables/name/{fqn}", fields="owners")
        owners = [o.get("fullyQualifiedName", o.get("name", "?")) for o in t.get("owners") or []]
        out.append((fqn, ", ".join(owners) if owners else "(none)"))
    return out


def alert_subscriptions(limit: int = 50) -> list[str]:
    """Return the names of all event subscriptions (alerts)."""
    r = get("/v1/events/subscriptions", limit=limit)
    return [s.get("name", "?") for s in r.get("data", [])]


def contracts(limit: int = 50) -> list[str]:
    """Return the names of all data contracts."""
    r = get("/v1/dataContracts", limit=limit)
    return [c.get("name", "?") for c in r.get("data", [])]


def installed_apps(limit: int = 50) -> list[str]:
    """Return the names of the installed applications (Settings > Applications)."""
    r = get("/v1/apps", limit=limit)
    return [a.get("name", "?") for a in r.get("data", [])]


def main() -> None:
    print("== tables per service ==")
    for service, fqns in sorted(tables_per_service().items()):
        print(f"  {service}: {len(fqns)} table(s)")
        for fqn in sorted(fqns):
            print(f"    {fqn}")
    print("== lineage downstream of raw.orders ==")
    edges = lineage_downstream()
    print(f"  {len(edges)} edge(s)")
    for frm, to, src in edges:
        print(f"    {frm} -> {to}  [{src}]")
    print("== test cases ==")
    tests = test_summary()
    failed = sum(1 for _, s, _ in tests if s == "Failed")
    print(f"  {len(tests)} test case(s), {failed} failed")
    for name, status, table in tests:
        print(f"    {status:14s} {name}  (on {table})")
    print("== PII-tagged columns ==")
    cols = pii_columns()
    print(f"  {len(cols)} column(s)")
    for fqn, col, tag in cols:
        print(f"    {fqn}.{col} -> {tag}")
    print("== glossary terms ==")
    terms = glossary_terms()
    print(f"  {len(terms)} term(s): {', '.join(terms) if terms else '(none)'}")
    print("== owners of the 7 Brightcup assets ==")
    for fqn, owners in owners_report():
        print(f"    {fqn.split('.')[-1]:15s} {owners}")
    print("== event subscriptions (alerts) ==")
    subs = alert_subscriptions()
    print(f"  {len(subs)} subscription(s): {', '.join(subs) if subs else '(none)'}")
    print("== data contracts ==")
    conts = contracts()
    print(f"  {len(conts)} contract(s): {', '.join(conts) if conts else '(none)'}")
    print("== installed apps ==")
    print(f"  {', '.join(installed_apps())}")


if __name__ == "__main__":
    main()
