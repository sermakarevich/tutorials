"""Chapter 02: set one column description and show it created a new entity version.

Idempotent: if the description is already set, it skips the PATCH and just
prints the version history. Run from project/:
uv run python -m openmetadata_tutorial.ch02_edit
"""

import json

from openmetadata_tutorial.client import api, get

FQN = "brightcup_pg.brightcup.raw.products"
COLUMN = "roast"
TEXT = "Roast level: light, medium or dark."


def column_index(table: dict, name: str = COLUMN) -> int:
    """Position of column `name` in `table["columns"]` (for index-based patch paths)."""
    for i, col in enumerate(table.get("columns", [])):
        if col.get("name") == name:
            return i
    raise ValueError(f"no column {name!r} in {[c.get('name') for c in table.get('columns', [])]}")


def patch_op(current: str) -> str:
    """JSON Patch op for setting the description: `add` when empty, `replace` otherwise."""
    return "replace" if current else "add"


def roast_rows(history: dict, column: str = COLUMN) -> list[tuple]:
    """One (version, updatedBy, roast description) row per stored version snapshot.

    `history` is the parsed body of `GET /v1/tables/{id}/versions`
    (`{"versions": [<entity JSON string>, ...]}`, newest first).
    """
    rows = []
    for snapshot in history.get("versions", []):
        entity = json.loads(snapshot)
        roast = next(c for c in entity["columns"] if c["name"] == column)
        rows.append((entity["version"], entity.get("updatedBy", "?"), roast.get("description", "")))
    return rows


def ensure_description(table: dict, text: str = TEXT, column: str = COLUMN) -> dict:
    """Patch `table`'s column description idempotently; return what main() should report.

    Returns {"action": "already-set" | "patched", "version": ...}: when the
    description already equals `text` no PATCH is sent (a no-op patch would
    mint no new version anyway); otherwise one PATCH sets it.
    """
    idx = column_index(table, column)
    current = table["columns"][idx].get("description", "")
    if current == text:
        return {"action": "already-set", "version": table["version"], "index": idx}
    patched = api(
        "PATCH",
        f"/v1/tables/{table['id']}",
        json=[{"op": patch_op(current), "path": f"/columns/{idx}/description", "value": text}],
    ).json()
    return {"action": "patched", "version": patched["version"], "index": idx}


def main() -> None:
    table = get(f"/v1/tables/name/{FQN}", fields="columns,version")
    result = ensure_description(table)
    if result["action"] == "already-set":
        print(f"description already set; version is {result['version']}")
    else:
        print(f"patched {FQN}.{COLUMN}; version is now {result['version']}")
    history = get(f"/v1/tables/{table['id']}/versions")
    print(f"{'version':<8} {'by':<15} roast description")
    for version, by, desc in roast_rows(history):
        print(f"{version:<8} {by:<15} {desc!r}")


if __name__ == "__main__":
    main()
