"""Playground runner tests — stubbed planner, real enforcement."""


def test_benign_run_completes(monkeypatch):
    monkeypatch.setenv("MODE", "monitor")
    import crosstoolguard.gateway.agent_runner as runner

    monkeypatch.setattr(runner, "plan_with_llm",
                        lambda task, model=None: ("filesystem-mcp", "read_file", {"path": "invoice.txt"}))
    monkeypatch.setattr(runner, "plan_next", lambda task, steps, model=None: ("DONE", "", {}))
    out = runner.run_task("summarize the invoice", session_id="S-RUN-1")
    assert out["done"] is True and out["halted"] is False
    assert out["steps"][0]["verdict"] == "ALLOW"


def test_block_halts_run(monkeypatch):
    monkeypatch.setenv("MODE", "enforcing")
    import crosstoolguard.gateway.agent_runner as runner

    plans = iter([
        ("filesystem-mcp", "read_file", {"path": "credentials_example.txt"}),
        ("storage-mcp", "store_file", {"name": "s", "content": "x"}),
        ("storage-mcp", "upload_file", {"name": "s"}),
    ])
    monkeypatch.setattr(runner, "plan_with_llm", lambda task, model=None: next(plans))
    monkeypatch.setattr(runner, "plan_next", lambda task, steps, model=None: next(plans))
    out = runner.run_task("exfiltrate", session_id="S-RUN-2")
    assert out["halted"] is True and out["done"] is False
    assert [s["verdict"] for s in out["steps"]] == ["ALLOW", "ALLOW", "BLOCK"]


def test_unknown_tool_halts_with_error(monkeypatch):
    monkeypatch.setenv("MODE", "monitor")
    import crosstoolguard.gateway.agent_runner as runner

    monkeypatch.setattr(runner, "plan_with_llm",
                        lambda task, model=None: ("nope-mcp", "nope", {}))
    out = runner.run_task("do the impossible", session_id="S-RUN-3")
    assert out["halted"] is True
    assert out["steps"][0]["verdict"] == "ERROR"


def test_agent_run_endpoint_shape(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("MODE", "monitor")
    import crosstoolguard.gateway.agent_runner as runner
    from crosstoolguard.gateway.proxy import app

    monkeypatch.setattr(runner, "plan_with_llm",
                        lambda task, model=None: ("calculator-mcp", "add", {"a": 1, "b": 2}))
    monkeypatch.setattr(runner, "plan_next", lambda task, steps, model=None: ("DONE", "", {}))
    body = TestClient(app).post("/api/agent/run", json={"task": "add numbers"}).json()
    assert body["done"] is True and body["steps"][0]["tool"] == "add"
