"""Lineage for chapter 06: read edges, draw them, add the missing dashboard, walk impact.

All reads go through ``openmetadata_tutorial.client`` (bot JWT from ``.env``).
Every create is an idempotent PUT (create-or-update), so re-running is safe.
"""

import re

import pandas as pd
from openmetadata_tutorial import client

#: The server rejects upstreamDepth/downstreamDepth above this (observed 400:
#: "[query param downstreamDepth must be less than or equal to 3]").
MAX_DEPTH = 3

PLURAL = {
    "table": "tables",
    "dashboard": "dashboards",
    "chart": "charts",
    "pipeline": "pipelines",
}

ORDERS = "brightcup_pg.brightcup.raw.orders"
FCT_ORDERS = "brightcup_pg.brightcup.analytics.fct_orders"
DAILY_REVENUE = "brightcup_pg.brightcup.analytics.daily_revenue"
CUSTOMER_LTV = "brightcup_pg.brightcup.analytics.customer_ltv"
AMOUNT_COLUMN = "brightcup_pg.brightcup.raw.orders.total_amount"

DASHBOARD_SERVICE = "brightcup_metabase"
CHART_NAME = "revenue_by_day"
CHART_DISPLAY = "Revenue by day"
DASHBOARD_NAME = "finance_overview"
DASHBOARD_DISPLAY = "Finance overview"

#: Parser-test view created in the last section of this chapter. The walks below
#: exclude it by default so they read the same on a first run (it does not exist
#: yet) and on a re-run (it does). The last section opts back in with `exclude=[]`.
DYNAMIC_VIEW = "brightcup_pg.brightcup.analytics.ch06_dynamic"


def _entity_id(fqn: str, entity_type: str) -> str:
    """Resolve an FQN to its entity id, e.g. table -> /v1/tables/name/<fqn>."""
    return client.get(f"/v1/{PLURAL[entity_type]}/name/{fqn}")["id"]


def _is_excluded(fqn: str, exclude: list[str] | None) -> bool:
    """Whether one FQN is on the caller's exclusion list (late-chapter stand-ins)."""
    return bool(exclude) and fqn in exclude


def _lineage(fqn: str, entity_type: str, up: int, down: int) -> dict:
    """Raw lineage response (entity + nodes + upstream/downstream edges)."""
    up = min(max(up, 0), MAX_DEPTH)
    down = min(max(down, 0), MAX_DEPTH)
    eid = _entity_id(fqn, entity_type)
    return client.get(f"/v1/lineage/{entity_type}/{eid}", upstreamDepth=up, downstreamDepth=down)


def view_sql(fqn: str) -> str:
    """The view definition OpenMetadata parsed lineage from (views only)."""
    t = client.get(f"/v1/tables/name/{fqn}", fields="schemaDefinition")
    return t.get("schemaDefinition") or ""


def edges(
    fqn: str,
    up: int = 1,
    down: int = 1,
    entity_type: str = "table",
    exclude: list[str] | None = None,
) -> pd.DataFrame:
    """Lineage edges around `fqn` as a table with (from, to, source) rows.

    Node ids are resolved to FQNs so the table reads without a lookup.
    Depths above 3 are clamped: the server rejects them (see MAX_DEPTH).
    `exclude` drops rows touching the listed FQNs. The default (`None`) drops
    the chapter's late parser-test view (`DYNAMIC_VIEW`, created in the last
    section), so walks read the same on a first run and on a re-run; pass
    `exclude=[]` to include everything.
    """
    if exclude is None:
        exclude = [DYNAMIC_VIEW]
    r = _lineage(fqn, entity_type, up, down)
    names = {n["id"]: n.get("fullyQualifiedName", n.get("name")) for n in r.get("nodes", [])}
    names[r["entity"]["id"]] = r["entity"].get("fullyQualifiedName", r["entity"].get("name"))
    rows = []
    for e in r.get("upstreamEdges", []) + r.get("downstreamEdges", []):
        ld = e.get("lineageDetails") or {}
        frm = names.get(e["fromEntity"], e["fromEntity"])
        to = names.get(e["toEntity"], e["toEntity"])
        if _is_excluded(frm, exclude) or _is_excluded(to, exclude):
            continue
        rows.append({"from": frm, "to": to, "source": ld.get("source", "Manual")})
    return pd.DataFrame(rows, columns=["from", "to", "source"]).drop_duplicates().reset_index(drop=True)


