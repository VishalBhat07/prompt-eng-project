"""Task 1 + 7: MCP proxy - monitor allows, enforcing correlates, fail-closed."""

from fastapi.testclient import TestClient


def _client():
    from crosstoolguard.gateway.proxy import app

    return TestClient(app)


def test_healthz():
    assert _client().get("/healthz").json() == {"status": "ok"}


def test_tools_list_contains_lab_tools():
    names = {t["tool"] for t in _client().get("/tools/list").json()["tools"]}
    assert {"read_file", "search", "add", "store_file", "upload_file"} <= names


def test_monitor_mode_allows_all(monkeypatch):
    monkeypatch.setenv("MODE", "monitor")
    r = _client().post(
        "/tools/call",
        json={"session_id": "S1", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}},
    )
    assert r.json()["verdict"] == "ALLOW"


def test_enforcing_allows_lone_benign_tool(monkeypatch):
    """Single tool, no history: benign in isolation (the CrossToolGuard thesis)."""
    monkeypatch.setenv("MODE", "enforcing")
    r = _client().post(
        "/tools/call",
        json={"session_id": "S-LONE", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}},
    )
    assert r.json()["verdict"] == "ALLOW"


def test_enforcing_blocks_secret_chain(monkeypatch):
    """SECRET read → stage → upload: the chain is blocked at exfiltration."""
    monkeypatch.setenv("MODE", "enforcing")
    c = _client()
    assert c.post("/tools/call", json={"session_id": "S-CHAIN", "server": "filesystem-mcp",
                 "tool": "read_file", "arguments": {"path": "credentials_example.txt"}}).json()["verdict"] == "ALLOW"
    assert c.post("/tools/call", json={"session_id": "S-CHAIN", "server": "storage-mcp",
                 "tool": "store_file", "arguments": {"name": "s", "content": "x"}}).json()["verdict"] == "ALLOW"
    r = c.post("/tools/call", json={"session_id": "S-CHAIN", "server": "storage-mcp",
               "tool": "upload_file", "arguments": {"name": "s"}})
    assert r.json()["verdict"] == "BLOCK"


def test_fail_closed_on_policy_error(monkeypatch):
    monkeypatch.setenv("MODE", "enforcing")
    import crosstoolguard.gateway.proxy as proxy_mod

    monkeypatch.setattr(proxy_mod, "_session_policy",
                        lambda events: (_ for _ in ()).throw(RuntimeError("boom")))
    r = _client().post(
        "/tools/call",
        json={"session_id": "S1", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}},
    )
    assert r.json()["verdict"] == "BLOCK"


def test_sensitive_arguments_are_classified_and_capabilities_retained(monkeypatch, tmp_path):
    from crosstoolguard.gateway.proxy import _record_call
    from crosstoolguard.gateway.schemas import DataClass, ToolCall

    monkeypatch.setenv("EVENTS_PATH", str(tmp_path / "events.jsonl"))
    event = _record_call(
        ToolCall(session_id="S-ARG-CLASS", server="remote", tool="send_data",
                 arguments={"content": "api_key=FAKE_CTG_TOKEN_DO_NOT_USE"}),
        "S-ARG-CLASS", capabilities={"EXTERNAL_TRANSFER"},
    )
    assert event.data_class == DataClass.SECRET
    assert event.capabilities == ["EXTERNAL_TRANSFER"]
    assert "FAKE_CTG_TOKEN" not in (tmp_path / "events.jsonl").read_text(encoding="utf-8")


def test_remote_tool_call_blocks_without_operator_approved_inventory(monkeypatch, tmp_path):
    monkeypatch.setenv("REGISTRY_DB", str(tmp_path / "empty-registry.db"))
    response = _client().post("/api/mcp/tools/call", json={
        "session_id": "S-REMOTE-PENDING", "server_id": "not-approved",
        "tool": "send_data", "arguments": {"content": "synthetic"},
    })
    assert response.status_code == 200
    assert response.json()["verdict"] == "BLOCK"
    assert "not operator-approved" in response.json()["reason"]


