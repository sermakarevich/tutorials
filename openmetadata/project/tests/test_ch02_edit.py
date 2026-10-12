"""Chapter 02 checks: the idempotent description patch and the version listing it prints."""

import json

import pytest

from openmetadata_tutorial import ch02_edit as E


def test_patch_op_add_when_empty_replace_otherwise():
    assert E.patch_op("") == "add"
    assert E.patch_op("something") == "replace"


def test_column_index_finds_roast():
    table = {"columns": [{"name": "product_id"}, {"name": "roast"}, {"name": "sku"}]}
    assert E.column_index(table) == 1
    with pytest.raises(ValueError):
        E.column_index({"columns": [{"name": "sku"}]})


def test_roast_rows_parses_versions_newest_first():
    def snap(version, desc):
        return json.dumps({"version": version, "updatedBy": "ingestion-bot", "columns": [{"name": "roast", "description": desc}]}, separators=(",", ":"))

    history = {"versions": [snap("0.3", E.TEXT), snap("0.2", ""), snap("0.1", "")]}
    assert E.roast_rows(history) == [("0.3", "ingestion-bot", E.TEXT), ("0.2", "ingestion-bot", ""), ("0.1", "ingestion-bot", "")]


def test_ensure_description_skips_patch_when_already_set(monkeypatch):
    table = {"id": "eid", "version": "0.3", "columns": [{"name": "roast", "description": E.TEXT}]}
    monkeypatch.setattr(E, "api", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no PATCH on no-op")))
    assert E.ensure_description(table) == {"action": "already-set", "version": "0.3", "index": 0}


def test_ensure_description_patches_once_then_reports_set(monkeypatch):
    table = {"id": "eid", "version": "0.2", "columns": [{"name": "roast", "description": ""}]}
    calls = []

    class R:
        def json(self):
            return {"version": "0.3"}

    def fake_api(method, path, **kwargs):
        calls.append((method, path, kwargs["json"]))
        return R()

    monkeypatch.setattr(E, "api", fake_api)
    assert E.ensure_description(table) == {"action": "patched", "version": "0.3", "index": 0}
    assert calls == [("PATCH", "/v1/tables/eid", [{"op": "add", "path": "/columns/0/description", "value": E.TEXT}])]


@pytest.mark.stack
def test_stack_rerun_is_a_noop_and_history_shows_three_versions():
    from openmetadata_tutorial.client import get

    table = get(f"/v1/tables/name/{E.FQN}", fields="columns,version")
    before = table["version"]
    assert E.ensure_description(table)["action"] == "already-set"
    assert get(f"/v1/tables/name/{E.FQN}", fields="version")["version"] == before
    rows = E.roast_rows(get(f"/v1/tables/{table['id']}/versions"))
    assert len(rows) >= 3
    assert rows[0][2] == E.TEXT  # only the newest version carries the text
    assert all(desc in ("", E.TEXT) for _, _, desc in rows)
