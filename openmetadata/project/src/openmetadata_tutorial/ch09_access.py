"""Chapter 09: access control. Users, teams, roles and policies on Brightcup.

Idempotent: every ensure-* call checks first and only creates what is missing.
Run from project/: ``uv run python -m openmetadata_tutorial.ch09_access <step>``
steps: setup | whoami | show-policy | mkpolicy | matrix

Never prints secrets: tokens and passwords are masked to 10 characters.
"""

import base64
import json
import os
import sys

import requests

from openmetadata_tutorial import client
from openmetadata_tutorial.config import project_root, settings

DANA_NAME = "dana.analyst"
FINANCE = "Finance"
DATA_ENG = "Data Engineering"
REVENUE_FQN = "brightcup_pg.brightcup.analytics.daily_revenue"
ORDERS_FQN = "brightcup_pg.brightcup.raw.orders"
CUSTOMERS_FQN = "brightcup_pg.brightcup.raw.customers"
PRODUCTS_FQN = "brightcup_pg.brightcup.raw.products"

# Descriptions as the catalog had them before this chapter's demo edits.
# cmd_matrix restores these (not whatever it found) so re-runs converge.
ORIGINAL_DESCRIPTIONS = {
    REVENUE_FQN: "Revenue and order count per day. Feeds the finance dashboard.",
    ORDERS_FQN: "One row per web-shop order.",
}


def mask(secret: str) -> str:
    return (secret[:10] + "...") if secret else "<empty>"


def dana_password() -> str:
    from dotenv import load_dotenv

    load_dotenv(project_root() / ".env", override=True)
    pw = os.environ.get("DANA_PASSWORD", "")
    if not pw:
        raise SystemExit("DANA_PASSWORD is not set in project/.env")
    return pw


def dana_email() -> str:
    from dotenv import load_dotenv

    load_dotenv(project_root() / ".env", override=True)
    return os.environ.get("DANA_EMAIL", "dana.analyst@brightcup.example")


def raw(method: str, path: str, token: str, **kwargs) -> requests.Response:
    s = settings()
    headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
    if method.upper() == "PATCH":
        headers.setdefault("Content-Type", "application/json-patch+json")
    return requests.request(method, f"{s.om_api}{path}", headers=headers, timeout=30, **kwargs)


def try_call(token: str, method: str, path: str, body=None) -> tuple[int, str]:
    """Call the API without raising; return (status, one-line summary)."""
    try:
        r = raw(method, path, token, json=body) if body is not None else raw(method, path, token)
        snippet = r.text.replace("\n", " ")[:220]
        return r.status_code, snippet
    except requests.HTTPError as e:
        resp = e.response
        return resp.status_code, resp.text.replace("\n", " ")[:220]
    except Exception as e:  # network error etc.
        return -1, f"{type(e).__name__}: {e}"


def get_or_none(path: str):
    try:
        return client.get(path)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise


def ensure_team(name: str, description: str) -> dict:
    team = get_or_none(f"/v1/teams/name/{name}")
    if team is not None:
        print(f"team {name}: exists ({team['id']})")
        return team
    team = client.api("POST", "/v1/teams", json={
        "name": name, "displayName": name, "description": description, "teamType": "Group",
    }).json()
    print(f"team {name}: created ({team['id']})")
    return team


def ensure_user_dana() -> dict:
    email = dana_email()
    pw = dana_password()
    user = get_or_none(f"/v1/users/name/{DANA_NAME}")
    if user is None:
        user = client.api("POST", "/v1/users", json={
            "name": DANA_NAME, "email": email,
            "createPasswordType": "ADMIN_CREATE",
            "password": pw, "confirmPassword": pw,
        }).json()
        print(f"user {DANA_NAME}: created ({user['id']})")
    else:
        print(f"user {DANA_NAME}: exists ({user['id']})")
        # Refresh the demo password so logins below always work. Password
        # changes need a real admin login; the ingestion-bot token is not enough.
        try:
            admin = client.login_token()
            raw("PUT", "/v1/users/changePassword", admin, json={
                "username": DANA_NAME,
                "requestType": "USER",
                "newPassword": pw, "confirmPassword": pw,
            }).raise_for_status()
            print(f"user {DANA_NAME}: password refreshed")
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            print(f"user {DANA_NAME}: password refresh -> {code} (login will tell)")
    # Membership in Finance (idempotent).
    finance = get_or_none(f"/v1/teams/name/{FINANCE}")
    if finance is not None:
        members = client.get(f"/v1/teams/{finance['id']}?fields=users").get("users", [])
        if not any(u.get("id") == user["id"] for u in members):
            client.api("POST", f"/v1/teams/{finance['id']}/users", json={"id": user["id"], "type": "user"})
            print(f"user {DANA_NAME}: added to team {FINANCE}")
        else:
            print(f"user {DANA_NAME}: already in team {FINANCE}")
    return user


