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
  definition_json TEXT NOT NULL DEFAULT '{}',
  description_hash TEXT NOT NULL,
  schema_hash TEXT NOT NULL,
  definition_hash TEXT NOT NULL DEFAULT '',
  capabilities TEXT NOT NULL,
  version INTEGER NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  integrity_status TEXT NOT NULL DEFAULT 'OK'
)
"""

_SERVER_SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_servers(
  server_id TEXT PRIMARY KEY,
  transport TEXT NOT NULL,
  server_info_json TEXT,
  protocol_version TEXT,
  instructions TEXT,
  capabilities_json TEXT NOT NULL,
  inventory_hash TEXT NOT NULL,
  integrity_status TEXT NOT NULL DEFAULT 'OK',
  assessment_json TEXT,
  endpoint_url TEXT,
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
    integrity_status: str  # NEW | OK | MODIFIED | APPROVED | REMOVED
    description_hash: str
    schema_hash: str
    definition_hash: str = ""


@dataclass
class ServerRecord:
    server_id: str
    transport: str
    version: int
    integrity_status: str
    inventory_hash: str


class ToolRegistry:
    def __init__(self, path: str = "registry.db") -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(_SCHEMA)
        self._db.execute(_SERVER_SCHEMA)
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(tools)")}
        if "definition_json" not in columns:
            self._db.execute("ALTER TABLE tools ADD COLUMN definition_json TEXT NOT NULL DEFAULT '{}'")
        if "definition_hash" not in columns:
            self._db.execute("ALTER TABLE tools ADD COLUMN definition_hash TEXT NOT NULL DEFAULT ''")
        if "active" not in columns:
            self._db.execute("ALTER TABLE tools ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        if "integrity_status" not in columns:
            self._db.execute("ALTER TABLE tools ADD COLUMN integrity_status TEXT NOT NULL DEFAULT 'OK'")
        server_columns = {row[1] for row in self._db.execute("PRAGMA table_info(mcp_servers)")}
        if "integrity_status" not in server_columns:
            self._db.execute("ALTER TABLE mcp_servers ADD COLUMN integrity_status TEXT NOT NULL DEFAULT 'OK'")
        if "assessment_json" not in server_columns:
            self._db.execute("ALTER TABLE mcp_servers ADD COLUMN assessment_json TEXT")
        if "endpoint_url" not in server_columns:
            self._db.execute("ALTER TABLE mcp_servers ADD COLUMN endpoint_url TEXT")
        self._db.commit()

    def register_server_inventory(self, inventory: dict) -> ServerRecord:
        """Persist server metadata and its inventory snapshot before tool rows."""
        server_id = str(inventory["server_id"])
        transport = str(inventory["transport"])
        endpoint_url = inventory.get("endpoint_url")
        definitions = inventory.get("tools", [])
        if not isinstance(definitions, list) or any(not isinstance(tool, dict) for tool in definitions):
            raise ValueError("inventory tools must be a list of tool-definition objects")
        names = [str(tool.get("name", "")).strip() for tool in definitions]
        if any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError("inventory contains a missing or duplicate tool name")
        for definition in definitions:
            json.dumps(definition, sort_keys=True, default=str)
        info = inventory.get("server_info")
        capabilities = inventory.get("capabilities") or {}
        snapshot = {
            "transport": transport,
            "server_info": info,
            "protocol_version": inventory.get("protocol_version"),
            "instructions": inventory.get("instructions"),
            "capabilities": capabilities,
            "tools": sorted(definitions, key=lambda item: str(item.get("name", ""))),
        }
        if endpoint_url:
            snapshot["endpoint_url"] = endpoint_url
        digest = fingerprint(snapshot)
        now = datetime.now(timezone.utc).isoformat()
        row = self._db.execute(
            "SELECT inventory_hash,version,integrity_status FROM mcp_servers WHERE server_id=?", (server_id,)
        ).fetchone()
        info_json = json.dumps(info, sort_keys=True, default=str) if info is not None else None
        caps_json = json.dumps(capabilities, sort_keys=True, default=str)
        if row is None:
            version, status = 1, "NEW"
            self._db.execute(
                "INSERT INTO mcp_servers (server_id,transport,server_info_json,protocol_version,instructions,"
                "capabilities_json,inventory_hash,integrity_status,endpoint_url,version,first_seen,last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (server_id, transport, info_json, inventory.get("protocol_version"),
                 inventory.get("instructions"), caps_json, digest, status, endpoint_url, version, now, now),
            )
        elif row[0] != digest:
            version, status = row[1] + 1, "MODIFIED"
            self._db.execute(
                "UPDATE mcp_servers SET transport=?,server_info_json=?,protocol_version=?,instructions=?,"
                "capabilities_json=?,inventory_hash=?,integrity_status=?,assessment_json=NULL,endpoint_url=?,version=?,last_seen=? "
                "WHERE server_id=?",
                (transport, info_json, inventory.get("protocol_version"), inventory.get("instructions"),
                 caps_json, digest, status, endpoint_url, version, now, server_id),
            )
        else:
            version, status = row[1], row[2]
            self._db.execute("UPDATE mcp_servers SET last_seen=?,endpoint_url=? WHERE server_id=?",
                             (now, endpoint_url, server_id))
        self._db.execute("UPDATE tools SET active=0 WHERE server=?", (server_id,))
        for tool in definitions:
            self.register_definition(server=server_id, definition=tool, preserve_status=True)
        self._db.execute(
            "UPDATE tools SET integrity_status='REMOVED' WHERE server=? AND active=0", (server_id,)
        )
        self._db.commit()
        return ServerRecord(server_id, transport, version, status, digest)

    def approve_server_inventory(self, server_id: str, expected_hash: str) -> bool:
        """Pin the exact currently stored snapshot after explicit operator review."""
        cursor = self._db.execute(
            "UPDATE mcp_servers SET integrity_status='APPROVED' "
            "WHERE server_id=? AND inventory_hash=?", (server_id, expected_hash)
        )
        if cursor.rowcount != 1:
            self._db.rollback()
            return False
        self._db.execute(
            "UPDATE tools SET integrity_status='APPROVED' WHERE server=? AND active=1", (server_id,)
        )
        self._db.commit()
        return True

    def revoke_server_inventory(self, server_id: str, *, expected_hash: str | None = None) -> bool:
        """Return a previously approved snapshot to review-required state.

        Use this when an operator finds a server unusable or no longer wants it
        in the autonomous tool catalog. The inventory itself is kept for audit.
        """
        query = "UPDATE mcp_servers SET integrity_status='NEW' WHERE server_id=? AND integrity_status='APPROVED'"
        cursor = (self._db.execute(query, (server_id,)) if expected_hash is None
                  else self._db.execute(query + " AND inventory_hash=?", (server_id, expected_hash)))
        if cursor.rowcount != 1:
            self._db.rollback()
            return False
        self._db.execute(
            "UPDATE tools SET integrity_status='NEW' WHERE server=? AND active=1", (server_id,)
        )
        self._db.commit()
        return True

    def get_server_inventory(self, server_id: str) -> dict | None:
        row = self._db.execute(
            "SELECT transport,server_info_json,protocol_version,instructions,capabilities_json,"
            "inventory_hash,version,integrity_status,assessment_json,endpoint_url,first_seen,last_seen "
            "FROM mcp_servers WHERE server_id=?", (server_id,)
        ).fetchone()
        if row is None:
            return None
        tool_rows = self._db.execute(
            "SELECT definition_json,version,description_hash,schema_hash,definition_hash,capabilities,integrity_status "
            "FROM tools WHERE server=? AND active=1 ORDER BY name", (server_id,)
        ).fetchall()
        removed_rows = self._db.execute(
            "SELECT name,version,definition_hash FROM tools WHERE server=? AND active=0 ORDER BY name", (server_id,)
        ).fetchall()
        return {
            "server_id": server_id,
            "transport": row[0],
            "server_info": json.loads(row[1]) if row[1] else None,
            "protocol_version": row[2],
            "instructions": row[3],
            "capabilities": json.loads(row[4]),
            "inventory_hash": row[5],
            "version": row[6],
            "integrity_status": row[7],
            "assessment": json.loads(row[8]) if row[8] else None,
            "endpoint_url": row[9],
            "first_seen": row[10],
            "last_seen": row[11],
            "tools": [
                {**json.loads(item[0]), "_registry": {
                    "version": item[1], "description_hash": item[2], "schema_hash": item[3],
                    "definition_hash": item[4], "capabilities": json.loads(item[5]),
                    "integrity_status": item[6],
                }} for item in tool_rows
            ],
            "removed_tools": [
                {"name": item[0], "version": item[1], "definition_hash": item[2], "integrity_status": "REMOVED"}
                for item in removed_rows
            ],
        }

    def save_assessment(self, server_id: str, report: dict) -> None:
        self._db.execute("UPDATE mcp_servers SET assessment_json=? WHERE server_id=?",
                         (json.dumps(report, sort_keys=True, default=str), server_id))
        self._db.commit()

    def list_server_inventories(self) -> list[dict]:
        ids = self._db.execute("SELECT server_id FROM mcp_servers ORDER BY server_id").fetchall()
        return [record for server_id, in ids if (record := self.get_server_inventory(server_id)) is not None]

    def register(self, *, server: str, tool: str, description: str, schema: dict) -> ToolRecord:
        return self.register_definition(server=server, definition={
            "name": tool, "description": description, "inputSchema": schema,
        })

    def register_definition(self, *, server: str, definition: dict,
                            preserve_status: bool = False) -> ToolRecord:
        """Register the complete server-advertised definition and detect changes."""
        tool = str(definition.get("name", "")).strip()
        if not tool:
            raise ValueError("MCP tool definition is missing a name")
        description = str(definition.get("description") or "")
        schema = {
            "inputSchema": definition.get("inputSchema", definition.get("input_schema", {})),
            "outputSchema": definition.get("outputSchema", definition.get("output_schema")),
            "annotations": definition.get("annotations"),
        }
        tool_id = f"{server}/{tool}"
        desc_hash = fingerprint(description)
        schema_hash = fingerprint(schema)
        definition_hash = fingerprint(definition)
        definition_json = json.dumps(definition, sort_keys=True, default=str)
        now = datetime.now(timezone.utc).isoformat()
        row = self._db.execute(
            "SELECT description_hash, schema_hash, definition_hash, version, capabilities,integrity_status "
            "FROM tools WHERE tool_id = ?", (tool_id,)).fetchone()
        if row is None:
            caps = sorted(extract_capabilities(tool, description))
            self._db.execute(
                "INSERT INTO tools (tool_id,server,name,description,schema_json,definition_json,"
                "description_hash,schema_hash,definition_hash,capabilities,version,first_seen,last_seen,active,integrity_status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,'NEW')",
                (tool_id, server, tool, description, json.dumps(schema), definition_json,
                 desc_hash, schema_hash, definition_hash, json.dumps(caps), 1, now, now),
            )
            self._db.commit()
            return ToolRecord(tool_id, server, tool, set(caps), 1, "NEW", desc_hash,
                              schema_hash, definition_hash)
        old_desc, old_schema, old_definition, version, old_caps, old_status = row
        if changed(old_desc, desc_hash) or changed(old_schema, schema_hash) or changed(old_definition, definition_hash):
            caps = sorted(extract_capabilities(tool, description))
            self._db.execute(
                "UPDATE tools SET description=?, schema_json=?, definition_json=?, description_hash=?,"
                " schema_hash=?, definition_hash=?, capabilities=?, version=?, last_seen=?,active=1,"
                "integrity_status='MODIFIED' WHERE tool_id=?",
                (description, json.dumps(schema), definition_json, desc_hash, schema_hash,
                 definition_hash,
                 json.dumps(caps), version + 1, now, tool_id),
            )
            self._db.commit()
            return ToolRecord(tool_id, server, tool, set(caps), version + 1, "MODIFIED",
                              desc_hash, schema_hash, definition_hash)
        if preserve_status and old_status in {"NEW", "MODIFIED", "APPROVED"}:
            status = old_status
        elif preserve_status and old_status == "REMOVED":
            status = "MODIFIED"
        else:
            status = "OK"
        self._db.execute("UPDATE tools SET last_seen=?,active=1,integrity_status=? WHERE tool_id=?",
                         (now, status, tool_id))
        self._db.commit()
        return ToolRecord(tool_id, server, tool, set(json.loads(old_caps)), version, status,
                          desc_hash, schema_hash, definition_hash)

    def get(self, server: str, tool: str) -> ToolRecord | None:
        row = self._db.execute(
            "SELECT tool_id,server,name,capabilities,version,description_hash,schema_hash,definition_hash "
            "FROM tools WHERE tool_id = ? AND active=1", (f"{server}/{tool}",)).fetchone()
        if row is None:
            return None
        return ToolRecord(row[0], row[1], row[2], set(json.loads(row[3])), row[4], "OK",
                          row[5], row[6], row[7])

    def close(self) -> None:
        self._db.close()


def seed_from_transport(reg: ToolRegistry) -> list[ToolRecord]:
    """Register every tool the lab transport exposes (dev/bootstrap seed)."""
    from crosstoolguard.gateway.transport import list_tools

    return [
        reg.register(server=t["server"], tool=t["tool"], description=t["description"], schema={})
        for t in list_tools()
    ]
