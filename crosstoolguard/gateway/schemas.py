"""Normalized MCP event schemas — proxy ↔ graph ↔ policy contract.

Global constraints enforced here:
- every event carries timestamp/session_id/server/tool/event_type/args_hash
- raw secrets never stored: only args_hash + classification + ≤500-char preview
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    MONITOR = "MONITOR"
    APPROVAL = "APPROVAL"
    QUARANTINE = "QUARANTINE"
    BLOCK = "BLOCK"


class EventType(str, Enum):
    TOOL_DISCOVERED = "TOOL_DISCOVERED"
    TOOL_CALL = "TOOL_CALL"
    TOOL_OUTPUT = "TOOL_OUTPUT"
    RESOURCE_READ = "RESOURCE_READ"
    DATA_CREATED = "DATA_CREATED"
    DATA_TRANSFORMED = "DATA_TRANSFORMED"
    DATA_SENT = "DATA_SENT"


class Trust(str, Enum):
    HIGH = "HIGH"  # user prompt / approval
    MED = "MED"  # user-owned files / DB
    LOW = "LOW"  # tool desc / output / web


class DataClass(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SECRET = "SECRET"
    CREDENTIAL = "CREDENTIAL"


class Event(BaseModel):
    event_id: str
    timestamp: datetime
    session_id: str
    server: str
    tool: str
    event_type: EventType
    trust: Trust = Trust.MED
    data_class: DataClass = DataClass.PUBLIC
    args_hash: str = ""
    output_preview: str = ""
    parent_id: str | None = None

    @field_validator("output_preview")
    @classmethod
    def _truncate_preview(cls, v: str) -> str:
        return v[:500]


class ToolCall(BaseModel):
    session_id: str
    server: str
    tool: str
    arguments: dict = Field(default_factory=dict)
