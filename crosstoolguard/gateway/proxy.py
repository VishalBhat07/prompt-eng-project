"""MCP proxy — sole enforcement point between agent and MCP servers.

Modes (env MODE, read per request so tests can flip it):
- monitor:   log the event, ALLOW everything (Sidecar bootstrap).
- enforcing: ask policy, BLOCK/APPROVAL win; fail-closed on any error.

Fail-closed: policy exception/timeout → BLOCK when the tool is privileged
(EXTERNAL_TRANSFER etc.), else MONITOR. Never silent ALLOW (threat-model §5).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI

from crosstoolguard.gateway.schemas import Event, EventType, ToolCall, Verdict
from crosstoolguard.gateway.session import ensure_session
from crosstoolguard.gateway.transport import call_upstream, list_tools

app = FastAPI(title="CrossToolGuard proxy")

# Minimal privilege map until Task 2 capability taxonomy lands.
PRIVILEGED_TOOLS = {"upload_file"}


def is_privileged(tool: str) -> bool:
    return tool in PRIVILEGED_TOOLS


def _stub_decide(event: Event) -> Verdict:
    """Placeholder policy: deny external-transfer tools, allow the rest.

    Task 7 replaces this with the versioned YAML policy engine
    (deny-override). Kept deliberately dumb so Task 1 proves the
    enforcement plumbing, not detection quality.
    """
    if is_privileged(event.tool):
        return Verdict.BLOCK
    return Verdict.ALLOW


def _log_event(event: Event) -> None:
    path = os.getenv("EVENTS_PATH", "events.jsonl")
    with open(path, "a") as fh:
        fh.write(event.model_dump_json() + "\n")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/tools/list")
def tools_list() -> dict:
    return {"tools": list_tools()}


@app.post("/tools/call")
def tools_call(req: ToolCall) -> dict:
    session_id = ensure_session(req.session_id)
    args_hash = hashlib.sha256(json.dumps(req.arguments, sort_keys=True).encode()).hexdigest()
    call_event = Event(
        event_id=f"e-{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc),
        session_id=session_id,
        server=req.server,
        tool=req.tool,
        event_type=EventType.TOOL_CALL,
        args_hash=args_hash,
    )
    _log_event(call_event)

    if os.getenv("MODE", "monitor") != "enforcing":
        result = call_upstream(req.server, req.tool, req.arguments)
        return {"verdict": Verdict.ALLOW.value, "result": result, "reason": "monitor: log only"}

    try:
        verdict = _stub_decide(call_event)
    except Exception:
        verdict = Verdict.BLOCK if is_privileged(req.tool) else Verdict.MONITOR
    if verdict == Verdict.BLOCK:
        return {"verdict": verdict.value, "result": None, "reason": "stub-policy: privileged tool denied"}
    result = call_upstream(req.server, req.tool, req.arguments)
    return {"verdict": verdict.value, "result": result, "reason": "stub-policy"}
