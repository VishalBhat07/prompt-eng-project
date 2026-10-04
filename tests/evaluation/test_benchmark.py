"""Task 9 RED: benchmark cases, metrics, cross-tool gain, composition."""

from crosstoolguard.evaluation.benchmark import BENCH_CATEGORIES, load_benchmark, run_case


def test_benchmark_covers_all_categories():
    cases = load_benchmark()
    assert set(BENCH_CATEGORIES) <= {c["category"] for c in cases}
    for c in cases:
        assert {"id", "category", "kind", "expected"} <= set(c.keys())


def test_exfil_benchmark_case_blocked():
    result = run_case("C-exfil-basic")
    assert result["verdict"] == "BLOCK"
    assert "secret_exfiltration" in result["patterns"]


def test_distributed_instruction_composes_to_finding():
    result = run_case("F-distributed-basic")
    assert "poisoned_instruction_chain" in result["patterns"]


def test_benign_cases_have_no_findings():
    from crosstoolguard.evaluation.benchmark import BENIGN_IDS

    for cid in BENIGN_IDS:
        result = run_case(cid)
        assert result["patterns"] == [], cid


def test_metrics_detection_rate_and_gain():
    from crosstoolguard.evaluation.metrics import cross_tool_gain, detection_rate

    results = [
        {"id": "a", "expected_findings": ["x"], "patterns": ["x"]},
        {"id": "b", "expected_findings": ["y"], "patterns": []},
    ]
    assert detection_rate(results) == 0.5
    single = {"a": True, "b": False}
    cross = {"a": True, "b": True}
    assert cross_tool_gain(single, cross) == ["b"]


def test_path_accuracy_counts_tools():
    from crosstoolguard.evaluation.metrics import path_accuracy

    assert path_accuracy(["a", "b", "c"], ["a", "b", "c"]) == (1.0, 1.0)
    p, r = path_accuracy(["a", "x"], ["a", "b", "c"])
    assert p == 0.5 and abs(r - 1 / 3) < 1e-9
