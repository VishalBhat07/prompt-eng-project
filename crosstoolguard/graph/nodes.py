"""Graph node types (doc §19). All edges point forward in time."""

from enum import Enum


class NodeType(str, Enum):
    TOOL = "TOOL"
    SERVER = "SERVER"
    INSTRUCTION = "INSTRUCTION"
    DATA = "DATA"
    DESTINATION = "DESTINATION"
    DECISION = "DECISION"
    CAPABILITY = "CAPABILITY"
