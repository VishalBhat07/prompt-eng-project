"""Trace builders — deterministic synthetic event chains (no live LLM needed)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from crosstoolguard.gateway.schemas import DataClass, Event, EventType

PUBLIC = DataClass.PUBLIC
SECRET = DataClass.SECRET
CREDENTIAL = DataClass.CREDENTIAL


class Trace:
    """Auto-timestamps events in order (builder sorts by time)."""

    def __init__(self, session: str) -> None:
        self.session = session
        self.events: list[Event] = []
        self.tick = datetime.now(timezone.utc)

    def _next(self) -> datetime:
        self.tick += timedelta(seconds=1)
        return self.tick

    def call(self, eid: str, server: str, tool: str, parent: str | None = None) -> Event:
        e = Event(event_id=eid, timestamp=self._next(), session_id=self.session,
                  server=server, tool=tool, event_type=EventType.TOOL_CALL,
                  args_hash="h", parent_id=parent)
        self.events.append(e)
        return e

    def out(self, eid: str, server: str, tool: str, data_class: DataClass = PUBLIC,
            preview: str = "", parent: str | None = None) -> Event:
        e = Event(event_id=eid, timestamp=self._next(), session_id=self.session,
                  server=server, tool=tool, event_type=EventType.TOOL_OUTPUT,
                  data_class=data_class, args_hash="h", parent_id=parent,
                  output_preview=preview)
        self.events.append(e)
        return e
