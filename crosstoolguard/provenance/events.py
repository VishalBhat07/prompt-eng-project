"""Event normalization — classification, redaction, hashing (plan G5/G9).

Layer 1 sieve (regex + entropy). No ML here; embeddings/LLM-judge arrive
in Task 4. Raw secrets are NEVER stored: previews are redacted, arguments
are hashed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter

# (pattern, data_class) — first match wins.
SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"AKIA[0-9A-Z]{16}", "CREDENTIAL"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "CREDENTIAL"),
    (r"(?i)\b(api[_-]?key|password|passwd|secret)\b\s*[:=]\s*\S+", "SECRET"),
    (r"\.env\b", "SECRET"),
    (r"id_rsa", "SECRET"),
]

_ENTROPY_THRESHOLD = 4.5
_ENTROPY_MIN_LEN = 40


def shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def classify_content(text: str) -> str:
    """PUBLIC | SECRET | CREDENTIAL for a tool-output string."""
    for pattern, data_class in SECRET_PATTERNS:
        if re.search(pattern, text):
            return data_class
    stripped = re.sub(r"\s+", "", text)
    if len(stripped) >= _ENTROPY_MIN_LEN and shannon_entropy(stripped) > _ENTROPY_THRESHOLD:
        return "SECRET"
    return "PUBLIC"


def redact(text: str) -> str:
    """Replace secret-shaped spans with [REDACTED]; safe for logs/UI."""
    redacted = text
    for pattern, _ in SECRET_PATTERNS:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted


def hash_arguments(arguments: dict) -> str:
    return hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()
