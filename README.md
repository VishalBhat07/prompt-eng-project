# CrossToolGuard

**Graph-based runtime detection of coordinated attacks in MCP-based LLM agents.**

Single tools look benign - `read_file → ALLOW, store_file → ALLOW, upload_file → ALLOW`.
The attack is the *path*: `SECRET → stage → external`. CrossToolGuard models tools,
capabilities, instructions, data, and runtime actions as a temporal attack graph and
blocks the chain (`ALLOW, ALLOW, BLOCK`) instead of judging tools in isolation.

> Full idea: `CrossToolGuard_Full_Detailed_Project_Document.md` · Plan: `docs/superpowers/plans/`
> Threat model: `docs/THREAT_MODEL.md` · Dashboard API: `docs/API_CONTRACT.md`

## Architecture

```
USER → LLM AGENT → CrossToolGuard PROXY (monitor/enforcing, fail-closed) → MCP SERVERS
                        │ events (hashes + labels, never raw secrets)
                        ▼ provenance → semantic (4 layers) → capability → attack graph
                          → correlation → risk (0–1) → policy → ALLOW / MONITOR / APPROVAL / BLOCK
```

| Risk band | 0.0–0.3 | 0.3–0.6 | 0.6–0.8 | 0.8–1.0 |
|---|---|---|---|---|
| Verdict | ALLOW | MONITOR | APPROVAL | BLOCK |

## Run the dashboard demo on Windows

Use Python 3.11+, Node.js 22, and a Groq API key for the live agent. The scripted
demo and offline benchmark run without a Groq key.

From the repository root, run this one-time setup in PowerShell:

```powershell
py -3 -m venv .venv-phase2
.\.venv-phase2\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix dashboard ci
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

Edit the existing keys in the root `.env` to use the local fixtures. Keep your
Groq key in that file.

```dotenv
GROQ_API_KEY=your_groq_key
MCP_INVENTORY_API_ENABLED=true
MCP_INVENTORY_ALLOWED_HOSTS=127.0.0.1
MCP_INVENTORY_ALLOWED_PORTS=8761,8762,8763
MCP_INVENTORY_ALLOW_PRIVATE_NETWORK=true
REGISTRY_DB=data/registry.db
CTG_RUNS_DIR=data/runs
CTG_SEMANTIC_MODE=heuristic
```

Start these three commands in separate PowerShell terminals, each from the
repository root:

| Terminal | Command |
| --- | --- |
| Local MCP fixtures | `.\.venv-phase2\Scripts\python.exe scripts/local_fixture_stack.py` |
| Gateway | `$env:MODE='enforcing'; .\.venv-phase2\Scripts\python.exe -m uvicorn crosstoolguard.gateway.proxy:app --host 127.0.0.1 --port 8000` |
| Dashboard | `npm --prefix dashboard run dev` |

Open the [dashboard](http://127.0.0.1:5173). Restart the gateway after changing
`.env`.

### Add and keep the inventory current

1. Open **Inventory**. Enter a stable **Inventory ID** and **MCP server URL**,
   then click **Inventory server**. Add these three fixtures for the local demo:

   | Inventory ID | MCP server URL |
   | --- | --- |
   | `fixture-invoice` | `http://127.0.0.1:8761/mcp` |
   | `fixture-file` | `http://127.0.0.1:8762/mcp` |
   | `fixture-send` | `http://127.0.0.1:8763/mcp` |

2. Expand each server row. Review its tool names, descriptions, schemas, and
   metadata findings. Click **Approve and pin this exact fingerprint** for the
   snapshot you want the agent to use.
3. To check a server for changes, submit **Inventory server** again with the
   **same ID and URL**. An unchanged snapshot keeps its approval. A changed
   snapshot is marked `MODIFIED` and needs a new review and approval.
   **Refresh inventories** reloads the saved list from the gateway. Re-submitting
   the server performs the upstream check. Use **Revoke approval** to remove a
   server's tools from new runs.
