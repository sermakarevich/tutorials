"""Chapter 05: read and change any entity over REST, and the same through the SDK.

Every call goes through ``openmetadata_tutorial.client`` (bot JWT from ``.env``),
so auth is done one way. Cells stay one idea each; paging loops, error mapping
and frame building live here. Run from project/ as, e.g.::

    uv run python -c "from openmetadata_tutorial import ch05_api as A; print(A.column_index(A.get_table(), 'quantity'))"
"""

import json
import warnings

import pandas as pd
import requests

from openmetadata_tutorial import client
from openmetadata_tutorial.config import settings

# Importing the SDK pulls in generated pydantic models that trigger a harmless
# upstream warning (a field named "schema" shadowing BaseModel.schema). Silence
# just that warning so notebook outputs stay clean.
warnings.filterwarnings(
    "ignore",
    message='Field name "schema" in "PostgresStoredProcedure" shadows an attribute.*',
)

#: The running example throughout: the order-lines table of the Brightcup shop.
ORDER_ITEMS = "brightcup_pg.brightcup.raw.order_items"

#: Canonical texts this chapter writes onto raw.order_items. Fixed strings, so
#: re-running the notebook (or the tests) is a no-op once they are set.
TABLE_DESCRIPTION = "One row per ordered product: which order, which product, how many, at what price."
QUANTITY_DESCRIPTION = "Number of units of the product in this order line."

#: Manual tier tag applied to raw.order_items (same shape the server returns).
TIER_TAG = {"tagFQN": "Tier.Tier3", "source": "Classification", "labelType": "Manual", "state": "Confirmed"}

#: Throwaway table for the delete/restore demo. Catalog-only: it never exists in
#: Postgres, so the next metadata re-run with markDeletedTables soft-deletes it.
SCRATCH = "brightcup_pg.brightcup.raw.ch05_scratch"


def get_table(fqn: str = ORDER_ITEMS, fields: str | None = None) -> dict:
    """GET one table by FQN; `fields` asks for heavy parts (owners, tags, ...)."""
    params = {"fields": fields} if fields else {}
    return client.get(f"/v1/tables/name/{fqn}", **params)


def payload_size(entity: dict) -> int:
    """Length of the entity as JSON text — the poor man's payload meter."""
    return len(json.dumps(entity))


def list_all(path: str, **params) -> object:
    """Yield every entity on a list endpoint, following `paging.after` cursors.

    A generator: `list(list_all("/v1/tables", database="brightcup_pg.brightcup"))`.
    """
    page = dict(params)
    page.setdefault("limit", 50)
    while True:
        r = client.get(path, **page)
        yield from r.get("data", [])
        after = (r.get("paging") or {}).get("after")
        if not after:
            return
        page["after"] = after


def column_index(table: dict, name: str) -> int:
    """Position of column `name` in `table["columns"]` (for index-based patch paths)."""
    for i, col in enumerate(table.get("columns", [])):
        if col.get("name") == name:
            return i
    raise ValueError(f"no column {name!r} in {[c.get('name') for c in table.get('columns', [])]}")


def patch(path: str, ops: list[dict]) -> dict:
    """Apply a JSON Patch (`ops`) to `path`; return the updated entity as JSON.

    Limit: a patch that changes nothing returns the entity with the same
    `version` — the server mints no new version for a no-op.
    """
    return client.api("PATCH", path, json=ops).json()


def set_description(entity_id: str, text: str) -> dict:
    """Set a table description idempotently; same text twice is a server no-op.

    Uses `op: add`, which the server also accepts when a description is already
    present (it overwrites). Returns the updated table.
    """
    return patch(f"/v1/tables/{entity_id}", [{"op": "add", "path": "/description", "value": text}])


def set_column_description(entity_id: str, column: str, text: str) -> dict:
    """Set one column description (index looked up by name just before patching)."""
    table = client.get(f"/v1/tables/{entity_id}", fields="columns")
    i = column_index(table, column)
    return patch(f"/v1/tables/{entity_id}", [{"op": "add", "path": f"/columns/{i}/description", "value": text}])


