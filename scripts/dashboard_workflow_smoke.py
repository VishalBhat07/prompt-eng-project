"""End-to-end dashboard API check with three local MCP fixtures and Groq."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosstoolguard.gateway.proxy import app
from crosstoolguard.registry.mcp_inspector import inspect_server
from crosstoolguard.registry.tools import ToolRegistry
from lab.http_mcp_fixture import PORTS


async def inspect_when_ready(server: str) -> dict:
    config = {"server_id": f"fixture-{server}", "transport": "streamable-http",
              "url": f"http://127.0.0.1:{PORTS[server]}/mcp", "headers": {}}
    for _ in range(30):
        try:
            return await inspect_server(config, allow_http=True)
        except Exception:
            await asyncio.sleep(0.5)
    raise RuntimeError(f"fixture {server} did not start")


def main() -> None:
    load_dotenv()
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is required")
    root = Path(__file__).resolve().parents[1]
    processes = []
    try:
        for server in PORTS:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            processes.append(subprocess.Popen(
                [sys.executable, "-m", "lab.http_mcp_fixture", "--server", server],
                cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags))
        inventories = [asyncio.run(inspect_when_ready(server)) for server in PORTS]
        with TemporaryDirectory(prefix="ctg-dashboard-check-") as temp:
            db_path = str(Path(temp) / "registry.db")
            registry = ToolRegistry(db_path)
            try:
                for inventory in inventories:
                    status = registry.register_server_inventory(inventory)
                    assert registry.approve_server_inventory(inventory["server_id"], status.inventory_hash)
            finally:
                registry.close()
            env = {"REGISTRY_DB": db_path, "CTG_RUNS_DIR": str(Path(temp) / "runs"),
                   "EVENTS_PATH": str(Path(temp) / "events.jsonl"), "MODE": "enforcing",
                   "CTG_SEMANTIC_MODE": "heuristic",
                   "MCP_INVENTORY_ALLOWED_HOSTS": "127.0.0.1",
                   "MCP_INVENTORY_ALLOWED_PORTS": ",".join(map(str, PORTS.values())),
                   "MCP_INVENTORY_ALLOW_PRIVATE_NETWORK": "true"}
            with patch.dict(os.environ, env), TestClient(app) as client:
                response = client.post("/api/mcp/agent/run",
                    json={"task": "Find invoice INV-1042 and summarize its total and status.",
                          "provider": "groq", "policy": "hardened"})
                response.raise_for_status()
                session = response.json()["session_id"]
                for _ in range(120):
                    state = client.get(f"/api/mcp/agent/runs/{session}").json()
                    if state["status"] in {"complete", "error"}:
                        break
                    time.sleep(0.5)
                assert state["status"] == "complete", state
                assert state.get("answer"), state
                detail = client.get(f"/api/sessions/{session}").json()
                assert len(detail["potential_paths"]) >= 1, detail
                assert len(detail["signals"]) >= 1, detail
                assert any(node.get("hypothetical") for node in detail["nodes"])
                report = detail["report"]
                assert "final_answer" not in report
                print("Agent calls:", [(call["tool"], call.get("verdict")) for call in report["calls"]])
                print("Possible paths:", len(detail["potential_paths"]),
                      "| Suspicious output signals:", len(detail["signals"]),
                      "| Observed attack findings:", len(detail["paths"]))
                print("Run outcome:", report["outcome"])
                print("Halted reason:", report["halted_reason"])
                assert report["outcome"] != "ERROR", report
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
