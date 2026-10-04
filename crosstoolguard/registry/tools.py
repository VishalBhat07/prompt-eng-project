"""Tool registry - identity, capabilities, and rug-pull detection.

Each tool is keyed `server/name` with content hashes. Re-registering an
unchanged tool → OK; changed description/schema → MODIFIED + version bump
so the tool is sent for reanalysis (integrity.py).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from crosstoolguard.registry.capabilities import extract_capabilities
from crosstoolguard.registry.integrity import changed, fingerprint

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tools(
  tool_id TEXT PRIMARY KEY,
  server TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  schema_json TEXT NOT NULL,
  description_hash TEXT NOT NULL,
  schema_hash TEXT NOT NULL,
  capabilities TEXT NOT NULL,
  version INTEGER NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL
)
"""


@dataclass
class ToolRecord:
    tool_id: str
    server: str
    name: str
    capabilities: set[str]
    version: int
    integrity_status: str  # NEW | OK | MODIFIED
    description_hash: str
    schema_hash: str


class ToolRegistry:
    def __init__(self, path: str = "registry.db") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def register(self, *, server: str, tool: str, description: str, schema: dict) -> ToolRecord:
        tool_id = f"{server}/{tool}"
        desc_hash = fingerprint(description)
        schema_hash = fingerprint(schema)
        now = datetime.now(timezone.utc).isoformat()
        row = self._db.execute("SELECT * FROM tools WHERE tool_id = ?", (tool_id,)).fetchone()
        if row is None:
            caps = sorted(extract_capabilities(tool, description))
            self._db.execute(
                "INSERT INTO tools VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (tool_id, server, tool, description, json.dumps(schema), desc_hash, schema_hash,
                 json.dumps(caps), 1, now, now),
            )
            self._db.commit()
            return ToolRecord(tool_id, server, tool, set(caps), 1, "NEW", desc_hash, schema_hash)
        (_id, _srv, _name, _desc, _sch, old_desc, old_sch, _caps, version, first_seen, _last) = row
        if changed(old_desc, desc_hash) or changed(old_sch, schema_hash):
            caps = sorted(extract_capabilities(tool, description))
            self._db.execute(
                "UPDATE tools SET description=?, schema_json=?, description_hash=?,"
                " schema_hash=?, capabilities=?, version=?, last_seen=? WHERE tool_id=?",
                (description, json.dumps(schema), desc_hash, schema_hash,
                 json.dumps(caps), version + 1, now, tool_id),
            )
            self._db.commit()
            return ToolRecord(tool_id, server, tool, set(caps), version + 1, "MODIFIED", desc_hash, schema_hash)
        self._db.execute("UPDATE tools SET last_seen=? WHERE tool_id=?", (now, tool_id))
        self._db.commit()
        return ToolRecord(tool_id, server, tool, set(json.loads(row[7])), version, "OK", desc_hash, schema_hash)

    def get(self, server: str, tool: str) -> ToolRecord | None:
        row = self._db.execute(
            "SELECT * FROM tools WHERE tool_id = ?", (f"{server}/{tool}",)).fetchone()
        if row is None:
            return None
        return ToolRecord(row[0], row[1], row[2], set(json.loads(row[7])), row[8], "OK", row[5], row[6])


def seed_from_transport(reg: ToolRegistry) -> list[ToolRecord]:
    """Register every tool the lab transport exposes (dev/bootstrap seed)."""
    from crosstoolguard.gateway.transport import list_tools

    return [
        reg.register(server=t["server"], tool=t["tool"], description=t["description"], schema={})
        for t in list_tools()
    ]
