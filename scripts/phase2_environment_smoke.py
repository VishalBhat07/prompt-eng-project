"""Dependency-light smoke check for the Phase 2 Python environment.

Run with: .venv-phase2/Scripts/python.exe scripts/phase2_environment_smoke.py
Uses only synthetic MCP definitions and a mocked remote session.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))

    from crosstoolguard.detection import correlation
    from crosstoolguard.gateway import proxy
    from crosstoolguard.gateway.schemas import Verdict
    from crosstoolguard.registry.tools import ToolRegistry

    local_ref = {"inputSchema": {
        "$defs": {"text": {"type": "string"}},
        "type": "object", "required": ["content"],
        "properties": {"content": {"$ref": "#/$defs/text"}},
    }}
    assert proxy._validate_tool_arguments(local_ref, {"content": "synthetic"}) is None
    external_ref = {"inputSchema": {"$ref": "https://example.invalid/schema.json"}}
    assert "non-local reference" in (proxy._validate_tool_arguments(external_ref, {}) or "")

    inventory = {
        "server_id": "phase2-smoke", "transport": "streamable-http",
        "endpoint_url": "https://mcp.example.test/mcp",
        "server_info": {"name": "synthetic smoke server", "version": "1"},
        "protocol_version": "smoke", "instructions": None, "capabilities": {},
        "tools": [
            {"name": "read_demo_credential", "description": "Read a fake API credential from synthetic test data.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "send_data", "description": "Send data to an external transfer destination.",
             "inputSchema": {"type": "object", "required": ["content"],
                             "properties": {"content": {"type": "string"}}}},
        ],
    }
    sink_calls: list[tuple[str, dict]] = []

    class FakeSession:
        async def call_tool(self, name: str, arguments: dict) -> SimpleNamespace:
            if name == "read_demo_credential":
                text = "api_key=FAKE_CTG_PHASE2_TOKEN"
            else:
                sink_calls.append((name, arguments))
                text = "mock sink accepted"
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                                   structuredContent=None, isError=False)

    inspector_stub = ModuleType("crosstoolguard.registry.mcp_inspector")

    @asynccontextmanager
    async def fake_open_session(config: dict, *, allow_http: bool = False):
        yield FakeSession(), object()

    async def fake_inventory_from_session(session, initialized, config):
        return inventory

    inspector_stub.open_mcp_session = fake_open_session
    inspector_stub.inventory_from_session = fake_inventory_from_session

    with TemporaryDirectory(prefix="ctg-phase2-smoke-") as temp_dir:
        db_path = str(Path(temp_dir) / "registry.db")
        registry = ToolRegistry(db_path)
        try:
            registered = registry.register_server_inventory(inventory)
            assert registry.approve_server_inventory(inventory["server_id"], registered.inventory_hash)
        finally:
            registry.close()

        environment = {
            "REGISTRY_DB": db_path,
            "MODE": "enforcing",
            "EVENTS_PATH": str(Path(temp_dir) / "events.jsonl"),
        }
        with patch.dict(os.environ, environment), \
                patch.object(proxy, "_validate_inventory_target", lambda _url: None), \
                patch.object(correlation, "classify", lambda _text: "DATA"), \
                patch.object(correlation, "compose_score", lambda _chunks: 0.0), \
                patch.dict(sys.modules, {"crosstoolguard.registry.mcp_inspector": inspector_stub}):
            client = TestClient(proxy.app)
            bad_schema = client.post("/api/mcp/tools/call", json={
                "session_id": "S-PHASE2-SCHEMA", "server_id": inventory["server_id"],
                "tool": "send_data", "arguments": {"content": 123},
            }).json()
            assert bad_schema["verdict"] == Verdict.BLOCK.value
            assert "input schema" in bad_schema["reason"]
            assert sink_calls == []

            read = client.post("/api/mcp/tools/call", json={
                "session_id": "S-PHASE2-EXFIL", "server_id": inventory["server_id"],
                "tool": "read_demo_credential", "arguments": {},
            }).json()
            assert read["verdict"] == Verdict.ALLOW.value, read
            send = client.post("/api/mcp/tools/call", json={
                "session_id": "S-PHASE2-EXFIL", "server_id": inventory["server_id"],
                "tool": "send_data", "arguments": {"content": "api_key=FAKE_CTG_PHASE2_TOKEN"},
            }).json()
            assert send["verdict"] == Verdict.BLOCK.value, send
            assert sink_calls == []

    print("Phase 2 environment smoke passed: schema rejection and cross-tool exfiltration block.")


if __name__ == "__main__":
    main()
