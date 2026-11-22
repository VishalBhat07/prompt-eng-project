"""Refresh the dashboard's labeled synthetic trace benchmark artifact."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("CTG_SEMANTIC_MODE", "heuristic")

from crosstoolguard.evaluation.benchmark import run_all
from crosstoolguard.evaluation.experiments import measure_latency, run_ablation, run_baselines
from crosstoolguard.evaluation.metrics import detection_rate, false_positive_rate


def main() -> None:
    results = run_all()
    baselines = run_baselines()
    ablation = run_ablation()
    full = baselines["E-full"]
    single = baselines["B-single-tool"]
    report = {
        "generated_by": "scripts/export_dashboard_benchmark.py",
        "cases": len(results),
        "attack_cases": sum(1 for result in results if result.get("expected_findings")),
        "benign_cases": sum(1 for result in results if "expected_findings" in result
                            and not result["expected_findings"]),
        "detection_rate": detection_rate(results),
        "false_positive_rate": false_positive_rate(results),
        "cross_tool_gain": sorted(full - single),
        "baselines": {name: {"caught": len(ids), "ids": sorted(ids)} for name, ids in baselines.items()},
        "ablation": {name: {"caught": len(ids), "ids": sorted(ids)} for name, ids in ablation.items()},
        "latency": measure_latency(),
    }
    output = Path(__file__).resolve().parents[1] / "dashboard/public/data/benchmark.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} synthetic trace cases to {output}")


if __name__ == "__main__":
    main()
