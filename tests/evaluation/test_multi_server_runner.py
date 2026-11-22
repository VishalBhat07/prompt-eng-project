import asyncio

import httpx

from crosstoolguard.evaluation.multi_server_runner import run_multi_server_task


def test_duplicate_model_action_does_not_call_mcp_twice():
    posts = []
    inventory = {"server_id": "invoice", "integrity_status": "APPROVED", "tools": [
        {"name": "search", "description": "Search invoices", "inputSchema": {"type": "object"}}]}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"inventories": [inventory]})
        posts.append(request)
        return httpx.Response(200, json={"verdict": "ALLOW", "result": "synthetic invoice"})

    choices = iter([
        '{"tool":"invoice/search","arguments":{"query":"x"}}',
        '{"tool":"invoice/search","arguments":{"query":"x"}}',
        '{"done":true,"answer":"done"}',
    ])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://guard") as client:
            return await run_multi_server_task(
                proxy_url="http://guard", task="Find invoice", allowed_tools=["invoice/search"],
                provider="groq", model="fake", require_tools=["invoice/search"],
                complete_fn=lambda *args, **kwargs: next(choices), client=client)

    report = asyncio.run(run())
    assert report["outcome"] == "PASS"
    assert report["duplicate_proposals"] == 1
    assert len(posts) == 1


def test_search_loop_stops_after_tool_call_limit():
    posts = []
    inventory = {"server_id": "invoice", "integrity_status": "APPROVED", "tools": [
        {"name": "search", "description": "Search invoices", "inputSchema": {"type": "object"}}]}

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"inventories": [inventory]})
        posts.append(request)
        return httpx.Response(200, json={"verdict": "ALLOW", "result": "No match"})

    choices = iter([
        '{"tool":"invoice/search","arguments":{"query":"one"}}',
        '{"tool":"invoice/search","arguments":{"query":"two"}}',
        '{"tool":"invoice/search","arguments":{"query":"three"}}',
        '{"done":true,"answer":"No matching invoice was found."}',
    ])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://guard") as client:
            return await run_multi_server_task(
                proxy_url="http://guard", task="Find invoice", allowed_tools=["invoice/search"],
                provider="groq", model="fake", require_tools=["invoice/search"],
                complete_fn=lambda *args, **kwargs: next(choices), client=client)

    report = asyncio.run(run())
    assert report["outcome"] == "PASS"
    assert report["tool_limit_proposals"] == 1
    assert len(posts) == 2
