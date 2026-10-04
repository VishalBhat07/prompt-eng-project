"""Task 1 + 7: MCP proxy — monitor allows, enforcing correlates, fail-closed."""

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

    monkeypatch.setattr(proxy_mod, "decide_for_session",
                        lambda events: (_ for _ in ()).throw(RuntimeError("boom")))
    r = _client().post(
        "/tools/call",
        json={"session_id": "S1", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}},
    )
    assert r.json()["verdict"] == "BLOCK"


def test_approval_grant_flow(monkeypatch):
    """APPROVAL → grant → ALLOW once → APPROVAL again (one-shot)."""
    monkeypatch.setenv("MODE", "enforcing")
    import crosstoolguard.gateway.proxy as proxy_mod
    from crosstoolguard.gateway.schemas import Verdict

    monkeypatch.setattr(proxy_mod, "decide_for_session", lambda events: Verdict.APPROVAL)
    c = _client()
    body = {"session_id": "S-APPR", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}}
    first = c.post("/tools/call", json=body).json()
    assert first["verdict"] == "APPROVAL"
    assert c.post("/approvals/grant", json={"approval_id": first["approval_id"]}).json()["granted"] is True
    body["approval_id"] = first["approval_id"]
    assert c.post("/tools/call", json=body).json()["verdict"] == "ALLOW"
    assert c.post("/tools/call", json=body).json()["verdict"] == "APPROVAL"
