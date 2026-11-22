from crosstoolguard.registry.capabilities import extract_capabilities
from crosstoolguard.registry.assessment import assess_tool


def test_generic_execute_and_negative_secret_language_do_not_infer_dangerous_capabilities():
    assert "SHELL_EXEC" not in extract_capabilities("add", "Executes a deterministic addition operation.")
    assert "SHELL_EXEC" not in extract_capabilities("echo", "Returns text and never runs commands.")
    assert "CREDENTIAL_READ" not in extract_capabilities(
        "whoami", "Reports client information; it never reads or returns credentials, secrets, passwords, or tokens."
    )


def test_explicit_command_and_credential_access_still_infer_capabilities():
    assert "SHELL_EXEC" in extract_capabilities("run_shell_command", "Execute the supplied shell command.")
    assert "CREDENTIAL_READ" in extract_capabilities("read_api_key", "Read the API key from a credential store.")


def test_schema_strings_and_read_only_annotations_do_not_create_capabilities():
    report = assess_tool({
        "name": "add", "description": "Executes a deterministic addition operation.",
        "annotations": {"readOnlyHint": True},
        "inputSchema": {
            "type": "object", "properties": {
                "a": {"type": "number", "description": "The first number."},
                "b": {"type": "number", "description": "The second number."},
                "note": {"type": "string", "description": "Never run shell commands."},
            },
        },
    })
    assert "SHELL_EXEC" not in report["capabilities"]
    assert "CREDENTIAL_READ" not in report["capabilities"]
    assert not any(item["id"] == "read_only_annotation_conflicts_with_capability"
                   for item in report["findings"])
