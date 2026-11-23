"""Exercise the real dashboard and gateway with inert data and a scripted model."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_http(url, process):
    for _ in range(80):
        if process.poll() is not None:
            raise RuntimeError(f"Server exited while starting {url}")
        try:
            if httpx.get(url, timeout=1).is_success:
                return
        except httpx.RequestError:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Server did not become ready: {url}")


def gateway():
    import uvicorn
    from crosstoolguard.llm import providers

    def scripted_action(provider, model, messages, **kwargs):
        task = messages[1]["content"].splitlines()[0].lower()
        tool = "fixture-send/send_data" if "send harmless" in task else "fixture-send/inspect_mock_sink"
        if any("Tool result from " in item["content"] for item in messages[2:]):
            return json.dumps({"done": True, "tool": "", "arguments_json": "{}", "answer": "Fixture task complete."})
        args = {"content": "hello dashboard"} if tool.endswith("/send_data") else {}
        return json.dumps({"done": False, "tool": tool, "arguments_json": json.dumps(args), "answer": ""})

    providers.complete_action = scripted_action
    uvicorn.run("crosstoolguard.gateway.proxy:app", host="127.0.0.1", port=int(os.environ["CTG_SMOKE_GATEWAY_PORT"]))


def smoke():
    from playwright.sync_api import expect, sync_playwright

    expect.set_options(timeout=15000)
    gateway_port, fixture_port, ui_port = (free_port() for _ in range(3))
    gateway_url = f"http://127.0.0.1:{gateway_port}"
    fixture_url = f"http://127.0.0.1:{fixture_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    dashboard = ROOT / "dashboard"
    processes = []

    def start(args, cwd=ROOT):
        process = subprocess.Popen(args, cwd=cwd, env=env,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        processes.append(process)
        return process

    with TemporaryDirectory(prefix="ctg-browser-smoke-") as temp:
        env = {**os.environ, "GROQ_API_KEY": "local-scripted-model",
               "REGISTRY_DB": str(Path(temp) / "registry.db"),
               "EVENTS_PATH": str(Path(temp) / "events.jsonl"),
               "CTG_RUNS_DIR": str(Path(temp) / "runs"),
               "MODE": "enforcing", "CTG_SEMANTIC_MODE": "heuristic",
               "MCP_INVENTORY_API_ENABLED": "true", "MCP_INVENTORY_ALLOWED_HOSTS": "127.0.0.1",
               "MCP_INVENTORY_ALLOWED_PORTS": str(fixture_port), "MCP_INVENTORY_ALLOW_PRIVATE_NETWORK": "true",
               "CTG_DASHBOARD_GATEWAY": gateway_url, "CTG_SMOKE_GATEWAY_PORT": str(gateway_port),
               "CTG_SMOKE_FIXTURE_PORT": str(fixture_port)}
        gateway_cmd = [sys.executable, __file__, "--gateway"]
        try:
            start([sys.executable, __file__, "--fixture"])
            api = start(gateway_cmd)
            wait_http(gateway_url + "/healthz", api)
            ui = start(["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1",
                        "--port", str(ui_port), "--strictPort"], dashboard)
            wait_http(ui_url, ui)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel=os.getenv("CTG_SMOKE_BROWSER", "msedge"))
                page = browser.new_page()
                page.set_default_timeout(15000)
                page.goto(ui_url + "/inventory")
                page.get_by_label("Inventory ID").fill("fixture-send")
                page.get_by_label("MCP server URL").fill(fixture_url + "/mcp")
                page.get_by_role("button", name="Inventory server").click()
                card = page.locator("summary").filter(has_text="fixture-send")
                expect(card).to_be_visible()
                expect(page.get_by_role("button", name="Approve and pin this exact fingerprint")).to_be_hidden()
                page.get_by_role("searchbox").fill("inspect_mock_sink")
                expect(card).to_be_visible()
                card.click()
                page.get_by_role("button", name="Approve and pin this exact fingerprint").click()
                expect(page.get_by_role("button", name="Revoke approval")).to_be_visible()
                page.get_by_role("button", name="Revoke approval").click()
                expect(page.get_by_text("Revoked approval for fixture-send", exact=False)).to_be_visible()
                page.goto(ui_url + "/demo")
                expect(page.get_by_text("No approved servers.", exact=False)).to_be_visible()
                page.goto(ui_url + "/inventory")
                page.locator("summary").filter(has_text="fixture-send").click()
                page.get_by_role("button", name="Approve and pin this exact fingerprint").click()
                expect(page.get_by_role("button", name="Revoke approval")).to_be_visible()
                page.goto(ui_url + "/demo")
                expect(page.get_by_label("Model provider")).to_be_hidden()
                page.get_by_text("Run settings", exact=False).click()
                expect(page.get_by_label("Model provider")).to_be_visible()
                page.get_by_text("Run settings", exact=False).click()
                page.get_by_label("Task", exact=True).fill("Inspect the local mock destination count")
                page.get_by_role("button", name="Run task").click()
                expect(page.get_by_text("Fixture task complete.")).to_be_visible()
                page.get_by_role("button", name="Start another run").click()
                page.get_by_label("Task", exact=True).fill("Send harmless text to the local mock destination")
                page.get_by_role("button", name="Run task").click()
                expect(page.get_by_text("Approval required: fixture-send/send_data")).to_be_visible()
                run_url = page.url
                page.goto(ui_url + "/approvals")
                with page.expect_response(lambda response: response.url.endswith("/api/approvals/grant")) as grant:
                    page.get_by_role("button", name="Grant once").click()
                assert grant.value.ok
                page.goto(run_url)
                expect(page.get_by_text("Fixture task complete.")).to_be_visible()
                page.get_by_role("link", name="Open this session's graph").click()
                expect(page.get_by_text("fixture-send/send_data → ALLOW")).to_be_visible()
                graph_url = page.url
                page.goto(ui_url + "/findings")
                expect(page.get_by_text("No attack paths detected", exact=False)).to_be_visible()
                page.goto(ui_url + "/demo")
                page.get_by_label("Task", exact=True).fill("Send harmless text to the local mock destination")
                page.get_by_role("button", name="Run task").click()
                expect(page.get_by_text("Approval required: fixture-send/send_data")).to_be_visible()
                page.get_by_role("button", name="Deny", exact=True).click()
                expect(page.get_by_text("The sensitive action was not executed", exact=False)).to_be_visible()
                expect(page.get_by_role("region", name="Task result").locator("[data-verdict='ALLOW']")).to_have_count(0)
                counter = httpx.post(gateway_url + "/api/mcp/tools/call", json={
                    "session_id": "smoke-counter", "server_id": "fixture-send",
                    "tool": "inspect_mock_sink", "arguments": {},
                })
                counter.raise_for_status()
                counter_body = counter.json()
                assert counter_body["verdict"] == "ALLOW"
                assert json.loads(counter_body["result"])["item_count"] == 1
                invalid = httpx.post(gateway_url + "/api/mcp/tools/call", json={
                    "session_id": "smoke-invalid-args", "server_id": "fixture-send",
                    "tool": "send_data", "arguments": {"content": 123},
                })
                assert invalid.json()["verdict"] == "BLOCK"
                page.goto(ui_url + "/findings")
                block = page.get_by_text("Why was this blocked?", exact=False)
                block.click()
                expect(page.get_by_text("Tool arguments failed the reviewed input schema", exact=False)).to_be_visible()
                page.get_by_role("link", name="Inspect evidence in graph").click()
                assert "focus=" in page.url
                baseline = page.get_by_role("region", name="Single-tool detector graph")
                graph = page.get_by_role("region", name="CrossToolGuard session graph")
                expect(graph.get_by_text("Proposed call · BLOCK")).to_be_visible()
                expect(graph.get_by_text("Checks · BLOCK")).to_be_visible()
                expect(baseline).to_have_count(0)
                page.get_by_role("button", name="Single-tool graph").click()
                expect(baseline.get_by_text("Proposed call · blocked by gateway")).to_be_visible()
                expect(graph).to_have_count(0)
                api.terminate()
                api.wait(timeout=10)
                api = start(gateway_cmd)
                wait_http(gateway_url + "/healthz", api)
                page.goto(graph_url)
                expect(page.get_by_text("fixture-send/send_data → ALLOW")).to_be_visible()
                expect(graph.get_by_role("heading", name="CrossToolGuard session graph")).to_be_visible()
                for panel, name in [(baseline, "Single-tool graph"), (graph, "CrossToolGuard graph")]:
                    page.get_by_role("button", name=name).click()
                    expect(panel.get_by_text("Agent ·", exact=False)).to_be_visible()
                    expect(panel.get_by_text("Step 1 ·", exact=False).first).to_be_visible()
                    expect(panel.get_by_text("Step 3 ·", exact=False).first).to_be_visible()
                    expect(panel.get_by_text("Receives output", exact=True)).to_be_visible()
                expect(graph.get_by_text("CrossToolGuard gateway", exact=True)).to_be_visible()
                expect(graph.get_by_text("Checks proposal", exact=True).first).to_be_visible()
                expect(page.locator(".react-flow__minimap")).to_have_count(0)
                page.get_by_role("button", name="Single-tool graph").click()
                expect(baseline.get_by_text("0 flagged / 1 output previews checked")).to_be_visible()
                expect(baseline.get_by_text("Proposes", exact=True).first).to_be_visible()
                expect(page.locator(".react-flow__minimap")).to_have_count(0)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "/graph"
                page.goto(ui_url + "/benchmark")
                expect(page.get_by_text("No benchmark results to display.")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "/benchmark"
                for route in ["/demo", "/inventory", "/sessions", "/approvals", "/findings"]:
                    page.goto(ui_url + route)
                    expect(page.get_by_role("heading", level=1)).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), route
                nav = page.get_by_role("navigation", name="primary")
                nav.get_by_role("link", name="Graph", exact=True).focus()
                page.keyboard.press("Tab")
                expect(nav.get_by_role("link", name="Findings", exact=True)).to_be_focused()
                page.keyboard.press("Enter")
                expect(page.get_by_role("heading", name="Findings")).to_be_visible()
                browser.close()
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
    print("Browser smoke passed: inventory, task, approvals, saved graph, and narrow-screen keyboard navigation.")


if __name__ == "__main__":
    if "--gateway" in sys.argv:
        gateway()
    elif "--fixture" in sys.argv:
        from lab.http_mcp_fixture import make_server
        server = make_server("send")
        server.settings.port = int(os.environ["CTG_SMOKE_FIXTURE_PORT"])
        server.run(transport="streamable-http")
    else:
        smoke()
