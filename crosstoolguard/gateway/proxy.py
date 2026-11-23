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

import asyncio
import hashlib
import ipaddress
import json
import os
import queue
import re
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import anyio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import networkx as nx
from pydantic import BaseModel, Field, field_validator

from crosstoolguard.detection.correlation import analyze_with_graph
from crosstoolguard.gateway.agent_runner import AgentRun
from crosstoolguard.gateway.schemas import DataClass, Event, EventType, ToolCall, Trust, Verdict
from crosstoolguard.gateway.session import ensure_session
from crosstoolguard.gateway.transport import call_upstream, list_tools
from crosstoolguard.policy.engine import decide, reasons_for
from crosstoolguard.policy.evaluator import finding_signals
from crosstoolguard.policy.explain import explain_finding
from crosstoolguard.provenance.events import classify_content, hash_arguments, redact
from crosstoolguard.registry.capabilities import extract_capabilities, PRIVILEGED_CAPS, sensitivity_for_path

load_dotenv()
app = FastAPI(title="CrossToolGuard proxy")


class MCPInventoryRequest(BaseModel):
    server_id: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2048)
    bearer_token: str | None = Field(default=None, max_length=4096)

    @field_validator("server_id")
    @classmethod
    def _strip_server_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("server_id cannot be blank")
        return value


class MCPInventoryApproval(BaseModel):
    server_id: str = Field(min_length=1, max_length=200)
    inventory_hash: str = Field(min_length=64, max_length=64)

    @field_validator("server_id")
    @classmethod
    def _strip_approval_server_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("server_id cannot be blank")
        return value