def ensure_owner(table_fqn: str, team_name: str) -> None:
    table = client.get(f"/v1/tables/name/{table_fqn}?fields=owners")
    team = client.get(f"/v1/teams/name/{team_name}")
    if any(o.get("id") == team["id"] for o in table.get("owners", [])):
        print(f"owner of {table_fqn}: {team_name} already set")
        return
    ref = {"id": team["id"], "type": "team", "name": team["name"],
           "fullyQualifiedName": team["fullyQualifiedName"]}
    client.api("PATCH", f"/v1/tables/{table['id']}",
               json=[{"op": "add", "path": "/owners", "value": [ref]}])
    print(f"owner of {table_fqn}: set to {team_name}")


def ensure_glossary() -> dict:
    glossary = get_or_none("/v1/glossaries/name/Brightcup")
    if glossary is None:
        glossary = client.api("POST", "/v1/glossaries", json={
            "name": "Brightcup", "displayName": "Brightcup",
            "description": "Business vocabulary of the Brightcup coffee-bean shop.",
        }).json()
        print("glossary Brightcup: created")
    else:
        print("glossary Brightcup: exists")
    term = get_or_none("/v1/glossaryTerms/name/Brightcup.Revenue")
    if term is None:
        term = client.api("POST", "/v1/glossaryTerms", json={
            "name": "Revenue", "displayName": "Revenue",
            "description": "Money earned from shipped, delivered and placed (non-cancelled) orders, in EUR.",
            "glossary": {"id": glossary["id"], "type": "glossary"},
        }).json()
        print("glossary term Brightcup.Revenue: created")
    else:
        print("glossary term Brightcup.Revenue: exists")
    return term


def ensure_pii_table_tag() -> None:
    """The deny rule matches table-level tags; auto-classification tags columns.

    Tag raw.customers itself PII.Sensitive so NoPIIForConsumers has something
    to match (column tags alone do not gate table-level sample reads).
    """
    table = client.get(f"/v1/tables/name/{CUSTOMERS_FQN}?fields=tags")
    if any(t.get("tagFQN") == "PII.Sensitive" for t in table.get("tags", [])):
        print(f"tag on {CUSTOMERS_FQN}: PII.Sensitive already set")
        return
    client.api("PATCH", f"/v1/tables/{table['id']}", json=[{
        "op": "add", "path": "/tags", "value": [{
            "tagFQN": "PII.Sensitive", "source": "Classification",
            "labelType": "Manual", "state": "Confirmed"}]}])
    print(f"tag on {CUSTOMERS_FQN}: PII.Sensitive set (table level, Manual)")


def login_as_dana() -> str:
    s = settings()
    pw = base64.b64encode(dana_password().encode()).decode()
    r = requests.post(f"{s.om_api}/v1/users/login",
                      json={"email": dana_email(), "password": pw}, timeout=30)
    r.raise_for_status()
    token = r.json()["accessToken"]
    print(f"dana login: ok, token {mask(token)}")
    return token


def cmd_setup() -> None:
    ensure_team(FINANCE, "Owns finance reporting (analytics.daily_revenue).")
    ensure_team(DATA_ENG, "Owns raw ingestion tables (raw.orders).")
    ensure_owner(REVENUE_FQN, FINANCE)
    ensure_owner(ORDERS_FQN, DATA_ENG)
    ensure_user_dana()
    ensure_glossary()
    ensure_pii_table_tag()


