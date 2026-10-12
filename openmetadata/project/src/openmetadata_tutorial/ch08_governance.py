"""Chapter 08 — governance helpers: owners, tiers, tags, glossary, domains, data products.

Every function is idempotent: running it twice changes nothing the second
time (PUT is create-or-update; PATCH first checks the current state).
Notebook cells call one or two of these and print what came back.
"""

from __future__ import annotations

import pandas as pd

from openmetadata_tutorial import client

SERVICE = "brightcup_pg"
RAW = f"{SERVICE}.brightcup.raw"
ANALYTICS = f"{SERVICE}.brightcup.analytics"

#: The seven Brightcup assets the governance report covers.
ALL_ASSETS = [
    f"{RAW}.customers",
    f"{RAW}.products",
    f"{RAW}.orders",
    f"{RAW}.order_items",
    f"{ANALYTICS}.fct_orders",
    f"{ANALYTICS}.daily_revenue",
    f"{ANALYTICS}.customer_ltv",
]

DAILY_REVENUE = f"{ANALYTICS}.daily_revenue"
CUSTOMERS = f"{RAW}.customers"
ORDERS = f"{RAW}.orders"


# ---------------------------------------------------------------- teams/users
def ensure_team(name: str, parent: str | None = None, description: str = "",
                team_type: str = "Group") -> dict:
    """Return the team `name`, creating it (PUT) only when missing.

    New Group teams appear under `Organization` automatically in 2.0.5
    (observed: `parents` is `[Organization]` after create). `parent` is
    reserved for an explicit parent and reported in `_how`; the chapter
    does not use it. Existing teams are returned untouched, so re-runs
    never overwrite another writer's edits.
    """
    try:
        team = client.get(f"/v1/teams/name/{name}")
        team["_how"] = "reused"
        return team
    except Exception:
        pass
    body = {"name": name, "displayName": name, "description": description,
            "teamType": team_type}
    team = client.api("PUT", "/v1/teams", json=body).json()
    team["_how"] = "created" + (f" (parent '{parent}' requested)" if parent else "")
    return team


def ensure_user(name: str, email: str, teams: list[str] | tuple[str, ...] = (),
                description: str = "") -> dict:
    """Return the user `name`, creating them only when missing.

    Team membership is additive: existing users keep their teams and gain
    any of `teams` they lack, so re-runs never remove memberships set
    elsewhere (e.g. by chapter 09).
    """
def _team_side_membership(user_id: str) -> list[str]:
    """Team names that list `user_id` in their users (the authoritative side).

    In 2.0.5 `GET /v1/users/name/...` returns `teams: []` even right after
    a PUT that the team itself records (observed) — so membership is read
    from the teams, not the user.
    """
    teams = client.get("/v1/teams", limit=100, fields="users")
    return [t["name"] for t in teams["data"]
            if any(u["id"] == user_id for u in t.get("users", []))]


def ensure_user(name: str, email: str, teams: list[str] | tuple[str, ...] = (),
                description: str = "") -> dict:
    """Return the user `name`, creating them only when missing.

    Team membership is additive and verified on the team side (see
    `_team_side_membership`): existing memberships — e.g. ones chapter 09
    adds — are kept, never replaced.
    """
    try:
        user = client.get(f"/v1/users/name/{name}")
    except Exception:
        user = None
    if user is None:
        body = {"name": name, "displayName": name.replace(".", " ").title(),
                "email": email, "description": description,
                "teams": [client.get(f"/v1/teams/name/{t}")["id"] for t in teams]}
        user = client.api("PUT", "/v1/users", json=body).json()
        user["_how"] = "created"
        user["_teams"] = _team_side_membership(user["id"])
        return user
    have = _team_side_membership(user["id"])
    missing = [t for t in teams if t not in have]
    if not missing:
        user["_how"] = "reused"
        user["_teams"] = have
        return user
    want = have + missing
    body = {"name": name, "displayName": user.get("displayName") or name,
            "email": user.get("email") or email,
            "description": user.get("description") or description,
            "teams": [client.get(f"/v1/teams/name/{t}")["id"] for t in want]}
    user = client.api("PUT", "/v1/users", json=body).json()
    user["_how"] = f"reused (joined {', '.join(missing)})"
    user["_teams"] = _team_side_membership(user["id"])
    return user


# ---------------------------------------------------------------- owners/tiers
def _table(fqn: str, fields: str = "owners,tags") -> dict:
    return client.get(f"/v1/tables/name/{fqn}", fields=fields)


