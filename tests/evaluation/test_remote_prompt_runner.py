import asyncio
import json

import httpx

from crosstoolguard.evaluation.remote_prompt_runner import run_remote_task


def test_remote_runner_routes_model_choice_through_guard_and_records_result():
    requests = []
    inventory = {
        "server_id": "public-echo", "integrity_status": "APPROVED", "inventory_hash": "abc",
        "tools": [{"name": "echo", "description": "Repeat text", "inputSchema": {"type": "object"}}],
    }

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/registry/inventories":
            assert request.url.params["server_id"] == "public-echo"
            return httpx.Response(200, json={"inventories": [inventory]})
        assert request.url.path == "/api/mcp/tools/call"
        assert json.loads(request.content)["tool"] == "echo"
        return httpx.Response(200, json={"verdict": "ALLOW", "result": "hello"})

    choices = iter(['{"tool":"echo","arguments":{"text":"hello"}}',
                    '{"done":true,"answer":"hello"}'])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://guard") as client:
            return await run_remote_task(proxy_url="http://guard", server_id="public-echo",
                                         task="Repeat hello", allowed_tool_names=["echo"],
                                         provider="groq", model="fake", require_tools=["echo"],
                                         complete_fn=lambda *args, **kwargs: next(choices), client=client)

    report = asyncio.run(run())
    assert report["outcome"] == "PASS"
    assert report["calls"][0]["verdict"] == "ALLOW"
    assert report["halted_reason"] == "completed"
    assert len(requests) == 2


def test_blocked_forbidden_tool_is_successful_defense():
    inventory = {"server_id": "s", "integrity_status": "APPROVED", "tools": [
        {"name": "send", "description": "Send text", "inputSchema": {"type": "object"}}]}

    def handler(request):
        if request.url.path.endswith("inventories"):
            return httpx.Response(200, json={"inventories": [inventory]})
        return httpx.Response(200, json={"verdict": "BLOCK", "reason": "policy"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://guard") as client:
            return await run_remote_task(proxy_url="http://guard", server_id="s", task="test",
                                         allowed_tool_names=["send"], provider="groq", model="fake",
                                         forbid_tools=["send"], client=client,
                                         complete_fn=lambda *args, **kwargs: '{"tool":"send","arguments":{}}')

    report = asyncio.run(run())
    assert report["outcome"] == "PASS"
    assert report["halted_reason"] == "guarded_call_block"
