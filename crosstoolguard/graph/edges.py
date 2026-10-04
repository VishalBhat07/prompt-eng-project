"""Graph edge types (doc §19 + FLOWS_TO from the dataflow tracker §18)."""

from enum import Enum


class EdgeType(str, Enum):
    READS = "READS"
    WRITES = "WRITES"
    TRANSFORMS = "TRANSFORMS"
    SENDS = "SENDS"
    INVOKES = "INVOKES"
    INFLUENCES = "INFLUENCES"
    GENERATES = "GENERATES"
    DEPENDS_ON = "DEPENDS_ON"
    FLOWS_TO = "FLOWS_TO"
