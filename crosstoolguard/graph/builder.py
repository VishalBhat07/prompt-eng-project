"""Attack graph builder - events → temporal NetworkX DiGraph.

One graph per session (mixed sessions → ValueError, G6). Edges point
forward in time so `find_paths` exposes the attack direction, not just
co-occurrence:

- Server INVOKES Tool (every call)
- Tool GENERATES Data (classified outputs; SECRET/CREDENTIAL only -
  PUBLIC outputs add no security signal)
- Data FLOWS_TO Tool (call whose parent is a classified output)
- Tool INFLUENCES Tool (consecutive calls: temporal order backbone)
- Tool SENDS Destination (EXTERNAL_TRANSFER-capable tools)
- Tool READS Data (calls whose arguments reference sensitive paths)
"""

from __future__ import annotations

import networkx as nx

from crosstoolguard.gateway.schemas import DataClass, Event, EventType
from crosstoolguard.graph.edges import EdgeType
from crosstoolguard.graph.nodes import NodeType
from crosstoolguard.registry.capabilities import extract_capabilities

_CLASSIFIED = {DataClass.SECRET, DataClass.CREDENTIAL}
EXTERNAL = "external"


def _tool_node(g: nx.DiGraph, event: Event) -> str:
    nid = f"tool:{event.tool}:{event.event_id}"
    if nid not in g:
        g.add_node(nid, type=NodeType.TOOL.value, session_id=event.session_id,
                   timestamp=event.timestamp.isoformat(), tool=event.tool,
                   server=event.server,
                   capabilities=sorted(extract_capabilities(event.tool, "")))
    return nid


def _data_node(g: nx.DiGraph, event: Event, origin_tool: str) -> str:
    nid = f"data:{event.data_class.value}:{event.event_id}"
    if nid not in g:
        g.add_node(nid, type=NodeType.DATA.value, session_id=event.session_id,
                   timestamp=event.timestamp.isoformat(),
                   data_class=event.data_class.value, origin_tool=origin_tool,
                   origin_capabilities=sorted(extract_capabilities(origin_tool, "")))
    return nid


def build(events: list[Event]) -> nx.DiGraph:
    sessions = {e.session_id for e in events}
    if len(sessions) > 1:
        raise ValueError(f"graph spans sessions {sorted(sessions)}; build one graph per session")
    g = nx.DiGraph()
    by_id = {e.event_id: e for e in events}
    prev_tool: str | None = None

    for event in sorted(events, key=lambda e: e.timestamp):
        tool_nid = _tool_node(g, event)
        server_nid = f"server:{event.server}"
        if server_nid not in g:
            g.add_node(server_nid, type=NodeType.SERVER.value,
                       session_id=event.session_id, server=event.server)
        g.add_edge(server_nid, tool_nid, type=EdgeType.INVOKES.value)

        if event.event_type == EventType.TOOL_OUTPUT and event.data_class in _CLASSIFIED:
            data_nid = _data_node(g, event, origin_tool=event.tool)
            g.add_edge(tool_nid, data_nid, type=EdgeType.GENERATES.value)

        if event.event_type == EventType.TOOL_CALL:
            parent = by_id.get(event.parent_id or "")
            if (parent is not None and parent.event_type == EventType.TOOL_OUTPUT
                    and parent.data_class in _CLASSIFIED):
                data_nid = _data_node(g, parent, origin_tool=parent.tool)
                g.add_edge(data_nid, tool_nid, type=EdgeType.FLOWS_TO.value)

        if prev_tool is not None and prev_tool != tool_nid:
            g.add_edge(prev_tool, tool_nid, type=EdgeType.INFLUENCES.value)
        prev_tool = tool_nid

        caps = g.nodes[tool_nid]["capabilities"]
        if "EXTERNAL_TRANSFER" in caps:
            dest = f"destination:{EXTERNAL}"
            if dest not in g:
                g.add_node(dest, type=NodeType.DESTINATION.value,
                           session_id=event.session_id, name=EXTERNAL)
            g.add_edge(tool_nid, dest, type=EdgeType.SENDS.value)

    return g
# NOTE (Task 6): add Tool READS Data for calls whose arguments reference
# sensitive paths (registry.sensitivity_for_path over argument values).
