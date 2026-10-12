"""Chapter 09: data contract on analytics.daily_revenue (ODCS import + validation).

Idempotent: the ODCS import merges into the existing contract when re-run.
Run from project/: ``uv run python -m openmetadata_tutorial.ch09_contract <step>``
steps: import | import-odcs | print-odcs | link-quality | semantics | owner-check | upstream | validate | show

One step adds one thing: `import-odcs` merges the ODCS document (schema plus
the `odcsQualityRules` block) onto the table; `link-quality` links the
`daily_revenue_has_rows` test case as the runnable quality expectation;
`semantics` adds the two JSON-Logic ownership/description rules via API;
`owner-check` verifies the table owner the semantics rule reads; `upstream`
lists the failing tests on the tables `daily_revenue` is built from.
`import` runs all four setup steps in order (idempotent). `print-odcs`
prints the exact ODCS document `import-odcs` sends (no rollback involved).

The contract file lives next to this module's data: ingestion/ch09_contract.yaml
is avoided on purpose -- /v1/dataContracts/odcs/yaml takes an ODCS document,
not a workflow file. The ODCS text is below as CONTRACT_YAML so the chapter
prints exactly what it sends.
"""

import json
import sys

import requests

from openmetadata_tutorial import client

REVENUE_FQN = "brightcup_pg.brightcup.analytics.daily_revenue"

CONTRACT_YAML = """\
apiVersion: v3.1.0
kind: DataContract
name: daily_revenue-contract
status: active
description:
  purpose: Revenue and order count per day. Feeds the finance dashboard.
  usage: Finance dashboard reads analytics.daily_revenue every morning.
team:
  members:
    - username: Finance
      role: owner
schema:
  - name: daily_revenue
    logicalType: object
    properties:
      - name: order_date
        logicalType: date
        physicalType: DATE
        description: The business day (one row per day).
      - name: orders
        logicalType: integer
        physicalType: BIGINT
        description: Orders placed that day, excluding cancelled ones.
      - name: revenue
        logicalType: number
        physicalType: NUMERIC
        description: Sum of total_amount in EUR for that day.
    quality:
      - id: daily_revenue_has_rows
        name: Daily revenue has between 1 and 1000 rows
        metric: rowCount
        mustBeBetween: [1, 1000]
slaProperties:
  - property: freshness
    value: 1
    unit: d
    element: daily_revenue.order_date
"""


def revenue_table() -> dict:
    return client.get(f"/v1/tables/name/{REVENUE_FQN}")


def cmd_print_odcs() -> None:
    """Print the exact ODCS document `import-odcs` sends (CONTRACT_YAML)."""
    print(CONTRACT_YAML, end="")


def cmd_import_odcs() -> dict:
    """Merge the ODCS contract document onto daily_revenue.

    This step only brings schema columns plus the informational
    `odcsQualityRules` block. The linked-test-case count prints 0 on a fresh
    contract: linking the runnable test case is the next step's one thing.
    """
    from openmetadata_tutorial.config import settings as _settings

    s = _settings()
    table = revenue_table()
    r = requests.put(
        f"{s.om_api}/v1/dataContracts/odcs/yaml",
        params={"entityId": table["id"], "entityType": "table", "mode": "merge"},
        headers={"Authorization": f"Bearer {client.token(s)}",
                 "Content-Type": "application/yaml"},
        data=CONTRACT_YAML.encode(), timeout=60)
    r.raise_for_status()
    contract = r.json()
    print(f"contract: {contract['name']} ({contract['id']}) status={contract.get('entityStatus')}")
    print(f"  schema columns: {[c['name'] for c in contract.get('schema', [])]}")
    print(f"  odcsQualityRules: {len(contract.get('odcsQualityRules', []))}")
    print(f"  linked quality expectations: {len(contract.get('qualityExpectations', []))}")
    return contract


def cmd_import() -> dict:
    """Import the ODCS contract onto daily_revenue, one concern per step."""
    contract = cmd_import_odcs()
    ensure_contract_owner(contract)
    ensure_quality_link(contract)
    ensure_semantics(contract)
    final = client.get(f"/v1/dataContracts/{contract['id']}")
    table_now = client.get(f"/v1/tables/name/{REVENUE_FQN}?fields=owners")
    print(f"contract now: {len(final.get('schema', []))} schema columns, "
          f"{len(final.get('qualityExpectations', []))} quality expectation(s), "
          f"{len(final.get('semantics', []))} semantics rule(s), "
          f"table owners={[o.get('name') for o in table_now.get('owners', [])]}")
    return contract


