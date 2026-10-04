"""Baselines, ablation ladder, latency (doc §54–55, plan Task 10).

Baselines: A no-security, B single-tool, C keyword scanner, E full system.
Ablation A–E peels layers off to show which components carry detection:
A semantic-only → B +provenance → C +capabilities → D +graph → E full.
"""

from __future__ import annotations

import re
import time

from crosstoolguard.evaluation.benchmark import _builder, load_benchmark

KEYWORDS = re.compile(
    r"ignor|disregard|exfiltrat|bypass|override|send .{0,20}(secret|database|\.env)|upload the",
    re.IGNORECASE)


def _attack_cases():
    return [c for c in load_benchmark()
            if c["kind"] == "detection" and c["expected"].get("patterns")]


def _events(case):
    return _builder(case["builder"])()


def keyword_detect(events) -> bool:
    """Baseline C: regex over output previews, no semantics, no graph."""
    from crosstoolguard.gateway.schemas import EventType

    return any(e.event_type == EventType.TOOL_OUTPUT and e.output_preview
               and KEYWORDS.search(e.output_preview) for e in events)


def _full_detect(case) -> bool:
    from crosstoolguard.detection.correlation import analyze

    events = _events(case)
    found = {f.pattern for f in analyze(events)}
    return bool(found & set(case["expected"]["patterns"]))


def run_baselines() -> dict[str, set[str]]:
    """Detected attack ids per baseline (A detects nothing by construction)."""
    from crosstoolguard.evaluation.benchmark import single_tool_detect

    out: dict[str, set[str]] = {"A-no-security": set(), "B-single-tool": set(),
                                "C-keyword": set(), "E-full": set()}
    for case in _attack_cases():
        events = _events(case)
        if single_tool_detect(events):
            out["B-single-tool"].add(case["id"])
        if keyword_detect(events):
            out["C-keyword"].add(case["id"])
        if _full_detect(case):
            out["E-full"].add(case["id"])
    return out


def _provenance_flag(events) -> bool:
    return any(getattr(e, "data_class", "PUBLIC") in ("SECRET", "CREDENTIAL") for e in events)


def _capability_flag(events) -> bool:
    from crosstoolguard.registry.capabilities import extract_capabilities

    tools = {e.tool for e in events}
    caps = {c for t in tools for c in extract_capabilities(t, "")}
    return _provenance_flag(events) and "EXTERNAL_TRANSFER" in caps


def _graph_no_enrich_detect(case) -> bool:
    """D: paths + patterns on the unenriched graph (no instruction nodes)."""
    from crosstoolguard.detection.patterns import load_patterns, pattern_matches
    from crosstoolguard.graph.builder import build
    from crosstoolguard.graph.paths import find_paths

    events = _events(case)
    graph = build(events)
    for pattern in load_patterns():
        q = pattern.query
        for path in find_paths(graph, source_class=q.get("source_class"),
                               source_trust=q.get("source_trust"), dest_cap=q["dest_cap"]):
            if pattern_matches(graph, path, pattern) and pattern.name in case["expected"]["patterns"]:
                return True
    return False


def run_ablation() -> dict[str, list[str]]:
    """Detected attack ids per layer configuration."""
    from crosstoolguard.evaluation.benchmark import single_tool_detect

    table: dict[str, list[str]] = {"A-semantic-only": [], "B-plus-provenance": [],
                                   "C-plus-capabilities": [], "D-graph-no-enrich": [], "E-full": []}
    for case in _attack_cases():
        events = _events(case)
        if single_tool_detect(events):
            table["A-semantic-only"].append(case["id"])
        if _provenance_flag(events):
            table["B-plus-provenance"].append(case["id"])
        if _capability_flag(events):
            table["C-plus-capabilities"].append(case["id"])
        if _graph_no_enrich_detect(case):
            table["D-graph-no-enrich"].append(case["id"])
        if _full_detect(case):
            table["E-full"].append(case["id"])
    return table


def measure_latency() -> dict[str, float]:
    """Wall-clock analyze() seconds per detection case (warmed-up embeddings)."""
    from crosstoolguard.detection.correlation import analyze
    from crosstoolguard.evaluation.benchmark import BENIGN_IDS, get_case

    cases = _attack_cases() + [get_case(cid) for cid in BENIGN_IDS]
    _builder(cases[0]["builder"])()
    lat: dict[str, float] = {}
    for case in cases:
        events = _events(case)
        start = time.perf_counter()
        analyze(events)
        lat[case["id"]] = time.perf_counter() - start
    return lat
