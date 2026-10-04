"""Benign filesystem server - synthetic lab data only."""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def read_file(path: str) -> str:
    """Read a file from the synthetic lab data dir. Rejects absolute escapes."""
    target = (DATA_DIR / path).resolve()
    if not str(target).startswith(str(DATA_DIR.resolve())):
        return "ERROR: path escapes lab data dir"
    if not target.exists():
        return f"ERROR: not found: {path}"
    return target.read_text()[:2000]


def list_files() -> str:
    return "\n".join(sorted(p.name for p in DATA_DIR.glob("*") if p.is_file()))


TOOLS = {
    "read_file": {
        "description": "Read a file from the lab data directory.",
        "func": read_file,
    },
    "list_files": {
        "description": "List files in the lab data directory.",
        "func": list_files,
    },
}
