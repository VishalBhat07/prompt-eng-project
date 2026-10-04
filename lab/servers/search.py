"""Benign search server — keyword search over synthetic lab data only."""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def search(query: str) -> str:
    """Case-insensitive keyword search across lab/data/*.txt (preview only)."""
    hits: list[str] = []
    for p in sorted(DATA_DIR.glob("*.txt")):
        text = p.read_text()
        if query.lower() in text.lower():
            idx = text.lower().index(query.lower())
            hits.append(f"{p.name}: ...{text[max(0, idx - 40):idx + 80]}...")
    return "\n".join(hits) if hits else "no matches"


TOOLS = {
    "search": {
        "description": "Keyword search over synthetic lab documents.",
        "func": search,
    },
}
