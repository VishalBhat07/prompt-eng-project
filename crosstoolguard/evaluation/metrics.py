"""Evaluation metrics — pure functions over benchmark results (doc §49–53)."""

from __future__ import annotations


def detection_rate(results: list[dict]) -> float:
    """Fraction of attack cases (non-empty expected findings) detected."""
    attacks = [r for r in results if r.get("expected_findings")]
    if not attacks:
        return 0.0
    hits = sum(1 for r in attacks if set(r["patterns"]) & set(r["expected_findings"]))
    return hits / len(attacks)


def false_positive_rate(results: list[dict]) -> float:
    """Fraction of benign cases (empty expected findings) flagged."""
    benign = [r for r in results if "expected_findings" in r and not r["expected_findings"]]
    if not benign:
        return 0.0
    flagged = sum(1 for r in benign if r["patterns"])
    return flagged / len(benign)


def cross_tool_gain(single: dict[str, bool], cross: dict[str, bool]) -> list[str]:
    """Case ids caught ONLY via multi-tool correlation (the thesis metric)."""
    return [cid for cid, hit in cross.items() if hit and not single.get(cid, False)]


def path_accuracy(predicted: list[str], truth: list[str]) -> tuple[float, float]:
    """(precision, recall) over tool names in predicted vs ground-truth chain."""
    if not predicted:
        return (0.0, 0.0 if truth else 1.0)
    hits = len(set(predicted) & set(truth))
    return (hits / len(predicted), hits / len(truth) if truth else 1.0)