class RemoteMCPToolCall(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    server_id: str = Field(min_length=1, max_length=200)
    tool: str = Field(min_length=1, max_length=200)
    arguments: dict = Field(default_factory=dict)
    bearer_token: str | None = Field(default=None, max_length=4096)
    approval_id: str | None = Field(default=None, max_length=128)

    @field_validator("session_id", "server_id", "tool")
    @classmethod
    def _strip_remote_call_names(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("session_id, server_id, and tool cannot be blank")
        return value


class ApprovalGrant(BaseModel):
    approval_id: str = Field(min_length=16, max_length=128)


class MultiServerRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=100_000)
    provider: str = "groq"
    model: str | None = None
    policy: str = "hardened"
    server_ids: list[str] | None = Field(default=None, max_length=100)
    auto_discover: bool = False
    max_steps: int = Field(default=6, ge=1, le=12)
    max_calls_per_tool: int = Field(default=2, ge=1, le=12)


# The dashboard keeps the initial model request small enough for an 8k
# token/minute Groq free-tier limit. Operators can raise this for other
# providers, but the catalog remains bounded to avoid accidental overspend.
MAX_AGENT_CONTEXT_CHARS = 20_000


def _agent_context_chars(inventories: list[dict]) -> int:
    """Estimate the compact catalog plus server instructions sent to the model."""
    instructions = [{"server_id": item["server_id"], "instructions": item.get("instructions")}
                    for item in inventories]
    catalog = [{"ref": f"{item['server_id']}/{tool['name']}",
                "summary": str(tool.get("description") or "")[:280]}
               for item in inventories for tool in item.get("tools", [])
               if tool.get("_registry", {}).get("integrity_status") == "APPROVED"]
    return (len(json.dumps(catalog, ensure_ascii=False, default=str)) +
            len(json.dumps(instructions, ensure_ascii=False, default=str)))


def _discover_tools(task: str, inventories: list[dict], context_limit: int) -> list[dict]:
    """Rank approved tools locally and fit the leading candidates into the prompt."""
    words = set(re.findall(r"[a-z0-9]{3,}", task.lower())) - {
        "the", "and", "for", "with", "from", "using", "use", "please", "find", "show",
    }
    candidates = []
    for item in inventories:
        for tool in item.get("tools", []):
            if tool.get("_registry", {}).get("integrity_status") != "APPROVED":
                continue
            identity = set(re.findall(r"[a-z0-9]{3,}", f"{item['server_id']} {tool['name']}".lower()))
            description = set(re.findall(r"[a-z0-9]{3,}", str(tool.get("description") or "")[:280].lower()))
            score = 3 * len(words & identity) + len(words & description)
            candidates.append((-score, item["server_id"], tool["name"], item, tool))
    selected = {}
    count = 0
    for _, server_id, _, item, tool in sorted(candidates, key=lambda candidate: candidate[:3]):
        group = selected.setdefault(server_id, {**item, "tools": []})
        group["tools"].append(tool)
        if _agent_context_chars(list(selected.values())) > context_limit:
            group["tools"].pop()
            if not group["tools"]:
                del selected[server_id]
            continue
        count += 1
        if count == 100:
            break
    return list(selected.values())


def _validate_inventory_target(url: str) -> None:
    """Limit app-triggered outbound connections to operator-approved hosts."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    local_http = (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                  and os.getenv("MCP_INVENTORY_ALLOW_PRIVATE_NETWORK", "false").lower() == "true")
    if (parsed.scheme != "https" and not local_http) or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise HTTPException(status_code=400, detail="Use an HTTPS MCP URL without credentials, query parameters, or fragments")
    allowed_hosts = {host.strip().lower().rstrip(".") for host in
                     os.getenv("MCP_INVENTORY_ALLOWED_HOSTS", "").split(",") if host.strip()}
    hostname = parsed.hostname.lower().rstrip(".")
    if not allowed_hosts or hostname not in allowed_hosts:
        raise HTTPException(status_code=403, detail="MCP host is not in MCP_INVENTORY_ALLOWED_HOSTS")
    port = parsed.port or 443
    allowed_ports = {int(item.strip()) for item in os.getenv("MCP_INVENTORY_ALLOWED_PORTS", "443").split(",")
                     if item.strip()}
    if port not in allowed_ports:
        raise HTTPException(status_code=403, detail="MCP port is not in MCP_INVENTORY_ALLOWED_PORTS")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise HTTPException(status_code=400, detail="MCP host could not be resolved") from exc
    if not addresses:
        raise HTTPException(status_code=400, detail="MCP host has no resolved addresses")
    if os.getenv("MCP_INVENTORY_ALLOW_PRIVATE_NETWORK", "false").lower() != "true":
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise HTTPException(status_code=403, detail="MCP host resolves to a non-public address")

# Minimal privilege map until Task 2 capability taxonomy lands.
PRIVILEGED_TOOLS = {"upload_file"}

# Bounded per-session memory (M2-friendly): last 200 events per session.
SESSION_EVENTS: dict[str, list[Event]] = {}
SESSION_LAST_OUTPUT: dict[str, str] = {}
SESSION_DECISIONS: dict[str, list[str]] = {}
SESSION_BLOCKS: dict[str, list[dict]] = {}
APPROVALS: dict[str, float] = {}
PENDING_APPROVALS: dict[str, float] = {}
PENDING_APPROVAL_INFO: dict[str, dict] = {}
RUN_STATUS: dict[str, dict] = {}
_APPROVAL_LOCK = threading.Lock()
_APPROVAL_TTL_SECONDS = 300
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


def is_privileged(tool: str, capabilities: set[str] | None = None) -> bool:
    return tool in PRIVILEGED_TOOLS or bool((capabilities or set()) & PRIVILEGED_CAPS)


def approval_id_for(session_id: str, server: str, tool: str, args_hash: str) -> str:
    return hashlib.sha256(f"{session_id}|{server}|{tool}|{args_hash}".encode()).hexdigest()[:16]


def _request_approval(approval_id: str) -> None:
    now = time.time()
    with _APPROVAL_LOCK:
        for pending_id, expiry in list(PENDING_APPROVALS.items()):
            if expiry <= now:
                PENDING_APPROVALS.pop(pending_id, None)
                PENDING_APPROVAL_INFO.pop(pending_id, None)
        for approved_id, expiry in list(APPROVALS.items()):
            if expiry <= now:
                APPROVALS.pop(approved_id, None)
        if APPROVALS.get(approval_id, 0) > now:
            return
        PENDING_APPROVALS[approval_id] = now + _APPROVAL_TTL_SECONDS


def _consume_approval(approval_id: str) -> bool:
    with _APPROVAL_LOCK:
        if APPROVALS.get(approval_id, 0) <= time.time():
            APPROVALS.pop(approval_id, None)
            return False
        APPROVALS.pop(approval_id, None)
        PENDING_APPROVALS.pop(approval_id, None)
        PENDING_APPROVAL_INFO.pop(approval_id, None)
        return True


def _log_event(event: Event) -> None:
    path = os.getenv("EVENTS_PATH", "events.jsonl")
    with open(path, "a") as fh:
        fh.write(event.model_dump_json() + "\n")


def _remember(session_id: str, event: Event) -> None:
    SESSION_EVENTS.setdefault(session_id, []).append(event)
    SESSION_EVENTS[session_id] = SESSION_EVENTS[session_id][-_EVENT_CAP:]
    HUB.publish(event.model_dump(mode="json"))


def _decision_response(session_id: str, payload: dict) -> dict:
    SESSION_DECISIONS.setdefault(session_id, []).append(str(payload.get("verdict", "ERROR")))
    SESSION_DECISIONS[session_id] = SESSION_DECISIONS[session_id][-_EVENT_CAP:]
    return payload


def _session_policy(events: list[Event]) -> tuple[Verdict, list[dict]]:
    graph, findings = analyze_with_graph(events)
    decisions = reasons_for(graph, findings)
    evidence = []
    for finding, (policy, action) in zip(findings, decisions):
        if action != Verdict.BLOCK.value:
            continue
        signals = finding_signals(graph, finding)
        evidence.append({"policy": policy, "pattern": finding.pattern, "node_ids": finding.path,
                         "tools": finding.tool_sequence, "data_classes": sorted(signals["data_classes"]),
                         "capabilities": sorted(signals["capabilities"])})
    return decide([action for _, action in decisions]), evidence


def _blocked_call(session_id: str, server: str, tool: str, reason: str, *,
                  check: str, event: Event | None = None, evidence: list[dict] | None = None) -> dict:
    SESSION_EVENTS.setdefault(session_id, [])
    blocks = SESSION_BLOCKS.setdefault(session_id, [])
    blocks.append({"id": event.event_id if event else uuid.uuid4().hex, "server": server,
                   "tool": tool, "reason": reason, "check": check, "evidence": evidence or [],
                   "call_node_id": f"tool:{event.tool}:{event.event_id}" if event else None})
    del blocks[:-_EVENT_CAP]
    return _decision_response(session_id, {"verdict": Verdict.BLOCK.value, "result": None, "reason": reason})


def _record_call(req: ToolCall, session_id: str,
                 capabilities: set[str] | None = None) -> Event:
    data_class = DataClass.PUBLIC
    argument_class = classify_content(json.dumps(req.arguments, ensure_ascii=False, default=str))
    if argument_class in {DataClass.SECRET.value, DataClass.CREDENTIAL.value}:
        data_class = DataClass(argument_class)
    for value in req.arguments.values():
        if sensitivity_for_path(str(value)) == "SECRET":
            if data_class != DataClass.CREDENTIAL:
                data_class = DataClass.SECRET
            break
    call_capabilities = sorted(capabilities if capabilities is not None else extract_capabilities(req.tool, ""))
    event = Event(event_id=f"e-{uuid.uuid4().hex[:8]}", timestamp=datetime.now(timezone.utc),
                  session_id=session_id, server=req.server, tool=req.tool,
                  event_type=EventType.TOOL_CALL, trust=Trust.MED,
                  data_class=data_class, capabilities=call_capabilities,
                  args_hash=hash_arguments(req.arguments),
                  parent_id=SESSION_LAST_OUTPUT.get(session_id))
    _remember(session_id, event)
    _log_event(event)
    return event


def _record_output(req: ToolCall, session_id: str, call_event: Event, result: str) -> None:
    event = Event(event_id=f"e-{uuid.uuid4().hex[:8]}", timestamp=datetime.now(timezone.utc),
                  session_id=session_id, server=req.server, tool=req.tool,
                  event_type=EventType.TOOL_OUTPUT, trust=Trust.LOW,
                  data_class=DataClass(classify_content(result)), capabilities=call_event.capabilities,
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
        return _decision_response(session_id, {"verdict": Verdict.ALLOW.value, "result": result, "reason": "monitor: log only"})

    try:
        verdict, evidence = _session_policy(SESSION_EVENTS[session_id])
    except Exception:
        verdict = Verdict.BLOCK if is_privileged(req.tool) else Verdict.MONITOR
        evidence = []

    if verdict == Verdict.BLOCK:
        reason = ("Session policy blocked the proposed tool call." if evidence else
                  "Policy evaluation failed, so the gateway blocked the sensitive call.")
        return _blocked_call(session_id, req.server, req.tool, reason,
                             check="session_policy" if evidence else "policy_error", event=call_event, evidence=evidence)
    if verdict in (Verdict.APPROVAL, Verdict.QUARANTINE):
        aid = approval_id_for(session_id, req.server, req.tool, call_event.args_hash)
        _request_approval(aid)
        PENDING_APPROVAL_INFO[aid] = {"id": aid, "session": session_id, "server": req.server,
                                      "tool": req.tool, "expires_at": PENDING_APPROVALS.get(aid),
                                      "argument_fields": sorted(req.arguments),
                                      "arguments_sha256": call_event.args_hash,
                                      "reason": "Session policy requires approval for the proposed call.",
                                      "destination_label": None,
                                      "data_class": call_event.data_class.value}
        if req.approval_id == aid and _consume_approval(aid):
            result = call_upstream(req.server, req.tool, req.arguments)
            _record_output(req, session_id, call_event, result)
            return _decision_response(session_id, {"verdict": Verdict.ALLOW.value, "result": result, "reason": "approval granted"})
        return _decision_response(session_id, {"verdict": Verdict.APPROVAL.value, "result": None,
                "approval_id": aid, "reason": "policy: untrusted-to-privileged"})
    result = call_upstream(req.server, req.tool, req.arguments)
    _record_output(req, session_id, call_event, result)
    return _decision_response(session_id, {"verdict": verdict.value, "result": result, "reason": "policy"})


@app.post("/approvals/grant")
@app.post("/api/approvals/grant")
def grant_approval(body: ApprovalGrant) -> dict:
    """Grant a currently pending approval in the local dashboard."""
    aid = body.approval_id
    with _APPROVAL_LOCK:
        expiry = PENDING_APPROVALS.get(aid, 0)
        if expiry <= time.time():
            PENDING_APPROVALS.pop(aid, None)
            raise HTTPException(status_code=404, detail="Approval request is unknown or expired")
        PENDING_APPROVALS.pop(aid, None)
        APPROVALS[aid] = time.time() + _APPROVAL_TTL_SECONDS
    return {"granted": True, "approval_id": aid}


@app.post("/api/agent/run")
def api_agent_run(body: AgentRun) -> dict:
    """Playground: run a prompt end-to-end, return the enforced trace."""
    from crosstoolguard.gateway.agent_runner import run_task

    return run_task(body.task, session_id=body.session_id, model=body.model,
                    max_steps=body.max_steps, provider=body.provider)


@app.get("/api/approvals")
def api_pending_approvals() -> dict:
    now = time.time()
    with _APPROVAL_LOCK:
        pending = [dict(info) for aid, info in PENDING_APPROVAL_INFO.items()
                   if PENDING_APPROVALS.get(aid, 0) > now and APPROVALS.get(aid, 0) <= now]
    return {"pending": pending}


@app.post("/api/approvals/{approval_id}/deny")
def api_deny_approval(approval_id: str) -> dict:
    with _APPROVAL_LOCK:
        was_pending = PENDING_APPROVALS.pop(approval_id, None) is not None
        PENDING_APPROVAL_INFO.pop(approval_id, None)
        APPROVALS.pop(approval_id, None)
    return {"denied": was_pending}


@app.get("/api/llm/providers")
def api_llm_providers() -> dict:
    """Configured providers + models (keys stay server-side)."""
    from crosstoolguard.llm.providers import list_providers

    return {"providers": list_providers()}


@app.post("/api/mcp/agent/run")
async def api_multi_server_run(body: MultiServerRunRequest) -> dict:
    """Start a task using all approved tools; the agent chooses the path."""
    from crosstoolguard.registry.tools import ToolRegistry
    from crosstoolguard.llm.providers import PROVIDERS, resolve

    try:
        provider, model = resolve(body.provider, body.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not os.getenv(PROVIDERS[provider]["env"]):
        raise HTTPException(status_code=400, detail="Selected model provider is not configured")
    registry = ToolRegistry(os.getenv("REGISTRY_DB", "registry.db"))
    try:
        inventories = [item for item in registry.list_server_inventories()
                       if item.get("integrity_status") == "APPROVED"]
    finally:
        registry.close()
    if body.server_ids is not None:
        requested = list(dict.fromkeys(item.strip() for item in body.server_ids if item.strip()))
        if not requested:
            raise HTTPException(status_code=422, detail="Select at least one approved MCP server for this run")
        by_id = {item["server_id"]: item for item in inventories}
        missing = [server_id for server_id in requested if server_id not in by_id]
        if missing:
            raise HTTPException(status_code=422,
                                detail="Selected server is missing or not approved: " + ", ".join(missing))
        inventories = [by_id[server_id] for server_id in requested]
    context_limit = int(os.getenv("CTG_MAX_AGENT_CONTEXT_CHARS", str(MAX_AGENT_CONTEXT_CHARS)))
    available_tool_count = sum(tool.get("_registry", {}).get("integrity_status") == "APPROVED"
                               for item in inventories for tool in item.get("tools", []))
    if body.auto_discover:
        inventories = _discover_tools(body.task, inventories, context_limit)
    refs = [f"{item['server_id']}/{tool['name']}" for item in inventories
            for tool in item.get("tools", [])
            if tool.get("_registry", {}).get("integrity_status") == "APPROVED"]
    if not refs:
        detail = ("No approved tool fits the configured discovery budget" if available_tool_count
                  else "No approved MCP tools are available; review an inventory first")
        raise HTTPException(status_code=422, detail=detail)
    if len(refs) > 100:
        raise HTTPException(status_code=422, detail="More than 100 approved tools; reduce approved inventories for this run")
    context_chars = _agent_context_chars(inventories)
    if context_chars > context_limit:
        raise HTTPException(
            status_code=422,
            detail=(f"Selected server catalog is too large for one model request "
                    f"({context_chars:,} chars; limit {context_limit:,}). Select fewer servers, "
                    "or raise CTG_MAX_AGENT_CONTEXT_CHARS for a provider with a larger limit."))
    session_id = f"agent-{uuid.uuid4().hex}"
    selected_server_ids = [item["server_id"] for item in inventories]
    RUN_STATUS[session_id] = {"status": "running", "session_id": session_id,
                              "approved_tool_count": len(refs),
                              "available_tool_count": available_tool_count,
                              "selected_server_ids": selected_server_ids,
                              "context_chars": context_chars,
                              "inventories": inventories}
    asyncio.create_task(_run_approved_agent(session_id, body, refs, provider, model))
    return {"session_id": session_id, "status": "running", "approved_tool_count": len(refs),
            "available_tool_count": available_tool_count,
            "selected_server_ids": selected_server_ids, "context_chars": context_chars}


async def _run_approved_agent(session_id: str, body: MultiServerRunRequest,
                              refs: list[str], provider: str, model: str) -> None:
    import httpx
    from crosstoolguard.evaluation.multi_server_runner import run_multi_server_task
    from crosstoolguard.gateway.run_store import save_run

    async def await_approval(approval_id: str) -> bool:
        RUN_STATUS[session_id]["status"] = "awaiting_approval"
        while True:
            with _APPROVAL_LOCK:
                granted = APPROVALS.get(approval_id, 0) > time.time()
                pending = PENDING_APPROVALS.get(approval_id, 0) > time.time()
            if granted:
                RUN_STATUS[session_id]["status"] = "running"
                return True
            if not pending:
                return False
            await asyncio.sleep(0.5)

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://ctg-gateway", timeout=90) as client:
            report = await run_multi_server_task(
                proxy_url="http://ctg-gateway", task=body.task, allowed_tools=refs,
                provider=provider, model=model, max_steps=body.max_steps,
                max_calls_per_tool=body.max_calls_per_tool, policy=body.policy,
                allow_side_effects=True, session_id=session_id,
                await_approval=await_approval, return_answer=True, compact_catalog=True, client=client)
        RUN_STATUS[session_id]["answer"] = report.pop("final_answer", "")
        RUN_STATUS[session_id]["report"] = report
        graph = api_graph(session_id)
        alerts = api_alerts(session_id)["alerts"]
        snapshot = {"session": session_id, **graph, "alerts": alerts,
                    "blocks": SESSION_BLOCKS.get(session_id, []),
                    "events": [event.model_dump(mode="json") for event in SESSION_EVENTS.get(session_id, [])],
                    "report": report}
        save_run(session_id, snapshot)
        RUN_STATUS[session_id]["status"] = "complete"
    except Exception as exc:
        RUN_STATUS[session_id]["status"] = "error"
        RUN_STATUS[session_id]["error"] = type(exc).__name__


@app.get("/api/mcp/agent/runs/{session_id}")
def api_multi_server_run_status(session_id: str) -> dict:
    state = RUN_STATUS.get(session_id)
    if state is None:
        from crosstoolguard.gateway.run_store import load_run
        try:
            saved = load_run(session_id)
        except ValueError:
            saved = None
        if saved is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"session_id": session_id, "status": "complete", "report": saved.get("report")}
    return {key: value for key, value in state.items() if key != "inventories"}


@app.get("/api/registry/inventories")
def api_registry_inventories(server_id: str | None = None) -> dict:
    """Read inventories gathered by the explicit MCP inspector CLI."""
    from crosstoolguard.registry.tools import ToolRegistry

    registry = ToolRegistry(os.getenv("REGISTRY_DB", "registry.db"))
    try:
        if server_id:
            inventory = registry.get_server_inventory(server_id)
            return {"inventories": [inventory] if inventory else []}
        return {"inventories": registry.list_server_inventories()}
    finally:
        registry.close()


@app.post("/api/registry/inspect")
async def api_registry_inspect(body: MCPInventoryRequest) -> dict:
    """Inventory one allowlisted HTTPS server; this never invokes its tools."""
    if os.getenv("MCP_INVENTORY_API_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Remote inventory is disabled by the operator")
    _validate_inventory_target(body.url)
    from crosstoolguard.registry.mcp_inspector import inspect_server
    from crosstoolguard.registry.assessment import assess_inventory
    from crosstoolguard.registry.tools import ToolRegistry

    headers = {"Authorization": f"Bearer {body.bearer_token}"} if body.bearer_token else {}
    try:
        inventory = await inspect_server({
            "server_id": body.server_id,
            "transport": "streamable-http",
            "url": body.url,
            "headers": headers,
        }, allow_http=body.url.startswith("http://"))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP inventory failed ({type(exc).__name__})") from exc

    registry = ToolRegistry(os.getenv("REGISTRY_DB", "registry.db"))
    try:
        status = registry.register_server_inventory(inventory)
        report = assess_inventory(inventory)
        registry.save_assessment(body.server_id, report)
        saved = registry.get_server_inventory(body.server_id)
        return {"inventory": saved, "assessment": report, "scan_status": status.integrity_status}
    finally:
        registry.close()


@app.post("/api/registry/approve")
def api_registry_approve(body: MCPInventoryApproval) -> dict:
    """Acknowledge and pin one exact inventory hash after operator review."""
    if os.getenv("MCP_INVENTORY_API_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Remote inventory approval is disabled by the operator")
    from crosstoolguard.registry.tools import ToolRegistry

    registry = ToolRegistry(os.getenv("REGISTRY_DB", "registry.db"))
    try:
        if not registry.approve_server_inventory(body.server_id, body.inventory_hash):
            raise HTTPException(status_code=409, detail="Inventory changed; refresh and review the current fingerprint")
        return {"inventory": registry.get_server_inventory(body.server_id), "approved": True}
    finally:
        registry.close()


@app.post("/api/registry/revoke")
def api_registry_revoke(body: MCPInventoryApproval) -> dict:
    """Withdraw approval for the reviewed snapshot while retaining its evidence."""
    if os.getenv("MCP_INVENTORY_API_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Remote inventory management is disabled")
    from crosstoolguard.registry.tools import ToolRegistry

    registry = ToolRegistry(os.getenv("REGISTRY_DB", "registry.db"))
    try:
        if not registry.revoke_server_inventory(body.server_id, expected_hash=body.inventory_hash):
            raise HTTPException(status_code=409, detail="Approval or fingerprint changed. Refresh the inventory.")
        return {"inventory": registry.get_server_inventory(body.server_id), "approved": False}
    finally:
        registry.close()


def _mcp_result_text(result: Any) -> str:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False, default=str)
    return "\n".join(
        str(block.text) for block in (getattr(result, "content", []) or [])
        if getattr(block, "type", None) == "text"
    )


def _external_schema_ref(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef", "$recursiveRef"}:
                if not isinstance(item, str) or not item.startswith("#"):
                    return True
            if _external_schema_ref(item):
                return True
    elif isinstance(value, list):
        return any(_external_schema_ref(item) for item in value)
    return False


def _validate_tool_arguments(definition: dict, arguments: dict) -> str | None:
    """Validate arguments against the pinned MCP input schema without remote refs."""
    schema = definition.get("inputSchema") or definition.get("input_schema")
    if not isinstance(schema, dict):
        return "tool has no usable input schema"
    try:
        packed_schema = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        packed_arguments = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return "tool schema or arguments are not valid JSON values"
    if len(packed_schema.encode("utf-8")) > 262144:
        return "tool input schema exceeds the validation size limit"
    if len(packed_arguments.encode("utf-8")) > 1_048_576:
        return "tool arguments exceed the validation size limit"
    if _external_schema_ref(schema):
        return "tool schema contains a non-local reference"

    try:
        import jsonschema

        validator_class = jsonschema.validators.validator_for(
            schema, default=jsonschema.Draft202012Validator)
        validator_class.check_schema(schema)
        error = next(iter(validator_class(schema).iter_errors(arguments)), None)
    except ImportError:
        return "JSON Schema validation dependency is unavailable"
    except Exception as exc:
        return f"tool input schema could not be validated ({type(exc).__name__})"
    if error is None:
        return None
    pointer = "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1")
                              for part in error.absolute_path)
    return f"arguments violate input schema at {pointer}: {error.validator}"


@app.post("/api/mcp/tools/call")
async def api_mcp_tool_call(body: RemoteMCPToolCall) -> dict:
    """Call one approved remote MCP tool through inventory pinning and session policy."""
    from crosstoolguard.registry.assessment import assess_inventory
    from crosstoolguard.registry.capabilities import extract_capabilities
    from crosstoolguard.registry.tools import ToolRegistry

    session_id = ensure_session(body.session_id)

    def inventory_block(reason: str) -> dict:
        return _blocked_call(session_id, body.server_id, body.tool, reason, check="inventory")

    registry = ToolRegistry(os.getenv("REGISTRY_DB", "registry.db"))
    try:
        saved = registry.get_server_inventory(body.server_id)
        if saved is None or saved.get("integrity_status") != "APPROVED":
            return inventory_block("Server inventory is missing or not operator-approved.")
        endpoint_url = saved.get("endpoint_url")
        if not endpoint_url:
            return inventory_block("Server has no saved Streamable HTTP endpoint.")
        _validate_inventory_target(endpoint_url)
        from crosstoolguard.registry.mcp_inspector import inventory_from_session, open_mcp_session

        headers = {"Authorization": f"Bearer {body.bearer_token}"} if body.bearer_token else {}
        config = {"server_id": body.server_id, "transport": "streamable-http",
                  "url": endpoint_url, "headers": headers}
        async with open_mcp_session(config, allow_http=endpoint_url.startswith("http://")) as (session, initialized):
            current = await inventory_from_session(session, initialized, config)
            status = registry.register_server_inventory(current)
            if status.inventory_hash != saved["inventory_hash"] or status.integrity_status != "APPROVED":
                registry.save_assessment(body.server_id, assess_inventory(current))
                return inventory_block("Server inventory changed or is no longer approved; review the new fingerprint.")

            definition = next((item for item in current["tools"] if item.get("name") == body.tool), None)
            if definition is None:
                return inventory_block("Requested tool is not in the approved inventory.")
            saved_tool = next((item for item in saved["tools"] if item.get("name") == body.tool), None)
            if not saved_tool or saved_tool.get("_registry", {}).get("integrity_status") != "APPROVED":
                return inventory_block("Requested tool fingerprint is not approved.")

            capability_text = " ".join(
                str(definition.get(field) or "") for field in ("title", "description")
            )
            capabilities = extract_capabilities(body.tool, capability_text)
            request = ToolCall(session_id=body.session_id, server=body.server_id, tool=body.tool,
                               arguments=body.arguments, approval_id=body.approval_id)
            call_event = _record_call(request, session_id, capabilities=capabilities)
            schema_error = _validate_tool_arguments(definition, body.arguments)
            if schema_error:
                return _blocked_call(session_id, body.server_id, body.tool,
                                     f"Tool arguments failed the reviewed input schema: {schema_error}",
                                     check="input_schema", event=call_event)
            verdict = Verdict.ALLOW
            if os.getenv("MODE", "monitor") == "enforcing":
                try:
                    verdict, evidence = _session_policy(SESSION_EVENTS[session_id])
                except Exception:
                    verdict = Verdict.BLOCK if is_privileged(body.tool, capabilities) else Verdict.MONITOR
                    evidence = []
                if verdict == Verdict.BLOCK:
                    reason = ("Session policy blocked the proposed call before the MCP server was invoked." if evidence else
                              "Policy evaluation failed, so the gateway blocked the sensitive call.")
                    return _blocked_call(session_id, body.server_id, body.tool, reason,
                        check="session_policy" if evidence else "policy_error", event=call_event, evidence=evidence)
                approval_reasons = []
                if verdict in (Verdict.APPROVAL, Verdict.QUARANTINE):
                    approval_reasons.append("Session policy flagged the proposed call.")
                if is_privileged(body.tool, capabilities):
                    approval_reasons.append("Tool has a sensitive capability: " +
                                            ", ".join(sorted(capabilities & PRIVILEGED_CAPS) or ["restricted tool"]) + ".")
                    verdict = Verdict.APPROVAL
                if call_event.data_class in {DataClass.SECRET, DataClass.CREDENTIAL}:
                    approval_reasons.append("Arguments contain data classified as " + call_event.data_class.value + ".")
                    verdict = Verdict.APPROVAL
                if verdict in (Verdict.APPROVAL, Verdict.QUARANTINE):
                    aid = approval_id_for(session_id, body.server_id, body.tool, call_event.args_hash)
                    _request_approval(aid)
                    PENDING_APPROVAL_INFO[aid] = {"id": aid, "session": session_id,
                                                  "server": body.server_id, "tool": body.tool,
                                                  "expires_at": PENDING_APPROVALS.get(aid),
                                                  "argument_fields": sorted(body.arguments),
                                                  "arguments_sha256": call_event.args_hash,
                                                  "reason": " ".join(approval_reasons),
                                                  "destination_label": None,
                                                  "data_class": call_event.data_class.value}
                    if body.approval_id != aid or not _consume_approval(aid):
                        return _decision_response(session_id, {"verdict": Verdict.APPROVAL.value, "result": None,
                                "approval_id": aid, "reason": " ".join(approval_reasons)})
                    verdict = Verdict.ALLOW

            result = await asyncio.wait_for(session.call_tool(body.tool, body.arguments), timeout=45)
            result_text = _mcp_result_text(result)
            _record_output(request, session_id, call_event, result_text)
            return _decision_response(session_id, {"verdict": verdict.value, "result": result_text[:65536],
                    "result_truncated": len(result_text) > 65536,
                    "is_error": bool(getattr(result, "isError", False)),
                    "reason": "MCP call completed through approved inventory"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Guarded MCP call failed ({type(exc).__name__})") from exc
    finally:
        registry.close()


@app.get("/api/graph")
def api_graph(session: str) -> dict:
    """Attack graph + suspicious paths for a live or saved session."""
    from crosstoolguard.graph.potential import project_possible_paths

    events = SESSION_EVENTS.get(session, [])
    if not events:
        from crosstoolguard.gateway.run_store import load_run

        try:
            snapshot = load_run(session)
        except ValueError:
            snapshot = None
        if snapshot is not None:
            return {"nodes": snapshot.get("nodes", []), "edges": snapshot.get("edges", []),
                    "paths": snapshot.get("paths", []),
                    "potential_paths": snapshot.get("potential_paths", []),
                    "signals": snapshot.get("signals", [])}
    graph, findings = analyze_with_graph(events) if events else (nx.DiGraph(), [])
    nodes = [{"id": n, **{k: v for k, v in d.items()}} for n, d in graph.nodes(data=True)]
    edges = [{"source": u, "target": v, **e} for u, v, e in graph.edges(data=True)]
    paths = [{"pattern": f.pattern, "severity": f.severity, "risk": round(f.risk, 3),
              "tools": f.tool_sequence, "node_ids": f.path} for f in findings]
    projected = project_possible_paths(RUN_STATUS.get(session, {}).get("inventories", []), events)
    signals = [{"node_id": node, "origin_tool": data.get("origin_tool", ""),
                "explanation": "Untrusted tool output contained an instruction-like command. "
                               "This signal alone does not show that the agent followed it."}
               for node, data in graph.nodes(data=True) if data.get("type") == "INSTRUCTION"]
    nodes.extend(projected["nodes"])
    edges.extend(projected["edges"])
    return {"nodes": nodes, "edges": edges, "paths": paths,
            "potential_paths": projected["paths"], "signals": signals}


@app.get("/api/sessions")
def api_sessions() -> dict:
    """Summarize live gateway sessions for the dashboard."""
    from crosstoolguard.gateway.run_store import list_runs

    rows = []
    for session_id, events in SESSION_EVENTS.items():
        graph, findings = analyze_with_graph(events) if events else (nx.DiGraph(), [])
        has_signal = any(data.get("type") == "INSTRUCTION" for _, data in graph.nodes(data=True))
        tools = {(event.server, event.tool) for event in events
                 if event.event_type == EventType.TOOL_CALL}
        blocked = SESSION_DECISIONS.get(session_id, []).count(Verdict.BLOCK.value)
        severity = {finding.severity for finding in findings}
        rows.append({"id": session_id, "tools": len(tools), "events": len(events),
                     "findings": len(findings), "blocked": blocked,
                     "signals": sum(data.get("type") == "INSTRUCTION" for _, data in graph.nodes(data=True)),
                     "possible_paths": len(api_graph(session_id)["potential_paths"]),
                     "outcome": RUN_STATUS.get(session_id, {}).get("report", {}).get("outcome"),
                     "maxRisk": max((finding.risk for finding in findings), default=0.0),
                     "run_status": RUN_STATUS.get(session_id, {}).get("status"),
                     "status": "CRITICAL" if "CRITICAL" in severity else "HIGH" if findings or blocked or has_signal else "CLEAN"})
    live_ids = {row["id"] for row in rows}
    for session_id in RUN_STATUS:
        if session_id not in live_ids:
            rows.append({"id": session_id, "tools": 0, "events": 0,
                         "findings": 0, "blocked": 0, "maxRisk": 0.0,
                         "signals": 0, "possible_paths": len(api_graph(session_id)["potential_paths"]),
                         "outcome": RUN_STATUS[session_id].get("report", {}).get("outcome"),
                         "run_status": RUN_STATUS[session_id].get("status"),
                         "status": "CLEAN"})
            live_ids.add(session_id)
    for snapshot in list_runs():
        session_id = snapshot.get("session")
        if not session_id or session_id in live_ids:
            continue
        paths = snapshot.get("paths", [])
        report = snapshot.get("report", {})
        rows.append({"id": session_id, "tools": len(set(call.get("tool") for call in report.get("calls", []))),
                     "events": len(snapshot.get("events", [])), "findings": len(paths),
                     "signals": len(snapshot.get("signals", [])),
                     "possible_paths": len(snapshot.get("potential_paths", [])),
                     "outcome": report.get("outcome"),
                     "blocked": sum(call.get("verdict") == "BLOCK" for call in report.get("calls", [])),
                     "maxRisk": max((path.get("risk", 0) for path in paths), default=0),
                     "run_status": "complete",
                     "status": "CRITICAL" if any(path.get("severity") == "CRITICAL" for path in paths)
                     else "HIGH" if paths or snapshot.get("signals") or any(call.get("verdict") == "BLOCK" for call in report.get("calls", [])) else "CLEAN"})
    return {"sessions": rows}


@app.delete("/api/sessions")
def api_clear_sessions() -> dict:
    """Clear prior demo sessions while preserving approved tool inventories."""
    from pathlib import Path
    from crosstoolguard.gateway.run_store import clear_runs

    if any(state.get("status") in {"running", "awaiting_approval"} for state in RUN_STATUS.values()):
        raise HTTPException(status_code=409, detail="Wait for active runs before clearing sessions")
    removed = clear_runs()
    SESSION_EVENTS.clear()
    SESSION_LAST_OUTPUT.clear()
    SESSION_DECISIONS.clear()
    SESSION_BLOCKS.clear()
    RUN_STATUS.clear()
    with _APPROVAL_LOCK:
        PENDING_APPROVALS.clear()
        PENDING_APPROVAL_INFO.clear()
        APPROVALS.clear()
    event_path = Path(os.getenv("EVENTS_PATH", "events.jsonl")).resolve()
    if event_path.is_relative_to(Path(__file__).resolve().parents[2]) and event_path.is_file():
        event_path.unlink()
    return {"cleared_saved_runs": removed}


@app.get("/api/sessions/{session_id}")
def api_session(session_id: str) -> dict:
    """Return one live session's redacted events and actual attack graph."""
    from crosstoolguard.gateway.run_store import load_run

    if session_id not in SESSION_EVENTS and session_id not in RUN_STATUS:
        try:
            snapshot = load_run(session_id)
        except ValueError:
            snapshot = None
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return snapshot
    graph = api_graph(session_id)
    saved = load_run(session_id)
    return {"session": session_id, **graph,
            "events": [event.model_dump(mode="json") for event in SESSION_EVENTS.get(session_id, [])],
            "alerts": api_alerts(session_id)["alerts"],
            "blocks": SESSION_BLOCKS.get(session_id, saved.get("blocks", []) if saved else []),
            "report": RUN_STATUS.get(session_id, {}).get("report") or
                      (saved.get("report") if saved else None)}


@app.get("/api/runs")
def api_runs() -> dict:
    from crosstoolguard.gateway.run_store import list_runs

    return {"runs": [{"session_id": item.get("session"), **item.get("report", {})}
                     for item in list_runs()]}


@app.get("/api/alerts")
def api_alerts(session: str) -> dict:
    """Ranked findings with NL explanations for a live or saved session."""
    events = SESSION_EVENTS.get(session, [])
    if not events:
        from crosstoolguard.gateway.run_store import load_run

        try:
            snapshot = load_run(session)
        except ValueError:
            snapshot = None
        return {"alerts": snapshot.get("alerts", []) if snapshot else []}
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