def brightcup_graph(exclude: list[str] | None = None) -> pd.DataFrame:
    """The whole Brightcup lineage graph: the 5 edges between the 4 shop tables.

    Built as the union of two walks (no single center reaches all 5 edges):
    everything upstream of customer_ltv plus everything upstream of daily_revenue.
    Sorted by (from, to): the API row order varies between runs, and without
    this the mermaid node numbers would shuffle on every re-run.
    `exclude` is passed to both walks (see `edges`); by default the late
    parser-test view is left out.
    """
    a = edges(CUSTOMER_LTV, up=2, down=0, exclude=exclude)
    b = edges(DAILY_REVENUE, up=1, down=0, exclude=exclude)
    return (
        pd.concat([a, b])
        .drop_duplicates()
        .sort_values(["from", "to"])
        .reset_index(drop=True)
    )


def _short(fqn: str) -> str:
    return fqn.split(".")[-1]


def to_mermaid(df: pd.DataFrame) -> str:
    """Render an edge table as a Mermaid flowchart (left to right, labelled edges)."""
    ids: dict[str, str] = {}

    def nid(fqn: str) -> str:
        if fqn not in ids:
            ids[fqn] = "n" + str(len(ids))
        return ids[fqn]

    lines = ["flowchart LR"]
    for fqn in pd.concat([df["from"], df["to"]]).drop_duplicates():
        lines.append(f'    {nid(fqn)}["{_short(fqn)}"]')
    for _, r in df.iterrows():
        label = re.sub(r"Lineage$", "", str(r["source"]))  # ViewLineage -> View
        lines.append(f'    {nid(r["from"])} -->|{label}| {nid(r["to"])}')
    return "\n".join(lines)


def column_edges(
    fqn: str, up: int = 1, down: int = 1, exclude: list[str] | None = None
) -> pd.DataFrame:
    """Column-level mappings on each edge around `fqn`: (from, to, from_column, to_column, source).

    `exclude` drops rows touching the listed FQNs (see `edges`); by default the
    late parser-test view is left out.
    """
    if exclude is None:
        exclude = [DYNAMIC_VIEW]
    r = _lineage(fqn, "table", up, down)
    names = {n["id"]: n.get("fullyQualifiedName", n.get("name")) for n in r.get("nodes", [])}
    names[r["entity"]["id"]] = r["entity"].get("fullyQualifiedName", r["entity"].get("name"))
    rows = []
    for e in r.get("upstreamEdges", []) + r.get("downstreamEdges", []):
        ld = e.get("lineageDetails") or {}
        frm = names.get(e["fromEntity"], e["fromEntity"])
        to = names.get(e["toEntity"], e["toEntity"])
        if _is_excluded(frm, exclude) or _is_excluded(to, exclude):
            continue
        for cl in ld.get("columnsLineage", []):
            for fc in cl.get("fromColumns", []):
                rows.append(
                    {
                        "from": frm,
                        "to": to,
                        "from_column": _short(fc),
                        "to_column": _short(cl.get("toColumn", "")),
                        "source": ld.get("source", "Manual"),
                    }
                )
    return pd.DataFrame(rows, columns=["from", "to", "from_column", "to_column", "source"])


