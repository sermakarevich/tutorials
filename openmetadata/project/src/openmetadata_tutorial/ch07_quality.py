"""Data quality for chapter 07: profiles, test definitions, results, history, incidents.

All reads go through ``openmetadata_tutorial.client`` (bot JWT from ``.env``).
Every write is idempotent where the server allows it; the notebook shows the
real outputs of each call against the Brightcup shop database.
"""

import time
import subprocess
import urllib.parse

import pandas as pd
import yaml

from openmetadata_tutorial import client
from openmetadata_tutorial.config import project_root

ORDERS = "brightcup_pg.brightcup.raw.orders"
CUSTOMERS = "brightcup_pg.brightcup.raw.customers"
PRODUCTS = "brightcup_pg.brightcup.raw.products"

_DAY_MS = 24 * 3600 * 1000


def table_summary(table_fqn: str) -> dict:
    """Table-level profile of `table_fqn`: row count, column count, size, sample.

    Comes from ``GET /v1/tables/<FQN>/tableProfile/latest`` (the verified path
    in 2.0.5: ``.../name/<FQN>/tableProfile/latest`` answers 404, and
    ``fields=profile,columns`` returns a null profile).
    """
    r = client.get(f"/v1/tables/{table_fqn}/tableProfile/latest")
    p = r.get("profile") or {}
    return {
        "table": table_fqn,
        "rowCount": p.get("rowCount"),
        "columnCount": p.get("columnCount"),
        "sizeInByte": p.get("sizeInByte"),
        "sample_percent": p.get("profileSample"),
        "how": "GET /v1/tables/<FQN>/tableProfile/latest",
    }


def profile(table_fqn: str) -> pd.DataFrame:
    """One row per column: nulls, distinct and unique counts, min, max.

    Same endpoint as :func:`table_summary`; the column statistics live on each
    column's ``profile`` object.
    """
    r = client.get(f"/v1/tables/{table_fqn}/tableProfile/latest")
    rows = []
    for c in r.get("columns", []):
        p = c.get("profile") or {}
        rows.append(
            {
                "column": c.get("name"),
                "nullCount": p.get("nullCount"),
                "distinctCount": p.get("distinctCount"),
                "uniqueCount": p.get("uniqueCount"),
                "min": p.get("min"),
                "max": p.get("max"),
            }
        )
    return pd.DataFrame(
        rows, columns=["column", "nullCount", "distinctCount", "uniqueCount", "min", "max"]
    )


def definitions() -> pd.DataFrame:
    """The 25 built-in test definitions: name, level (TABLE/COLUMN), supported types.

    ``GET /v1/dataQuality/testDefinitions?limit=100``. Check
    ``supportedDataTypes`` before writing a test: an unsupported column type
    fails at run time or is skipped.
    """
    r = client.get("/v1/dataQuality/testDefinitions", limit=100)
    rows = [
        {
            "name": d.get("name"),
            "entityType": d.get("entityType"),
            "supportedDataTypes": ", ".join(d.get("supportedDataTypes") or []),
        }
        for d in r.get("data", [])
    ]
    return pd.DataFrame(rows, columns=["name", "entityType", "supportedDataTypes"]).sort_values(
        ["entityType", "name"]
    ).reset_index(drop=True)


def results(table_fqn: str) -> pd.DataFrame:
    """Latest result of every test case on one table: test, definition, status, message.

    Test cases on a column carry the column in their FQN, e.g.
    ``...raw.orders.order_id.orders_order_id_unique``. The server's
    ``entityLink``/``entityFQN`` filters only return table-level cases in
    2.0.5, so this lists and keeps every case whose FQN starts with the table.
    """
    r = client.get("/v1/dataQuality/testCases", limit=100, fields="testCaseResult,testDefinition")
    rows = []
    for t in r.get("data", []):
        if not str(t.get("fullyQualifiedName", "")).startswith(table_fqn + "."):
            continue
        tc = t.get("testCaseResult") or {}
        rows.append(
            {
                "test": t.get("name"),
                "definition": (t.get("testDefinition") or {}).get("name"),
                "status": tc.get("testCaseStatus"),
                "message": tc.get("result"),
            }
        )
    return pd.DataFrame(rows, columns=["test", "definition", "status", "message"]).sort_values(
        "test"
    ).reset_index(drop=True)


