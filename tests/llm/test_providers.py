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


def test_groq_agent_action_uses_strict_json_schema(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace
    from crosstoolguard.llm.providers import complete_action

    captured = {}
    groq_module = ModuleType("groq")

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"done":true,"tool":"","arguments_json":"{}","answer":"ok"}'))])

    groq_module.Groq = FakeGroq
    groq_module.BadRequestError = type("BadRequestError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "groq", groq_module)
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    result = complete_action("groq", "openai/gpt-oss-120b", [{"role": "user", "content": "test"}])
    assert '"done":true' in result
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert captured["reasoning_format"] == "hidden"


def test_groq_agent_action_retries_json_validation_failure(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace
    from crosstoolguard.llm.providers import complete_action

    formats = []

    class FakeBadRequestError(Exception):
        body = {"error": {"code": "json_validate_failed"}}

    class FakeGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kwargs):
            formats.append(kwargs["response_format"]["type"])
            if len(formats) == 1:
                raise FakeBadRequestError()
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"done":true,"answer":"ok"}'))])

    groq_module = ModuleType("groq")
    groq_module.Groq = FakeGroq
    groq_module.BadRequestError = FakeBadRequestError
    monkeypatch.setitem(sys.modules, "groq", groq_module)
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    assert '"done":true' in complete_action("groq", "openai/gpt-oss-120b", [{"role": "user", "content": "test"}])
    assert formats == ["json_schema", "json_object"]
