"""Provenance tracker — facade over classification + lineage.

Every tool call/output becomes a normalized Event (hashes + redacted
previews only) linked into a per-session origin chain.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from crosstoolguard.gateway.schemas import DataClass, Event, EventType, Trust
from crosstoolguard.provenance.events import classify_content, hash_arguments, redact
from crosstoolguard.provenance.lineage import LineageStore
from crosstoolguard.registry.capabilities import sensitivity_for_path


class ProvenanceTracker:
    def __init__(self, path: str = "lineage.db") -> None:
        self.store = LineageStore(path)

    def _register(self, event: Event, origin: str, parent_id: str | None) -> Event:
        self.store.add(event_id=event.event_id, session_id=event.session_id,
                       origin=origin, parent_id=parent_id)
        return event

    def record_call(self, *, session_id: str, server: str, tool: str,
                    arguments: dict, trust: str = "MED") -> Event:
        origin = f"{server}.{tool}"
        data_class = DataClass.PUBLIC
        for value in arguments.values():
            if sensitivity_for_path(str(value)) == "SECRET":
                data_class = DataClass.SECRET
                break
        return self._register(
            Event(event_id=f"e-{uuid.uuid4().hex[:8]}", timestamp=datetime.now(timezone.utc),
                  session_id=session_id, server=server, tool=tool,
                  event_type=EventType.TOOL_CALL, trust=Trust(trust),
                  data_class=data_class, args_hash=hash_arguments(arguments)),
            origin, parent_id=None)

    def record_output(self, *, session_id: str, server: str, tool: str, content: str,
                      trust: str = "LOW", parent_id: str | None = None) -> Event:
        origin = f"{server}.{tool}"
        data_class = DataClass(classify_content(content))
        return self._register(
            Event(event_id=f"e-{uuid.uuid4().hex[:8]}", timestamp=datetime.now(timezone.utc),
                  session_id=session_id, server=server, tool=tool,
                  event_type=EventType.TOOL_OUTPUT, trust=Trust(trust),
                  data_class=data_class, output_preview=redact(content)[:500]),
            origin, parent_id=parent_id)

    def original_source(self, event_id: str) -> str:
        return self.store.original_source(event_id)
