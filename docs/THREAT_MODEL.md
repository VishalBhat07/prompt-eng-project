# Threat Model v1 - CrossToolGuard

> Current implementation: semester lab prototype. All attacks use synthetic data in an
> isolated Docker network. No real secrets, keys, or PII are ever used.
> Expansion target: see `docs/superpowers/plans/2026-11-21-mcp-preflight-research-roadmap.md`.

## 1. System components

- **User**: issues tasks (e.g. "summarize my invoice").
- **LLM agent**: ReAct loop (`Reason → Action → Observation`), Groq-hosted
  by default (`llama-3.3-70b-versatile`), local `llama3.2:3b` fallback.
- **CrossToolGuard proxy**: FastAPI layer between agent and MCP servers.
  Sole enforcement point. Started in `monitor`, hardened to `enforcing`.
- **MCP servers**: benign (filesystem, calculator, search, storage) plus
  controlled malicious variants (poisoned-search, rug-pull) for benchmarks.
- **Dashboard**: read-only visualization of graphs/alerts (labels only).

## 2. Attacker capabilities (IN scope)

- Controls **tool descriptions** (`tools/list`) and **tool outputs**
  (`tools/call` results, `resources/read`, web content via search).
- Controls **at most one malicious MCP server** at a time.
- Can split instructions across tools (distributed poisoning), paraphrase,
  base64/URL-encode payloads, and chain individually-benign capabilities
  (`FILE_READ → STORE → EXTERNAL_TRANSFER`).
- Can change a previously-approved tool's description/schema (rug pull).
- Knows CrossToolGuard exists and tries to evade regex/keyword checks.

## 3. Attacker limitations (OUT of scope)

- Does **NOT** control proxy code, policy YAML, LLM weights, dashboard,
  or the host/Docker daemon.
- No kernel exploits, container escapes, side-channels, or compromise of
  Groq/Ollama infrastructure.
- No attack on the human approver (social engineering out of scope).
- No denial-of-service against the proxy beyond normal tool-call volume.

## 4. Trust levels

| Level | Source | Examples |
|-------|--------|----------|
| HIGH  | User prompt | task text, approval decisions |
| MED   | User-owned data | files under `lab/data/`, local DB rows |
| LOW   | Tool-controlled | descriptions, outputs, web/search content |

Provenance MUST preserve the original LOW source through transforms
(summarizer, format conversion) to defeat context laundering.

## 5. Assets & security goals

- **Confidentiality**: `SECRET`/`CREDENTIAL` data (synthetic `.env`,
  fake API keys, mock customer rows) must never reach `EXTERNAL` sinks.
- **Integrity**: LOW-trust instructions must never trigger PRIVILEGED
  tools without approval.
- **Availability (bounded)**: rule-path overhead p95 < 150 ms; LLM-judge
  off critical path; fail-closed on proxy/policy errors for privileged
  actions (BLOCK), never silent ALLOW.

## 6. Safety & ethics guardrails

- Synthetic data only (`lab/data/`), isolated `ctg-lab` Docker network,
  external uploads directed to a mock sink, never the real internet.
- Proxy stores `arguments_hash` (SHA-256) + classification labels, never
  raw secret values; tool-output previews truncated to 500 chars, redacted.
- Dashboard shows labels and paths, never secret contents.
- No real `.env`, SSH keys, or PII in repo, logs, or screenshots.

## 7. Expanded research scope (planned)

The next development phases add pre-use assessment for user-supplied MCP servers and runtime defense across their tool chains. Tool definitions, schemas, annotations, outputs, and resources are treated as LOW-trust input. A nice description or clean metadata scan is not evidence that the server's implementation is safe.

Assessment runs must use a restricted sandbox, synthetic data, fake credentials, and mock destinations. No production credentials or uncontrolled third-party side effects are allowed. Reports must identify whether each result came from metadata review, source/package review, sandbox behavior, or runtime monitoring, and must disclose blind spots when the process or network effects were not observed.

This project does not claim that a finite test suite can prove an arbitrary MCP server safe. It measures detection and task impact for the stated threat model and test corpus. Dormant, time-triggered, and environment-dependent behavior remains a limitation; least privilege and runtime controls remain necessary.
