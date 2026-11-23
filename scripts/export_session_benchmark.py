"""Score versioned, inert session records and export public dashboard evidence."""

import hashlib
import json
import os
from statistics import median
from time import perf_counter

import yaml

from run_replay_evaluation import ROOT, events_for, graph_result, grouped_rate, percentile
from crosstoolguard.evaluation.benchmark import single_tool_flags
from crosstoolguard.gateway.schemas import DataClass, EventType

MANIFEST = "crosstoolguard/evaluation/data/SESSION_BENCHMARK_V3.yaml"
EXPANSION = "crosstoolguard/evaluation/data/SESSION_BENCHMARK_EXPANSION.yaml"
METHODS = ("single_output", "session_rule", "graph_without_dependencies", "cross_tool_guard")


def read_case(case):
    """Normalize the authored rows into the existing replay event format."""
    signal, path, verdict = case["expect"]
    expected = {"title": case["title"], "signal": signal, "path": path, "verdict": verdict,
                "alert": None if path is None else signal or path}
    events = []
    for kind, server, tool, data_class, detail, *parent in case["events"]:
        event = {"server": server, "tool": tool, "data_class": data_class}
        if kind == "out" and isinstance(detail, str):
            event.update(event_type="TOOL_OUTPUT", output_preview=detail)
        elif kind == "call" and isinstance(detail, list):
            event.update(event_type="TOOL_CALL", capabilities=detail)
        else:
            raise ValueError(f"Invalid event in {case['id']}: {kind}")
        if parent:
            event["parent"], = parent
        events.append(event)
    record = {"id": case["id"], "group": case["group"], "expected": expected, "events": events}
    for key in ("example", "source", "pair"):
        if key in case:
            record[key] = case[key]
    return record


def read_pairs(pairs):
    for pair in pairs:
        variants = pair["variants"]
        if len(variants) != 2:
            raise ValueError(f"{pair['id']} must have two variants")
        for suffix, title, expected, events in variants:
            yield read_case({
                "id": f"{pair['id']}-{suffix}", "title": title, "group": pair["group"],
                "expect": expected, "events": pair["prefix"] + events, "pair": pair["id"],
            })


def pair_agreement(rows):
    pairs = {}
    for row in rows:
        if "pair" in row:
            pairs.setdefault(row["pair"], []).append(row)
    scored = [pair for pair in pairs.values() if all(row["expected"]["alert"] is not None for row in pair)]
    return {
        name: {
            "numerator": sum(
                all(row["methods"][name]["alert"] == row["expected"]["alert"] for row in pair)
                for pair in scored
            ),
            "denominator": len(scored),
        }
        for name in METHODS
    }


def session_rule(events, flags):
    """An output alert or co-occurrence in order, regardless of which result was used."""
    saw_restricted = False
    for event in events:
        if event.event_type == EventType.TOOL_OUTPUT:
            saw_restricted |= event.data_class in {DataClass.SECRET, DataClass.CREDENTIAL}
        elif (event.event_type == EventType.TOOL_CALL and saw_restricted
              and "EXTERNAL_TRANSFER" in event.capabilities):
            return {"alert": True}
    return {"alert": bool(flags)}


def evaluate(events):
    def output_result():
        flags = single_tool_flags(events)
        return {"alert": bool(flags), "signal": bool(flags), "flagged_event_ids": flags}

    specs = {
        "single_output": output_result,
        "session_rule": lambda: session_rule(events, single_tool_flags(events)),
        "graph_without_dependencies": lambda: graph_result(
            [event.model_copy(update={"parent_id": None}) for event in events], enrich=True),
        "cross_tool_guard": lambda: graph_result(events, enrich=True),
    }
    methods = {}
    for name, run in specs.items():
        observed = run()
        timings = []
        for _ in range(5):
            start = perf_counter()
            run()
            timings.append((perf_counter() - start) * 1000)
        methods[name] = {**observed, "latency_ms": timings}
    return methods