def owners_of(fqn: str) -> list[str]:
    """Owner names of a table or view."""
    return [o.get("fullyQualifiedName", o["name"]) for o in _table(fqn, "owners").get("owners", [])]


def set_owners(fqn: str, team: str) -> tuple[list[str], str]:
    """Make `team` an owner of `fqn` (keeps existing owners). Returns (owners, how)."""
    current = _table(fqn, "owners").get("owners", [])
    if any(o["name"] == team for o in current):
        return ([o.get("fullyQualifiedName", o["name"]) for o in current], "already owner")
    tid = client.get(f"/v1/teams/name/{team}")["id"]
    refs = [{"id": o["id"], "type": o["type"]} for o in current] + [{"id": tid, "type": "team"}]
    updated = client.api("PATCH", f"/v1/tables/name/{fqn}",
                         json=[{"op": "replace", "path": "/owners", "value": refs}]).json()
    return ([o.get("fullyQualifiedName", o["name"]) for o in updated.get("owners", [])], "owner added")


def tier_of(fqn: str) -> str | None:
    """The Tier tag on `fqn`, e.g. 'Tier.Tier1', or None."""
    for t in _table(fqn, "tags").get("tags", []):
        if t["tagFQN"].startswith("Tier."):
            return t["tagFQN"]
    return None


def set_tier(fqn: str, tier: str) -> tuple[str | None, str]:
    """Set the Tier tag (`Tier` is mutually exclusive: one value only)."""
    want = tier if tier.startswith("Tier.") else f"Tier.{tier}"
    tags = _table(fqn, "tags").get("tags", [])
    if any(t["tagFQN"] == want for t in tags):
        return (want, "already set")
    kept = [t for t in tags if not t["tagFQN"].startswith("Tier.")]
    kept.append({"tagFQN": want, "source": "Classification",
                 "labelType": "Manual", "state": "Confirmed"})
    client.api("PATCH", f"/v1/tables/name/{fqn}",
               json=[{"op": "replace", "path": "/tags", "value": kept}])
    return (want, "tier set")


def tier_search(tier: str) -> tuple[list[str], str]:
    """FQNs carrying a Tier tag, via a search query_filter on tier.tagFQN."""
    import json as _json

    want = tier if tier.startswith("Tier.") else f"Tier.{tier}"
    qf = _json.dumps({"query": {"bool": {"must": [{"term": {"tier.tagFQN": want}}]}}})
    r = client.get("/v1/search/query", q="*", index="table_search_index",
                   size=50, query_filter=qf)
    fqns = [h["_source"]["fullyQualifiedName"] for h in r["hits"]["hits"]]
    return (fqns, "live")


# ---------------------------------------------------------------- tags
def _column_index(fqn: str, column: str) -> int:
    cols = _table(fqn, "columns").get("columns", [])
    for i, c in enumerate(cols):
        if c["name"] == column:
            return i
    raise ValueError(f"no column {column!r} on {fqn}")


def column_tags(fqn: str, column: str) -> list[dict]:
    """Tag labels on one column (each has tagFQN, source, labelType, state).

    Note: the column `fields` alone omits nested tags in 2.0.5 — `tags`
    must be requested too (observed), hence `fields="columns,tags"`.
    """
    cols = client.get(f"/v1/tables/name/{fqn}", fields="columns,tags").get("columns", [])
    for c in cols:
        if c["name"] == column:
            return c.get("tags", [])
    raise ValueError(f"no column {column!r} on {fqn}")


def column_tag_detail(fqn: str, column: str) -> list[dict]:
    """Provenance of one column's tags: FQN, labelType, state, appliedBy, reason.

    `appliedBy`/`reason` are the evidence of auto origin: the classifier
    writes `appliedBy: ingestion-bot` plus which recognizer/pattern fired.
    `reason` is shortened to its first line for printing.
    """
    out = []
    for t in column_tags(fqn, column):
        reason = (t.get("reason") or "").strip().splitlines()
        out.append({"tagFQN": t["tagFQN"], "labelType": t.get("labelType"),
                    "state": t.get("state"), "appliedBy": t.get("appliedBy"),
                    "reason": reason[0] if reason else ""})
    return out


def reapply_generated_tag(fqn: str, tag_fqn: str, column: str) -> tuple[list[str], str]:
    """Put the classifier's exact label back (Generated/Suggested).

    On an already-governed stack the false positive is already gone, so the
    removal demo would print "nothing to do". Re-applying the same label
    the auto-classification workflow writes makes the correction visible
    again with real PATCH output. On a fresh stack this step is unneeded —
    the tag is already there from the classify run.
    """
    return add_tag(fqn, tag_fqn, column=column, source="Classification",
                   label_type="Generated", state="Suggested")


