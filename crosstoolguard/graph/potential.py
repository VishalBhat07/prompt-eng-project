"""Clearly labeled possible paths from approved capabilities and observed output.

These are risk hypotheses, never evidence that an uncalled tool executed.
"""

from __future__ import annotations

import re
from typing import Any

from crosstoolguard.registry.capabilities import extract_capabilities

_READ = re.compile(r"\b(read|fetch|access|retrieve)\b", re.I)
_SENSITIVE = re.compile(r"\b(credential|secret|api[ _-]?key|token)\b", re.I)
_INSTRUCTION = re.compile(r"\b(ignore|disregard|override)\b|\b(read|send).{0,50}\b(credential|secret)\b", re.I)


def project_possible_paths(inventories: list[dict[str, Any]], events: list[Any]) -> dict[str, list[dict]]:
    sources: list[str] = []
    sinks: list[str] = []
    for inventory in inventories:
        if inventory.get("integrity_status") != "APPROVED":
            continue
        server = str(inventory.get("server_id") or "")
        for tool in inventory.get("tools", []):
            if tool.get("_registry", {}).get("integrity_status") not in {None, "APPROVED"}:
                continue
            name = str(tool.get("name") or "")
            text = f"{name.replace('_', ' ')} {tool.get('description') or ''}"
            ref = f"{server}/{name}"
            if _READ.search(text) and _SENSITIVE.search(text):
                sources.append(ref)
            if "EXTERNAL_TRANSFER" in extract_capabilities(name, text):
                sinks.append(ref)
    triggers = []
    for event in events:
        if str(getattr(event, "event_type", "")).endswith("TOOL_OUTPUT"):
            preview = str(getattr(event, "output_preview", "") or "")
            if _INSTRUCTION.search(preview):
                triggers.append({"event_id": event.event_id, "server": event.server,
                                 "tool": event.tool})
    nodes: list[dict] = []
    edges: list[dict] = []
    paths: list[dict] = []
    for source in sources:
        for sink in sinks:
            if source == sink:
                continue
            source_id, sink_id = f"possible:{source}", f"possible:{sink}"
            nodes.extend([{"id": source_id, "type": "TOOL", "tool": source,
                           "hypothetical": True},
                          {"id": sink_id, "type": "TOOL", "tool": sink,
                           "hypothetical": True}])
            edges.append({"source": source_id, "target": sink_id, "type": "POSSIBLE_FLOW",
                          "hypothetical": True})
            for trigger in triggers:
                edges.append({"source": f"tool:{trigger['tool']}:{trigger['event_id']}",
                              "target": source_id, "type": "POSSIBLE_INFLUENCE",
                              "hypothetical": True})
            paths.append({"source": source, "destination": sink, "trigger_events": triggers,
                          "explanation": "An approved tool could read sensitive data and another could transfer it. "
                          "This is a possible path; it has not been observed or blocked in this run."})
    unique_nodes = {node["id"]: node for node in nodes}
    unique_edges = {(edge["source"], edge["target"], edge["type"]): edge for edge in edges}
    return {"nodes": list(unique_nodes.values()), "edges": list(unique_edges.values()), "paths": paths}
