"""Export case-level development evidence without contacting external providers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crosstoolguard.evaluation.benchmark import load_benchmark, run_all


def rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def development_report():
    specs = {case["id"]: case for case in load_benchmark()}
    rows = []
    for result in run_all():
        case = specs[result["id"]]
        expected = case["expected"]
        if case["kind"] == "detection":
            group = ("benign" if case["category"] == "N" else
                     "pattern_expected" if expected.get("patterns") else "known_gap")
            actual = {key: result[key] for key in ("patterns", "verdict", "chains")}
        else:
            group = case["kind"]
            key = "integrity" if group == "integrity" else "origin"
            actual = {key: result[key]}
        rows.append({"id": result["id"], "category": case["category"],
                     "kind": case["kind"], "group": group, "expected": expected, "actual": actual})

    positives = [row for row in rows if row["group"] == "pattern_expected"]
    benign = [row for row in rows if row["group"] == "benign"]
    decisions = [row for row in rows if "verdict" in row["expected"]]
    return {
        "cases": rows,
        "summary": {
            "case_count": len(rows),
            "expected_pattern_detected": rate(sum(bool(set(row["expected"]["patterns"])
                                                     & set(row["actual"]["patterns"]))
                                                for row in positives), len(positives)),
            "benign_false_alerts": rate(sum(bool(row["actual"]["patterns"]) for row in benign), len(benign)),
            "verdict_agreement": rate(sum(row["actual"]["verdict"] == row["expected"]["verdict"]
                                          for row in decisions), len(decisions)),
            "known_gap_ids": [row["id"] for row in rows if row["group"] == "known_gap"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/development-pilot.json")
    args = parser.parse_args()
    os.environ["CTG_SEMANTIC_MODE"] = "heuristic"
    report = development_report()
    inputs = [
        "crosstoolguard/evaluation/data/BENCHMARK.yaml",
        "crosstoolguard/detection/data/PATTERNS.yaml",
        "crosstoolguard/policy/data/POLICIES.yaml",
        "crosstoolguard/registry/data/CAPABILITY_TAXONOMY.yaml",
    ]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    report.update({
        "schema_version": 1,
        "dataset": "development_synthetic",
        "semantic_mode": "heuristic",
        "base_commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "python_version": platform.python_version(),
        "input_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs},
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