def add_tag(fqn: str, tag_fqn: str, column: str | None = None,
            source: str = "Classification", label_type: str = "Manual",
            state: str = "Confirmed") -> tuple[list[str], str]:
    """Add a tag (table-level, or on `column`). Never duplicates. Returns (tagFQNs, how)."""
    label = {"tagFQN": tag_fqn, "source": source,
             "labelType": label_type, "state": state}
    if column is None:
        tags = _table(fqn, "tags").get("tags", [])
        if any(t["tagFQN"] == tag_fqn for t in tags):
            return ([t["tagFQN"] for t in tags], "already tagged")
        tags = [*tags, label]
        updated = client.api("PATCH", f"/v1/tables/name/{fqn}",
                             json=[{"op": "replace", "path": "/tags", "value": tags}]).json()
        return ([t["tagFQN"] for t in updated.get("tags", [])], "tag added")
    idx = _column_index(fqn, column)
    tags = column_tags(fqn, column)
    if any(t["tagFQN"] == tag_fqn for t in tags):
        return ([t["tagFQN"] for t in tags], "already tagged")
    tags = [*tags, label]
    updated = client.api("PATCH", f"/v1/tables/name/{fqn}",
                         json=[{"op": "replace", "path": f"/columns/{idx}/tags",
                                "value": tags}]).json()
    return ([t["tagFQN"] for t in updated["columns"][idx].get("tags", [])], "tag added")


def remove_tag(fqn: str, tag_fqn: str, column: str | None = None) -> tuple[list[str], str]:
    """Remove one tag (table-level, or from `column`). Returns (remaining tagFQNs, how)."""
    if column is None:
        tags = _table(fqn, "tags").get("tags", [])
        if tag_fqn not in [t["tagFQN"] for t in tags]:
            return ([t["tagFQN"] for t in tags], "not present (nothing to do)")
        tags = [t for t in tags if t["tagFQN"] != tag_fqn]
        client.api("PATCH", f"/v1/tables/name/{fqn}",
                   json=[{"op": "replace", "path": "/tags", "value": tags}])
        return ([t["tagFQN"] for t in tags], "tag removed")
    idx = _column_index(fqn, column)
    current = column_tags(fqn, column)
    if tag_fqn not in [t["tagFQN"] for t in current]:
        return ([t["tagFQN"] for t in current], "not present (nothing to do)")
    tags = [t for t in current if t["tagFQN"] != tag_fqn]
    updated = client.api("PATCH", f"/v1/tables/name/{fqn}",
                         json=[{"op": "replace", "path": f"/columns/{idx}/tags",
                                "value": tags}]).json()
    return ([t["tagFQN"] for t in updated["columns"][idx].get("tags", [])], "tag removed")


def confirm_tag(fqn: str, tag_fqn: str, column: str) -> tuple[list[str], str]:
    """Re-label an auto tag as human-confirmed (labelType Manual, state Confirmed)."""
    idx = _column_index(fqn, column)
    current = column_tags(fqn, column)
    if any(t["tagFQN"] == tag_fqn and t.get("labelType") == "Manual"
           and t.get("state") == "Confirmed" for t in current):
        return ([(t["tagFQN"], t.get("labelType"), t.get("state")) for t in current],
                "already confirmed")
    tags = [{"tagFQN": t["tagFQN"], "source": t.get("source", "Classification"),
             "labelType": "Manual", "state": "Confirmed"}
            if t["tagFQN"] == tag_fqn else t for t in current]
    updated = client.api("PATCH", f"/v1/tables/name/{fqn}",
                         json=[{"op": "replace", "path": f"/columns/{idx}/tags",
                                "value": tags}]).json()
    return ([(t["tagFQN"], t.get("labelType"), t.get("state"))
             for t in updated["columns"][idx].get("tags", [])], "confirmed by human")


def ensure_classification(name: str, description: str = "") -> dict:
    """Create-or-update a tag vocabulary (a classification)."""
    return client.api("PUT", "/v1/classifications",
                      json={"name": name, "displayName": name,
                            "description": description}).json()


def ensure_tag(classification: str, name: str, description: str = "") -> dict:
    """Create-or-update one tag value inside a classification."""
    return client.api("PUT", "/v1/tags",
                      json={"name": name, "displayName": name,
                            "description": description,
                            "classification": classification}).json()


