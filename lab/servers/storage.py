"""Benign storage server - mock sink. Lab uploads NEVER leave the machine."""

STORE: dict[str, str] = {}


def store_file(name: str, content: str) -> str:
    """Stage content in the in-memory mock sink (5000-char cap)."""
    STORE[name] = content[:5000]
    return f"stored {name} ({len(STORE[name])} chars) in mock sink"


def upload_file(name: str) -> str:
    """Mock external upload - logs intent, does NOT transmit (lab safety)."""
    if name not in STORE:
        return f"ERROR: {name} not staged; call store_file first"
    return f"mock-upload {name} -> sink://lab/{name} (no network egress)"


TOOLS = {
    "store_file": {
        "description": "Stage content in the lab mock sink.",
        "func": store_file,
    },
    "upload_file": {
        "description": "Mock upload from sink (no real network egress).",
        "func": upload_file,
    },
}
