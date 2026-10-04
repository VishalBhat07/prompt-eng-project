"""Task 1 RED: MCP proxy — monitor allows, enforcing blocks, fail-closed."""

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


def test_enforcing_mode_blocks_external_transfer(monkeypatch):
    monkeypatch.setenv("MODE", "enforcing")
    r = _client().post(
        "/tools/call",
        json={"session_id": "S1", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}},
    )
    assert r.json()["verdict"] in ("BLOCK", "APPROVAL")


def test_fail_closed_on_policy_error(monkeypatch):
    monkeypatch.setenv("MODE", "enforcing")
    import crosstoolguard.gateway.proxy as proxy_mod

    monkeypatch.setattr(proxy_mod, "_stub_decide", lambda event: (_ for _ in ()).throw(RuntimeError("boom")))
    r = _client().post(
        "/tools/call",
        json={"session_id": "S1", "server": "storage-mcp", "tool": "upload_file", "arguments": {"name": "x"}},
    )
    assert r.json()["verdict"] == "BLOCK"
