"""Graph risk engine (doc §30).

Risk(path) = ΣNodeRisk + ΣEdgeRisk + DataSensitivity + CapabilityRisk
             + BehaviorAnomaly + PatternBonus, normalized to 0.0–1.0.

NORMALIZER is tuned on the lab set (exfil ≈ 2.0, benign ≈ 0.2) and MUST
be re-validated in the Task 10 ablation - it is experimental, not law.
Policy bands: 0.0–0.3 ALLOW, 0.3–0.6 MONITOR, 0.6–0.8 APPROVAL, 0.8–1.0 BLOCK.
"""

from __future__ import annotations

import networkx as nx

from crosstoolguard.detection.anomaly import deviation
from crosstoolguard.graph.edges import EdgeType
from crosstoolguard.graph.nodes import NodeType

NORMALIZER = 2.2

_NODE_RISK = {"CREDENTIAL": 0.40, "SECRET": 0.30}
_EDGE_RISK = {EdgeType.SENDS.value: 0.20, EdgeType.FLOWS_TO.value: 0.15,
              EdgeType.GENERATES.value: 0.05, EdgeType.INFLUENCES.value: 0.05}
_DANGEROUS_CAPS = {"EXTERNAL_TRANSFER", "CREDENTIAL_READ", "SHELL_EXEC", "EMAIL_SEND"}
_SEVERITY_BONUS = {"CRITICAL": 0.40, "HIGH": 0.30}


def _node_risk(graph: nx.DiGraph, nid: str) -> float:
    attrs = graph.nodes[nid]
    risk = _NODE_RISK.get(attrs.get("data_class", ""), 0.0)
    if attrs.get("type") == NodeType.INSTRUCTION.value and attrs.get("trust") == "LOW":
        risk += 0.40  # attacker foothold: untrusted instruction in the loop
    caps = set(attrs.get("capabilities", [])) | set(attrs.get("origin_capabilities", []))
    if "EXTERNAL_TRANSFER" in caps:
        risk += 0.30
    elif "PRIVILEGED" in caps:
        risk += 0.20
    elif attrs.get("type") == NodeType.TOOL.value:
        risk += 0.05
    if attrs.get("type") == NodeType.DESTINATION.value:
        risk += 0.20
    return risk


def score_path(graph: nx.DiGraph, path: list[str], severities: list[str] | None = None) -> float:
    nodes = sum(_node_risk(graph, nid) for nid in path)
    edges = 0.0
    for u, v in zip(path, path[1:]):
        w = _EDGE_RISK.get(graph.edges[u, v].get("type", ""), 0.02)
        if graph.nodes[u].get("type") == NodeType.INSTRUCTION.value:
            w += 0.15  # instruction steering a tool is the attack motion
        edges += w
    sensitivity = max([_NODE_RISK.get(graph.nodes[nid].get("data_class", ""), 0.0) for nid in path] or [0.0])
    dangerous = {c for nid in path for c in
                 (set(graph.nodes[nid].get("capabilities", []))
                  | set(graph.nodes[nid].get("origin_capabilities", []))) & _DANGEROUS_CAPS}
    capability_risk = min(0.30, 0.15 * len(dangerous))
    pattern_bonus = sum(_SEVERITY_BONUS.get(s, 0.0) for s in (severities or []))
    total = nodes + edges + sensitivity + capability_risk + deviation(graph, path) + pattern_bonus
    return max(0.0, min(1.0, total / NORMALIZER))