# ---------------------------------------------------------------- glossary
def ensure_glossary(name: str, description: str = "") -> dict:
    """Create-or-update a glossary (business vocabulary)."""
    return client.api("PUT", "/v1/glossaries",
                      json={"name": name, "displayName": name,
                            "description": description}).json()


def ensure_term(glossary: str, name: str, description: str = "",
                synonyms: list[str] | tuple[str, ...] = (),
                related: list[str] | tuple[str, ...] = (),
                reviewers: list[str] | tuple[str, ...] = ()) -> dict:
    """Create-or-update a glossary term; then link `related` terms (by FQN).

    Returns the fresh term with `_how` ("created", "reused", or
    "review-locked, kept" when the term is In Review and the bot may not
    edit it — see `set_reviewers`).
    """
    fqn = f"{glossary}.{name}"
    try:
        term = client.get(f"/v1/glossaryTerms/name/{fqn}", fields="relatedTerms")
        how = "reused"
    except Exception:
        term, how = None, "created"
    body = {"name": name, "displayName": name, "description": description,
            "glossary": glossary, "synonyms": list(synonyms)}
    if reviewers:
        body["reviewers"] = [{"id": client.get(f"/v1/users/name/{u}")["id"],
                              "type": "user"} for u in reviewers]
    if term is None or not reviewers:
        same = (term is not None
                and (term.get("description") or "") == description
                and sorted(term.get("synonyms") or []) == sorted(synonyms))
        if term is None or not same:
            try:
                client.api("PUT", "/v1/glossaryTerms", json=body)
                how = "created" if term is None else "updated"
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status == 403 and term is not None:
                    fresh = client.get(f"/v1/glossaryTerms/name/{fqn}", fields="relatedTerms")
                    fresh["_how"] = "review-locked, kept"
                    return fresh
                raise
    for other in related:
        oid = client.get(f"/v1/glossaryTerms/name/{other}")["id"]
        fresh = client.get(f"/v1/glossaryTerms/name/{fqn}", fields="relatedTerms")
        have = {(r.get("term") or {}).get("id") for r in fresh.get("relatedTerms") or []}
        if oid not in have:
            try:
                client.api("PATCH", f"/v1/glossaryTerms/name/{fqn}",
                           json=[{"op": "add", "path": "/relatedTerms",
                                  "value": [{"term": {"id": oid, "type": "glossaryTerm"}}]}])
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status != 403:
                    raise
    fresh = client.get(f"/v1/glossaryTerms/name/{fqn}", fields="relatedTerms")
    fresh["_how"] = how
    return fresh


def set_reviewers(term_fqn: str, users: list[str] | tuple[str, ...]) -> dict:
    """Ask `users` (by user name) to review a term: it moves to In Review
    and non-reviewers can no longer edit it (bot edits get 403)."""
    term = client.get(f"/v1/glossaryTerms/name/{term_fqn}")
    body = {"name": term["name"], "displayName": term.get("displayName") or term["name"],
            "description": term.get("description") or "",
            "glossary": term["glossary"]["name"],
            "synonyms": term.get("synonyms") or [],
            "reviewers": [{"id": client.get(f"/v1/users/name/{u}")["id"], "type": "user"}
                          for u in users]}
    updated = None
    try:
        updated = client.api("PUT", "/v1/glossaryTerms", json=body).json()
    except Exception as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status == 403:
            updated = client.get(f"/v1/glossaryTerms/name/{term_fqn}")
    return updated


def bot_update_attempt(term_fqn: str, description: str) -> tuple[int | None, str]:
    """Try editing a glossary term as the ingestion bot; return (status, message).

    Used to show the review lock: on an In-Review term the bot gets
    403 "not a reviewer". Never raises.
    """
    term = client.get(f"/v1/glossaryTerms/name/{term_fqn}")
    body = {"name": term["name"], "displayName": term.get("displayName") or term["name"],
            "description": description, "glossary": term["glossary"]["name"],
            "synonyms": term.get("synonyms") or []}
    try:
        client.api("PUT", "/v1/glossaryTerms", json=body)
        return (200, "edit allowed")
    except Exception as e:
        resp = getattr(e, "response", None)
        try:
            msg = resp.json().get("message", str(e)) if resp is not None else str(e)
        except Exception:
            msg = str(e)
        return (resp.status_code if resp is not None else None, msg)


