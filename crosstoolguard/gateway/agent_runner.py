"""Playground runner — prompt → planned tool calls → enforced trace.

Single-user v1: server-side Groq key, model override per run. Every step
goes through the same execute path as the HTTP route, so verdicts are
real enforcement, not a reenactment. Halts on BLOCK/APPROVAL/ERROR.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from crosstoolguard.gateway.schemas import ToolCall
from crosstoolguard.gateway.session import ensure_session
from lab.agent import plan_next, plan_with_llm


class AgentRun(BaseModel):
    task: str
    session_id: str | None = None
    provider: str | None = None
    model: str | None = None
    max_steps: int = Field(default=5, le=10)


def run_task(task: str, session_id: str | None = None, model: str | None = None,
             max_steps: int = 5, provider: str | None = None) -> dict:
    from crosstoolguard.gateway.proxy import execute_tool_call

    session = ensure_session(session_id)
    steps: list[dict] = []
    server, tool, args = plan_with_llm(task, model=model, provider=provider or "groq")
    for _ in range(max_steps):
        if server == "DONE":
            return {"session_id": session, "steps": steps, "halted": False,
                    "done": True, "provider": provider or "groq", "model": model}
        try:
            out = execute_tool_call(
                ToolCall(session_id=session, server=server, tool=tool, arguments=args), session)
        except Exception as exc:
            steps.append({"server": server, "tool": tool, "arguments": args,
                          "verdict": "ERROR", "observation": f"{type(exc).__name__}: {exc}"[:300]})
            return {"session_id": session, "steps": steps, "halted": True,
                    "done": False, "provider": provider or "groq", "model": model}
        observation = str(out.get("result") or "")[:500]
        step = {"server": server, "tool": tool, "arguments": args,
                "verdict": out["verdict"], "observation": observation}
        if out.get("approval_id"):
            step["approval_id"] = out["approval_id"]
        steps.append(step)
        if out["verdict"] != "ALLOW":
            return {"session_id": session, "steps": steps, "halted": True,
                    "done": False, "provider": provider or "groq", "model": model}
        server, tool, args = plan_next(task, steps, model=model, provider=provider or "groq")
    return {"session_id": session, "steps": steps, "halted": True,
            "done": False, "provider": provider or "groq", "model": model,
            "reason": "step budget exhausted"}
