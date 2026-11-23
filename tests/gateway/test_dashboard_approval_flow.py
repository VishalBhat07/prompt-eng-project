from contextlib import asynccontextmanager
import json
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_agent_waits_for_operator_approval_then_resumes(monkeypatch, tmp_path):
    from crosstoolguard.gateway import proxy
    from crosstoolguard.llm import providers
    from crosstoolguard.registry.tools import ToolRegistry

    inventory = {"server_id": "approval-fixture", "transport": "streamable-http",
        "endpoint_url": "https://fixture.invalid/mcp", "server_info": {"name": "fixture", "version": "1"},
        "protocol_version": "test", "instructions": None, "capabilities": {}, "tools": [
            {"name": "send_data", "description": "Send text to an external transfer destination.",
             "inputSchema": {"type": "object", "required": ["content"],
                             "properties": {"content": {"type": "string"}}}}]}
    db_path = str(tmp_path / "registry.db")
    registry = ToolRegistry(db_path)
    try:
        status = registry.register_server_inventory(inventory)
        assert registry.approve_server_inventory("approval-fixture", status.inventory_hash)
    finally:
        registry.close()
    monkeypatch.setenv("REGISTRY_DB", db_path)
    monkeypatch.setenv("CTG_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("EVENTS_PATH", str(tmp_path / "events.jsonl"))
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    monkeypatch.setenv("MODE", "enforcing")
    monkeypatch.setenv("CTG_SEMANTIC_MODE", "heuristic")
    invoked = []

    class FakeSession:
        async def call_tool(self, name, arguments):
            invoked.append((name, arguments))
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="sent")],
                                   structuredContent=None, isError=False)

    inspector = ModuleType("crosstoolguard.registry.mcp_inspector")

    @asynccontextmanager
    async def open_session(config, *, allow_http=False):
        yield FakeSession(), object()

    async def current_inventory(session, initialized, config):
        return inventory

    inspector.open_mcp_session = open_session
    inspector.inventory_from_session = current_inventory
    choices = iter([
        json.dumps({"done": False, "tool": "approval-fixture/send_data",
                    "arguments_json": '{}', "answer": ""}),
        json.dumps({"done": False, "tool": "approval-fixture/send_data",
                    "arguments_json": '{"content":"hello"}', "answer": ""}),
        json.dumps({"done": True, "tool": "", "arguments_json": "{}", "answer": "done"}),
    ])
    monkeypatch.setattr(providers, "complete_action", lambda *args, **kwargs: next(choices))
    with patch.object(proxy, "_validate_inventory_target", lambda url: None), \
            patch.dict(sys.modules, {"crosstoolguard.registry.mcp_inspector": inspector}), \
            TestClient(proxy.app) as client:
        started = client.post("/api/mcp/agent/run", json={"task": "send hello"}).json()
        session_id = started["session_id"]
        for _ in range(100):
            state = client.get(f"/api/mcp/agent/runs/{session_id}").json()
            if state["status"] == "awaiting_approval":
                break
            time.sleep(0.05)
        assert state["status"] == "awaiting_approval", state
        assert invoked == []
        pending = client.get("/api/approvals").json()["pending"]
        request = next(item for item in pending if item["session"] == session_id)
        assert request["argument_fields"] == ["content"]
        assert request["arguments_sha256"]
        assert "EXTERNAL_TRANSFER" in request["reason"]
        assert request["destination_label"] is None
        approval_id = request["id"]
        assert client.post("/api/approvals/grant",
                           json={"approval_id": approval_id}).status_code == 200
        for _ in range(100):
            state = client.get(f"/api/mcp/agent/runs/{session_id}").json()
            if state["status"] == "complete":
                break
            time.sleep(0.05)
        assert state["status"] == "complete", state
        assert state["answer"] == "done"
        assert len(invoked) == 1
        assert [call["verdict"] for call in state["report"]["calls"]] == ["APPROVAL", "ALLOW"]
        assert "final_answer" not in client.get(f"/api/sessions/{session_id}").json()["report"]
