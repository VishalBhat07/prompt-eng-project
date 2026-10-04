"""Task 10 RED: baselines, ablation ladder, latency budget."""

from crosstoolguard.evaluation.benchmark import BENIGN_IDS, load_benchmark


def _attack_ids():
    return [c["id"] for c in load_benchmark()
            if c["kind"] == "detection" and c["expected"].get("patterns")]


def test_baseline_coverage_ordered():
    from crosstoolguard.evaluation.experiments import run_baselines

    cov = run_baselines()
    assert cov["A-no-security"] == set()
    assert cov["C-keyword"] <= cov["E-full"]
    assert cov["B-single-tool"] <= cov["E-full"]


def test_ablation_proves_enrichment_matters():
    from crosstoolguard.evaluation.experiments import run_ablation

    table = run_ablation()
    assert set(table["D-graph-no-enrich"]) < set(table["E-full"])
    assert "F-distributed-basic" in set(table["E-full"]) - set(table["D-graph-no-enrich"])


def test_latency_budget_reported():
    from crosstoolguard.evaluation.experiments import measure_latency

    lat = measure_latency()
    assert set(lat) == set(_attack_ids()) | set(BENIGN_IDS)
    assert all(v >= 0 for v in lat.values())
    p95 = sorted(lat.values())[int(0.95 * (len(lat) - 1))]
    assert p95 < 5.0
