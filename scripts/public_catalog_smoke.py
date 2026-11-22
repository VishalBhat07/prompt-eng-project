"""One harmless read per public server and an optional agent usability check."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
import httpx

CASES = [
    ("microsoft-learn", "microsoft_docs_search", {"query": "Azure Functions overview"}),
    ("deepwiki", "read_wiki_structure", {"repoName": "fastapi/fastapi"}),
    ("cloudflare-docs", "search_cloudflare_documentation", {"query": "Workers overview"}),
    ("aws-knowledge", "aws___list_regions", {}),
    ("huggingface", "hub_repo_search", {"query": "bert", "repo_types": ["model"], "limit": 2}),
    ("context7", "resolve-library-id", {"libraryName": "FastAPI", "query": "path parameters"}),
    ("grep", "searchGitHub", {"query": "asyncio.gather(", "language": ["Python"]}),
    # Expanded public catalog: one harmless read-only call each.
    ("gitmcp", "search_generic_documentation",
     {"owner": "fastapi", "repo": "fastapi", "query": "path parameters"}),
    ("claudeskills", "search_skills", {"query": "code review"}),
    ("drawio", "search_shapes", {"query": "database"}),
    ("twilio-docs", "twilio__search", {"query": "send SMS"}),
    ("theaimeters", "list_meters", {}),
    ("discgolfapi", "search_courses", {"limit": 2}),
    ("callejear", "callejear_get_coverage", {}),
    ("coworkingview", "list_coworking_locations", {"country": "Germany"}),
    ("coingecko", "get-global-market", {}),
]

async def main():
    load_dotenv()
    from crosstoolguard.gateway.proxy import app
    from crosstoolguard.evaluation.multi_server_runner import run_multi_server_task
    from crosstoolguard.llm.providers import resolve
    with TemporaryDirectory(prefix="ctg-public-smoke-") as temp:
        db = str(Path(temp) / "registry.db")
        shutil.copy2(os.getenv("REGISTRY_DB", "data/registry.db"), db)
        with patch.dict(os.environ, {"REGISTRY_DB": db, "EVENTS_PATH": str(Path(temp) / "events.jsonl"),
                "CTG_RUNS_DIR": str(Path(temp) / "runs"), "MODE": "enforcing", "CTG_SEMANTIC_MODE": "heuristic"}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ctg") as client:
                results = []
                for server, tool, arguments in ([] if '--agent-only' in sys.argv else CASES):
                    response = await client.post('/api/mcp/tools/call', json={"session_id": "check-"+server,
                        "server_id": server, "tool": tool, "arguments": arguments})
                    body = response.json()
                    row = {"server": server, "http": response.status_code, "verdict": body.get("verdict"),
                           "is_error": body.get("is_error"), "reason": body.get("reason", body.get("detail"))}
                    results.append(row)
                    print(json.dumps(row), flush=True)
                if '--agent' in sys.argv or '--agent-only' in sys.argv:
                    inventory = (await client.get('/api/registry/inventories')).json()['inventories']
                    refs = [i['server_id']+'/'+t['name'] for i in inventory if i['integrity_status']=='APPROVED' for t in i['tools']]
                    provider, model = resolve('groq', None)
                    report = await run_multi_server_task(proxy_url='http://ctg', task='Look up the AWS region codes for Mumbai and Frankfurt using the available tools.',
                        allowed_tools=refs, provider=provider, model=model, max_steps=4, allow_side_effects=True, compact_catalog=True, client=client)
                    results.append({'agent_outcome':report['outcome'], 'reason':report['halted_reason'], 'calls':report['calls']})
                    print(json.dumps(results[-1]), flush=True)
                Path('data/public-call-check.json').write_text(json.dumps(results, indent=2), encoding='utf-8')

if __name__ == '__main__':
    asyncio.run(main())