def history(test_case_fqn: str, days: int = 7) -> pd.DataFrame:
    """Every recorded result of one test case, oldest first.

    ``GET /v1/dataQuality/testCases/testCaseResults/<testCaseFQN>`` with a
    millisecond ``startTs``/``endTs`` window. ``failedRows`` is filled only by
    definitions that report row counts (a null-count failure, for example,
    carries its number in the message instead, with ``failedRows`` None).
    """
    now_ms = int(time.time() * 1000)
    r = client.get(
        f"/v1/dataQuality/testCases/testCaseResults/{test_case_fqn}",
        startTs=now_ms - days * _DAY_MS,
        endTs=now_ms,
    )
    rows = [
        {
            "timestamp": pd.to_datetime(h.get("timestamp"), unit="ms"),
            "status": h.get("testCaseStatus"),
            "failedRows": h.get("failedRows"),
            "message": h.get("result"),
        }
        for h in r.get("data", [])
    ]
    return pd.DataFrame(rows, columns=["timestamp", "status", "failedRows", "message"]).sort_values(
        "timestamp"
    ).reset_index(drop=True)


def incidents() -> pd.DataFrame:
    """Every recorded incident transition: which test, its status, who, and when.

    ``GET /v1/dataQuality/testCases/testCaseIncidentStatus``. The list only
    grows: one row per transition, oldest first — a failed test opens an
    incident in status ``New`` and people (or the catalog, for owned tables)
    move it ``New -> Ack -> Assigned -> Resolved``. The last row per test case
    is its current state. ``assignee`` names the team/user on Assigned rows.
    """
    r = client.get("/v1/dataQuality/testCases/testCaseIncidentStatus", limit=100)
    rows = []
    user_names: dict[str, str] = {}
    for d in r.get("data", []):
        det = d.get("testCaseResolutionStatusDetails") or {}
        who = det.get("assignee") or {}
        assignee = who.get("name") or ""
        if not assignee and who.get("type") == "user" and who.get("id"):
            # Assignments made by user id carry no name; resolve it once per id
            # (otherwise the table fills with opaque "(user)" rows).
            uid = who["id"]
            if uid not in user_names:
                try:
                    user_names[uid] = client.get(f"/v1/users/{uid}").get("name") or uid
                except Exception:
                    user_names[uid] = uid
            assignee = user_names[uid]
        rows.append(
            {
                "testCase": (d.get("testCaseReference") or {}).get("fullyQualifiedName"),
                "status": d.get("testCaseResolutionStatusType"),
                "assignee": assignee or (f"({who['type']})" if who else ""),
                "updatedBy": (d.get("updatedBy") or {}).get("name"),
                "timestamp": pd.to_datetime(d.get("timestamp"), unit="ms"),
            }
        )
    df = pd.DataFrame(rows, columns=["testCase", "status", "assignee", "updatedBy", "timestamp"])
    return df.sort_values(["testCase", "timestamp"]).reset_index(drop=True)


def _user_id(name: str) -> str:
    return client.get(f"/v1/users/name/{name}")["id"]


def set_incident(
    test_case_fqn: str, status: str, assignee: str | None = None, reason: str | None = None
) -> dict:
    """Move a test case's incident to `status` (Ack, Assigned or Resolved).

    ``POST /v1/dataQuality/testCases/testCaseIncidentStatus`` with the test
    case FQN as ``testCaseReference``. ``Assigned`` needs ``assignee`` (a user
    name, e.g. ``"admin"``); ``Resolved`` needs ``reason`` (one of
    FalsePositive, MissingData, Duplicates, OutOfBounds, Other) and a comment
    is stored with it. Returns the created status object.
    """
    body: dict = {"testCaseReference": test_case_fqn, "testCaseResolutionStatusType": status}
    if status == "Assigned":
        if not assignee:
            raise ValueError("assignee is required for status Assigned")
        body["testCaseResolutionStatusDetails"] = {
            "assignee": {"id": _user_id(assignee), "type": "user"}
        }
    if status == "Resolved":
        if not reason:
            raise ValueError("reason is required for status Resolved")
        body["testCaseResolutionStatusDetails"] = {
            "testCaseFailureReason": reason,
            "testCaseFailureComment": f"Resolved from the 07_data_quality chapter ({reason}).",
        }
    r = client.api("POST", "/v1/dataQuality/testCases/testCaseIncidentStatus", json=body)
    return r.json()


