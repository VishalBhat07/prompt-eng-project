from crosstoolguard.evaluation.prompt_preflight import _parse_action, _resolve_tool


def test_parse_action_accepts_fenced_json_and_preamble():
    action = _parse_action('Plan follows:\n```json\n{"tool":"search","arguments":{"q":"x"}}\n```')
    assert action == {"tool": "search", "arguments": {"q": "x"}}


def test_parse_action_accepts_done_result():
    assert _parse_action('{"done":true,"answer":"No tool needed."}') == {
        "done": True, "answer": "No tool needed."
    }


def test_resolve_tool_accepts_name_and_server_qualified_name():
    names = {"search", "read_record"}
    assert _resolve_tool("search", names, "server-a") == "search"
    assert _resolve_tool("server-a/read_record", names, "server-a") == "read_record"
    assert _resolve_tool("other-server/search", names, "server-a") is None
