"""Run the frozen evaluation on inert records without connecting to tools."""

import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
from statistics import median
import subprocess
import sys
from time import perf_counter

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crosstoolguard.detection.correlation import analyze_with_graph
from crosstoolguard.evaluation.benchmark import single_tool_detect
from crosstoolguard.evaluation.experiments import keyword_detect
from crosstoolguard.gateway.schemas import Event
from crosstoolguard.policy.engine import decide, reasons_for

INPUTS = [
    "crosstoolguard/evaluation/data/REPLAY_V1.yaml",
    "crosstoolguard/detection/data/PATTERNS.yaml",
    "crosstoolguard/policy/data/POLICIES.yaml",
    "crosstoolguard/registry/data/CAPABILITY_TAXONOMY.yaml",
]


def percentile(values, proportion):
    return sorted(values)[max(0, math.ceil(len(values) * proportion) - 1)] if values else None


def events_for(case):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = []
    for index, fields in enumerate(case["events"]):
        fields = dict(fields)
        parent = fields.pop("parent", None)
        if parent is not None and not 0 <= parent < index:
            raise ValueError(f"invalid event parent in {case['id']}")
        events.append(Event(event_id=f"{case['id']}-{index}", session_id=case["id"],
                            timestamp=start + timedelta(seconds=index),
                            parent_id=None if parent is None else events[parent].event_id, **fields))
    return events


def graph_result(events, *, enrich):
    graph, findings = analyze_with_graph(events, enrich_instructions=enrich)
    signal_ids = [node_id for node_id, node in graph.nodes(data=True) if node.get("type") == "INSTRUCTION"]
    return {
        "alert": bool(signal_ids or findings), "signal": bool(signal_ids), "signal_ids": signal_ids, "path": bool(findings),
        "findings": [asdict(finding) for finding in findings],
        "verdict": decide([action for _, action in reasons_for(graph, findings)]).value,
    }


def grouped_rate(rows, hit):
    groups = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(int(hit(row)))
    values = list(groups.values())
    numerator = sum(map(sum, values))
    rng = random.Random(20261122)
    draws = []
    for _ in range(2000):
        sample = rng.choices(values, k=len(values))
        draws.append(sum(map(sum, sample)) / sum(map(len, sample)))
    return {"numerator": numerator, "denominator": len(rows),
            "groups": len(values), "value": numerator / len(rows),
            "bootstrap_95": [percentile(draws, .025), percentile(draws, .975)]}


def run():
    cases = yaml.safe_load((ROOT / INPUTS[0]).read_bytes())["cases"]
    if len({case["id"] for case in cases}) != 24:
        raise ValueError("replay set must contain 24 unique cases")
    methods = {
        "no_detector": lambda events: {"alert": False},
        "keyword": lambda events: {"alert": keyword_detect(events)},
        "single_output": lambda events: {"alert": single_tool_detect(events)},
        "graph_without_instruction_enrichment": lambda events: graph_result(events, enrich=False),
        "full_graph": lambda events: graph_result(events, enrich=True),
    }
    rows = []
    for case in cases:
        events = events_for(case)
        results = {}
        for name, method in methods.items():
            observed = method(events)
            samples = []
            for _ in range(5):
                start = perf_counter()
                method(events)
                samples.append((perf_counter() - start) * 1000)
            results[name] = {**observed, "latency_ms": samples}
        rows.append({"id": case["id"], "group": case["group"], "event_count": len(events),
                     "expected": case["expected"], "methods": results})
    positive = [row for row in rows if row["expected"]["alert"]]
    benign = [row for row in rows if not row["expected"]["alert"]]
    if (len(positive), len(benign)) != (12, 12):
        raise ValueError("replay set must contain 12 positive and 12 benign cases")
    summary = {}
    for name in methods:
        samples = [value for row in rows for value in row["methods"][name]["latency_ms"]]
        summary[name] = {
            "alert_recall": grouped_rate(positive, lambda row: row["methods"][name]["alert"]),
            "false_alerts": grouped_rate(benign, lambda row: row["methods"][name]["alert"]),
            "latency_ms": {"median": median(samples), "p95": percentile(samples, .95), "n": len(samples)},
        }
    summary["full_graph"]["verdict_agreement"] = grouped_rate(
        rows, lambda row: row["methods"]["full_graph"]["verdict"] == row["expected"]["verdict"])
    return {"cases": rows, "summary": summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/replay-v1.json")
    args = parser.parse_args()
    os.environ["CTG_SEMANTIC_MODE"] = "heuristic"
    report = run()
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    report.update({"dataset": "synthetic_replay_v1", "label_review": "single-author, pre-run",
                   "semantic_mode": "heuristic", "base_commit": revision.stdout.strip(),
                   "environment": {"python": platform.python_version(), "os": platform.platform(),
                                   "processor": platform.processor()},
                   "input_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in INPUTS}})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, result in report["summary"].items():
        print(name, "alerts", result["alert_recall"]["numerator"], "/ 12",
              "false alerts", result["false_alerts"]["numerator"], "/ 12")
    print("Full graph verdict agreement:", report["summary"]["full_graph"]["verdict_agreement"])


if __name__ == "__main__":
    main()