def column_path(start_column: str, depth: int = 3, exclude: list[str] | None = None) -> pd.DataFrame:
    """Follow one column downstream hop by hop: (step, from_column, to_column).

    `start_column` is a column FQN, e.g. brightcup_pg.brightcup.raw.orders.total_amount.
    Each step follows the column mappings on the downstream table edges, so a
    fork (one column feeding two metrics) shows up as two rows with the same step.
    `exclude` skips mappings into or out of the listed table FQNs (see `edges`);
    by default the late parser-test view is left out.
    """
    if exclude is None:
        exclude = [DYNAMIC_VIEW]
    table = start_column.rsplit(".", 1)[0]
    r = _lineage(table, "table", 0, min(depth, MAX_DEPTH))
    names = {n["id"]: n.get("fullyQualifiedName", n.get("name")) for n in r.get("nodes", [])}
    names[r["entity"]["id"]] = r["entity"].get("fullyQualifiedName", r["entity"].get("name"))
    children: dict[str, list[str]] = {}
    for e in r.get("downstreamEdges", []):
        frm = names.get(e["fromEntity"], e["fromEntity"])
        to = names.get(e["toEntity"], e["toEntity"])
        if _is_excluded(frm, exclude) or _is_excluded(to, exclude):
            continue
        for cl in (e.get("lineageDetails") or {}).get("columnsLineage", []):
            for fc in cl.get("fromColumns", []):
                children.setdefault(fc, []).append(cl.get("toColumn", ""))
    rows = []
    frontier = [(start_column, 0)]
    seen = {start_column}
    while frontier:
        col, step = frontier.pop(0)
        if step >= depth:
            continue
        for nxt in children.get(col, []):
            rows.append({"step": step + 1, "from_column": col, "to_column": nxt})
            if nxt not in seen:
                seen.add(nxt)
                frontier.append((nxt, step + 1))
    return pd.DataFrame(rows, columns=["step", "from_column", "to_column"])


#: A view the SQL parser may not fully resolve: CTEs, UNION ALL, a function
#: call (upper), and an expression (quantity * unit_price). FQN in DYNAMIC_VIEW
#: above; kept afterwards on purpose: dropping it would soft-delete it on the
#: next metadata run.
DYNAMIC_VIEW_SQL = """
CREATE OR REPLACE VIEW analytics.ch06_dynamic AS
WITH recent AS (
  SELECT order_id, customer_id, upper(status) AS status, total_amount
  FROM raw.orders
),
items AS (
  SELECT order_id, sum(quantity * unit_price) AS items_total
  FROM raw.order_items
  GROUP BY order_id
)
SELECT order_id, customer_id, status, total_amount AS amount FROM recent
UNION ALL
SELECT i.order_id, NULL::int AS customer_id, 'items' AS status, i.items_total AS amount
FROM items i
"""


def create_dynamic_view() -> dict:
    """Create (or replace) analytics.ch06_dynamic as shop_admin; return its FQN.

    Idempotent: CREATE OR REPLACE plus GRANT, so re-running changes nothing.
    """
    import psycopg

    from openmetadata_tutorial.config import settings

    s = settings()
    dsn = (
        f"host={s.shop_host} port={s.shop_port} dbname={s.shop_db} "
        f"user={s.shop_admin_user} password={s.shop_admin_password}"
    )
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(DYNAMIC_VIEW_SQL)
        conn.execute("GRANT SELECT ON analytics.ch06_dynamic TO om_reader")
    return {"view": DYNAMIC_VIEW,
            "how": "CREATE OR REPLACE (re-running keeps the same view)"}


def query_log_total(limit: int = 100) -> dict:
    """How many SQL statements the server log holds right now (live GET /v1/queries).

    Returns {"total": n, "returned": m, "how": ...}: `total` is the server's
    paging total, `returned` how many rows one page of `limit` brought back.
    """
    r = client.get("/v1/queries", limit=limit)
    total = (r.get("paging") or {}).get("total", len(r.get("data", [])))
    return {"total": total, "returned": len(r.get("data", [])), "how": "live GET /v1/queries"}


def queries_for(fqn: str, limit: int = 100) -> pd.DataFrame:
    """Logged SQL statements mentioning one asset: (name, query).

    These are the raw material query lineage is parsed from. The `entityFQN`
    query parameter is ignored by the server in 2.0.5 (observed: any FQN
    returns the same first page as the unfiltered list), so this lists the
    log (one page of `limit`) and keeps the statements whose SQL mentions
    the asset's short name, e.g. `customer_ltv`.
    """
    short = fqn.split(".")[-1].lower()
    r = client.get("/v1/queries", limit=limit)
    rows = [
        {"name": q.get("name"), "query": q.get("query", "")}
        for q in r.get("data", [])
        if short in (q.get("query") or "").lower()
    ]
    return pd.DataFrame(rows, columns=["name", "query"])


def nightly_job_sql() -> str:
    """The CREATE TABLE AS statement the nightly job runs (from transform.py).

    Shown from the local job definition, not the server log: the logged copy
    ages out of pg_stat_statements once it falls outside the lineage
    workflow's query-log window, while this text is identical on every run.
    """
    from openmetadata_tutorial.transform import CUSTOMER_LTV_SQL

    return CUSTOMER_LTV_SQL.strip()