def test_case(name: str, table_fqn: str = CUSTOMERS) -> dict:
    """Fetch one test case by short name (e.g. ``customers_email_not_null``).

    Column-level cases carry the column in their FQN, so this matches by the
    trailing name instead of building the FQN by hand.
    """
    r = client.get("/v1/dataQuality/testCases", limit=100)
    for t in r.get("data", []):
        if t.get("name") == name and str(t.get("fullyQualifiedName", "")).startswith(table_fqn + "."):
            return t
    raise KeyError(f"no test case {name!r} on {table_fqn}")


def delete_test_case(test_id: str) -> None:
    """Hard-delete one test case by id (removing it from YAML does not do this).

    ``recursive=true`` is required in 2.0.5: without it the server answers 400,
    because the case is still linked from its test suite. Deleting the case
    also removes its history points and its incident rows.
    """
    client.api("DELETE", f"/v1/dataQuality/testCases/{test_id}?hardDelete=true&recursive=true")


def run_workflow(name: str = "ch07_customers_quality", command: str = "test", tail_n: int = 6) -> str:
    """Run one ingestion workflow (`just ingest <name> <command>`) and return its tail.

    The workflow runs inside the ingestion container; ``just`` prints the
    recipe line on stdout but the metadata CLI's own log (including the
    ``Workflow Success %`` summary) arrives on stderr, so this tails the two
    streams combined. Raises if the workflow exits non-zero.
    """
    r = subprocess.run(
        ["just", "ingest", name, command],
        cwd=project_root(),
        capture_output=True,
        text=True,
    )
    combined = (r.stdout or "") + "\n" + (r.stderr or "")
    lines = [ln for ln in combined.splitlines() if ln.strip()]
    tail = "\n".join(lines[-tail_n:])
    if r.returncode != 0:
        raise AssertionError(f"`just ingest {name} {command}` failed:\n{tail}")
    return tail


def sql(query: str) -> str:
    """Run one read-only query against the shop database and return what it printed.

    This is the same ``just sql "<query>"`` the chapter cites (docker exec
    into ``om-tutorial-shopdb`` as ``shop_admin``); its table output arrives
    on stdout.
    """
    r = subprocess.run(
        ["just", "sql", query], cwd=project_root(), capture_output=True, text=True
    )
    if r.returncode != 0:
        raise AssertionError(f"`just sql` failed: {(r.stderr or '')[-500:]}")
    return (r.stdout or "").strip()


def yaml_case_params(yaml_name: str, case_name: str) -> dict:
    """Read one test case's live parameters back from a workflow YAML file.

    Returns ``{"forceUpdate": ..., "params": {name: value}}`` parsed from
    ``project/ingestion/<yaml_name>`` — what the file *actually* says, so a
    cell can compare it against what the catalog holds.
    """
    text = (project_root() / "ingestion" / yaml_name).read_text()
    doc = yaml.safe_load(text)
    cfg = doc["processor"]["config"]
    params = {}
    for t in cfg.get("testCases", []):
        if t.get("name") == case_name:
            params = {p["name"]: p["value"] for p in t.get("parameterValues", [])}
    return {"forceUpdate": cfg.get("forceUpdate"), "params": params}


def create_test_case(
    name: str,
    entity_link: str,
    definition: str,
    parameters: dict | None = None,
    compute_rows: bool = False,
) -> dict:
    """Write one test case through the REST API (no YAML involved).

    ``POST /v1/dataQuality/testCases`` with the test *definition name* as a
    string (e.g. ``"columnValuesToBeNotNull"`` — an EntityReference id answers
    400 in 2.0.5). The new case joins the table's basic suite, so the next
    ``TestSuite`` workflow run executes it. ``compute_rows=True`` stores
    passed/failed row counts and the failed-rows sample with each result.
    Returns the created test case (id, name, fullyQualifiedName).
    """
    body: dict = {"name": name, "entityLink": entity_link, "testDefinition": definition}
    if parameters:
        body["parameterValues"] = [{"name": k, "value": v} for k, v in parameters.items()]
    if compute_rows:
        body["computePassedFailedRowCount"] = True
    r = client.api("POST", "/v1/dataQuality/testCases", json=body)
    created = r.json()
    return {
        "id": created["id"],
        "name": created["name"],
        "fullyQualifiedName": created["fullyQualifiedName"],
    }


