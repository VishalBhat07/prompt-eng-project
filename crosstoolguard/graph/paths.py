"""Path queries — the heart of CrossToolGuard (doc §21).

An attack is a suspicious *path*, not a suspicious node: find directed
routes from classified Data to attacker-useful capabilities/destinations.
"""

from __future__ import annotations

import networkx as nx

from crosstoolguard.graph.nodes import NodeType


def find_paths(graph: nx.DiGraph, *, source_class: str, dest_cap: str,
               cutoff: int = 8) -> list[list[str]]:
    """All directed Data(source_class) → Tool(dest_cap)/Destination paths."""
    sources = [n for n, d in graph.nodes(data=True)
               if d.get("type") == NodeType.DATA.value and d.get("data_class") == source_class]
    targets = [n for n, d in graph.nodes(data=True)
               if (d.get("type") == NodeType.TOOL.value and dest_cap in d.get("capabilities", []))
               or d.get("type") == NodeType.DESTINATION.value]
    paths: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for src in sources:
        for dst in targets:
            if src == dst:
                continue
            for path in nx.all_simple_paths(graph, src, dst, cutoff=cutoff):
                key = tuple(tool_sequence(graph, path))
                if key not in seen:
                    seen.add(key)
                    paths.append(path)
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
