"""Validate checkpoint 3 artifacts and write a compact results bundle."""

from collections import Counter
import argparse
import hashlib
from importlib.metadata import version
import json
import random
from statistics import mean, median

from run_replay_evaluation import ROOT, percentile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-dashboard", action="store_true", help="Copy aggregate counts to the dashboard.")
    args = parser.parse_args()
    directory = ROOT / "data/evaluation"
    replay_path = directory / "replay-v1.json"
    benign_path = directory / "benign-v1.json"
    replay = json.loads(replay_path.read_bytes())
    benign = json.loads(benign_path.read_bytes())
    trials_path = directory / benign["results"]
    trials = [json.loads(row) for row in trials_path.read_text(encoding="utf-8").splitlines()]
    assert len(replay["cases"]) == len({row["id"] for row in replay["cases"]}) == 24
    assert len(trials) == benign["scheduled_runs"] == 48
    tasks = sorted({row["group"] for row in trials})
    repeats = {1, 2, 3}
    conditions = ("automatic", "explicit_scope")
    assert len(tasks) == 8
    assert Counter((row["group"], row["condition"], row["repeat"]) for row in trials) == Counter(
        (task, condition, repeat) for task in tasks for condition in conditions for repeat in repeats)
    for name, digest in replay["input_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    task_manifest = ROOT / "crosstoolguard/evaluation/data/BENIGN_TASKS_V1.yaml"
    assert hashlib.sha256(task_manifest.read_bytes()).hexdigest() == benign["task_sha256"]

    completed = {(row["group"], row["condition"], row["repeat"]): row["completed"] for row in trials}
    differences = [
        mean(completed[task, "automatic", repeat] - completed[task, "explicit_scope", repeat] for repeat in repeats)
        for task in tasks
    ]
    rng = random.Random(benign["seed"])
    draws = [mean(rng.choices(differences, k=len(differences))) for _ in range(2000)]
    results = {
        "schema_version": 1,
        "datasets": {"replay": replay["dataset"], "benign": benign["dataset"]},
        "model": {"provider": benign["provider"], "model": benign["model"]},
        "replay": replay["summary"],
        "benign": benign["summary"],
        "paired_completion_difference": {
            "automatic_minus_explicit": mean(differences),
            "bootstrap_95": [percentile(draws, .025), percentile(draws, .975)],
            "task_clusters": len(tasks),
        },
        "trial_wall_time_ms": {},
        "completion_by_task": {},
        "dependency_versions": {name: version(name) for name in ("fastapi", "groq", "httpx", "mcp", "networkx", "pydantic", "PyYAML")},
        "report_sha256": {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                          for file in (replay_path, benign_path, trials_path)},
    }
    for condition in conditions:
        outcomes = [row for row in trials if row["condition"] == condition]
        observed = [row["elapsed_ms"] for row in outcomes if "elapsed_ms" in row]
        results["trial_wall_time_ms"][condition] = {
            "median": median(observed) if observed else None,
            "p95": percentile(observed, .95), "n": len(observed),
        }
        assert results["benign"][condition]["completion"]["numerator"] == sum(row["completed"] for row in outcomes)
    for task in tasks:
        results["completion_by_task"][task] = {
            condition: {
                "completed": sum(completed[task, condition, repeat] for repeat in repeats),
                "scheduled": len(repeats),
                "infrastructure_errors": sum(bool(row.get("error")) for row in trials
                                             if row["group"] == task and row["condition"] == condition),
            }
            for condition in conditions
        }
    output = directory / "checkpoint-3-results.json"
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    if args.publish_dashboard:
        public = {key: results[key] for key in ("schema_version", "datasets", "model", "replay",
                                               "benign", "trial_wall_time_ms")}
        target = ROOT / "dashboard/public/data/evaluation-results-v1.json"
        target.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    print(f"Validated 24 replay rows and 48 scheduled trial rows. Wrote {output}.")


if __name__ == "__main__":
    main()
