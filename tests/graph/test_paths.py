"""Task 5 RED: exfil path detection, session isolation, benign, order."""

from datetime import datetime, timezone

from crosstoolguard.gateway.schemas import DataClass, Event, EventType


def _evt(eid, session, server, tool, etype, data_class=DataClass.PUBLIC, parent=None):
    return Event(event_id=eid, timestamp=datetime.now(timezone.utc), session_id=session,
                 server=server, tool=tool, event_type=etype,
                 data_class=data_class, args_hash="h", parent_id=parent)


def _exfil_events(session="S1"):
    return [
        _evt("e1", session, "filesystem-mcp", "read_file", EventType.TOOL_OUTPUT, DataClass.SECRET),
        _evt("e2", session, "storage-mcp", "store_file", EventType.TOOL_CALL, parent="e1"),
        _evt("e3", session, "storage-mcp", "upload_file", EventType.TOOL_CALL, parent="e2"),
    ]


def test_exfil_path_detected():
    from crosstoolguard.graph.builder import build
    from crosstoolguard.graph.paths import find_paths, tool_sequence

    g = build(_exfil_events())
    paths = find_paths(g, source_class="SECRET", dest_cap="EXTERNAL_TRANSFER")
    assert len(paths) == 1
    assert tool_sequence(g, paths[0]) == ["read_file", "store_file", "upload_file"]


def test_mixed_sessions_rejected():
    from crosstoolguard.graph.builder import build

    try:
        build(_exfil_events("S1") + _exfil_events("S2"))
    except ValueError:
        return
    raise AssertionError("mixed sessions accepted")


def test_benign_events_yield_no_secret_path():
    from crosstoolguard.graph.builder import build
    from crosstoolguard.graph.paths import find_paths

    events = [
        _evt("e1", "S9", "filesystem-mcp", "read_file", EventType.TOOL_OUTPUT),
        _evt("e2", "S9", "search-mcp", "search", EventType.TOOL_CALL, parent="e1"),
    ]
    assert find_paths(build(events), source_class="SECRET", dest_cap="EXTERNAL_TRANSFER") == []


def test_reversed_order_yields_no_path():
    from crosstoolguard.graph.builder import build
    from crosstoolguard.graph.paths import find_paths

    events = [
        _evt("e1", "S7", "storage-mcp", "upload_file", EventType.TOOL_CALL),
        _evt("e2", "S7", "filesystem-mcp", "read_file", EventType.TOOL_OUTPUT, DataClass.SECRET, parent="e1"),
    ]
    assert find_paths(build(events), source_class="SECRET", dest_cap="EXTERNAL_TRANSFER") == []