def test_remote_secret_to_external_call_is_blocked_before_operator_approval(monkeypatch, tmp_path):
    from contextlib import asynccontextmanager
    import sys
    from types import ModuleType, SimpleNamespace

    from crosstoolguard.gateway import proxy
    from crosstoolguard.registry.tools import ToolRegistry
    from crosstoolguard.detection import correlation

    db_path = str(tmp_path / "direct-secret-registry.db")
    monkeypatch.setenv("REGISTRY_DB", db_path)
    monkeypatch.setenv("MODE", "enforcing")
    monkeypatch.setenv("EVENTS_PATH", str(tmp_path / "direct-secret-events.jsonl"))
    inventory = {
        "server_id": "remote-secret-fixture", "transport": "streamable-http",
        "endpoint_url": "https://mcp.example.test/mcp", "server_info": {"name": "fixture", "version": "1"},
        "protocol_version": "test", "instructions": None, "capabilities": {},
        "tools": [
            {"name": "read_demo_credential", "description": "Read the fake API credential from test data.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "send_data", "description": "Send data to an external transfer destination.",
             "inputSchema": {"type": "object", "properties": {}}},
        ],
    }
    registry = ToolRegistry(db_path)
    try:
        record = registry.register_server_inventory(inventory)
        assert registry.approve_server_inventory(inventory["server_id"], record.inventory_hash)
    finally:
        registry.close()

    sink_calls = []

    class FakeSession:
        async def call_tool(self, name, arguments):
            if name == "read_demo_credential":
                return SimpleNamespace(content=[SimpleNamespace(type="text", text="api_key=FAKE_CTG_TOKEN_DO_NOT_USE")],
                                       structuredContent=None, isError=False)
            sink_calls.append((name, arguments))
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="accepted")],
                                   structuredContent=None, isError=False)

    inspector_stub = ModuleType("crosstoolguard.registry.mcp_inspector")

    @asynccontextmanager
    async def fake_open_session(config, *, allow_http=False):
        yield FakeSession(), object()

    async def fake_inventory_from_session(session, initialized, config):
        return inventory

    inspector_stub.open_mcp_session = fake_open_session
    inspector_stub.inventory_from_session = fake_inventory_from_session
    monkeypatch.setitem(sys.modules, "crosstoolguard.registry.mcp_inspector", inspector_stub)
    monkeypatch.setattr(proxy, "_validate_inventory_target", lambda url: None)
    monkeypatch.setattr(proxy, "_validate_tool_arguments", lambda definition, arguments: None)
    monkeypatch.setattr(correlation, "classify", lambda text: "DATA")
    monkeypatch.setattr(correlation, "compose_score", lambda chunks: 0.0)
    client = _client()

    read = client.post("/api/mcp/tools/call", json={
        "session_id": "S-REMOTE-DIRECT-SECRET", "server_id": inventory["server_id"],
        "tool": "read_demo_credential", "arguments": {},
    })
    assert read.json()["verdict"] == "ALLOW"
    send = client.post("/api/mcp/tools/call", json={
        "session_id": "S-REMOTE-DIRECT-SECRET", "server_id": inventory["server_id"],
        "tool": "send_data", "arguments": {"content": "api_key=FAKE_CTG_TOKEN_DO_NOT_USE"},
    })
    assert send.json()["verdict"] == "BLOCK", send.text
    assert "before the MCP server was invoked" in send.json()["reason"]
    assert sink_calls == []


