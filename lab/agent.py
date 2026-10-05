"""Minimal ReAct lab agent - Groq-first (free tier), local fallback.

Routes EVERY tool call via PROXY_URL when reachable (CrossToolGuard sees
the full event stream). Falls back to direct local dispatch only when the
proxy is not running (pre-Task-1 dev), with a loud warning.

Usage:
    export GROQ_API_KEY="gsk_..."            # free at console.groq.com
    python lab/agent.py --task "summarize lab/data/invoice.txt"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROXY_URL = os.getenv("PROXY_URL", "http://localhost:8000")
# Verified live on Groq 2026-10-04. gpt-oss are reasoning models: keep
# max_tokens generous (>=1024) or replies come back empty.
AGENT_MODEL = os.getenv("AGENT_MODEL", "openai/gpt-oss-120b")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-oss-20b")

CATALOG = [
    ("filesystem-mcp", "list_files", "List files in the lab data directory.", {}),
    ("filesystem-mcp", "read_file", "Read a file from the lab data directory.", {"path": "invoice.txt"}),
    ("calculator-mcp", "add", "Add two numbers.", {"a": 1, "b": 2}),
    ("search-mcp", "search", "Keyword search over synthetic lab documents.", {"query": "invoice"}),
    ("storage-mcp", "store_file", "Stage content in the lab mock sink.", {"name": "x", "content": "y"}),
]


def _local_dispatch(server: str, tool: str, args: dict) -> str:
    from lab.servers import calculator, filesystem, search, storage

    modules = {
        "filesystem-mcp": filesystem,
        "calculator-mcp": calculator,
        "search-mcp": search,
        "storage-mcp": storage,
    }
    mod = modules.get(server)
    if mod is None:
        return f"ERROR: unknown server {server}"
    fn = mod.TOOLS.get(tool, {}).get("func")
    if fn is None:
        return f"ERROR: unknown tool {tool}"
    try:
        result = fn(**args)
        return str(result)
    except TypeError as exc:
        return f"ERROR: bad args for {tool}: {exc}"


def call_tool(session_id: str, server: str, tool: str, args: dict) -> str:
    """Call a tool via proxy when up, else local fallback (dev only)."""
    try:
        import httpx

        r = httpx.post(
            f"{PROXY_URL}/tools/call",
            json={"session_id": session_id, "server": server, "tool": tool, "arguments": args},
            timeout=5.0,
        )
        r.raise_for_status()
        return str(r.json().get("result", r.text))
    except Exception:
        print(f"[agent] proxy unreachable at {PROXY_URL} - local fallback (dev only)", flush=True)
        return _local_dispatch(server, tool, args)


KNOWN_SERVERS = ("filesystem-mcp", "calculator-mcp", "search-mcp", "storage-mcp")


def _parse_plan(content: str) -> tuple[str, str, dict]:
    """Parse planner JSON, tolerating reasoning preambles around it."""
    import re

    try:
        plan = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", content or "", re.S)
        try:
            plan = json.loads(match.group(0)) if match else {}
        except (json.JSONDecodeError, TypeError, AttributeError):
            return ("filesystem-mcp", "read_file", {"path": "invoice.txt"})
    if plan.get("server") == "DONE":
        return ("DONE", "", {})
    server, tool = str(plan.get("server", "")), str(plan.get("tool", ""))
    if "." in tool:  # models often return "server.tool" in one field
        server, tool = tool.split(".", 1)
    if server not in KNOWN_SERVERS and f"{server}-mcp" in KNOWN_SERVERS:
        server = f"{server}-mcp"
    if not tool:
        return ("filesystem-mcp", "read_file", {"path": "invoice.txt"})
    return (server, tool, plan.get("arguments", {}) or {})


def _groq_plan(messages: list[dict], model: str | None) -> tuple[str, str, dict]:
    """One Groq planning call; offline/error fallback returns a sane default."""
    from groq import Groq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("[agent] GROQ_API_KEY unset - using offline default plan", flush=True)
        return ("filesystem-mcp", "read_file", {"path": "invoice.txt"})
    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=model or AGENT_MODEL, messages=messages,
            temperature=0, max_tokens=1024)
        return _parse_plan(resp.choices[0].message.content or "{}")
    except Exception as exc:
        print(f"[agent] Groq error ({exc}) - offline default plan", flush=True)
        return ("filesystem-mcp", "read_file", {"path": "invoice.txt"})


def _lab_context() -> str:
    """Ground the planner with real lab state (file list), not guesses."""
    try:
        from lab.servers.filesystem import list_files
        return f"Files in lab data dir:\n{list_files()}"
    except Exception:
        return ""


def plan_with_llm(task: str, model: str | None = None) -> tuple[str, str, dict]:
    """Ask Groq which tool to call first; offline fallback returns a sane default."""
    catalog_txt = "\n".join(f"- {s}.{t}: {d} args={a}" for s, t, d, a in CATALOG)
    context = _lab_context()
    return _groq_plan([
        {"role": "system", "content": "Pick ONE lab tool as JSON: {\"server\":..., \"tool\":..., \"arguments\":{...}}. Reply with JSON only."},
        {"role": "user", "content": f"Task: {task}\nTools:\n{catalog_txt}\n{context}"},
    ], model)


def plan_next(task: str, history: list[dict], model: str | None = None) -> tuple[str, str, dict]:
    """Next step given prior tool results; reply DONE when the task is complete."""
    trail = "\n".join(
        f"- {h['server']}.{h['tool']} {h['arguments']} -> {h['verdict']}: {h['observation'][:300]}"
        for h in history)
    catalog_txt = "\n".join(f"- {s}.{t}: {d}" for s, t, d, _ in CATALOG)
    return _groq_plan([
        {"role": "system", "content": "Reply with EITHER {\"server\":\"DONE\"} when the task is complete, OR one tool call as JSON: {\"server\":..., \"tool\":..., \"arguments\":{...}}. JSON only."},
        {"role": "user", "content": f"Task: {task}\nTools:\n{catalog_txt}\nSo far:\n{trail}"},
    ], model)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--session", default=None)
    args = ap.parse_args()
    session_id = args.session or f"S-{uuid.uuid4().hex[:8]}"
    print(f"[agent] session={session_id} task={args.task!r}")

    server, tool, tool_args = plan_with_llm(args.task)
    print(f"[agent] action: {server}.{tool} {tool_args}")
    observation = call_tool(session_id, server, tool, tool_args)
    print(f"[agent] observation (preview): {observation[:500]}")
    print(f"[agent] done session={session_id}")


if __name__ == "__main__":
    main()
