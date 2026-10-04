"""Finding signals — reduce a graph path to policy-matchable facts."""

from __future__ import annotations

import networkx as nx

from crosstoolguard.detection.correlation import Finding
from crosstoolguard.graph.nodes import NodeType


def finding_signals(graph: nx.DiGraph, finding: Finding) -> dict:
    data_classes: set[str] = set()
    capabilities: set[str] = set()
    capability_sequence: list[str] = []
    low_trust_instruction = False
    for nid in finding.path:
        attrs = graph.nodes[nid]
        if attrs.get("data_class"):
            data_classes.add(attrs["data_class"])
        caps = set(attrs.get("capabilities", [])) | set(attrs.get("origin_capabilities", []))
        capabilities |= caps
        if caps and attrs.get("type") in (NodeType.TOOL.value, NodeType.DATA.value):
            # DATA nodes credit their origin tool: the chain reads end-to-end.
            capability_sequence.append(sorted(caps)[0])
        if attrs.get("type") == NodeType.INSTRUCTION.value and attrs.get("trust") == "LOW":
            low_trust_instruction = True
    return {"data_classes": data_classes, "capabilities": capabilities,
            "capability_sequence": capability_sequence,
            "low_trust_instruction": low_trust_instruction}
