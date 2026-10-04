"""Lineage store — parent-linked events with session isolation.

`original_source()` walks to the chain root, so laundered content
(summarized, reformatted, re-stored) still points at the true origin.
Parents from another session are rejected: no cross-session edges (G6).
"""

from __future__ import annotations

import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lineage(
  event_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  origin TEXT NOT NULL,
  parent_id TEXT
)
"""


class LineageStore:
    def __init__(self, path: str = "lineage.db") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def add(self, *, event_id: str, session_id: str, origin: str, parent_id: str | None = None) -> None:
        if parent_id is not None:
            row = self._db.execute(
                "SELECT session_id FROM lineage WHERE event_id = ?", (parent_id,)).fetchone()
            if row is None:
                raise ValueError(f"unknown parent: {parent_id}")
            if row[0] != session_id:
                raise ValueError(f"parent {parent_id} belongs to another session")
        self._db.execute(
            "INSERT INTO lineage VALUES (?,?,?,?)", (event_id, session_id, origin, parent_id))
        self._db.commit()

    def chain(self, event_id: str) -> list[str]:
        """Origin chain root-first, e.g. [read, summarize, store]."""
        origins: list[str] = []
        current: str | None = event_id
        while current is not None:
            row = self._db.execute(
                "SELECT origin, parent_id FROM lineage WHERE event_id = ?", (current,)).fetchone()
            if row is None:
                raise ValueError(f"unknown event: {current}")
            origins.append(row[0])
            current = row[1]
        return origins[::-1]

    def original_source(self, event_id: str) -> str:
        return self.chain(event_id)[0]