def quality_status(fqn: str) -> pd.DataFrame:
    """Latest result of every test case on one asset: (test, status).

    Used for the quality angle of impact analysis: a Failed test on an upstream
    table flows to everything downstream of it.
    """
    import urllib.parse

    entity_link = urllib.parse.quote(f"<#E::table::{fqn}>", safe="")
    r = client.get("/v1/dataQuality/testCases?entityLink=" + entity_link, fields="testCaseResult")
    rows = [
        {"test": t.get("name"), "status": (t.get("testCaseResult") or {}).get("testCaseStatus")}
        for t in r.get("data", [])
    ]
    return pd.DataFrame(rows, columns=["test", "status"])


def negative_amount_count() -> dict:
    """How many rows in raw.orders have a negative total_amount (live SQL).

    The number behind the `orders_no_negative_amounts` test: the custom SQL
    test fails with "Found 5 row(s)", and this counts those rows directly.
    Returns {"rows": n, "how": "live SQL against the shop database"}.
    """
    import psycopg

    from openmetadata_tutorial.config import settings

    s = settings()
    dsn = (
        f"host={s.shop_host} port={s.shop_port} dbname={s.shop_db} "
        f"user={s.shop_admin_user} password={s.shop_admin_password}"
    )
    with psycopg.connect(dsn) as conn:
        n = conn.execute("SELECT count(*) FROM raw.orders WHERE total_amount < 0").fetchone()[0]
    return {"rows": n, "how": "live SQL against the shop database"}


def ensure_dashboard() -> dict:
    """Create (or reuse) the finance dashboard stand-in; return its FQNs and ids.

    The finance team's real dashboard tool is not connected to OpenMetadata, so we
    register a stand-in service plus one chart and one dashboard in it. Uses the
    CustomDashboard service type: there is no real dashboard server to point at,
    so a Metabase/Superset type with a dummy URL would pretend a connection exists.
    """
    svc = client.api(
        "PUT",
        "/v1/services/dashboardServices",
        json={
            "name": DASHBOARD_SERVICE,
            "serviceType": "CustomDashboard",
            "connection": {"config": {"type": "CustomDashboard", "sourcePythonClass": "custom"}},
        },
    ).json()
    chart = client.api(
        "PUT",
        "/v1/charts",
        json={
            "name": CHART_NAME,
            "displayName": CHART_DISPLAY,
            "description": "Daily revenue line chart for the finance team.",
            "service": DASHBOARD_SERVICE,
            "chartType": "Line",
        },
    ).json()
    dash = client.api(
        "PUT",
        "/v1/dashboards",
        json={
            "name": DASHBOARD_NAME,
            "displayName": DASHBOARD_DISPLAY,
            "description": "Finance overview (stand-in for the unconnected dashboard tool).",
            "service": DASHBOARD_SERVICE,
            "charts": [chart["fullyQualifiedName"]],
        },
    ).json()
    return {
        "service": svc["fullyQualifiedName"],
        "chart": chart["fullyQualifiedName"],
        "dashboard": dash["fullyQualifiedName"],
        "dashboard_id": dash["id"],
        "how": "PUT create-or-update (re-running keeps the same FQNs)",
    }


def add_edge(
    from_fqn: str,
    from_type: str,
    to_fqn: str,
    to_type: str,
    description: str,
    column_pairs: list[tuple[str, str]] | None = None,
) -> dict:
    """Add one manual lineage edge (PUT /v1/lineage); return what was linked.

    `column_pairs` is only valid table -> table: the server rejects lineageDetails
    on edges pointing at other kinds (observed 400), so dashboard edges carry the
    description on the edge itself and no column mapping.
    """
    edge: dict = {
        "fromEntity": {"id": _entity_id(from_fqn, from_type), "type": from_type},
        "toEntity": {"id": _entity_id(to_fqn, to_type), "type": to_type},
    }
    if column_pairs is not None and from_type == "table" and to_type == "table":
        edge["lineageDetails"] = {
            "description": description,
            "columnsLineage": [{"fromColumns": [a], "toColumn": b} for a, b in column_pairs],
            "source": "Manual",
        }
    else:
        edge["description"] = description
    r = client.api("PUT", "/v1/lineage", json={"edge": edge})
    r.raise_for_status()  # PUT returns 200 with an empty body
    return {"from": from_fqn, "to": to_fqn, "description": description, "how": "manual edge"}


