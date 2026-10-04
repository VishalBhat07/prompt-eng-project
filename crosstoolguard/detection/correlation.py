"""Cross-tool correlation engine — the heart of CrossToolGuard (doc §21).

Instead of judging one tool call, analyze() evaluates whole paths:
build the attack graph, enrich it with semantic instruction nodes, match
the pattern library, and score every suspicious path. Returns findings
sorted by risk, deduped by (pattern, tool chain).
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from crosstoolguard.analyzer.semantic import classify
from crosstoolguard.detection.patterns import load_patterns, pattern_matches
from crosstoolguard.detection.risk import score_path
from crosstoolguard.gateway.schemas import Event, EventType
from crosstoolguard.graph.builder import build
from crosstoolguard.graph.edges import EdgeType
from crosstoolguard.graph.nodes import NodeType
from crosstoolguard.graph.paths import find_paths, tool_sequence
from crosstoolguard.registry.capabilities import extract_capabilities


@dataclass
class Finding:
    pattern: str
    severity: str
    tool_sequence: list[str]
    risk: float
    path: list[str]


def _enrich_instructions(graph: nx.DiGraph, events: list[Event]) -> None:
    """Add INSTRUCTION nodes for SUSPICIOUS tool outputs (semantic layer).

    Only the label and score are stored — never raw output text.
    """
    for event in events:
        if event.event_type != EventType.TOOL_OUTPUT or not event.output_preview:
            continue
        if classify(event.output_preview) != "SUSPICIOUS":
            continue
        nid = f"instruction:{event.event_id}"
        graph.add_node(nid, type=NodeType.INSTRUCTION.value, session_id=event.session_id,
                       timestamp=event.timestamp.isoformat(), trust="LOW",
                       origin_tool=event.tool,
                       origin_capabilities=sorted(extract_capabilities(event.tool, "")))
        for child in events:
            if child.parent_id == event.event_id and child.event_type == EventType.TOOL_CALL:
                graph.add_edge(nid, f"tool:{child.tool}:{child.event_id}",
                               type=EdgeType.INFLUENCES.value)


def analyze_with_graph(events: list[Event]) -> tuple[nx.DiGraph, list[Finding]]:
    graph = build(events)
    _enrich_instructions(graph, events)
    findings: list[Finding] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for pattern in load_patterns():
        query = pattern.query
        for path in find_paths(graph, source_class=query.get("source_class"),
                               source_trust=query.get("source_trust"),
                               dest_cap=query["dest_cap"]):
            if not pattern_matches(graph, path, pattern):
                continue
            seq = tool_sequence(graph, path)
            key = (pattern.name, tuple(seq))
            if key in seen:
                continue
            seen.add(key)
            findings.append(Finding(pattern.name, pattern.severity, seq,
                                    score_path(graph, path, [pattern.severity]), path))
    findings.sort(key=lambda f: f.risk, reverse=True)
    return graph, findings


def analyze(events: list[Event]) -> list[Finding]:
    return analyze_with_graph(events)[1]