def summary(rows):
    positive = [row for row in rows if row["expected"]["alert"] is True]
    negative = [row for row in rows if row["expected"]["alert"] is False]
    paths = [row for row in rows if row["expected"]["path"] is True]
    no_paths = [row for row in rows if row["expected"]["path"] is False]
    verdicts = [row for row in rows if row["expected"]["verdict"] is not None]
    signals = [row for row in rows if row["expected"]["signal"]]
    no_signals = [row for row in rows if not row["expected"]["signal"]]
    results = {}
    for name in METHODS:
        samples = [time for row in rows for time in row["methods"][name]["latency_ms"]]
        result = {
            "recall": grouped_rate(positive, lambda row: row["methods"][name]["alert"]),
            "false_alerts": grouped_rate(negative, lambda row: row["methods"][name]["alert"]),
            "latency_ms": {"median": median(samples), "p95": percentile(samples, .95), "n": len(samples)},
        }
        if name != "session_rule":
            result.update(
                signals_found=grouped_rate(signals, lambda row: row["methods"][name]["signal"]),
                false_signals=grouped_rate(no_signals, lambda row: row["methods"][name]["signal"]),
            )
        if name.startswith("graph") or name == "cross_tool_guard":
            result.update(
                paths_found=grouped_rate(paths, lambda row: row["methods"][name]["path"]),
                false_paths=grouped_rate(no_paths, lambda row: row["methods"][name]["path"]),
                verdict_agreement=grouped_rate(verdicts, lambda row: row["methods"][name]["verdict"] == row["expected"]["verdict"]),
            )
        results[name] = result
    return results


def main():
    os.environ["CTG_SEMANTIC_MODE"] = "heuristic"
    manifest = yaml.safe_load((ROOT / MANIFEST).read_bytes())
    expansion = yaml.safe_load((ROOT / EXPANSION).read_bytes())
    standalone = [read_case(case) for case in manifest["cases"] + expansion["cases"]]
    cases = standalone + list(read_pairs(expansion["pairs"]))
    if len(cases) != len({case["id"] for case in cases}):
        raise ValueError("Replay case IDs must be unique")
    inputs = [MANIFEST, EXPANSION, "scripts/export_session_benchmark.py",
              "scripts/run_replay_evaluation.py", "crosstoolguard/evaluation/benchmark.py",
              "crosstoolguard/analyzer/semantic.py", "crosstoolguard/graph/builder.py",
              "crosstoolguard/graph/paths.py", "crosstoolguard/graph/edges.py",
              "crosstoolguard/detection/correlation.py", "crosstoolguard/detection/risk.py",
              "crosstoolguard/detection/data/PATTERNS.yaml", "crosstoolguard/policy/data/POLICIES.yaml",
              "crosstoolguard/policy/engine.py", "crosstoolguard/registry/data/CAPABILITY_TAXONOMY.yaml"]
    fingerprints = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs}
    records_sha256 = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
    rows = []
    for case in cases:
        events = events_for(case)
        rows.append({**case, "events": [event.model_dump(mode="json") for event in events],
                     "methods": evaluate(events)})
    report = {
        "schema_version": 2, "dataset": "synthetic-session-replay-v3", "semantic_mode": "heuristic",
        "label_review": manifest["label_review"], "input_sha256": fingerprints,
        "records_sha256": records_sha256, "summary": summary(rows), "cases": rows,
        "pair_alert_agreement": pair_agreement(rows), "references": expansion["references"],
        "counts": {"total": len(rows), "groups": len({row["group"] for row in rows}),
                   "standalone": len(standalone), "pairs": len(expansion["pairs"]),
                   "positive": sum(row["expected"]["alert"] is True for row in rows),
                   "negative": sum(row["expected"]["alert"] is False for row in rows),
                   "unclear": sum(row["expected"]["alert"] is None for row in rows)},
    }
    path = ROOT / "dashboard/public/data/session-benchmark-v3.json"
    path.write_text(json.dumps(report, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
