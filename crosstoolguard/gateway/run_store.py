"""Persist redacted dashboard run snapshots by opaque session ID."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


def _path(session_id: str) -> Path:
    if not _SAFE_ID.fullmatch(session_id):
        raise ValueError("invalid session ID")
    return Path(os.getenv("CTG_RUNS_DIR", "data/runs")) / f"{session_id}.json"


def save_run(session_id: str, snapshot: dict) -> None:
    path = _path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_run(session_id: str) -> dict | None:
    path = _path(session_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def list_runs() -> list[dict]:
    root = Path(os.getenv("CTG_RUNS_DIR", "data/runs"))
    if not root.is_dir():
        return []
    rows = []
    for path in root.glob("*.json"):
        if _SAFE_ID.fullmatch(path.stem):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
    return rows


def clear_runs() -> int:
    """Delete only saved run JSON files inside this project workspace."""
    project = Path(__file__).resolve().parents[2]
    root = Path(os.getenv("CTG_RUNS_DIR", "data/runs")).resolve()
    if not root.is_relative_to(project):
        raise ValueError("run directory is outside the project workspace")
    if not root.is_dir():
        return 0
    removed = 0
    for path in root.glob("*.json"):
        if path.is_file() and _SAFE_ID.fullmatch(path.stem):
            path.unlink()
            removed += 1
    return removed