def cmd_whoami() -> None:
    token = login_as_dana()
    me = raw("GET", "/v1/users/loggedInUser?fields=teams,roles", token).json()
    print(json.dumps({
        "name": me.get("name"), "email": me.get("email"),
        "teams": [t.get("name") for t in me.get("teams", [])],
        "roles": [r.get("name") for r in me.get("roles", [])],
    }, indent=1))


def cmd_show_policy() -> None:
    """Print the default DataConsumerPolicy rules: what dana may do by default.

    This is the evidence behind the matrix below: the EditRule allows
    EditDescription (and EditTags, among others) on All resources to everyone,
    so description edits return 200 for dana even without any policy of our
    own. EditOwners and ViewSampleData are nowhere in it.
    """
    policy = client.get("/v1/policies/name/DataConsumerPolicy")
    for rule in policy.get("rules", []):
        ops = ", ".join(rule.get("operations", []))
        res = ", ".join(rule.get("resources", []))
        print(f"{rule.get('name')}: {rule.get('effect')} [{ops}] on [{res}]")


def default_policy_allows(operation: str) -> bool:
    """True when the default DataConsumerPolicy allows `operation` for everyone."""
    policy = client.get("/v1/policies/name/DataConsumerPolicy")
    return any(
        rule.get("effect") == "allow" and operation in rule.get("operations", [])
        for rule in policy.get("rules", [])
    )


def probe_access() -> dict:
    """The access matrix as dana: label -> (status, snippet).

    Description PATCHes overwrite table descriptions; cmd_matrix (below)
    restores them afterwards, so tests that call this helper may leave the
    demo text behind -- cmd_matrix is the chapter's entry point, this helper
    is the tests' entry point. Expected on 2.0.5: reads 200, description
    PATCH on the PII-tagged table 403 (explicit deny wins over the permissive
    default), description PATCHes elsewhere 200 (the default allows them),
    PII sample read 403, plain sample read 200.
    """
    token = login_as_dana()
    rev = client.get(f"/v1/tables/name/{REVENUE_FQN}")
    ord_ = client.get(f"/v1/tables/name/{ORDERS_FQN}")
    cust = client.get(f"/v1/tables/name/{CUSTOMERS_FQN}")
    prod = client.get(f"/v1/tables/name/{PRODUCTS_FQN}")
    patch_desc = [{"op": "add", "path": "/description",
                   "value": "Edited by the ch09 access demo."}]
    calls = [
        ("GET daily_revenue", "GET", f"/v1/tables/{rev['id']}", None),
        ("PATCH description daily_revenue", "PATCH", f"/v1/tables/{rev['id']}", patch_desc),
        ("PATCH description raw.customers", "PATCH", f"/v1/tables/{cust['id']}", patch_desc),
        ("PATCH description raw.orders", "PATCH", f"/v1/tables/{ord_['id']}", patch_desc),
        ("GET raw.customers sampleData", "GET", f"/v1/tables/{cust['id']}/sampleData", None),
        ("GET raw.products sampleData", "GET", f"/v1/tables/{prod['id']}/sampleData", None),
    ]
    out = {}
    for label, method, path, body in calls:
        out[label] = try_call(token, method, path, body)
    return out


def cmd_matrix() -> None:
    """The access matrix as dana, then restore the demo-edited descriptions."""
    probe = probe_access()
    for label, (status, snippet) in probe.items():
        print(f"dana {label}: {status}")
        print(f"  -> {snippet}")
    # The description PATCHes above overwrote two tables (the customers PATCH
    # is denied, so that table is untouched). Restore them so other chapters
    # keep seeing the catalog as they left it.
    for tid_fqn, desc in ORIGINAL_DESCRIPTIONS.items():
        tid = client.get(f"/v1/tables/name/{tid_fqn}")["id"]
        client.api("PATCH", f"/v1/tables/{tid}",
                   json=[{"op": "add", "path": "/description", "value": desc}])
    print("descriptions: restored")