def ensure_semantics(contract: dict) -> None:
    """Two metadata rules (JSON Logic): the asset must have an owner and a
    description. The ODCS file cannot express these, so they go in via API.
    """
    wanted = [
        {"name": "Owners is set",
         "description": "Every reporting table needs an owner.",
         "rule": '{"and":[{"some":[{"var":"owners"},{"!=":[{"var":"fullyQualifiedName"},null]}]}]}',
         "enabled": True},
        {"name": "Description is set",
         "description": "Every reporting table needs a description.",
         "rule": '{"and":[{"!=":[{"var":"description"},null]}]}',
         "enabled": True},
    ]
    full = client.get(f"/v1/dataContracts/{contract['id']}")
    have = {s.get("name") for s in full.get("semantics", [])}
    missing = [r for r in wanted if r["name"] not in have]
    if not missing:
        print("contract semantics: both rules already present")
        return
    client.api("PATCH", f"/v1/dataContracts/{contract['id']}",
               json=[{"op": "add", "path": "/semantics", "value": missing}])
    print(f"contract semantics: added {[r['name'] for r in missing]}")


def ensure_quality_link(contract: dict) -> None:
    tc = client.get(
        "/v1/dataQuality/testCases/name/"
        "brightcup_pg.brightcup.analytics.daily_revenue.daily_revenue_has_rows")
    full = client.get(f"/v1/dataContracts/{contract['id']}")
    if any(q.get("id") == tc["id"] for q in full.get("qualityExpectations", [])):
        print("contract quality: daily_revenue_has_rows already linked")
        return
    ref = {"id": tc["id"], "type": "testCase", "name": tc["name"],
           "fullyQualifiedName": tc["fullyQualifiedName"]}
    client.api("PATCH", f"/v1/dataContracts/{contract['id']}",
               json=[{"op": "add", "path": "/qualityExpectations", "value": [ref]}])
    print("contract quality: linked daily_revenue_has_rows")
    full = client.get(f"/v1/dataContracts/{contract['id']}")
    suite_id = (full.get("testSuite") or {}).get("id")
    if suite_id:
        # Runs execute the contract's own suite: the linked test must be a member.
        client.api("PUT", "/v1/dataQuality/testCases/logicalTestCases",
                   json={"testSuiteId": suite_id, "testCaseIds": [tc["id"]]})
        print("contract suite: test case added")


def ensure_contract_owner(contract: dict) -> None:
    """Ownership lives on the table, not on the contract object.

    Verified 2026-10-12: ``GET /v1/dataContracts/{id}`` has no ``owners``
    field at all (a PUT *response* echoes them, a later GET drops them).
    The ODCS ``team:`` block is informational; what the "Owners is set"
    semantics rule checks is the table's owners -- set by ch09_access setup.
    So this step only checks the table.
    """
    table = client.get(f"/v1/tables/name/{REVENUE_FQN}?fields=owners")
    team = client.get("/v1/teams/name/Finance")
    if any(o.get("id") == team["id"] for o in table.get("owners", [])):
        print("contract owner: Finance owns daily_revenue (on the table)")
    else:
        print("contract owner: MISSING on daily_revenue -- run ch09_access setup")


def current_contract() -> dict:
    """The contract on daily_revenue (fresh GET), or exit with a hint."""
    contracts = client.get("/v1/dataContracts?limit=100").get("data", [])
    table = revenue_table()
    contract = next((c for c in contracts if c.get("entity", {}).get("id") == table["id"]), None)
    if contract is None:
        raise SystemExit("no contract on daily_revenue yet; run import-odcs first")
    return client.get(f"/v1/dataContracts/{contract['id']}")


def cmd_link_quality() -> None:
    """Link the daily_revenue row-count test as the runnable quality expectation.

    The ODCS `quality:` block arrives as informational `odcsQualityRules` only;
    validation executes the contract's own test suite, so the test case must
    be linked here (created by `just ingest ch09_daily_revenue_quality test`).
    """
    ensure_quality_link(current_contract())


def cmd_semantics() -> None:
    """Add the two JSON-Logic rules the ODCS file cannot express."""
    ensure_semantics(current_contract())


def cmd_owner_check() -> None:
    """Verify the table owner the 'Owners is set' rule reads."""
    ensure_contract_owner(current_contract())


UPSTREAM_TABLES = [
    "brightcup_pg.brightcup.raw.orders",
    "brightcup_pg.brightcup.raw.customers",
]


def upstream_failures() -> list:
    """Failing test cases on the tables daily_revenue is built from.

    Same query as chapter 07's results table (latest result of every test
    case whose FQN starts with the table). Returns one row per failing test:
    table, test, definition, message. Pure data (no printing) for tests.
    """
    r = client.get("/v1/dataQuality/testCases", limit=100,
                   fields="testCaseResult,testDefinition")
    rows = []
    for t in r.get("data", []):
        fqn = str(t.get("fullyQualifiedName", ""))
        table = next((u for u in UPSTREAM_TABLES if fqn.startswith(u + ".")), None)
        if table is None:
            continue
        if ((t.get("testCaseResult") or {}).get("testCaseStatus")) != "Failed":
            continue
        rows.append({
            "table": table.split(".")[-1],
            "test": t.get("name"),
            "definition": (t.get("testDefinition") or {}).get("name"),
            "message": (t.get("testCaseResult") or {}).get("result"),
        })
    return sorted(rows, key=lambda d: (d["table"], d["test"]))


