"""Attack pattern matching — ordered stages as path subsequences."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import networkx as nx
import yaml

from crosstoolguard.graph.nodes import NodeType


@dataclass
class Pattern:
    name: str
    severity: str
    query: dict
    stages: list[dict]


@lru_cache(maxsize=1)
def load_patterns() -> list[Pattern]:
    raw = yaml.safe_load((Path(__file__).parent / "data" / "PATTERNS.yaml").read_text())
    return [Pattern(**p) for p in raw["patterns"]]


def _node_caps(graph: nx.DiGraph, nid: str) -> set[str]:
    """Capabilities of a node: own, or origin-tool's for DATA/INSTRUCTION."""
    attrs = graph.nodes[nid]
    caps = set(attrs.get("capabilities", []))
    caps.update(attrs.get("origin_capabilities", []))
    return caps


def _stage_matches(graph: nx.DiGraph, nid: str, stage: dict) -> bool:
    attrs = graph.nodes[nid]
    if "node" in stage and attrs.get("type") != stage["node"]:
        return False
    if "data_classification" in stage and attrs.get("data_class") != stage["data_classification"]:
        return False
    if "trust" in stage and attrs.get("trust") != stage["trust"]:
        return False
    if "capability" in stage:
        want = {stage["capability"]} if isinstance(stage["capability"], str) else set(stage["capability"])
        if not (want & _node_caps(graph, nid)):
            return False
    return True


def pattern_matches(graph: nx.DiGraph, path: list[str], pattern: Pattern) -> bool:
    """True when stages match nodes in order (gaps allowed, order kept)."""
    idx = 0
    for nid in path:
        if _stage_matches(graph, nid, pattern.stages[idx]):
            idx += 1
            if idx == len(pattern.stages):
                return True
    return False


def match_all(graph: nx.DiGraph, path: list[str]) -> list[Pattern]:
    return [p for p in load_patterns() if pattern_matches(graph, path, p)]
