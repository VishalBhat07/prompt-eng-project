"""Policy engine — findings → verdict with deny-override (plan G7).

Severity order: BLOCK > APPROVAL > QUARANTINE > MONITOR > ALLOW.
No findings → ALLOW. QUARANTINE degrades to APPROVAL at the proxy
(no quarantine store exists yet — Task 8 dashboard flow).
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
    actions = [p.action for f in findings for p in load_policies()
               if policy_triggers(p, finding_signals(graph, f))]
    return decide(actions)