def ensure_deleted(name: str, table_fqn: str = CUSTOMERS) -> bool:
    """Hard-delete the throwaway test case `name` on `table_fqn` if it exists.

    Makes demo sections re-runnable: a fresh case means fresh history (exactly
    the points this run appends) and, for unowned tables, a fresh incident in
    status New. Returns True when something was deleted.
    """
    try:
        case_id = test_case(name, table_fqn)["id"]
    except KeyError:
        return False
    delete_test_case(case_id)
    return True


def failed_rows_sample(test_case_id: str, limit: int = 5) -> pd.DataFrame:
    """The failed-rows sample of one test case: actual failing rows, as a table.

    ``GET /v1/dataQuality/testCases/<id>/failedRowsSample``. Only cases
    created with row-count computation (``computePassedFailedRowCount``) store
    a sample; otherwise the server answers 404. One DataFrame row per failing
    row, first `limit` rows.
    """
    r = client.get(f"/v1/dataQuality/testCases/{test_case_id}/failedRowsSample")
    return pd.DataFrame(r.get("rows", []), columns=r.get("columns", [])).head(limit)


def history_trend(test_case_fqn: str, days: int = 7, last_n: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Results over time, summarized: counts per status plus the last few runs.

    Returns ``(counts, recent)`` where ``counts`` is one row per status
    (``status``, ``runs``) and ``recent`` is the last `last_n` points of
    :func:`history` (timestamp, status, failedRows, message). A wall of
    identical Failures reads as a source bug; a single Failed among Successes
    reads as a one-off.
    """
    h = history(test_case_fqn, days=days)
    counts = (
        h["status"].value_counts().rename_axis("status").reset_index(name="runs")
        if len(h)
        else pd.DataFrame(columns=["status", "runs"])
    )
    recent = h.tail(last_n).reset_index(drop=True) if len(h) else h
    return counts, recent


def current_incidents(table_like: str = "raw.customers") -> pd.DataFrame:
    """The reproducible incident view: one row per test case — its current state.

    The full transition list only grows (every authoring click appends rows),
    so this keeps the last row per test case (status, assignee, who moved it
    last, when). Filtered to test cases whose FQN contains `table_like`.
    """
    inc = incidents()
    cus = inc[inc["testCase"].str.contains(table_like, na=False)]
    if not len(cus):
        return pd.DataFrame(columns=["test", "status", "assignee", "updatedBy", "timestamp"])
    last = cus.loc[cus.groupby("testCase")["timestamp"].idxmax()].copy()
    last["test"] = last["testCase"].str.split(".").str[-1]
    return last[["test", "status", "assignee", "updatedBy", "timestamp"]].sort_values(
        "test"
    ).reset_index(drop=True)


def table_owners(table_fqn: str) -> pd.DataFrame:
    """Who owns `table_fqn`: the catalog's ``owners`` field, as a table.

    ``GET /v1/tables/name/<FQN>?fields=owners``. Owners decide incident
    routing: a failing test on an owned table is auto-assigned to the owner.
    """
    t = client.get(f"/v1/tables/name/{table_fqn}", fields="owners")
    rows = [
        {"name": o.get("name"), "type": o.get("type"), "description": o.get("description")}
        for o in (t.get("owners") or [])
    ]
    return pd.DataFrame(rows, columns=["name", "type", "description"])


def suites() -> pd.DataFrame:
    """Every test suite in the catalog: basic (one per table) and logical.

    ``GET /v1/dataQuality/testSuites``. A *basic* suite (``basic: True``)
    holds one table's cases and is what the ``TestSuite`` workflow runs; a
    *logical* suite (``basic: False``) groups cases across tables — e.g. the
    ``Data Contract - daily_revenue-contract`` suite chapter 09's contract
    created. Same cases, different grouping.
    """
    r = client.get("/v1/dataQuality/testSuites", limit=100)
    rows = [
        {
            "suite": d.get("displayName") or d.get("name"),
            "basic": d.get("basic"),
            "description": d.get("description") or "",
        }
        for d in r.get("data", [])
    ]
    return pd.DataFrame(rows, columns=["suite", "basic", "description"]).sort_values(
        ["basic", "suite"], ascending=[False, True]
    ).reset_index(drop=True)


def deleted_case_traces(test_case_fqn: str) -> dict:
    """What is left of test case `test_case_fqn`: history points and incident rows.

    After a hard delete the ``testCaseResults/<FQN>`` endpoint answers 404
    (no points) and the incident list holds no rows for the FQN — deleting
    the case removes its history points and its incident rows with it.
    Returns ``{"history": ..., "incident_rows": ...}`` for the notebook to
    print, so the claim is shown, not asserted.
    """
    try:
        h = history(test_case_fqn)
        hist: str = f"{len(h)} points"
    except Exception:
        hist = "gone (404: no points)"
    inc = incidents()
    rows = int((inc["testCase"] == test_case_fqn).sum()) if len(inc) else 0
    return {"history": hist, "incident_rows": rows}


def status_plot_svg(test_case_fqn: str, days: int = 7, width: int = 640, height: int = 180) -> str:
    """A dependency-free status-over-runs plot of one test case, as an SVG string.

    One dot per recorded result, oldest first: Failed draws at the top,
    Success at the bottom, joined by a step line. The notebook displays it
    with ``IPython.display.SVG`` — no chart library ships with this project,
    so the SVG (plain string, no new dependency) stands in for the
    status/failed-rows plot the results-over-time section needs. Returns the
    SVG document (the cell prints its point counts alongside).
    """
    h = history(test_case_fqn, days=days)
    n = len(h)
    if n == 0:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="60">'
            '<text x="10" y="30" font-size="13">no recorded results</text></svg>'
        )
    ys = [1 if s == "Failed" else 0 for s in h["status"]]
    pad_l, pad_r, pad_t, pad_b = 70, 15, 18, 30
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    xs = [pad_l + (i / (n - 1)) * iw if n > 1 else pad_l + iw / 2 for i in range(n)]
    y_of = lambda v: pad_t + (1 - v) * ih  # Failed (1) at top, Success (0) at bottom
    pts = " ".join(f"{x:.1f},{y_of(v):.1f}" for x, v in zip(xs, ys))
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y_of(v):.1f}" r="4" fill="{"#c0392b" if v else "#1e8449"}"/>'
        for x, v in zip(xs, ys)
    )
    first = str(h["timestamp"].iloc[0])[:16]
    last = str(h["timestamp"].iloc[-1])[:16]
    short = test_case_fqn.split(".")[-1]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
        f'<text x="{pad_l}" y="14" font-size="13">{short}: {n} runs '
        f'({sum(ys)} Failed, {n - sum(ys)} Success)</text>'
        f'<line x1="{pad_l}" y1="{y_of(1)}" x2="{width - pad_r}" y2="{y_of(1)}" stroke="#ddd"/>'
        f'<line x1="{pad_l}" y1="{y_of(0)}" x2="{width - pad_r}" y2="{y_of(0)}" stroke="#ddd"/>'
        f'<text x="8" y="{y_of(1) + 4}" font-size="11">Failed</text>'
        f'<text x="8" y="{y_of(0) + 4}" font-size="11">Success</text>'
        f'<polyline points="{pts}" fill="none" stroke="#555" stroke-width="1.5"/>'
        f"{dots}"
        f'<text x="{pad_l}" y="{height - 8}" font-size="11">{first}</text>'
        f'<text x="{width - pad_r - 110}" y="{height - 8}" font-size="11">{last}</text>'
        "</svg>"
    )


def capture_incident_screenshot(
    path: str,
    out: str = "assets/07_incident.png",
    wait_text: str | None = None,
    tries: int = 3,
) -> str:
    """Save a UI screenshot, retrying the login/navigation a few times.

    The notebook kernel shares its event loop, and a cold server answers
    slowly: a single ``Page.goto``/signin can exceed Playwright's default
    30 s timeout. This retries ``screenshots.capture`` up to `tries` times
    (5 s between attempts) and returns the saved path; the last error is
    raised when every attempt fails.
    """
    from openmetadata_tutorial import screenshots

    last: Exception | None = None
    for _ in range(tries):
        try:
            return screenshots.capture(path, out, wait_text)
        except Exception as e:  # noqa: BLE001 — retried below, raised after tries
            last = e
            time.sleep(5)
    assert last is not None
    raise last
