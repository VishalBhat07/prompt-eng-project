"""Policy rules - versioned YAML policies with finding-signal matching."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass
class Policy:
    name: str
    version: int
    condition: dict
    action: str


@lru_cache(maxsize=1)
def load_policies() -> list[Policy]:
    raw = yaml.safe_load((Path(__file__).parent / "data" / "POLICIES.yaml").read_text())
    return [Policy(**p) for p in raw["policies"]]


def policy_triggers(policy: Policy, signals: dict) -> bool:
    """Every condition key must hold against the finding's signals."""
    cond = policy.condition
    if "data_involved" in cond:
        if not (set(cond["data_involved"]) & signals.get("data_classes", set())):
            return False
    if cond.get("external_sink") and "EXTERNAL_TRANSFER" not in signals.get("capabilities", set()):
        return False
    if cond.get("low_trust_instruction") and not signals.get("low_trust_instruction", False):
        return False
    if cond.get("privileged_target") and "PRIVILEGED" not in signals.get("capabilities", set()):
        return False
    if "capability_chain" in cond:
        chain = signals.get("capability_sequence", [])
        idx = 0
        for cap in chain:
            if cap == cond["capability_chain"][idx]:
                idx += 1
                if idx == len(cond["capability_chain"]):
                    break
        if idx < len(cond["capability_chain"]):
            return False
    return True
