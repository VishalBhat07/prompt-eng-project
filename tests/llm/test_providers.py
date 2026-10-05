"""Provider layer tests — resolve/validate without network."""


def test_resolve_defaults_and_rejects():
    from crosstoolguard.llm.providers import resolve

    assert resolve(None, None) == ("groq", "openai/gpt-oss-120b")
    assert resolve("openai", None) == ("openai", "gpt-4o-mini")
    try:
        resolve("groq", "nope-9000")
    except ValueError:
        return
    raise AssertionError("unknown model accepted")


def test_list_marks_configured(monkeypatch):
    from crosstoolguard.llm import providers

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    by_id = {p["id"]: p for p in providers.list_providers()}
    assert by_id["groq"]["configured"] is True
    assert by_id["openai"]["configured"] is False
    assert len(by_id["groq"]["models"]) >= 2


def test_runner_passes_provider_through(monkeypatch):
    monkeypatch.setenv("MODE", "monitor")
    import crosstoolguard.gateway.agent_runner as runner

    seen: dict = {}

    def fake_plan(task, model=None, provider="groq"):
        seen["provider"] = provider
        seen["model"] = model
        return ("calculator-mcp", "add", {"a": 1, "b": 2})

    monkeypatch.setattr(runner, "plan_with_llm", fake_plan)
    monkeypatch.setattr(runner, "plan_next", lambda task, steps, model=None, provider="groq": ("DONE", "", {}))
    out = runner.run_task("add", session_id="S-PROV", provider="groq", model="openai/gpt-oss-20b")
    assert seen == {"provider": "groq", "model": "openai/gpt-oss-20b"}
    assert out["provider"] == "groq" and out["done"] is True