def reset_reviewers(term_fqn: str) -> dict:
    """Clear a term's reviewers as the admin (so `set_reviewers` triggers
    a fresh In-Review cycle on every run)."""
    import requests

    from openmetadata_tutorial.config import settings

    s = settings()
    term = client.get(f"/v1/glossaryTerms/name/{term_fqn}")
    headers = {"Authorization": f"Bearer {client.login_token(s)}",
               "Content-Type": "application/json-patch+json"}
    r = requests.patch(f"{s.om_api}/v1/glossaryTerms/{term['id']}", headers=headers,
                       json=[{"op": "replace", "path": "/reviewers", "value": []}],
                       timeout=client.TIMEOUT)
    r.raise_for_status()
    return r.json()


def wait_status(term_fqn: str, want: str = "In Review", timeout: int = 90) -> dict:
    """Poll a glossary term until `entityStatus == want` (review moves are
    async: a background workflow flips the status seconds after reviewers
    are set — observed). Returns the term; raises on timeout."""
    import time

    deadline = time.time() + timeout
    term = client.get(f"/v1/glossaryTerms/name/{term_fqn}")
    while term.get("entityStatus") != want and time.time() < deadline:
        time.sleep(5)
        term = client.get(f"/v1/glossaryTerms/name/{term_fqn}")
    if term.get("entityStatus") != want:
        raise TimeoutError(f"{term_fqn} still {term.get('entityStatus')} after {timeout}s")
    return term


def approve_term(term_fqn: str) -> dict:
    """Approve an In-Review term as the admin (PATCH /entityStatus)."""
    import requests

    from openmetadata_tutorial.config import settings

    s = settings()
    term = client.get(f"/v1/glossaryTerms/name/{term_fqn}")
    headers = {"Authorization": f"Bearer {client.login_token(s)}",
               "Content-Type": "application/json-patch+json"}
    r = requests.patch(f"{s.om_api}/v1/glossaryTerms/{term['id']}", headers=headers,
                       json=[{"op": "replace", "path": "/entityStatus", "value": "Approved"}],
                       timeout=client.TIMEOUT)
    r.raise_for_status()
    return r.json()


def link_term_to_column(term_fqn: str, table_fqn: str, column: str) -> tuple[list[str], str]:
    """Attach a glossary term to a column (a tag with source Glossary)."""
    return add_tag(table_fqn, term_fqn, column=column, source="Glossary")


# ---------------------------------------------------------------- domains
def ensure_domain(name: str, description: str = "",
                  domain_type: str = "Consumer-aligned",
                  owner_team: str | None = None) -> dict:
    """Create-or-update a business domain."""
    body = {"name": name, "displayName": name, "description": description,
            "domainType": domain_type}
    if owner_team:
        tid = client.get(f"/v1/teams/name/{owner_team}")["id"]
        body["owners"] = [{"id": tid, "type": "team"}]
    return client.api("PUT", "/v1/domains", json=body).json()


def set_domain(fqn: str, domain: str) -> tuple[list[str], str]:
    """Assign `fqn` to a domain (2.0.5 stores a list at /domains)."""
    did = client.get(f"/v1/domains/name/{domain}")["id"]
    current = _table(fqn, "domains").get("domains", [])
    if any(d["name"] == domain for d in current):
        return ([d["name"] for d in current], "already in domain")
    updated = client.api("PATCH", f"/v1/tables/name/{fqn}",
                         json=[{"op": "replace", "path": "/domains",
                                "value": [{"id": did, "type": "domain"}]}]).json()
    return ([d["name"] for d in updated.get("domains", [])], "domain assigned")


