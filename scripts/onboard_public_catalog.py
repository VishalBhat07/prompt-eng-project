"""Inventory a bounded catalog of publisher-documented public MCP endpoints.

Only initialization and tools/list are sent. Tool calls are never made here.
Approval is a separate operator decision: pass ``--approve`` to pin the exact
snapshot that was just inventoried and assessed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

from crosstoolguard.registry.assessment import assess_inventory
from crosstoolguard.registry.mcp_inspector import inspect_server
from crosstoolguard.registry.tools import ToolRegistry

# Publisher-documented, public, no-account endpoints used by the demo. Keep this
# list bounded and prefer read-only documentation/search/data services. A
# listing is not a safety certification; review each snapshot before approval.
CATALOG = [
    # Existing demo catalog
    ("microsoft-learn", "https://learn.microsoft.com/api/mcp", "Microsoft documentation"),
    ("deepwiki", "https://mcp.deepwiki.com/mcp", "Public repository wiki"),
    ("cloudflare-docs", "https://docs.mcp.cloudflare.com/mcp", "Cloudflare documentation"),
    ("aws-knowledge", "https://knowledge-mcp.global.api.aws", "AWS documentation"),
    ("huggingface", "https://huggingface.co/mcp", "Model/dataset hub"),
    ("context7", "https://mcp.context7.com/mcp", "Library documentation"),
    ("grep", "https://mcp.grep.app", "Public code search"),
    # Expanded public catalog (metadata-only inventory; no tool calls)
    ("gitmcp", "https://gitmcp.io/docs", "Public GitHub repository docs/code"),
    ("claudeskills", "https://claudeskills.club/mcp", "Agent skill catalog"),
    ("drawio", "https://mcp.draw.io/mcp", "Diagram generation and shape search"),
    ("tavily-docs", "https://docs.tavily.com/mcp", "Tavily documentation"),
    ("mintlify-docs", "https://www.mintlify.com/docs/mcp", "Mintlify documentation"),
    ("twilio-docs", "https://mcp.twilio.com/docs", "Twilio documentation"),
    ("theaimeters", "https://www.theaimeters.com/mcp", "Public environmental data"),
    ("discgolfapi", "https://io.discgolfapi.com/mcp", "Public disc-golf course data"),
    ("boim", "https://boim.io/api/mcp", "Public Korean business directory"),
    ("callejear", "https://callejear.de/api/mcp", "Public German street data"),
    ("coworkingview", "https://mcp.coworkingview.com/mcp", "Public coworking-space data"),
    ("coingecko", "https://mcp.coingecko.com/mcp", "Public crypto market data"),
    ("youth4work", "https://mcp.youth4work.com/public/mcp", "Public jobs and colleges"),
    # Kept for a truthful unavailable/authentication-dependent record
    ("cloudflare-radar", "https://radar.mcp.cloudflare.com/mcp", "Cloudflare Radar (requires auth)"),
]

# Servers whose advertised tool set includes a write or feedback action. They are
# still useful for inventory review, but the demo does not treat them as
# read-only. This note is informational only; approval is explicit.
WRITE_TOOL_SERVERS = {"tavily-docs", "mintlify-docs", "coingecko", "drawio"}

# A metadata inventory can succeed while every tool call fails server-side.
# Keep such servers out of the autonomous catalog until a harmless call passes.
KNOWN_CALL_FAILURES = {"boim", "youth4work"}


def cause(exc: BaseException) -> str:
    children = getattr(exc, "exceptions", None)
    return cause(children[0]) if children else f"{type(exc).__name__}: {str(exc)[:250]}"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory public MCP servers (metadata only)")
    parser.add_argument("--only", nargs="*", help="Inventory only these server IDs")
    parser.add_argument("--approve", action="store_true",
                        help="Pin each successfully inventoried snapshot after assessment")
    parser.add_argument("--timeout", type=float, default=45.0, help="Per-server timeout in seconds")
    parser.add_argument("--report", default="data/public-catalog-report.json",
                        help="Where to write the JSON report")
    args = parser.parse_args()

    load_dotenv()
    selected = [item for item in CATALOG if not args.only or item[0] in set(args.only)]
    if not selected:
        raise SystemExit("No catalog entries matched --only")

    registry = ToolRegistry(os.getenv("REGISTRY_DB", "data/registry.db"))
    rows = []
    try:
        for server, url, purpose in selected:
            row = {"server_id": server, "url": url, "purpose": purpose}
            try:
                inventory = await asyncio.wait_for(
                    inspect_server({"server_id": server, "transport": "streamable-http", "url": url}),
                    timeout=args.timeout,
                )
                record = registry.register_server_inventory(inventory)
                report = assess_inventory(inventory)
                registry.save_assessment(server, report)
                row.update(
                    status="inventoried",
                    scan_status=record.integrity_status,
                    tools=[tool["name"] for tool in inventory["tools"]],
                    risk_band=report["risk_band"],
                    finding_count=report["finding_count"],
                    write_tools_advertised=server in WRITE_TOOL_SERVERS,
                )
                if args.approve:
                    if report["risk_band"] == "CRITICAL":
                        row["approved"] = False
                        row["approval_note"] = "not auto-approved: CRITICAL metadata risk band"
                    elif server in KNOWN_CALL_FAILURES:
                        row["approved"] = False
                        row["approval_note"] = "not auto-approved: harmless smoke call failed server-side"
                    else:
                        row["approved"] = registry.approve_server_inventory(
                            server, record.inventory_hash)
                        if not row["approved"]:
                            row["approval_note"] = "snapshot changed before approval; re-inventory"
                saved = registry.get_server_inventory(server)
                row["integrity_status"] = saved.get("integrity_status") if saved else None
            except Exception as exc:  # noqa: BLE001 - report each endpoint truthfully
                row.update(status="unavailable", reason=cause(exc))
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        registry.close()

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "approve_requested": args.approve,
        "servers": rows,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
