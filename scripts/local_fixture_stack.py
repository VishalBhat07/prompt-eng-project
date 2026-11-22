"""Keep three synthetic HTTP MCP fixtures running for the dashboard demo."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    processes = []
    try:
        for server in ("invoice", "file", "send"):
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            processes.append(subprocess.Popen(
                [sys.executable, "-m", "lab.http_mcp_fixture", "--server", server],
                cwd=ROOT, creationflags=flags))
        print("Synthetic MCP fixtures: http://127.0.0.1:8761/mcp, :8762/mcp, :8763/mcp")
        print("Keep this terminal open; Ctrl+C stops all three fixtures.")
        while all(process.poll() is None for process in processes):
            time.sleep(1)
        raise RuntimeError("A fixture server stopped unexpectedly")
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