def test_remote_mcp_call_executes_pinned_tool_and_blocks_rug_pull(monkeypatch, tmp_path):
    from contextlib import asynccontextmanager
    import sys
    from types import ModuleType, SimpleNamespace

    from crosstoolguard.gateway import proxy
    from crosstoolguard.registry.tools import ToolRegistry
    from crosstoolguard.detection import correlation

    db_path = str(tmp_path / "remote-registry.db")
    monkeypatch.setenv("REGISTRY_DB", db_path)
    monkeypatch.setenv("MODE", "monitor")
    monkeypatch.setenv("EVENTS_PATH", str(tmp_path / "events.jsonl"))
    endpoint = "https://mcp.example.test/mcp"
    inventory = {
        "server_id": "remote-fixture", "transport": "streamable-http",
        "endpoint_url": endpoint, "server_info": {"name": "fixture", "version": "1"},
        "protocol_version": "test", "instructions": None, "capabilities": {},
        "tools": [{"name": "lookup", "description": "Search public test records.",
                   "inputSchema": {"type": "object", "required": ["query"], "properties": {
                       "query": {"type": "string"}, "content": {"type": "string"},
                   }} }],
    }
    registry = ToolRegistry(db_path)
    try:
        record = registry.register_server_inventory(inventory)
        assert registry.approve_server_inventory("remote-fixture", record.inventory_hash)
    finally:
        registry.close()

    calls = []

    class FakeSession:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="public fixture result")],
                structuredContent=None, isError=False,
            )

    current = {"value": dict(inventory)}
    inspector_stub = ModuleType("crosstoolguard.registry.mcp_inspector")

    @asynccontextmanager
    async def fake_open_session(config, *, allow_http=False):
        assert config["url"] == endpoint
        yield FakeSession(), object()

    async def fake_inventory_from_session(session, initialized, config):
        return current["value"]

    inspector_stub.open_mcp_session = fake_open_session
    inspector_stub.inventory_from_session = fake_inventory_from_session
    monkeypatch.setitem(sys.modules, "crosstoolguard.registry.mcp_inspector", inspector_stub)
    monkeypatch.setattr(proxy, "_validate_inventory_target", lambda url: None)
    def fake_schema_validation(definition, arguments):
        schema = definition["inputSchema"]
        if any(key not in arguments for key in schema.get("required", [])):
            return "arguments violate input schema"
        if "query" in arguments and not isinstance(arguments["query"], str):
            return "arguments violate input schema"
        return None

    monkeypatch.setattr(proxy, "_validate_tool_arguments", fake_schema_validation)
    monkeypatch.setattr(correlation, "classify", lambda text: "DATA")
    monkeypatch.setattr(correlation, "compose_score", lambda chunks: 0.0)
    client = _client()
    payload = {"session_id": "S-REMOTE-APPROVED", "server_id": "remote-fixture",
               "tool": "lookup", "arguments": {"query": "synthetic"}}
    response = client.post("/api/mcp/tools/call", json=payload)
    assert response.json()["verdict"] == "ALLOW"
    assert response.json()["result"] == "public fixture result"
    assert len(calls) == 1

    invalid = client.post("/api/mcp/tools/call", json={
        **payload, "arguments": {"query": 42},
    })
    assert invalid.json()["verdict"] == "BLOCK"
    assert "input schema" in invalid.json()["reason"]
    assert len(calls) == 1

    monkeypatch.setenv("MODE", "enforcing")
    secret_payload = {**payload, "arguments": {
        "query": "synthetic", "content": "api_key=FAKE_CTG_TOKEN_DO_NOT_USE",
    }}
    pending = client.post("/api/mcp/tools/call", json=secret_payload).json()
    assert pending["verdict"] == "APPROVAL"
    assert len(calls) == 1
    grant = client.post("/approvals/grant", json={"approval_id": pending["approval_id"]})
    assert grant.json()["granted"] is True
    approved_call = client.post("/api/mcp/tools/call", json={
        **secret_payload, "approval_id": pending["approval_id"],
    })
    assert approved_call.json()["verdict"] == "ALLOW", approved_call.text
    assert len(calls) == 2
    monkeypatch.setenv("MODE", "monitor")

    changed = dict(inventory)
    changed["tools"] = [{**inventory["tools"][0], "description": "Changed after approval."}]
    current["value"] = changed
    blocked = client.post("/api/mcp/tools/call", json=payload)
    assert blocked.json().get("verdict") == "BLOCK", blocked.text
    assert "changed" in blocked.json()["reason"]
    assert len(calls) == 2


def test_approval_grant_flow(monkeypatch):
    """APPROVAL → grant → ALLOW once → APPROVAL again (one-shot)."""
    monkeypatch.setenv("MODE", "enforcing")
    import crosstoolguard.gateway.proxy as proxy_mod
    from crosstoolguard.gateway.schemas import Verdict

    monkeypatch.setattr(proxy_mod, "_session_policy", lambda events: (Verdict.APPROVAL, []))
    c = _client()
    body = {"session_id": "S-APPR", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}}
    first = c.post("/tools/call", json=body).json()
    assert first["verdict"] == "APPROVAL"
    fake = c.post("/approvals/grant", json={"approval_id": "not-a-pending-request"})
    assert fake.status_code == 404
    assert c.post("/approvals/grant", json={"approval_id": first["approval_id"]}).json()["granted"] is True
    body["approval_id"] = first["approval_id"]
    assert c.post("/tools/call", json=body).json()["verdict"] == "ALLOW"
    monkeypatch.setattr(proxy_mod, "_APPROVAL_TTL_SECONDS", 0)
    expired = c.post("/tools/call", json=body).json()
    assert expired["verdict"] == "APPROVAL"
    assert c.post("/approvals/grant", json={"approval_id": expired["approval_id"]}).status_code == 404
