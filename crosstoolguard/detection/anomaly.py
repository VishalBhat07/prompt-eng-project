"""Behavioral anomaly — expected-vs-observed workflow deviation (doc §28).

v1: always 0.0 (no baseline learned yet). The hook exists so risk.py
already accounts for the term; learning per-task baselines
(SEARCH→READ→SUMMARIZE vs observed) is a Sprint 4 stretch extension.
"""

from __future__ import annotations

import networkx as nx


def deviation(graph: nx.DiGraph, path: list[str]) -> float:
    return 0.0
