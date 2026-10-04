"""Policy engine - findings → verdict with deny-override (plan G7).

Severity order: BLOCK > APPROVAL > QUARANTINE > MONITOR > ALLOW.
No findings → ALLOW. QUARANTINE degrades to APPROVAL at the proxy
(no quarantine store exists yet - Task 8 dashboard flow).
"""

from __future__ import annotations

from crosstoolguard.detection.correlation import analyze_with_graph
from crosstoolguard.gateway.schemas import Event, Verdict
from crosstoolguard.policy.evaluator import finding_signals
from crosstoolguard.policy.rules import load_policies, policy_triggers

_ORDER = [Verdict.ALLOW, Verdict.MONITOR, Verdict.QUARANTINE, Verdict.APPROVAL, Verdict.BLOCK]


def decide(actions: list[str]) -> Verdict:
    """Deny-override across action names; empty → ALLOW."""
    verdicts = [Verdict(a) for a in actions] or [Verdict.ALLOW]
    return max(verdicts, key=_ORDER.index)


def decide_for_session(events: list[Event]) -> Verdict:
    """Correlate a session's events and return the enforced verdict."""
    graph, findings = analyze_with_graph(events)
    return decide([action for _, action in reasons_for(graph, findings)])


def reasons_for(graph, findings: list) -> list[tuple[str, str]]:
    """Aligned (policy_name, action) per finding; default-allow when clean."""
    reasons: list[tuple[str, str]] = []
    for f in findings:
        sig = finding_signals(graph, f)
        hits = [(p.name, p.action) for p in load_policies() if policy_triggers(p, sig)]
        hits.sort(key=lambda h: _ORDER.index(Verdict(h[1])), reverse=True)
        reasons.append(hits[0] if hits else ("allow-by-default", "ALLOW"))
    return reasons