4. Inventory and approvals are stored in `data/registry.db` by default and
   survive a restart. A fresh checkout starts with an empty local inventory.
   Inspection reads tool definitions. Approval pins that metadata snapshot.

For a **public MCP server**, add its exact hostname to
`MCP_INVENTORY_ALLOWED_HOSTS` and port `443` to
`MCP_INVENTORY_ALLOWED_PORTS`, then restart the gateway. Use the publisher's
Streamable HTTP MCP endpoint over HTTPS, without credentials, query parameters,
or fragments in the URL. For a public-only setup, set
`MCP_INVENTORY_ALLOW_PRIVATE_NETWORK=false`. See the
[public catalog and walkthrough](docs/DASHBOARD_DEMO.md#public-catalog-added)
and the [inventory CLI guide](docs/MCP_INVENTORY.md).

### Run a task and verify the decision

1. Open **Demo** and enter `Find invoice INV-1042 and summarize its total and
   status.` Click **Run task**. The Groq agent selects tools from approved
   servers. To isolate a fixture run when public tools are also approved,
   expand **Run settings** and enable **Limit discovery to selected servers**.
2. Click **Open this session's graph** or select the run in **Sessions**.
   Switch between the **Single-tool graph** and **CrossToolGuard graph**.
   **Findings** shows observed signals, policy explanations, and possible
   paths. An `ALLOW` on an invoice lookup is consistent with an ordinary task.
3. To see the approval flow, ask the agent to send `hello dashboard` to the local
   fixture's mock destination. If a request appears, open **Approvals** and
   choose **Deny** or **Grant once** for that call.

For a repeatable block demonstration, run this command from the repository root:

```powershell
.\.venv-phase2\Scripts\python.exe scripts/poisoned_workflow_demo.py
```

The scripted agent uses three synthetic servers. Expect a final `BLOCK` and zero
mock destination calls. Open **Sessions** and select the printed session ID
to inspect the result. That run shows the simulated provider. Groq runs record
the model's actual choices, which can vary.

## Test and benchmark

```powershell
.\.venv-phase2\Scripts\python.exe -m pytest -q
npm --prefix dashboard run build
.\.venv-phase2\Scripts\python.exe scripts/export_session_benchmark.py
```

The **Benchmark** tab compares four methods on 100 offline replay records.
Live demo runs are available under **Sessions**. See the
[benchmark methodology and results](docs/SESSION_BENCHMARK_V3.md).

## Layout

```
crosstoolguard/
  gateway/      proxy.py (monitor/enforcing, fail-closed, approvals) · session.py
                transport.py (lab adapter) · schemas.py · run_store.py
  registry/     tools.py (SQLite, NEW/OK/MODIFIED) · mcp_inspector.py · assessment.py
                capabilities.py · integrity.py
  provenance/   provenance.py · lineage.py (SQLite parent chains) · events.py (classify/redact)
  analyzer/     semantic.py (regex → MiniLM → keywords → Groq prompt-guard) · instruction.py
  graph/        builder.py (session-partitioned DiGraph) · paths.py · nodes.py · edges.py
  detection/    correlation.py (analyze: build→enrich→match→score) · patterns.py · risk.py
  policy/       engine.py (deny-override) · evaluator.py · rules.py · explain.py
  attacks/      10-category trace builders (A–J) + 8 benign workflows
  evaluation/   BENCHMARK.yaml · benchmark.py · metrics.py · experiments.py (baselines/ablation/latency)
lab/            Groq-first ReAct agent + 4 benign servers + synthetic data only
dashboard/      Vite + React + React Flow (inventory, demo, graphs, approvals, benchmark)
tests/          backend, evaluation, and gateway tests
```

## Safety & conventions

- **Synthetic data only** (`lab/data/`, `SYNTHETIC_*` markers). No real secrets, keys, or PII -
  in repo, logs, or screenshots. Events store hashes + labels; previews redacted + truncated.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
  Work on `feat/*` branches, merge to `main` at sprint boundaries, push then.
- Key hygiene: `.env` is git-ignored. If a key ever touches chat/code, revoke it in the
  Groq console and mint a fresh one.
