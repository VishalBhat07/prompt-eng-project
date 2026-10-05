"""MCP proxy - sole enforcement point between agent and MCP servers.

Modes (env MODE, read per request so tests can flip it):
- monitor:   log events, ALLOW everything (Sidecar bootstrap).
- enforcing: record call + output events per session, correlate the
  session history (Task 6), enforce the Task 7 policy verdict.

Fail-closed: correlation/policy errors → BLOCK privileged tools, else
MONITOR. Never silent ALLOW (threat-model §5).

Parent heuristic v1: a call's parent is the session's most recent tool
output (temporal proximity). Explicit caller-supplied parents are the
future API; over-linking is acceptable because findings still require
pattern + risk agreement, not mere adjacency.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import uuid
from datetime import datetime, timezone

import anyio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import networkx as nx

from crosstoolguard.detection.correlation import analyze_with_graph
from crosstoolguard.gateway.agent_runner import AgentRun
from crosstoolguard.gateway.schemas import DataClass, Event, EventType, ToolCall, Trust, Verdict
from crosstoolguard.gateway.session import ensure_session
from crosstoolguard.gateway.transport import call_upstream, list_tools
from crosstoolguard.policy.engine import decide_for_session, reasons_for
from crosstoolguard.policy.explain import explain_finding
from crosstoolguard.provenance.events import classify_content, hash_arguments, redact
from crosstoolguard.registry.capabilities import sensitivity_for_path

app = FastAPI(title="CrossToolGuard proxy")

# Minimal privilege map until Task 2 capability taxonomy lands.
PRIVILEGED_TOOLS = {"upload_file"}

# Bounded per-session memory (M2-friendly): last 200 events per session.
SESSION_EVENTS: dict[str, list[Event]] = {}
SESSION_LAST_OUTPUT: dict[str, str] = {}
APPROVALS: set[str] = set()
_EVENT_CAP = 200


class _Hub:
    """Fan-out for WS subscribers; sync-safe via Queue (see /ws/events)."""

    def __init__(self) -> None:
        self.queues: list[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        self.queues.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        if q in self.queues:
            self.queues.remove(q)

    def publish(self, message: dict) -> None:
        for q in self.queues:
            q.put(message)


HUB = _Hub()


def is_privileged(tool: str) -> bool:
    return tool in PRIVILEGED_TOOLS


def approval_id_for(session_id: str, server: str, tool: str, args_hash: str) -> str:
    return hashlib.sha256(f"{session_id}|{server}|{tool}|{args_hash}".encode()).hexdigest()[:16]


def _log_event(event: Event) -> None:
    path = os.getenv("EVENTS_PATH", "events.jsonl")
    with open(path, "a") as fh:
        fh.write(event.model_dump_json() + "\n")


def _remember(session_id: str, event: Event) -> None:
    SESSION_EVENTS.setdefault(session_id, []).append(event)
    SESSION_EVENTS[session_id] = SESSION_EVENTS[session_id][-_EVENT_CAP:]
    HUB.publish(event.model_dump(mode="json"))


def _record_call(req: ToolCall, session_id: str) -> Event:
    data_class = DataClass.PUBLIC
    for value in req.arguments.values():
        if sensitivity_for_path(str(value)) == "SECRET":
            data_class = DataClass.SECRET
            break
    event = Event(event_id=f"e-{uuid.uuid4().hex[:8]}", timestamp=datetime.now(timezone.utc),
                  session_id=session_id, server=req.server, tool=req.tool,
                  event_type=EventType.TOOL_CALL, trust=Trust.MED,
                  data_class=data_class, args_hash=hash_arguments(req.arguments),
                  parent_id=SESSION_LAST_OUTPUT.get(session_id))
    _remember(session_id, event)
    _log_event(event)
    return event


def _record_output(req: ToolCall, session_id: str, call_event: Event, result: str) -> None:
    event = Event(event_id=f"e-{uuid.uuid4().hex[:8]}", timestamp=datetime.now(timezone.utc),
                  session_id=session_id, server=req.server, tool=req.tool,
                  event_type=EventType.TOOL_OUTPUT, trust=Trust.LOW,
                  data_class=DataClass(classify_content(result)),
                  output_preview=redact(result)[:500], parent_id=call_event.event_id)
    _remember(session_id, event)
    _log_event(event)
    SESSION_LAST_OUTPUT[session_id] = event.event_id


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/tools/list")
def tools_list() -> dict:
    return {"tools": list_tools()}


@app.get("/api/tools/list")
def api_tools_list() -> dict:
    return tools_list()


@app.post("/tools/call")
def tools_call(req: ToolCall) -> dict:
    return execute_tool_call(req, ensure_session(req.session_id))


def execute_tool_call(req: ToolCall, session_id: str) -> dict:
    """Shared core: record, decide, execute-or-halt. Used by the route + runner."""
    call_event = _record_call(req, session_id)

    if os.getenv("MODE", "monitor") != "enforcing":
        result = call_upstream(req.server, req.tool, req.arguments)
        _record_output(req, session_id, call_event, result)
        return {"verdict": Verdict.ALLOW.value, "result": result, "reason": "monitor: log only"}

    try:
        verdict = decide_for_session(SESSION_EVENTS[session_id])
    except Exception:
        verdict = Verdict.BLOCK if is_privileged(req.tool) else Verdict.MONITOR

    if verdict == Verdict.BLOCK:
        return {"verdict": verdict.value, "result": None, "reason": "policy: secret-never-external"}
    if verdict in (Verdict.APPROVAL, Verdict.QUARANTINE):
        aid = approval_id_for(session_id, req.server, req.tool, call_event.args_hash)
        if req.approval_id in APPROVALS:
            APPROVALS.discard(req.approval_id)
            result = call_upstream(req.server, req.tool, req.arguments)
            _record_output(req, session_id, call_event, result)
            return {"verdict": Verdict.ALLOW.value, "result": result, "reason": "approval granted"}
        return {"verdict": Verdict.APPROVAL.value, "result": None,
                "approval_id": aid, "reason": "policy: untrusted-to-privileged"}
    result = call_upstream(req.server, req.tool, req.arguments)
    _record_output(req, session_id, call_event, result)
    return {"verdict": verdict.value, "result": result, "reason": "policy"}


@app.post("/approvals/grant")
def grant_approval(body: dict) -> dict:
    """Human-in-the-loop seam (dashboard calls this in Task 8). One-shot."""
    aid = body.get("approval_id", "")
    APPROVALS.add(aid)
    return {"granted": True, "approval_id": aid}


@app.post("/api/agent/run")
def api_agent_run(body: AgentRun) -> dict:
    """Playground: run a prompt end-to-end, return the enforced trace."""
    from crosstoolguard.gateway.agent_runner import run_task

    return run_task(body.task, session_id=body.session_id,
                    model=body.model, max_steps=body.max_steps)


@app.get("/api/graph")
def api_graph(session: str) -> dict:
    """Attack graph + suspicious paths for a session (dashboard contract)."""
    from crosstoolguard.graph.builder import build

    events = SESSION_EVENTS.get(session, [])
    graph = build(events) if events else nx.DiGraph()
    _, findings = analyze_with_graph(events) if events else (graph, [])
    nodes = [{"id": n, **{k: v for k, v in d.items()}} for n, d in graph.nodes(data=True)]
    edges = [{"source": u, "target": v, **e} for u, v, e in graph.edges(data=True)]
    paths = [{"pattern": f.pattern, "severity": f.severity, "risk": round(f.risk, 3),
              "tools": f.tool_sequence, "node_ids": f.path} for f in findings]
    return {"nodes": nodes, "edges": edges, "paths": paths}


@app.get("/api/alerts")
def api_alerts(session: str) -> dict:
    """Ranked findings with NL explanations for a session."""
    events = SESSION_EVENTS.get(session, [])
    if not events:
        return {"alerts": []}
    graph, findings = analyze_with_graph(events)
    alerts = []
    for finding, (policy, action) in zip(findings, reasons_for(graph, findings)):
        alerts.append({"pattern": finding.pattern, "severity": finding.severity,
                       "risk": round(finding.risk, 3), "tools": finding.tool_sequence,
                       "policy": policy, "verdict": action,
                       "explanation": explain_finding(graph, finding, verdict=action, policy=policy)})
    return {"alerts": alerts}


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """Live event stream (polled fan-out; 50 ms cadence)."""
    await websocket.accept()
    q = HUB.subscribe()
    try:
        while True:
            await anyio.sleep(0.05)
            while not q.empty():
                await websocket.send_json(q.get_nowait())
    except WebSocketDisconnect:
        pass
    finally:
        HUB.unsubscribe(q)
