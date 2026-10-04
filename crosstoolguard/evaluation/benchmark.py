"""Benchmark runner — cases → findings → verdicts (plan Task 9).

Builders live in crosstoolguard.attacks; this module only loads the YAML,
dispatches by kind, and records results for metrics.py.
"""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path

import yaml

BENCH_CATEGORIES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
BENIGN_IDS = ["N-search-read", "N-invoice-calc", "N-list-files", "N-store-local",
              "N-read-public", "N-add-multiply", "N-search-no-match", "N-read-then-search"]


@lru_cache(maxsize=1)
def load_benchmark() -> list[dict]:
    raw = yaml.safe_load((Path(__file__).parent / "data" / "BENCHMARK.yaml").read_text())
    return raw["cases"]


def _builder(spec: str):
    module, func = spec.split(":")
    return getattr(importlib.import_module(f"crosstoolguard.attacks.{module}"), func)


def get_case(case_id: str) -> dict:
    for case in load_benchmark():
        if case["id"] == case_id:
            return case
    raise KeyError(f"unknown case: {case_id}")


def run_case(case_id: str) -> dict:
    """Run one case → {id, patterns, verdict, ...} for metrics."""
    from crosstoolguard.detection.correlation import analyze
    from crosstoolguard.policy.engine import decide_for_session

    case = get_case(case_id)
    made = _builder(case["builder"])()
    if case["kind"] == "detection":
        findings = analyze(made)
        verdict = decide_for_session(made).value
        return {"id": case_id, "expected_findings": case["expected"].get("patterns", []),
                "patterns": [f.pattern for f in findings], "verdict": verdict,
                "expected_verdict": case["expected"].get("verdict"),
                "chains": [f.tool_sequence for f in findings]}
    if case["kind"] == "integrity":
        return {"id": case_id, "integrity": made["integrity"],
                "expected_integrity": case["expected"]["integrity"]}
    if case["kind"] == "provenance":
        return {"id": case_id, "origin": made["origin"],
                "expected_origin": case["expected"]["origin"]}
    raise ValueError(f"unknown kind: {case['kind']}")


def run_all() -> list[dict]:
    return [run_case(c["id"]) for c in load_benchmark()]


def single_tool_detect(events) -> bool:
    """Baseline B: per-event judgment only — SUSPICIOUS text, or a lone
    SECRET-arg call to an external-transfer tool. No cross-event reasoning."""
    from crosstoolguard.analyzer.semantic import classify
    from crosstoolguard.gateway.schemas import EventType

    for e in events:
        if e.event_type == EventType.TOOL_OUTPUT and e.output_preview:
            if classify(e.output_preview) == "SUSPICIOUS":
                return True
    return False
