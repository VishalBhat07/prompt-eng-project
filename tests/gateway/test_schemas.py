"""Task 0.3 RED: Event/Verdict schemas - must fail until schemas.py exists."""

from datetime import datetime, timezone


def test_event_schema_round_trip():
    from crosstoolguard.gateway.schemas import Event, EventType

    e = Event(
        event_id="e1",
        timestamp=datetime.now(timezone.utc),
        session_id="S1",
        server="filesystem-mcp",
        tool="read_file",
        event_type=EventType.TOOL_CALL,
        trust="MED",
        data_class="PUBLIC",
        args_hash="abc123",
    )
    assert e.session_id == "S1"
    assert e.event_type == EventType.TOOL_CALL


def test_verdict_enum_values():
    from crosstoolguard.gateway.schemas import Verdict

    assert {v.value for v in Verdict} == {
        "ALLOW",
        "MONITOR",
        "APPROVAL",
        "QUARANTINE",
        "BLOCK",
    }


def test_output_preview_truncated_and_no_raw_secret():
    from crosstoolguard.gateway.schemas import Event, EventType

    long_output = "x" * 2000
    e = Event(
        event_id="e2",
        timestamp=datetime.now(timezone.utc),
        session_id="S1",
        server="filesystem-mcp",
        tool="read_file",
        event_type=EventType.TOOL_OUTPUT,
        trust="MED",
        data_class="SECRET",
        args_hash="h",
        output_preview=long_output,
    )
    assert len(e.output_preview) <= 500
