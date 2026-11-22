# CrossToolGuard

**Graph-based runtime detection of coordinated attacks in MCP-based LLM agents.**

Single tools look benign - `read_file → ALLOW, store_file → ALLOW, upload_file → ALLOW`.
The attack is the *path*: `SECRET → stage → external`. CrossToolGuard models tools,
capabilities, instructions, data, and runtime actions as a temporal attack graph and
blocks the chain (`ALLOW, ALLOW, BLOCK`) instead of judging tools in isolation.

> Full idea: `CrossToolGuard_Full_Detailed_Project_Document.md` · Plan: `docs/superpowers/plans/`
> Threat model: `docs/THREAT_MODEL.md` · Dashboard API: `docs/API_CONTRACT.md`

For the current Windows dashboard walkthrough with real multi-server Groq runs, saved session graphs, and the controlled blocked-path demo, follow [DASHBOARD_DEMO.md](docs/DASHBOARD_DEMO.md). The Benchmark page distinguishes the synthetic trace benchmark from recorded model runs; repeated model-run research evaluation remains in progress.

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

## Prerequisites

- Python 3.11+ (tested 3.11 / 3.13), Node 18+, Docker (optional, for compose)
- A **Groq API key** (free at console.groq.com) - agent reasoning + L4 prompt-guard judge.
  No OpenAI subscription needed. Local fallback: `ollama pull llama3.2:3b` (~2 GB, M2-Air safe).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then put GROQ_API_KEY=... inside (.env is git-ignored, never commit it)
set -a; source .env; set +a # load env (zsh)
cd dashboard && npm install --no-audit && cd ..
```

## Run (3 terminals)

```bash
# 1 - proxy (use MODE=monitor to log-only, MODE=enforcing to block)
MODE=enforcing python -m uvicorn crosstoolguard.gateway.proxy:app --port 8000

# 2 - lab agent (Groq plans, every call routed via the proxy)
python lab/agent.py --task "summarize lab/data/invoice.txt"

# 3 - dashboard
cd dashboard && npm run dev   # → http://127.0.0.1:5173 (proxies /api + /ws to :8000)
```

Docker alternative: `docker compose up --build` (proxy on :8000, isolated `ctg-lab` net).

## Inventory an MCP server

CrossToolGuard can make a read-only inventory of an MCP server over Streamable HTTP or stdio.
Create a JSON connection profile and follow [MCP_INVENTORY.md](docs/MCP_INVENTORY.md).
The command saves complete tool definitions and fingerprints to `registry.db`; the dashboard
shows saved snapshots at `/inventory`. Inventory does not call tools or prove server behavior safe.
Only launch stdio servers inside an isolated environment, and do not supply production credentials.

The current local demo registry contains **24 snapshots**, **20 approved servers**, and **80 approved tools** from public documentation, code-search, repository, diagram, agent-skill, environmental, municipal, coworking, and crypto-data MCP services. The Run a task page scopes each run to selected servers so a free-tier model is not sent the entire catalog at once. Four snapshots remain unapproved for documented smoke-test failures or CRITICAL metadata risk. Refresh with `scripts/onboard_public_catalog.py --approve`; see [DASHBOARD_DEMO.md](docs/DASHBOARD_DEMO.md) for the catalog table and manual agent prompts.

For model-backed prompt checks, `python -m crosstoolguard.evaluation.prompt_runner --provider groq`
runs the bundled benign/poisoned cases against the shipped synthetic MCP fixture. You can pass
`--task` and `--system-prompt-file` to evaluate your own prompts against that fixture. The runner
does not execute arbitrary server code; use synthetic prompts only, since prompts are sent to the
configured model provider. For arbitrary inventoried servers, `python -m
crosstoolguard.evaluation.prompt_preflight --inventory inventory.json --task "..." --forbid-tool
tool_name` screens the model's proposed tool action without connecting to or invoking the server.
After reviewing and pinning a snapshot, an agent can call approved Streamable HTTP tools through
`POST /api/mcp/tools/call`; enable `MODE=enforcing` for pre-call policy decisions. See
[MCP_INVENTORY.md](docs/MCP_INVENTORY.md) for constraints and examples.

## 60-second demo (the thesis, live)

```bash
S=S-DEMO
curl -s -X POST localhost:8000/tools/call -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$S\",\"server\":\"filesystem-mcp\",\"tool\":\"read_file\",\"arguments\":{\"path\":\"credentials_example.txt\"}}" | head -c 60; echo
curl -s -X POST localhost:8000/tools/call -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$S\",\"server\":\"storage-mcp\",\"tool\":\"store_file\",\"arguments\":{\"name\":\"s\",\"content\":\"x\"}}" | head -c 60; echo
curl -s -X POST localhost:8000/tools/call -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$S\",\"server\":\"storage-mcp\",\"tool\":\"upload_file\",\"arguments\":{\"name\":\"s\"}}" | head -c 60; echo
# → ALLOW … ALLOW … BLOCK, then open the dashboard (session S-DEMO) for the red path + explanation.
curl -s "http://localhost:8000/api/alerts?session=$S" | python -m json.tool | head -20
```

## Test & measure

```bash
python -m pytest tests/ -q          # 103 passed, 1 skipped: schemas, proxy, registry,
                                    # provenance, analyzer, graph, detection, policy, API, benchmark
python -c "from crosstoolguard.evaluation.benchmark import run_all
print(len(run_all()), 'cases')"     # 19-case benchmark (A–J attacks + N benign)
python -c "from crosstoolguard.evaluation.experiments import run_baselines, run_ablation
print(run_baselines()); print(run_ablation())"
```

Measured on v1 (see report for method): detection **8/8** targeted attacks, FPR **0.000**,
cross-tool gain **7** cases invisible to the single-tool baseline, `analyze()` mean **14 ms**
/ p95 **66 ms**. Known designed gap: `B-indirect-basic` (reconnaissance with no sink or
privilege reached) is recorded as an expected miss.

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
dashboard/      Vite + React + React Flow (MVP UI; full polished website planned post-evaluation)
tests/          mirrors src, 103 passing tests plus 1 optional embedding-layer skip
```

## Safety & conventions

- **Synthetic data only** (`lab/data/`, `SYNTHETIC_*` markers). No real secrets, keys, or PII -
  in repo, logs, or screenshots. Events store hashes + labels; previews redacted + truncated.
- Commits: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
  Work on `feat/*` branches, merge to `main` at sprint boundaries, push then.
- Key hygiene: `.env` is git-ignored. If a key ever touches chat/code, revoke it in the
  Groq console and mint a fresh one.
