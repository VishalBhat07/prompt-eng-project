"""Read-only MCP server inventory using the official Python MCP client.

This module lists advertised definitions only; it never invokes a tool.
Launching a stdio server executes a local command, so callers must explicitly
set ``allow_stdio_launch=True`` after arranging an isolated assessment host.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlparse

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client


def _validate_http_url(url: str, *, allow_http: bool) -> None:
    parsed = urlparse(url)
    allowed = {"https"} | ({"http"} if allow_http else set())
    if parsed.scheme not in allowed or not parsed.hostname:
        raise ValueError("MCP endpoint must be an HTTPS URL (HTTP requires explicit opt-in)")
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("MCP endpoint URL cannot contain credentials, query parameters, or a fragment")


@asynccontextmanager
async def _connection(config: dict[str, Any], *, allow_stdio_launch: bool,
                       allow_http: bool) -> AsyncIterator[tuple[Any, Any]]:
    transport = config.get("transport")
    if transport == "stdio":
        if not allow_stdio_launch:
            raise PermissionError("stdio launches a local process; explicit isolated-launch approval is required")
        command = config.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("stdio server requires a command")
        params = StdioServerParameters(
            command=command,
            args=list(config.get("args") or []),
            env=dict(config.get("env") or {}),
        )
        async with stdio_client(params) as (read_stream, write_stream):
            yield read_stream, write_stream
        return

    if transport == "streamable-http":
        url = str(config.get("url") or "")
        _validate_http_url(url, allow_http=allow_http)
        async with streamablehttp_client(url, headers=dict(config.get("headers") or {})) as (
            read_stream, write_stream, _get_session_id
        ):
            yield read_stream, write_stream
        return

    raise ValueError("transport must be 'stdio' or 'streamable-http'")


async def inspect_server(config: dict[str, Any], *, allow_stdio_launch: bool = False,
                         allow_http: bool = False, page_limit: int = 100) -> dict[str, Any]:
    """Connect, negotiate, and collect the complete paginated tool inventory.

    ``config`` accepts ``{server_id, transport, url, headers}`` for HTTP or
    ``{server_id, transport, command, args, env}`` for stdio. The result keeps
    complete server-advertised definitions so callers can fingerprint and
    review descriptions, schemas, annotations, and metadata together.
    """
    server_id = str(config.get("server_id") or "").strip()
    if not server_id:
        raise ValueError("server_id is required")
    if page_limit < 1 or page_limit > 1000:
        raise ValueError("page_limit must be between 1 and 1000")

    async with open_mcp_session(config, allow_stdio_launch=allow_stdio_launch,
                                allow_http=allow_http) as (session, initialized):
        return await inventory_from_session(session, initialized, config, page_limit=page_limit)


@asynccontextmanager
async def open_mcp_session(config: dict[str, Any], *, allow_stdio_launch: bool = False,
                           allow_http: bool = False) -> AsyncIterator[tuple[Any, Any]]:
    """Open and initialize one MCP session for inventory plus an optional guarded call."""
    async with _connection(config, allow_stdio_launch=allow_stdio_launch,
                           allow_http=allow_http) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialized = await asyncio.wait_for(session.initialize(), timeout=30)
            yield session, initialized


async def inventory_from_session(session: ClientSession, initialized: Any,
                                 config: dict[str, Any], *, page_limit: int = 100) -> dict[str, Any]:
    """Read all advertised tools on an already initialized MCP session."""
    if page_limit < 1 or page_limit > 1000:
        raise ValueError("page_limit must be between 1 and 1000")
    tools: list[dict[str, Any]] = []
    cursor: str | None = None
    pages = 0
    while True:
        result = await asyncio.wait_for(session.list_tools(cursor=cursor), timeout=30)
        pages += 1
        for tool in result.tools:
            tools.append(tool.model_dump(mode="json", by_alias=True, exclude_none=False))
        cursor = getattr(result, "nextCursor", None) or getattr(result, "next_cursor", None)
        if not cursor:
            break
        if pages >= page_limit:
            raise RuntimeError(f"MCP tool inventory exceeded page limit ({page_limit})")

    tools.sort(key=lambda item: str(item.get("name", "")))
    server_info = getattr(initialized, "serverInfo", None) or getattr(initialized, "server_info", None)
    capabilities = getattr(initialized, "capabilities", None)
    endpoint_url = config.get("url") if config.get("transport") == "streamable-http" else None
    return {
        "server_id": str(config["server_id"]),
        "transport": config["transport"],
        "endpoint_url": endpoint_url,
        "server_info": server_info.model_dump(mode="json", by_alias=True)
        if server_info is not None else None,
        "protocol_version": getattr(initialized, "protocolVersion", None)
        or getattr(initialized, "protocol_version", None),
        "instructions": getattr(initialized, "instructions", None),
        "capabilities": capabilities.model_dump(mode="json", by_alias=True)
        if capabilities is not None else None,
        "tools": tools,
    }


def register_inventory(registry: Any, inventory: dict[str, Any]) -> list[Any]:
    """Persist server metadata and every current definition, deactivating removed tools."""
    if hasattr(registry, "register_server_inventory"):
        return registry.register_server_inventory(inventory)
    server_id = inventory["server_id"]
    return [registry.register_definition(server=server_id, definition=tool)
            for tool in inventory["tools"]]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Read-only MCP server tool inventory")
    parser.add_argument("--config", required=True, help="JSON file with one MCP connection profile")
    parser.add_argument("--output", required=True, help="Path to write the inventory JSON")
    parser.add_argument("--registry-db", default=os.getenv("REGISTRY_DB", "registry.db"),
                        help="SQLite inventory database (default: REGISTRY_DB or registry.db)")
    parser.add_argument("--launch-stdio", action="store_true",
                        help="Allow the configured stdio command to launch; isolate it yourself")
    parser.add_argument("--allow-http", action="store_true",
                        help="Allow a non-TLS HTTP endpoint (use only for trusted local test servers)")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    inventory = asyncio.run(inspect_server(config, allow_stdio_launch=args.launch_stdio,
                                          allow_http=args.allow_http))
    from crosstoolguard.registry.tools import ToolRegistry
    from crosstoolguard.registry.assessment import assess_inventory

    registry = ToolRegistry(args.registry_db)
    registry_status = register_inventory(registry, inventory)
    assessment = assess_inventory(inventory)
    registry.save_assessment(inventory["server_id"], assessment)
    registry.close()
    inventory["registry_status"] = {
        "server": registry_status.integrity_status,
        "version": registry_status.version,
    }
    inventory["assessment"] = assessment
    output = Path(args.output)
    output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Inventoried {len(inventory['tools'])} tools from {inventory['server_id']} -> {output}")


if __name__ == "__main__":
    main()
