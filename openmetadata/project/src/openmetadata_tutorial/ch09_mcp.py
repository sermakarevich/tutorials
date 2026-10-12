"""Chapter 09: AI assistants via the built-in MCP server (/mcp).

Minimal JSON-RPC client (requests only): initialize, tools/list, then three
tool calls answering "how is revenue computed and can I trust it?".
Run from project/: ``uv run python -m openmetadata_tutorial.ch09_mcp``

Never prints the token (masked to 10 characters).
"""

import json
import sys

import requests

from openmetadata_tutorial import client
from openmetadata_tutorial.config import settings

REVENUE_FQN = "brightcup_pg.brightcup.analytics.daily_revenue"


def mask(secret: str) -> str:
    return (secret[:10] + "...") if secret else "<empty>"


class MCP:
    def __init__(self) -> None:
        s = settings()
        self.url = f"{s.om_url}/mcp"
        self.token = client.token(s)
        self._id = 0

    def call(self, method: str, params: dict) -> dict:
        self._id += 1
        r = requests.post(self.url, headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}"},
            json={"jsonrpc": "2.0", "id": self._id,
                  "method": method, "params": params}, timeout=90)
        r.raise_for_status()
        body = r.json()
        if body.get("error"):
            raise RuntimeError(json.dumps(body["error"])[:300])
        return body["result"]

    def tool(self, name: str, arguments: dict) -> str:
        res = self.call("tools/call", {"name": name, "arguments": arguments})
        return "\n".join(b.get("text", "") for b in res.get("content", []))


def short(text: str, limit: int = 900) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + " ..."


def token_kind() -> str:
    """Which identity the MCP calls run as (for the chapter's auth line)."""
    from openmetadata_tutorial.config import settings as _settings

    s = _settings()
    if s.om_jwt_token:
        return "ingestion-bot token"
    return "admin login token"


def tool_names(mcp: "MCP | None" = None) -> list:
    mcp = mcp if mcp is not None else MCP()
    tools = mcp.call("tools/list", {})
    return [t["name"] for t in tools["tools"]]


def search_revenue(mcp: "MCP | None" = None, size: int = 5) -> dict:
    """Raw `search_metadata` answer for 'revenue' (parsed JSON)."""
    mcp = mcp if mcp is not None else MCP()
    return json.loads(mcp.tool("search_metadata", {"query": "revenue", "size": size}))


def lineage_counts(mcp: "MCP | None" = None) -> dict:
    """Upstream/downstream edges of daily_revenue via the MCP lineage tool.

    Returns {"upstream": [(from, to), ...], "downstream": [...]}. The chapter
    states 3 upstream / 1 downstream; tests assert exactly that.
    """
    mcp = mcp if mcp is not None else MCP()
    lineage = json.loads(mcp.tool("get_entity_lineage",
                                  {"entityType": "table", "fqn": REVENUE_FQN}))
    ups = [(e.get("fromFQN"), e.get("toFQN")) for e in lineage.get("upstream", [])]
    downs = [(e.get("fromFQN"), e.get("toFQN")) for e in lineage.get("downstream", [])]
    return {"upstream": ups, "downstream": downs}


def glossary_description(mcp: "MCP | None" = None) -> str:
    mcp = mcp if mcp is not None else MCP()
    term = json.loads(mcp.tool("get_entity_details",
                               {"entityType": "glossaryTerm", "fqn": "Brightcup.Revenue"}))
    return term.get("description", "")


def semantic_search_raw(mcp: "MCP | None" = None) -> str:
    mcp = mcp if mcp is not None else MCP()
    return mcp.tool("semantic_search", {"query": "revenue per day", "size": 3})


def main(argv: list[str]) -> None:
    mcp = MCP()
    hello = mcp.call("initialize", {"protocolVersion": "2025-06-18",
                                    "capabilities": {},
                                    "clientInfo": {"name": "ch09-demo", "version": "1"}})
    print(f"mcp server: {hello['serverInfo']['name']} {hello['serverInfo']['version']}")
    print(f"mcp auth: Bearer {mask(mcp.token)} ({token_kind()} for this demo; "
          "a read-only identity in production)")

    names = tool_names(mcp)
    print(f"tools ({len(names)}): {', '.join(names)}")

    d = search_revenue(mcp)
    print(f"search_metadata 'revenue': {d.get('message', '')}")
    for hit in d.get("results", [])[:5]:
        print(f"  - {hit.get('entityType')}: {hit.get('fullyQualifiedName')}")

    counts = lineage_counts(mcp)
    ups, downs = counts["upstream"], counts["downstream"]
    print(f"lineage of daily_revenue: {len(ups)} upstream edge(s), {len(downs)} downstream")
    for a, b in (ups + downs)[:6]:
        print(f"  - {a} -> {b}")

    print(f"glossary Brightcup.Revenue: {short(glossary_description(mcp), 200)}")

    try:
        print(f"semantic_search: {short(semantic_search_raw(mcp), 300)}")
    except Exception as e:
        print(f"semantic_search: not available here ({e})")


if __name__ == "__main__":
    main(sys.argv)