def ensure_data_product(name: str, domain: str, description: str = "",
                        assets: list[tuple[str, str]] | tuple = ()) -> dict:
    """Create-or-update a data product in `domain`; attach `assets` as (kind, fqn).

    `kind` is the entity type ('table' for tables and views, 'dashboard'
    for dashboards). Missing kinds are skipped and reported in `_skipped`.

    In 2.0.5 the product-side `assets` field is deprecated: a PUT carrying
    it stores nothing and `GET ...?fields=assets` reads back `null`
    (observed). The link that persists — and that GET, search, the report
    and the UI table page all show — is the back-reference on each asset
    (`PATCH /v1/<kind>s/name/<fqn>` on `/dataProducts`), which this
    function sets additively. Linked FQNs are reported in `_assets`.
    """
    body = {"name": name, "displayName": name, "description": description,
            "domains": [domain]}
    dp = client.api("PUT", "/v1/dataProducts", json=body).json()
    linked, skipped = [], []
    for kind, fqn in assets:
        plural = f"/v1/{kind}s/name/{fqn}"
        try:
            eid = client.get(plural, fields="id")["id"]
        except Exception:
            skipped.append(fqn)  # e.g. the chapter-06 dashboard is absent: skip honestly
            continue
        current = client.get(plural, fields="dataProducts").get("dataProducts", [])
        if any(p["id"] == dp["id"] for p in current):
            linked.append(fqn)
            continue
        try:
            updated = client.api("PATCH", plural,
                                 json=[{"op": "replace", "path": "/dataProducts",
                                        "value": [{"id": p["id"], "type": p["type"]}
                                                  for p in current]
                                        + [{"id": dp["id"], "type": "dataProduct"}]}]).json()
            linked.extend(p.get("fullyQualifiedName", fqn)
                          for p in updated.get("dataProducts", []))
        except Exception:
            skipped.append(fqn)
    dp["_assets"] = sorted(set(linked))
    dp["_skipped"] = skipped
    return dp


def data_products_of(fqn: str) -> list[str]:
    """Data product names linked to a table or view (the readable side)."""
    t = client.get(f"/v1/tables/name/{fqn}", fields="dataProducts")
    return [p.get("fullyQualifiedName", p["name"]) for p in t.get("dataProducts", [])]


# ---------------------------------------------------------------- certification
def set_certification(fqn: str, level: str) -> tuple[str, str]:
    """Certify an asset: Bronze, Silver or Gold (a tag in Certification)."""
    want = level if level.startswith("Certification.") else f"Certification.{level}"
    current = (_table(fqn, "certification").get("certification") or {}).get("tagLabel", {})
    if current.get("tagFQN") == want:
        return (want, "already certified")
    value = {"tagLabel": {"tagFQN": want, "source": "Classification",
                          "labelType": "Manual", "state": "Confirmed"}}
    updated = client.api("PATCH", f"/v1/tables/name/{fqn}",
                         json=[{"op": "add", "path": "/certification",
                                "value": value}]).json()
    return (updated["certification"]["tagLabel"]["tagFQN"], "certified")


# ---------------------------------------------------------------- report
def metadata_source_config() -> dict:
    """The shared metadata workflow's sourceConfig (read-only).

    Returns whether an override flag is set and the config block itself.
    `ingestion/metadata.yaml` is the designer's file — this only reads it,
    so the notebook can quote exactly what the workflow would overwrite.
    """
    import re

    from openmetadata_tutorial.config import project_root

    text = (project_root() / "ingestion" / "metadata.yaml").read_text()
    m = re.search(r"config:\n((?:      .*\n)+)", text.split("sourceConfig:")[1])
    block = m.group(0) if m else ""
    return {"override_flag_present": "overrideMetadata" in text, "source_config": block}
def report(fqns: list[str] | tuple[str, ...] = tuple(ALL_ASSETS)) -> pd.DataFrame:
    """One row per asset: owner, tier, certification, domain, products, PII, glossary."""
    rows = []
    for fqn in fqns:
        t = client.get(f"/v1/tables/name/{fqn}",
                       fields="owners,tags,domains,dataProducts,columns,certification")
        owners = ", ".join(o["name"] for o in t.get("owners", []))
        tier = next((g["tagFQN"] for g in t.get("tags", []) if g["tagFQN"].startswith("Tier.")), "")
        cert = (t.get("certification") or {}).get("tagLabel", {}).get("name", "")
        domains = ", ".join(d["name"] for d in t.get("domains", []))
        products = ", ".join(p.get("name", p.get("fullyQualifiedName", "?"))
                             for p in t.get("dataProducts", []))
        pii, gloss = [], []
        for c in t.get("columns", []):
            for g in c.get("tags", []):
                if g["tagFQN"].startswith("PII."):
                    pii.append(f"{c['name']} ({g['tagFQN'].split('.')[1]}/{g.get('labelType')})")
                if g.get("source") == "Glossary":
                    gloss.append(f"{c['name']}←{g['tagFQN'].split('.')[-1]}")
        rows.append({"fqn": fqn, "owners": owners, "tier": tier, "certification": cert,
                     "domain": domains, "data products": products,
                     "PII columns": ", ".join(pii), "glossary terms": ", ".join(gloss)})
    return pd.DataFrame(rows, columns=["fqn", "owners", "tier", "certification", "domain",
                                       "data products", "PII columns", "glossary terms"])
