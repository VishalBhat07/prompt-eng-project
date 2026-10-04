"""Instruction/data separation at span level.

A tool output is rarely pure: one sentence carries data, the next an
embedded instruction. Split into sentences, classify each; a span set
containing both is MIXED (the laundering-relevant case).
"""

from __future__ import annotations

import re

from crosstoolguard.analyzer.semantic import classify


def split_data_instruction(text: str) -> list[dict]:
    """Split text into sentences labeled DATA/INSTRUCTION/SUSPICIOUS."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    return [{"span": s, "label": classify(s)} for s in sentences]