def ensure_policy(name: str, description: str, rules: list) -> dict:
    existing = get_or_none(f"/v1/policies/name/{name}")
    body = {"name": name, "displayName": name, "description": description, "rules": rules}
    if existing is None:
        policy = client.api("POST", "/v1/policies", json=body).json()
        print(f"policy {name}: created ({policy['id']})")
        return policy
    policy = client.api("PUT", "/v1/policies", json=body).json()
    print(f"policy {name}: updated ({policy['id']})")
    return policy


def ensure_role(name: str, description: str, policy_names: list[str]) -> dict:
    # NOTE: POST/PUT /v1/roles resolves `policies` by name; passing UUIDs
    # returns 404 "policy instance ... not found" on this server version.
    existing = get_or_none(f"/v1/roles/name/{name}")
    body = {"name": name, "displayName": name, "description": description, "policies": policy_names}
    if existing is None:
        role = client.api("POST", "/v1/roles", json=body).json()
        print(f"role {name}: created ({role['id']})")
        return role
    role = client.api("PUT", "/v1/roles", json=body).json()
    print(f"role {name}: updated ({role['id']})")
    return role


def assign_role_to_team(role_name: str, team_name: str) -> None:
    role = client.get(f"/v1/roles/name/{role_name}")
    team = client.get(f"/v1/teams/name/{team_name}")
    full = client.get(f"/v1/teams/{team['id']}?fields=defaultRoles")
    current = [r.get("id") for r in full.get("defaultRoles", [])]
    if role["id"] in current:
        print(f"team {team_name}: already has role {role_name}")
        return
    ref = {"id": role["id"], "type": "role", "name": role["name"],
           "fullyQualifiedName": role["fullyQualifiedName"]}
    client.api("PATCH", f"/v1/teams/{team['id']}",
               json=[{"op": "add", "path": "/defaultRoles", "value": [ref]}])
    print(f"team {team_name}: granted role {role_name}")


def cmd_mkpolicy() -> None:
    finance_edit = ensure_policy("FinanceEditRevenue",
        "Finance members may edit descriptions and tags on tables they own.",
        [{
            "name": "FinanceEditRevenue-OwnerEdit",
            "description": "Allow owners to edit descriptions and tags of their tables.",
            "effect": "allow",
            "operations": ["EditDescription", "EditTags"],
            "resources": ["table"],
            "condition": "isOwner()",
        }])
    nopii = ensure_policy("NoPIIForConsumers",
        "Nobody on this role may read sample rows of, or edit, assets tagged PII.Sensitive.",
        [{
            "name": "NoPIIForConsumers-DenySensitiveSamples",
            "description": "Deny sample-data reads on anything tagged PII.Sensitive.",
            "effect": "deny",
            "operations": ["ViewSampleData"],
            "resources": ["table"],
            "condition": "matchAnyTag('PII.Sensitive')",
        }, {
            "name": "NoPIIForConsumers-DenySensitiveEdits",
            "description": "Deny description and tag edits on anything tagged PII.Sensitive. "
                           "Needed on 2.0.5 because the shipped default already allows "
                           "description/tag edits to everyone -- without this deny rule no "
                           "description PATCH can return 403, and deny wins over that default.",
            "effect": "deny",
            "operations": ["EditDescription", "EditTags"],
            "resources": ["table"],
            "condition": "matchAnyTag('PII.Sensitive')",
        }])
    print(f"policies: {finance_edit['name']} {finance_edit['id']} / {nopii['name']} {nopii['id']}")
    ensure_role("FinanceEditor", "Edits finance-owned tables; blocked from PII sample rows and PII edits.",
                ["FinanceEditRevenue", "NoPIIForConsumers"])
    assign_role_to_team("FinanceEditor", FINANCE)


def main(argv: list[str]) -> None:
    step = argv[1] if len(argv) > 1 else "setup"
    {"setup": cmd_setup, "whoami": cmd_whoami, "show-policy": cmd_show_policy,
     "matrix": cmd_matrix, "mkpolicy": cmd_mkpolicy}[step]()


if __name__ == "__main__":
    main(sys.argv)
