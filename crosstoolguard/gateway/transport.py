"""Upstream transport — Task 1 lab adapter (in-process).

Calls the benign lab servers directly. Replaced by real MCP stdio /
Streamable-HTTP transport in Task 2 (tool registry); the proxy ↔ transport
boundary (`call_upstream(server, tool, args) -> str`) stays stable.
"""

from __future__ import annotations


def list_tools() -> list[dict]:
    """Catalog of (server, tool, description) for GET /tools/list."""
    from lab.servers import calculator, filesystem, search, storage

    catalog: list[dict] = []
    for server, mod in (
        ("filesystem-mcp", filesystem),
        ("calculator-mcp", calculator),
        ("search-mcp", search),
        ("storage-mcp", storage),
    ):
        for name, meta in mod.TOOLS.items():
            catalog.append({"server": server, "tool": name, "description": meta["description"]})
    return catalog


def call_upstream(server: str, tool: str, args: dict) -> str:
    from lab.servers import calculator, filesystem, search, storage

    modules = {
        "filesystem-mcp": filesystem,
        "calculator-mcp": calculator,
        "search-mcp": search,
        "storage-mcp": storage,
    }
    mod = modules.get(server)
    if mod is None:
        raise ValueError(f"unknown server: {server}")
    fn = mod.TOOLS.get(tool, {}).get("func")
    if fn is None:
        raise ValueError(f"unknown tool: {server}.{tool}")
    return str(fn(**args))
