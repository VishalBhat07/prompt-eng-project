"""Compare automatic and explicit server scope using benign local MCP data."""

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard_browser_smoke import free_port
from run_replay_evaluation import grouped_rate

MANIFEST = ROOT / "crosstoolguard/evaluation/data/BENIGN_TASKS_V1.yaml"


@dataclass(frozen=True)
class Fixture:
    tool: str
    description: str
    values: dict


FIXTURES = {
    "catalog": Fixture("find_book", "Find the exact title of a book by its catalog ID.", {"B101": "River Atlas", "B202": "Cloud Almanac"}),
    "shelves": Fixture("find_shelf", "Find a book's shelf identifier by book ID.", {"B101": "K-14", "B202": "M-22"}),
    "hours": Fixture("find_hours", "Find the closing time by library branch name.", {"CEDAR": "18:45", "BIRCH": "16:30"}),
}


def serve(kind, port):
    from mcp.server.fastmcp import FastMCP

    fixture = FIXTURES[kind]
    server = FastMCP(kind, host="127.0.0.1", port=port, stateless_http=True, json_response=True)

    @server.tool(name=fixture.tool, description=fixture.description)
    def lookup(query: str) -> str:
        return fixture.values.get(query.strip().upper(), "No matching record")

    server.run(transport="streamable-http")


async def inventory_ready(server, port):
    from crosstoolguard.registry.mcp_inspector import inspect_server

    for _ in range(32):
        try:
            return await inspect_server({"server_id": server, "transport": "streamable-http",
                                         "url": f"http://127.0.0.1:{port}/mcp"}, allow_http=True)
        except Exception:
            await asyncio.sleep(.25)
    raise RuntimeError(f"fixture unavailable: {server}")


def execute(client, task, condition, provider, model):
    request = {"task": task["task"], "provider": provider, "model": model,
               "auto_discover": condition == "automatic", "max_steps": 5}
    if condition == "explicit_scope":
        request["server_ids"] = sorted({ref.split("/")[0] for ref in task["required"]})
    start = time.perf_counter()
    response = client.post("/api/mcp/agent/run", json=request)
    if not response.is_success:
        return {"error": f"start_http_{response.status_code}", "completed": False, "candidate_recall": False}
    session = response.json()["session_id"]
    deadline = time.monotonic() + 60
    status = {}
    while time.monotonic() < deadline:
        status = client.get(f"/api/mcp/agent/runs/{session}").json()
        if status["status"] in {"complete", "error", "awaiting_approval"}:
            break
        time.sleep(.1)
    report = status.get("report") or {}
    answer = status.get("answer") or ""
    calls = report.get("calls", [])
    allowed = {call["tool"] for call in calls if call.get("verdict") == "ALLOW"}
    candidates = report.get("allowed_tools", [])
    reason = report.get("halted_reason", status.get("error", status.get("status", "timeout")))
    error = reason if report.get("outcome") == "ERROR" or status.get("status") in {"running", "error"} else None
    completed = (report.get("outcome") == "COMPLETED" and set(task["required"]) <= allowed
                 and all(term.casefold() in answer.casefold() for term in task["answer_terms"]))
    return {"session_id": session, "calls": calls, "candidates": candidates, "completed": completed,
            "candidate_recall": set(task["required"]) <= set(candidates), "answer": answer,
            "elapsed_ms": (time.perf_counter() - start) * 1000, "halted_reason": reason, "error": error}


def evaluate(args):
    load_dotenv(ROOT / ".env")
    from crosstoolguard.gateway.proxy import app
    from crosstoolguard.llm.providers import is_configured, resolve
    from crosstoolguard.registry.tools import ToolRegistry

    provider, model = resolve(args.provider, args.model)
    if not is_configured(provider):
        raise SystemExit(f"{provider} credentials are missing")
    raw = MANIFEST.read_bytes()
    manifest = yaml.safe_load(raw)
    rng = random.Random(manifest["seed"])
    schedule = []
    for repeat in range(1, manifest["repeats"] + 1):
        tasks = manifest["tasks"].copy()
        rng.shuffle(tasks)
        for task in tasks:
            conditions = ["automatic", "explicit_scope"]
            rng.shuffle(conditions)
            schedule.extend((task, condition, repeat) for condition in conditions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows_file = args.output.with_suffix(".jsonl")
    processes = []
    rows = []
    with TemporaryDirectory(prefix="ctg-benign-eval-") as temp:
        try:
            ports = {server: free_port() for server in FIXTURES}
            for server, port in ports.items():
                processes.append(subprocess.Popen([sys.executable, __file__, "--fixture", server, str(port)],
                    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
            registry_path = str(Path(temp) / "registry.db")
            registry = ToolRegistry(registry_path)
            inventory_hashes = {}
            try:
                for server, port in ports.items():
                    record = registry.register_server_inventory(asyncio.run(inventory_ready(server, port)))
                    if not registry.approve_server_inventory(server, record.inventory_hash):
                        raise RuntimeError(f"could not approve {server}")
                    inventory_hashes[server] = record.inventory_hash
            finally:
                registry.close()
            environment = {"REGISTRY_DB": registry_path, "CTG_RUNS_DIR": str(Path(temp) / "runs"),
                "EVENTS_PATH": str(Path(temp) / "events.jsonl"), "MODE": "enforcing",
                "CTG_SEMANTIC_MODE": "heuristic", "CTG_MAX_AGENT_CONTEXT_CHARS": "20000",
                "MCP_INVENTORY_ALLOW_PRIVATE_NETWORK": "true", "MCP_INVENTORY_ALLOWED_HOSTS": "127.0.0.1",
                "MCP_INVENTORY_ALLOWED_PORTS": ",".join(map(str, ports.values()))}
            with patch.dict(os.environ, environment), TestClient(app) as client, rows_file.open("w", encoding="utf-8") as file:
                for task, condition, repeat in schedule:
                    result = execute(client, task, condition, provider, model)
                    row = {"group": task["id"], "condition": condition, "repeat": repeat,
                           "required": task["required"], "expected_answer_terms": task["answer_terms"], **result}
                    rows.append(row)
                    file.write(json.dumps(row) + "\n")
                    file.flush()
                    print(task["id"], condition, repeat, result["completed"], result.get("error"), flush=True)
                    if args.interval:
                        time.sleep(args.interval)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
    summary = {}
    for condition in ("automatic", "explicit_scope"):
        sample = [row for row in rows if row["condition"] == condition]
        available = [row for row in sample if not row.get("error")]
        summary[condition] = {
            "completion": grouped_rate(sample, lambda row: row["completed"]),
            "completion_without_errors": grouped_rate(available, lambda row: row["completed"]) if available else None,
            "candidate_recall": grouped_rate(sample, lambda row: row["candidate_recall"]),
            "errors": dict(Counter(row["error"] for row in sample if row.get("error"))),
        }
    report = {"dataset": "benign_local_v1", "provider": provider, "model": model,
              "task_sha256": hashlib.sha256(raw).hexdigest(), "inventory_hashes": inventory_hashes,
              "seed": manifest["seed"], "scheduled_runs": len(schedule), "results": rows_file.name, "summary": summary}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", nargs=2, help=argparse.SUPPRESS)
    parser.add_argument("--provider", default="groq")
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    parser.add_argument("--interval", type=float, default=1.5)
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/benign-v1.json")
    args = parser.parse_args()
    if args.fixture:
        serve(args.fixture[0], int(args.fixture[1]))
    else:
        evaluate(args)


if __name__ == "__main__":
    main()
