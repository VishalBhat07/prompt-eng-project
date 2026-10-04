"""Path queries — the heart of CrossToolGuard (doc §21).

An attack is a suspicious *path*, not a suspicious node: find directed
routes from classified Data to attacker-useful capabilities/destinations.
"""

from __future__ import annotations

import networkx as nx

from crosstoolguard.graph.nodes import NodeType


def find_paths(graph: nx.DiGraph, *, source_class: str | None = None,
               source_trust: str | None = None, dest_cap: str,
               cutoff: int = 8) -> list[list[str]]:
    """Directed source → Tool(dest_cap)/Destination paths.

    source_class selects DATA nodes (e.g. SECRET); source_trust selects
    INSTRUCTION nodes (e.g. LOW). Exactly one source selector is required.
    """
    if (source_class is None) == (source_trust is None):
        raise ValueError("pass exactly one of source_class / source_trust")
    if source_class is not None:
        sources = [n for n, d in graph.nodes(data=True)
                   if d.get("type") == NodeType.DATA.value and d.get("data_class") == source_class]
    else:
        sources = [n for n, d in graph.nodes(data=True)
                   if d.get("type") == NodeType.INSTRUCTION.value and d.get("trust") == source_trust]
    targets = [n for n, d in graph.nodes(data=True)
               if (d.get("type") == NodeType.TOOL.value and dest_cap in d.get("capabilities", []))
               or d.get("type") == NodeType.DESTINATION.value]
    paths: list[list[str]] = []
    best: dict[tuple[str, ...], list[str]] = {}
    for src in sources:
        for dst in targets:
            if src == dst:
                continue
            for path in nx.all_simple_paths(graph, src, dst, cutoff=cutoff):
                key = tuple(tool_sequence(graph, path))
                # Same chain, longer node path = more complete attack story.
                if key not in best or len(path) > len(best[key]):
                    best[key] = path
    paths.extend(best.values())
    return paths


def tool_sequence(graph: nx.DiGraph, path: list[str]) -> list[str]:
    """Human-readable tool chain for a path (Data nodes credit origin tool)."""
    seq: list[str] = []
    for nid in path:
        attrs = graph.nodes[nid]
        tool = attrs.get("tool") or attrs.get("origin_tool")
        if tool is not None and (not seq or seq[-1] != tool):
            seq.append(tool)
    return seq