def _owners(entity_type: str, eid: str) -> str:
    try:
        ent = client.get(f"/v1/{PLURAL[entity_type]}/{eid}", fields="owners")
    except Exception:
        return ""
    return ", ".join(o.get("fullyQualifiedName", o.get("name", "")) for o in ent.get("owners", []))


def impact(fqn: str, column: str | None = None, depth: int = 3, exclude: list[str] | None = None) -> pd.DataFrame:
    """Walk downstream of `fqn` and list what a change would reach.

    Rows: (level, kind, fqn, owners, via_column). With `column` set (a column FQN
    under `fqn`), only assets fed by that column are listed and via_column names
    the downstream column that carries the impact; otherwise every downstream
    asset is listed with the column mappings on the edge that reaches it.
    Depth is clamped to 3 (the server maximum). `exclude` skips the listed
    asset FQNs entirely (see `edges`); by default the late parser-test view
    is left out.
    """
    if exclude is None:
        exclude = [DYNAMIC_VIEW]
    depth = min(max(depth, 1), MAX_DEPTH)
    center = _lineage(fqn, "table", 0, depth)
    info = {n["id"]: n for n in center.get("nodes", [])}
    info[center["entity"]["id"]] = center["entity"]
    names = {eid: n.get("fullyQualifiedName", n.get("name", "")) for eid, n in info.items()}
    edge_rows = []
    for e in center.get("downstreamEdges", []):
        if _is_excluded(names.get(e["fromEntity"], ""), exclude) or _is_excluded(
            names.get(e["toEntity"], ""), exclude
        ):
            continue
        ld = e.get("lineageDetails") or {}
        edge_rows.append(
            {
                "from": e["fromEntity"],
                "to": e["toEntity"],
                "maps": [(fc, cl.get("toColumn", "")) for cl in ld.get("columnsLineage", []) for fc in cl.get("fromColumns", [])],
            }
        )

    if column is None:
        # Table-level walk: BFS over table edges.
        seen = {center["entity"]["id"]}
        frontier = [(center["entity"]["id"], 0)]
        out = []
        while frontier:
            eid, level = frontier.pop(0)
            if level >= depth:
                continue
            for er in edge_rows:
                if er["from"] != eid or er["to"] in seen:
                    continue
                seen.add(er["to"])
                node = info.get(er["to"], {})
                via = "; ".join(f"{_short(a)}->{_short(b)}" for a, b in er["maps"])
                out.append(
                    {
                        "level": level + 1,
                        "kind": node.get("type", ""),
                        "fqn": node.get("fullyQualifiedName", ""),
                        "owners": _owners(node.get("type", "table"), er["to"]),
                        "via_column": via,
                    }
                )
                frontier.append((er["to"], level + 1))
        return pd.DataFrame(out, columns=["level", "kind", "fqn", "owners", "via_column"])

    # Column-level walk: BFS over column mappings.
    children: dict[str, list[tuple[str, str]]] = {}
    for er in edge_rows:
        for a, b in er["maps"]:
            children.setdefault(a, []).append((b, er["to"]))
    seen_cols = {column}
    frontier_c = [(column, 0)]
    hits: dict[str, dict] = {}
    while frontier_c:
        col, level = frontier_c.pop(0)
        if level >= depth:
            continue
        for nxt, eid in children.get(col, []):
            if nxt not in seen_cols:
                seen_cols.add(nxt)
                frontier_c.append((nxt, level + 1))
            node = info.get(eid, {})
            prev = hits.get(eid)
            if prev is None or level + 1 < prev["level"]:
                hits[eid] = {
                    "level": level + 1,
                    "kind": node.get("type", ""),
                    "fqn": node.get("fullyQualifiedName", ""),
                    "owners": _owners(node.get("type", "table"), eid),
                    "via_column": _short(nxt),
                }
    return pd.DataFrame(sorted(hits.values(), key=lambda h: h["level"]), columns=["level", "kind", "fqn", "owners", "via_column"])
