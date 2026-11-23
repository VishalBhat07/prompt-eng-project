"""Export the same inert records for per-output and graph comparisons."""

import hashlib
import json
import os

import yaml

from run_replay_evaluation import ROOT, events_for, graph_result
from crosstoolguard.analyzer.semantic import classify
from crosstoolguard.gateway.schemas import EventType

MANIFEST = ROOT / "crosstoolguard/evaluation/data/MATCHED_REPLAY_V1.yaml"


def evaluate_pair(pair):
    cases = []
    for variant in pair["variants"]:
        overrides = variant["overrides"]
        case_id = f"{pair['id']}-{variant['id']}"
        specs = [{**event, **overrides.get(index, {})} for index, event in enumerate(pair["events"])]
        events = events_for({"id": case_id, "events": specs})
        per_output = [event.event_id for event in events if event.event_type == EventType.TOOL_OUTPUT
                      and classify(event.output_preview) == "SUSPICIOUS"]
        cases.append({
            "id": case_id, "variant": variant["id"], "expected": variant["expected"],
            "events": [event.model_dump(mode="json") for event in events],
            "single_output": {"alert": bool(per_output), "flagged_event_ids": per_output},
            "full_graph": graph_result(events, enrich=True),
        })
    return {"id": pair["id"], "title": pair["title"], "change": pair["change"], "cases": cases}


def main():
    os.environ["CTG_SEMANTIC_MODE"] = "heuristic"
    raw = MANIFEST.read_bytes()
    pairs = [evaluate_pair(pair) for pair in yaml.safe_load(raw)["pairs"]]
    cases = [case for pair in pairs for case in pair["cases"]]
    summary = {}
    for method in ("single_output", "full_graph"):
        positives = [case for case in cases if case["expected"]["alert"]]
        controls = [case for case in cases if not case["expected"]["alert"]]
        summary[method] = {"detections": sum(case[method]["alert"] for case in positives),
                           "positive_cases": len(positives),
                           "false_alerts": sum(case[method]["alert"] for case in controls),
                           "control_cases": len(controls)}
    report = {"schema_version": 1, "dataset": "matched_synthetic_replay_v1",
              "semantic_mode": "heuristic", "manifest_sha256": hashlib.sha256(raw).hexdigest(),
              "summary": summary, "pairs": pairs}
    path = ROOT / "dashboard/public/data/matched-comparison-v1.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
