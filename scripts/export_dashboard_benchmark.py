"""Refresh the dashboard's labeled synthetic trace benchmark artifact."""

from __future__ import annotations

import json
import os
import math
from pathlib import Path
import sys
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("CTG_SEMANTIC_MODE", "heuristic")

from crosstoolguard.evaluation.benchmark import BENIGN_IDS, load_benchmark, run_all
from crosstoolguard.evaluation.experiments import measure_latency, run_ablation, run_baselines
from crosstoolguard.evaluation.metrics import detection_rate, false_positive_rate


def main() -> None:
    results = run_all()
    baselines = run_baselines()
    ablation = run_ablation()
    full = baselines["E-full"]
    single = baselines["B-single-tool"]
    by_id = {case["id"]: case for case in load_benchmark()}
    timings = measure_latency()
    ordered = sorted(timings.values())
    report = {
        "generated_by": "scripts/export_dashboard_benchmark.py",
        "schema_version": 2,
        "cases": len(results),
        "attack_cases": sum(1 for result in results if result.get("expected_findings")),
        "benign_cases": len(BENIGN_IDS),
        "detection_rate": detection_rate(results),
        "false_positive_rate": false_positive_rate([result for result in results if result["id"] in BENIGN_IDS]),
        "case_results": [{"category": by_id[row["id"]]["category"], "kind": by_id[row["id"]]["kind"],
                          "metric_group": ("benign" if row["id"] in BENIGN_IDS else "expected pattern"
                                           if row.get("expected_findings") else "known gap"
                                           if "expected_findings" in row else by_id[row["id"]]["kind"]),
                          **row} for row in results],
        "cross_tool_gain": sorted(full - single),
        "baselines": {name: {"caught": len(ids), "ids": sorted(ids)} for name, ids in baselines.items()},
        "ablation": {name: {"caught": len(ids), "ids": sorted(ids)} for name, ids in ablation.items()},
        "latency": {"mean_s": mean(ordered), "median_s": median(ordered),
                    "p95_s": ordered[math.ceil(.95 * len(ordered)) - 1], "n": len(ordered),
                    "per_case_s": timings},
    }
    output = Path(__file__).resolve().parents[1] / "dashboard/public/data/benchmark.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} synthetic trace cases to {output}")


if __name__ == "__main__":
    main()