def ensure_tier_tag(entity_id: str, tag: dict | None = None) -> dict:
    """Append the tier tag; re-running does not duplicate it. Returns the table."""
    return patch(f"/v1/tables/{entity_id}", [{"op": "add", "path": "/tags/-", "value": tag or TIER_TAG}])


def change_summary(entity: dict) -> str:
    """One-line summary of a changeDescription: added/updated/deleted field names."""
    cd = entity.get("changeDescription") or {}
    parts = []
    for key, verb in (("fieldsAdded", "added"), ("fieldsUpdated", "updated"), ("fieldsDeleted", "deleted")):
        for f in cd.get(key) or []:
            parts.append(f"{verb}:{f.get('name')}")
    for name in (cd.get("changeSummary") or {}):
        if name not in {p.split(":", 1)[1] for p in parts}:
            parts.append(f"~:{name}")
    return "; ".join(parts)


def change_detail(entity: dict) -> dict:
    """The version step an entity carries: previous version + one-line summary.

    Returns {"previousVersion", "summary"} read off `changeDescription`, so a
    cell can print both without digging through the raw JSON.
    """
    cd = entity.get("changeDescription") or {}
    return {"previousVersion": cd.get("previousVersion"), "summary": change_summary(entity)}


def snapshot_column(entity_id: str, version: str, column: str, entity: str = "tables") -> dict:
    """One column's description inside one stored version snapshot, plus context.

    Returns {"description", "previousVersion", "summary"}: what the snapshot
    says about `column`, and what that snapshot's own `changeDescription`
    lists (previous version + one-line summary). Shows whether a nested edit
    got its own history entry.
    """
    snap = client.get(f"/v1/{entity}/{entity_id}/versions/{version}")
    desc = None
    for col in snap.get("columns", []):
        if col.get("name") == column:
            desc = col.get("description")
            break
    cd = snap.get("changeDescription") or {}
    return {"description": desc, "previousVersion": cd.get("previousVersion"), "summary": change_summary(snap)}


def versions_frame(entity_id: str, entity: str = "tables") -> pd.DataFrame:
    """Version history of one entity: (version, updatedBy, updatedAt, previous, changed).

    This is the audit log of the entity: who changed what, and when. Each row
    carries the `changeDescription` of that version: which fields were
    added/updated/deleted and which version came before (`previousVersion`;
    `None` for the first version, which has no changeDescription).
    """
    import json as _json

    r = client.get(f"/v1/{entity}/{entity_id}/versions")
    rows = []
    for raw in r.get("versions", []):
        v = _json.loads(raw)
        cd = v.get("changeDescription") or {}
        rows.append(
            {
                "version": v.get("version"),
                "updatedBy": v.get("updatedBy"),
                "updatedAt": pd.to_datetime(v.get("updatedAt"), unit="ms"),
                "previousVersion": cd.get("previousVersion"),
                "changed": change_summary(v),
            }
        )
    return pd.DataFrame(rows, columns=["version", "updatedBy", "updatedAt", "previousVersion", "changed"])


def search_frame(
    q: str, index: str = "table_search_index", query_filter: str | None = None, size: int = 10, frm: int = 0
) -> pd.DataFrame:
    """Search the catalog; one row per hit: (entity, fqn, kind, description).

    `query_filter` is an Elasticsearch query as a JSON string (a bool filter).
    `size`/`frm` page through hits (`frm` is the `from` offset; `from` is a
    Python keyword so the argument is spelled `frm`). The frame's `total`
    attribute is the total hit count, which can exceed the rows shown when
    `size` is smaller than the total. Limit: search matches words, it does
    not judge relevance — narrow with `query_filter`.
    """
    params = {"q": q, "index": index, "size": size, "from": frm}
    if query_filter:
        params["query_filter"] = query_filter
    r = client.get("/v1/search/query", **params)
    rows = []
    for h in r["hits"]["hits"]:
        s = h.get("_source", {})
        rows.append(
            {
                "entity": s.get("entityType", ""),
                "fqn": s.get("fullyQualifiedName", s.get("name", "")),
                "kind": s.get("tableType") or s.get("chartType") or s.get("entityType", ""),
                "description": (s.get("description") or "")[:60],
            }
        )
    df = pd.DataFrame(rows, columns=["entity", "fqn", "kind", "description"])
    df.attrs["total"] = (r.get("hits", {}).get("total") or {}).get("value", len(df))
    return df


