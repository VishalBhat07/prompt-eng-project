"""Task 2 RED: capability extraction, rug-pull integrity, sensitivity, seed."""


def test_upload_has_external_transfer():
    from crosstoolguard.registry.capabilities import extract_capabilities

    caps = extract_capabilities("upload_file", "Mock upload from sink")
    assert "EXTERNAL_TRANSFER" in caps
    assert "NETWORK_SEND" in caps


def test_read_is_not_external():
    from crosstoolguard.registry.capabilities import extract_capabilities

    caps = extract_capabilities("read_file", "Read a file from the lab data directory.")
    assert "FILE_READ" in caps
    assert "EXTERNAL_TRANSFER" not in caps


def test_hash_change_flagged_as_modified():
    from crosstoolguard.registry.tools import ToolRegistry

    reg = ToolRegistry(":memory:")
    r1 = reg.register(server="storage-mcp", tool="upload_file", description="v1", schema={})
    r2 = reg.register(server="storage-mcp", tool="upload_file", description="v2 changed", schema={})
    assert r1.integrity_status == "NEW"
    assert r2.integrity_status == "MODIFIED"
    assert r2.version == r1.version + 1


def test_same_reregister_is_ok():
    from crosstoolguard.registry.tools import ToolRegistry

    reg = ToolRegistry(":memory:")
    reg.register(server="search-mcp", tool="search", description="same", schema={})
    r2 = reg.register(server="search-mcp", tool="search", description="same", schema={})
    assert r2.integrity_status == "OK"


def test_server_inventory_status_persists_until_explicit_approval():
    from crosstoolguard.registry.tools import ToolRegistry

    reg = ToolRegistry(":memory:")
    inventory = {
        "server_id": "test-server", "transport": "stdio", "tools": [
            {"name": "lookup", "description": "Read public test records.",
             "inputSchema": {"type": "object", "properties": {}}},
        ],
    }
    first = reg.register_server_inventory(inventory)
    repeated = reg.register_server_inventory(inventory)
    assert first.integrity_status == "NEW"
    assert repeated.integrity_status == "NEW"
    assert reg.approve_server_inventory("test-server", first.inventory_hash)
    approved = reg.register_server_inventory(inventory)
    assert approved.integrity_status == "APPROVED"
    tool = reg.get_server_inventory("test-server")["tools"][0]
    assert tool["_registry"]["integrity_status"] == "APPROVED"


def test_changed_inventory_stays_modified_and_rejects_stale_approval():
    from crosstoolguard.registry.tools import ToolRegistry

    reg = ToolRegistry(":memory:")
    inventory = {
        "server_id": "test-server", "transport": "stdio", "tools": [
            {"name": "lookup", "description": "Read public test records.",
             "inputSchema": {"type": "object", "properties": {}}},
        ],
    }
    original = reg.register_server_inventory(inventory)
    assert reg.approve_server_inventory("test-server", original.inventory_hash)
    changed = {**inventory, "tools": [{**inventory["tools"][0],
                                        "description": "Read public test records and change behavior."}]}
    modified = reg.register_server_inventory(changed)
    repeated = reg.register_server_inventory(changed)
    assert modified.integrity_status == "MODIFIED"
    assert repeated.integrity_status == "MODIFIED"
    assert not reg.approve_server_inventory("test-server", original.inventory_hash)
    assert reg.approve_server_inventory("test-server", modified.inventory_hash)
    assert reg.get_server_inventory("test-server")["integrity_status"] == "APPROVED"


def test_sensitive_path_classified_secret():
    from crosstoolguard.registry.capabilities import sensitivity_for_path

    assert sensitivity_for_path(".env") == "SECRET"
    assert sensitivity_for_path("invoice.txt") == "PUBLIC"


def test_seed_from_transport_registers_lab_tools():
    from crosstoolguard.registry.tools import ToolRegistry, seed_from_transport

    reg = ToolRegistry(":memory:")
    records = seed_from_transport(reg)
    assert len(records) == 7
    by_name = {r.name: r for r in records}
    assert "EXTERNAL_TRANSFER" in by_name["upload_file"].capabilities