def cmd_upstream() -> None:
    """Print the failing upstream tests the contract stays green through."""
    for row in upstream_failures():
        print(f"{row['table']}.{row['test']}: Failed ({row['definition']}) -- {row['message']}")
    if not upstream_failures():
        print("no failing upstream tests right now")


def validation_summary(result: dict) -> dict:
    """Per-section pass counts of a contract validation result.

    Pure function (no I/O) so tests can check the exact numbers the prose
    relies on: schema 3/3 columns, semantics 2/2 rules, quality 1 passed /
    0 failed of 1 total. A mid-run (`Running`) result has no quality section
    yet -- quality comes back as None, which the caller prints as-is.
    """
    schema = result.get("schemaValidation") or {}
    sem = result.get("semanticsValidation") or {}
    return {
        "status": result.get("contractExecutionStatus"),
        "schema": (schema.get("passed"), schema.get("total")),
        "semantics": (sem.get("passed"), sem.get("total")),
        "quality": result.get("qualityValidation"),
        "note": (result.get("result") or "")[:200],
    }


def cmd_validate() -> dict:
    """Run validation now and print the per-section result.

    The quality section runs as an Airflow pipeline, so the POST returns
    `Running` with no quality section yet (printed as `quality: null` while
    in flight). This polls `/results/latest` to the final state (up to
    ~5 minutes); if the server is still busy afterwards it prints the
    in-flight state plus what to do instead of pretending it finished.
    The first trigger after a (re)deploy occasionally fails with "Failed to
    trigger IngestionPipeline": retry once in that case.
    """
    import time

    contracts = client.get("/v1/dataContracts?limit=100").get("data", [])
    table = revenue_table()
    contract = next((c for c in contracts if c.get("entity", {}).get("id") == table["id"]), None)
    if contract is None:
        raise SystemExit("no contract on daily_revenue yet; run import first")
    result = client.api("POST", f"/v1/dataContracts/{contract['id']}/validate").json()
    if result.get("contractExecutionStatus") == "Aborted" and "Failed to trigger" in (result.get("result") or ""):
        print("validation trigger missed Airflow once; retrying...")
        time.sleep(10)
        result = client.api("POST", f"/v1/dataContracts/{contract['id']}/validate").json()
    for _ in range(30):
        if result.get("contractExecutionStatus") not in ("Running", "Queued"):
            break
        time.sleep(10)
        result = client.get(f"/v1/dataContracts/{contract['id']}/results/latest")
    summary = validation_summary(result)
    print(f"validation: {summary['status']}")
    if summary["status"] in ("Running", "Queued"):
        print("  (still queued in Airflow after ~5 min of polling; "
              "wait a little and re-run validate)")
    print(f"  schema: {summary['schema'][0]}/{summary['schema'][1]} columns passed")
    print(f"  semantics: {summary['semantics'][0]}/{summary['semantics'][1]} rules passed")
    print(f"  quality: {json.dumps(summary['quality'])}")
    if summary["note"]:
        print(f"  note: {summary['note']}")
    return result


def cmd_show() -> None:
    contracts = client.get("/v1/dataContracts?limit=100").get("data", [])
    table = revenue_table()
    contract = next((c for c in contracts if c.get("entity", {}).get("id") == table["id"]), None)
    if contract is None:
        print("no contract on daily_revenue")
        return
    full = client.get(f"/v1/dataContracts/{contract['id']}")
    table = client.get(f"/v1/tables/name/{REVENUE_FQN}?fields=owners")
    print(json.dumps({
        "name": full.get("name"), "entityStatus": full.get("entityStatus"),
        "entity": REVENUE_FQN,
        "tableOwners": [o.get("name") for o in table.get("owners", [])],
        "schema": [(c.get("name"), c.get("dataType")) for c in full.get("schema", [])],
        "semantics": [s.get("name") for s in full.get("semantics", [])],
        "qualityExpectations": [q.get("name") for q in full.get("qualityExpectations", [])],
        "latestResult": full.get("latestResult"),
    }, indent=1))


def main(argv: list[str]) -> None:
    step = argv[1] if len(argv) > 1 else "import"
    {"import": cmd_import, "import-odcs": cmd_import_odcs,
     "print-odcs": cmd_print_odcs,
     "link-quality": cmd_link_quality, "semantics": cmd_semantics,
     "owner-check": cmd_owner_check, "upstream": cmd_upstream,
     "validate": cmd_validate, "show": cmd_show}[step]()


if __name__ == "__main__":
    main(sys.argv)