def analytics_only_filter() -> str:
    """Elasticsearch bool filter keeping only assets in the `analytics` schema."""
    return json.dumps({"query": {"bool": {"filter": [{"term": {"databaseSchema.name.keyword": "analytics"}}]}}})


def probe_error(kind: str) -> dict:
    """Trigger one real API error; return {"status": ..., "message": ...}.

    kinds: "missing" (wrong FQN -> 404), "bad-patch" (bad patch path -> 400),
    "bad-fields" (unknown `fields=` value -> 400),
    "bad-token" (bogus Bearer token -> 401).
    """
    s = settings()
    if kind == "missing":
        try:
            client.get("/v1/tables/name/brightcup_pg.brightcup.raw.NOPE")
        except requests.HTTPError as e:
            return {"status": e.response.status_code, "message": e.response.json().get("message", "")}
    elif kind == "bad-patch":
        eid = get_table()["id"]
        try:
            patch(f"/v1/tables/{eid}", [{"op": "add", "path": "/nope", "value": "x"}])
        except requests.HTTPError as e:
            return {"status": e.response.status_code, "message": e.response.json().get("message", "")[:120]}
    elif kind == "bad-fields":
        try:
            client.get(f"/v1/tables/name/{ORDER_ITEMS}", fields="BOGUS_FIELD")
        except requests.HTTPError as e:
            return {"status": e.response.status_code, "message": e.response.json().get("message", "")[:120]}
    elif kind == "bad-token":
        try:
            r = requests.get(
                f"{s.om_api}/v1/tables/name/{ORDER_ITEMS}",
                headers={"Authorization": "Bearer x"},
                timeout=30,
            )
            r.raise_for_status()
        except requests.HTTPError as e:
            return {"status": e.response.status_code, "message": e.response.json().get("message", "")}
    else:
        raise ValueError(f"unknown error kind {kind!r}")
    raise AssertionError(f"expected an HTTP error for {kind!r}, the call succeeded")


def ensure_scratch() -> dict:
    """Create (or reuse) the throwaway table for the delete/restore demo."""
    r = client.api(
        "PUT",
        "/v1/tables",
        json={"name": "ch05_scratch", "databaseSchema": "brightcup_pg.brightcup.raw", "columns": [{"name": "id", "dataType": "INT"}]},
    )
    body = r.json()
    return {"fqn": body["fullyQualifiedName"], "id": body["id"], "status": r.status_code, "how": "PUT create-or-update"}


def get_status(entity_id: str, **params) -> dict:
    """GET one table by id without raising; return {"status", "deleted", "name"}."""
    try:
        t = client.get(f"/v1/tables/{entity_id}", **params)
        return {"status": 200, "deleted": t.get("deleted", False), "name": t.get("name")}
    except requests.HTTPError as e:
        return {"status": e.response.status_code, "deleted": None, "name": None}


def auth_info() -> dict:
    """Who this chapter acts as: bot name, bot flag, and where the token came from.

    Never returns the token itself (only whether it came from `.env`).
    """
    s = settings()
    me = client.get("/v1/users/loggedInUser")
    return {"user": me.get("name"), "isBot": me.get("isBot"), "via": "OM_JWT_TOKEN in .env" if s.om_jwt_token else "admin login"}


def sdk_release() -> dict:
    """Versions on both ends of the SDK: the installed ingestion distribution and the server.

    The SDK works when the distribution matches the server version (here 2.0.5.x
    against server 2.0.5). Returns {"pkg", "server"}.
    """
    import importlib.metadata as _metadata

    pkg = _metadata.version("openmetadata-ingestion")
    server = client.get("/v1/system/version").get("version")
    return {"pkg": pkg, "server": server}
