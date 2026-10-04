"""Task 8 RED: dashboard API contract, alerts, NL explanations, WS."""

from fastapi.testclient import TestClient


def _client():
    from crosstoolguard.gateway.proxy import app

    return TestClient(app)


def _drive_chain(session="S-API"):
    c = _client()
    c.post("/tools/call", json={"session_id": session, "server": "filesystem-mcp",
           "tool": "read_file", "arguments": {"path": "credentials_example.txt"}})
    c.post("/tools/call", json={"session_id": session, "server": "storage-mcp",
           "tool": "store_file", "arguments": {"name": "s", "content": "x"}})
    c.post("/tools/call", json={"session_id": session, "server": "storage-mcp",
           "tool": "upload_file", "arguments": {"name": "s"}})
    return c


def test_graph_api_shape():
    c = _drive_chain()
    body = c.get("/api/graph", params={"session": "S-API"}).json()
    assert set(body.keys()) == {"nodes", "edges", "paths"}
    assert any(n["type"] == "DATA" for n in body["nodes"])
    assert any(e["type"] == "SENDS" for e in body["edges"])
    assert body["paths"][0]["pattern"] == "secret_exfiltration"


def test_alerts_contain_explanation():
    c = _drive_chain("S-ALERTS")
    alerts = c.get("/api/alerts", params={"session": "S-ALERTS"}).json()["alerts"]
    assert len(alerts) == 1
    text = alerts[0]["explanation"]
    for needle in ("read_file", "upload_file", "secret-never-external", "BLOCK"):
        assert needle in text


def test_explain_names_origin_policy_decision():
    from crosstoolguard.policy.explain import explain_finding
    from crosstoolguard.detection.correlation import analyze_with_graph
    from tests.detection.test_correlation import _exfil

    graph, findings = analyze_with_graph(_exfil())
    text = explain_finding(graph, findings[0], verdict="BLOCK", policy="secret-never-external")
    for needle in ("read_file", "store_file", "upload_file", "secret-never-external", "BLOCK", "Sensitive"):
        assert needle in text


def test_ws_receives_tool_call_event():
    c = _client()
    with c.websocket_connect("/ws/events") as ws:
        c.post("/tools/call", json={"session_id": "S-WS", "server": "calculator-mcp",
               "tool": "add", "arguments": {"a": 1, "b": 2}})
        msg = ws.receive_json()
    assert msg["tool"] == "add" and msg["session_id"] == "S-WS"
