"""Task 3 RED: provenance lineage, content classifier, redaction, isolation."""

FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"


def _tracker():
    from crosstoolguard.provenance.provenance import ProvenanceTracker

    return ProvenanceTracker(":memory:")


def test_provenance_survives_summarizer():
    t = _tracker()
    e1 = t.record_output(session_id="S1", server="filesystem-mcp", tool="read_file", content="SECRET:X")
    e2 = t.record_output(session_id="S1", server="search-mcp", tool="summarize", content="summary of X", parent_id=e1.event_id)
    e3 = t.record_output(session_id="S1", server="storage-mcp", tool="store_file", content="stored summary", parent_id=e2.event_id)
    assert t.original_source(e3.event_id) == "filesystem-mcp.read_file"


def test_classifier_flags_aws_key_as_credential():
    from crosstoolguard.provenance.events import classify_content

    assert classify_content(f"key={FAKE_AWS_KEY}") == "CREDENTIAL"


def test_classifier_public_for_benign():
    from crosstoolguard.provenance.events import classify_content

    assert classify_content("Invoice total $239.00, status PAID") == "PUBLIC"


def test_preview_redacts_raw_secret():
    t = _tracker()
    e = t.record_output(session_id="S1", server="filesystem-mcp", tool="read_file", content=f"key={FAKE_AWS_KEY}")
    assert FAKE_AWS_KEY not in e.output_preview
    assert "[REDACTED]" in e.output_preview
    assert e.data_class == "CREDENTIAL"


def test_parent_from_other_session_rejected():
    t = _tracker()
    e1 = t.record_output(session_id="S1", server="filesystem-mcp", tool="read_file", content="x")
    try:
        t.record_output(session_id="S2", server="search-mcp", tool="search", content="y", parent_id=e1.event_id)
    except ValueError:
        return
    raise AssertionError("cross-session parent accepted")


def test_call_event_stores_hash_not_raw_args():
    import json

    t = _tracker()
    e = t.record_call(session_id="S1", server="filesystem-mcp", tool="read_file", arguments={"path": ".env"})
    assert FAKE_AWS_KEY not in json.dumps(e.model_dump(mode="json"))
    assert len(e.args_hash) == 64
    assert e.data_class == "SECRET"
