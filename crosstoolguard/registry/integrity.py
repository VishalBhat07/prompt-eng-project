"""Tool integrity - content hashes that catch rug pulls.

A tool that changes description/schema after approval is re-analyzed
instead of trusted (threat-model §2, plan G-attack E).
"""

from __future__ import annotations

import hashlib
import json


def fingerprint(payload: object) -> str:
    """Stable SHA-256 over any JSON-serializable payload."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def changed(old_hash: str, new_hash: str) -> bool:
    return old_hash != new_hash
