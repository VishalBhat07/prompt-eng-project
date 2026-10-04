"""Session management — one isolated id per agent run.

Every event/graph node carries session_id; no edges ever cross sessions
(threat-model §4, plan G6). Stub grows into auth-aware sessions in Task 7+.
"""

from __future__ import annotations

import uuid


def ensure_session(provided: str | None) -> str:
    """Return the provided id, or mint `S-<8 hex>` when absent/blank."""
    if provided and provided.strip():
        return provided.strip()
    return f"S-{uuid.uuid4().hex[:8]}"
