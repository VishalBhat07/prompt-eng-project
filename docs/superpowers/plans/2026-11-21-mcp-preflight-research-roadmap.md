# MCP Preflight and Cross-Tool Defense: Research Roadmap

## Goal

Extend CrossToolGuard from a fixed lab demonstration into a tool that can assess MCP servers before use and protect agent workflows at runtime. The target is to detect and limit tool poisoning and coordinated attacks spread across multiple tools, while measuring false positives, utility, and overhead. The system reports evidence and coverage; it does not certify that an MCP server is universally safe.

## Current baseline and known gap

The repository already contains a lab proxy, tool registry and fingerprints, capability rules, event/provenance handling, semantic output analysis, attack graphs, risk/policy decisions, a dashboard, and a synthetic benchmark. The upstream adapter in `crosstoolguard/gateway/transport.py` remains an in-process adapter for fixed lab servers. Arbitrary Streamable HTTP servers can now be inventoried, assessed, pinned, and called through a separate guarded route; the model-backed behavioral runner remains fixture-only, with a no-call prompt preflight for any saved inventory. The existing trace benchmark and final research corpus still need reconciliation with the larger benchmark in the original project document. See `docs/MCP_INVENTORY.md` for scope and commands.

## Research questions

- **RQ1 — Cross-tool value:** Does provenance-aware graph correlation detect distributed attacks that single-tool and keyword/semantic baselines miss?
- **RQ2 — Poisoned-tool value:** Does scanning and pinning complete tool definitions, combined with runtime controls, reduce attack success when poisoning appears in metadata, schemas, outputs, or behavior?
- **RQ3 — Practical trade-offs:** What are the false-positive rate, legitimate task success, path accuracy, latency, and assessment coverage of the system?

These are questions to test, not results to assume. Any novelty claim must be checked against a documented related-work review.

## Threat model

### In scope

- A malicious or compromised MCP server supplies deceptive tool names, descriptions, schemas, annotations, outputs, errors, or resources.
- A server changes its advertised tool definition after review (rug pull), or its behavior changes while metadata remains constant.
- An attacker distributes instructions across tool outputs, encodings, transformations, sessions within a workflow, or several otherwise-benign tools.
- The agent is induced to access sensitive data, invoke privileged operations, or send data to an unauthorized destination.
- Benign tasks may resemble suspicious chains; the detector must measure and report this cost.

### Out of scope for the first research release

- Proving arbitrary server source code free of vulnerabilities or malicious behavior.
- Detecting every dormant, time-triggered, or environment-specific payload from a finite test set.
- Host-kernel compromise, sandbox escape, compromise of the selected model provider, or attacks on the human approver.
- Uncontrolled testing against third-party services or real accounts.

### Trust and safety rules

- Tool metadata, server outputs, and remote resources are LOW trust until assessed; transformations preserve their original provenance.
- Use synthetic data, fake credentials, mock destinations, and isolated execution for attacks.
- Do not pass production credentials to an unreviewed server or assessment run.
- Clearly distinguish metadata-only review, sandbox execution, source/package review, and runtime monitoring in the report.
- If direct network or process side effects are not observable, report that limitation rather than treating an MCP call trace as complete evidence.

## Phased implementation

### Phase 1 — Research scope and acceptance contract

**Deliverables:** this roadmap; aligned threat model; RQs; measurable definition of done.

**Exit criteria:** attack and trust boundaries are explicit; tests are synthetic and isolated; metrics and claims are defined before experiments.

### Phase 2 — MCP onboarding and inventory

Add a connection workflow for supported MCP transports (initially stdio and Streamable HTTP, with legacy support only if required by selected servers). Enumerate complete server identity and tool definitions, including input/output schemas and annotations. Store versioned snapshots and full-definition fingerprints. Validate server configuration and present an explicit warning/approval step before launching an untrusted local process.

**Exit criteria:** a user can add a local or remote test server, list its tools, persist an inventory, and detect any definition change; all lab servers continue to work through the adapter boundary.

### Phase 3 — Pre-use assessment

Produce per-server and per-tool findings for metadata injection signals, capability/permission scope, schema hazards, definition integrity, package/source provenance when available, and stated-versus-observed behavior. Mark each finding with evidence, severity, confidence, and assessment coverage. Separate known facts from heuristics and unknowns.

Keep description triage intentionally conservative and easy to audit: use a small set of direct warning patterns, and do not scan serialized schemas or annotations as if their words were natural-language instructions. This triage supports review; the core security contribution remains detection and enforcement of coordinated cross-tool paths at runtime.

**Exit criteria:** reports are reproducible from a pinned server version and contain no raw secrets; a metadata-only assessment never claims behavioral safety.

### Phase 4 — Isolated attack lab and prompt test runner

Build benign and controlled malicious MCP fixtures and a repeatable harness using synthetic data and a mock egress sink. Cover the original A–J taxonomy: direct poisoning, indirect injection, cross-tool exfiltration, capability escalation, rug pull, distributed instructions, context laundering, shadow workflows, credential-to-network, and multi-stage attacks. Add benign task families and prompt mutations. Store test inputs, versions, traces, expected safe behavior, and ground-truth paths.

**Exit criteria:** each case can be replayed; tests cannot reach real credentials or destinations; attack and benign sets are separately identified.

**Current implementation:** existing A–J synthetic event traces plus a fixed MCP fixture with benign and poisoned variants, synthetic prompts, a mock sink, and a model-backed fixture runner. A separate non-executing prompt preflight accepts any saved MCP inventory and evaluates task prompts against advertised metadata. The preflight accepts custom system prompts and records only hashes. Broader attack-family coverage, prompt mutations, behavior traces, and arbitrary-server behavioral testing remain incomplete.

### Phase 5 — Runtime enforcement and evidence

Connect the real MCP client/proxy path to normalized events, provenance, dataflow, temporal graph correlation, and deny-override policy. Enforce tool-definition pinning, least privilege, argument/schema validation, destination controls, approval for sensitive actions, and safe failure behavior. Add process/network observation or explicitly report where the MCP-level trace cannot see internal server side effects.

**Exit criteria:** an unsafe chain is stopped before the protected side effect in the controlled lab; a benign workflow completes; reports explain source, data lineage, tool path, policy, and decision.

**Current implementation:** an approved Streamable HTTP tool-call route re-lists definitions on the same MCP session, checks arguments against the pinned `inputSchema` (without remote references), and blocks inventory changes or schema failures before invocation. Calls carry metadata-derived capabilities and classified secret arguments into the existing event/policy pipeline. Direct secret/credential-to-external-transfer patterns now produce a deny-override BLOCK, and remote calls run graph policy before any approval escalation, so approval cannot release a blocked path. Other policy-flagged or secret-bearing calls require one-shot approval; grants require a live matching request and expire after five minutes or one use. The local dashboard has no login and the gateway must stay bound to localhost. Full cross-tool attack-family coverage, per-user approval identity, and observation of internal remote-server side effects remain open.

### Phase 6 — Experimental evaluation

Compare on the same test cases: no protection; independent single-tool checks; keyword/semantic checks; and full CrossToolGuard. Run ablations removing metadata checks, provenance, capability analysis, graph correlation, integrity pinning, and runtime policy. Split tuning and held-out tests by attack template/server rather than randomly mixing variants. Repeat stochastic agent runs with fixed model/provider/version and settings where possible.

**Metrics:** attack success rate (ASR), attack detection/recall, false-positive rate, legitimate task success, cross-tool detection gain, node/edge/path precision and recall, block-before-side-effect rate, definition-change detection, assessment coverage, latency, and explanation/provenance completeness. Report confidence intervals and limitations; do not pre-commit to favorable numbers.

**Exit criteria:** results are reproducible from documented seeds/configuration; each baseline and ablation uses the same corpus; known misses and false positives are included.

### Phase 7 — Research paper and final demonstration

Write: abstract; problem and threat model; related work; design; benchmark and fixtures; experimental setup; results; ablations; limitations; ethics/safety; conclusion. Include the three-stage demo from the original document: benign tools individually, coordinated attack, then CrossToolGuard explanation and block. Archive code, synthetic corpus, configs, and run instructions.

**Exit criteria:** every contribution is implemented and supported by an experiment; claims match observed evidence; a clean environment can reproduce the main tables and demo.

## Dashboard implementation checkpoints

### User verification gate — 2026-11-22

Current authorized milestone: finish dashboard consistency, expand the real public MCP inventory, and supply manual test prompts. Separate session execution state, suspicious output signals, observed attack paths, hypothetical paths, and path-only risk. Keep manual approvals without an operator key. Record reachable endpoints and unavailable/authentication-dependent candidates truthfully.

Stop after delivering the dashboard and test prompts for user verification. Do not start repeated benchmarking, experimental evaluation, paper work, or later phases until the user explicitly verifies the dashboard and authorizes continuation. The broader project goal remains unfinished.

The dashboard must show observed experiment data, with one run/session ID linking the agent's selected tools, gateway verdicts, graph paths, and benchmark rows. Stop after each checkpoint for operator review and a manual demo run.

1. **Live sessions and graph — implemented:** the Sessions and Graph pages read live gateway events and saved run snapshots. The bundled sample session was removed.
2. **Recorded runs — implemented for dashboard demo:** multi-server model runs and controlled scripted runs save redacted events, graph paths, and reports under `data/runs`, visible after proxy restart.
3. **Agent task page — implemented for approved Streamable HTTP tools:** the user enters a task and selects provider, model, policy, and an optional server scope. The agent chooses tools within that scope. The dashboard runs on localhost without an operator key. Controlled local fixtures are documented in `docs/DASHBOARD_DEMO.md`.
4. **Findings, possible harm, and approvals — implemented for gateway state:** observed graph alerts and capability-based possible paths are displayed separately. Possible paths are labeled as hypotheses and drawn dashed. Sensitive calls pause a run for a one-shot operator decision and resume after approval. Pending requests expire and are not persisted after restart.
5. **Benchmark and home — implemented for current evidence:** refresh the labeled 19-case synthetic trace artifact with `scripts/export_dashboard_benchmark.py`; list recorded model runs separately. Repeated model experiments, uncertainty estimates, and research tables remain Phase 6 work; the dashboard must not present single model runs as benchmark rates.
6. **Final demo review — dashboard checkpoint ready; clean-environment review open:** inventory, agent runs, graph, findings, approvals, and benchmark pages are wired. The expanded public catalog and manual prompt checklist are delivered. A clean-environment walkthrough and the larger research benchmark still need completion.

### Delivered checkpoint — 2026-11-22

**Status: awaiting user verification.** This checkpoint finishes the dashboard consistency pass, expands the real public MCP inventory, and supplies manual agent prompts. It does not complete the research project or authorize Phase 6 work.

**Dashboard consistency fixes**

- Visible branding is **CrossToolGuard** throughout; the old VeriGraph UI label is gone.
- Home links to live `/sessions` and `/inventory`; the attack-class list now covers all ten A-J classes.
- Sessions can clear saved runs with `DELETE /api/sessions` while keeping approved inventories.
- Inventory shows server/tool counts, `first_seen`/`last_seen`, and a refresh action.
- `/api/graph` and `/api/alerts` fall back to saved run snapshots after a proxy restart.
- Benchmark counts come from `benchmark.json`; recorded model runs can be refreshed.
- Graph "Suspicious only" includes suspicious-output signal nodes.
- Findings separates observed attack paths, suspicious output signals, and possible harm paths with counts.
- **Run a task** scopes the catalog to selected servers; the default is the three local fixtures. The gateway rejects an initial catalog over 20,000 characters, avoiding Groq free-tier `rate_limit_exceeded` errors from sending all 80 tools and every server instruction in one request.
- Tests default to `CTG_SEMANTIC_MODE=heuristic`; the embedding-layer test is skipped when NumPy/sentence-transformers are unavailable.

**Public MCP inventory**

The registry contains **24 server snapshots**, of which **20 are approved** and expose **80 approved tools**. The approved public catalog now covers documentation, code search, repository docs, diagrams, agent skills, public environmental data, disc golf, German municipal data, coworking spaces, and crypto market data:

`microsoft-learn`, `deepwiki`, `cloudflare-docs`, `aws-knowledge`, `huggingface`, `context7`, `grep`, `gitmcp`, `claudeskills`, `drawio`, `twilio-docs`, `theaimeters`, `discgolfapi`, `callejear`, `coworkingview`, `coingecko`, plus the existing `mcptest-echo` positive control.

The 16 newly added public servers each completed one harmless read through the guarded gateway. `drawio`, `coingecko`, `tavily-docs`, and `mintlify-docs` advertise a write/feedback action and are treated as review targets, not read-only services.

Four snapshots are inventoried but deliberately **not approved**:

- `boim` and `youth4work`: every harmless smoke call failed server-side or returned 403.
- `tavily-docs` and `mintlify-docs`: CRITICAL metadata risk band, including `submit_feedback`.

`cloudflare-radar` was attempted but returned 401 and was not added as a usable anonymous inventory. No external account keys were invented or added. Refresh commands and the full table are in `docs/DASHBOARD_DEMO.md`.

**Manual verification material**

`docs/DASHBOARD_DEMO.md` contains 24 prompts: ten for the original local/public workflow, twelve additional public-catalog and cross-server prompts, and two direct blocked-path prompts. They cover single-server grounding, two-server graph construction, documentation/code comparison, public data lookups, local fixture suspicious output, the one-shot approval path, and a poisoned-instruction chain that reaches the final transfer. The Run a task page defaults to the local fixtures; select only the public server or two named in a public prompt. These are functional checks, not benchmark statistics.

**Verification run**

- `pytest`: **103 passed, 1 skipped**.
- Dashboard production build: **passed** (`tsc --noEmit && vite build`).
- Synthetic trace artifact: **19 cases, 8 attack, 9 integrity/provenance/no-finding; detection 1.0, FPR 0.0**.
- Saved-session `/api/graph` and `/api/alerts` fallback verified after the gateway restart.
- All 16 newly approved public servers passed one harmless read; smoke results are written to `data/public-call-check.json`.
- Live scoped Groq run: `aws-knowledge` only (5 tools, 1,505 context chars) completed with Mumbai `ap-south-1` and Frankfurt `eu-central-1`. The unscoped 80-tool catalog is rejected at 33,305 chars before any model call.
- Live blocked-path run: the poisoned invoice prompt drove `search_invoices` ALLOW, `read_demo_credential` ALLOW, then `send_data` BLOCK. The graph reported `poisoned_instruction_chain` and `direct_secret_exfiltration`; no mock destination call occurred.

**Next action:** the operator should run the prompts, inspect the linked session graphs and findings, and confirm the dashboard behavior. Only after explicit verification should work continue to repeated model runs, the larger benchmark, or later research phases.

## Next plan after the dashboard review

The active follow-on goal and its review stops are tracked in [CrossToolGuard next goal](crosstoolguard-next-goal.md).

1. **Reproduce the dashboard from a clean checkout.** Verify fixture setup, inventory review, task answer, approval grant and deny, graph rendering, and saved evidence after restart in a browser. Add a small browser smoke suite covering those flows and error states. Capture the commands and platform used. Local registry and run files are generated by the setup and stay out of Git.
2. **Finish the remaining dashboard controls.** Expose inventory revocation through the gateway and the Inventory page. Show when a server leaves the approved catalog and verify that a subsequent run cannot use it. Improve graph navigation and add consistent loading, empty, and partial error states for live and saved data. Include narrow viewport and keyboard checks in the browser review.
3. **Improve automatic tool discovery.** Treat the current server scope and context guard as usable fallbacks for large inventories. Add bounded automatic discovery across approved servers, keep optional scope as a user control, and measure whether tools needed for ordinary multi-server tasks remain discoverable. Preserve schema validation and fingerprint checks immediately before execution.
4. **Close the defensive evidence gaps.** Expand source and permission evidence in inventory reviews, improve how the runtime tracks observed provenance, and verify block and one-use approval behavior with recorded events and inert fixtures. Document which effects the gateway can observe and which alerts are capability-based inferences. Keep the localhost approval model explicit.
5. **Prepare and run the research evaluation after user sign-off.** Freeze a versioned protocol with benign controls, held-out recorded traces, configured policies, provider settings, repeated benign task runs, and independent labels. Report detection and false alerts, benign completion, blocked fixture actions, latency, and uncertainty. Record provider errors separately from security outcomes, and keep trace and model results separate in the dashboard.
6. **Write the paper and package the demo.** Use measured evidence for the claims and include scripts, configuration, versioned data, and clean setup instructions. Complete related work, limitations, and reproducibility checks before marking the overall goal complete.

The existing dashboard verification gate still applies to Phase 6 and the paper. The dashboard fixes above are backlog items, with user review as the next checkpoint.

For local review, group the current changes into three commits: gateway, registry, and their tests; dashboard and its benchmark export; and setup, demo scripts, documentation, and roadmap. Keep the generated registry, run snapshots, logs, public catalog checks, and local secrets outside the commits.

## Baselines and related work

The paper must account for existing MCP security work, including MCPTox and MCP Security Bench. Do not claim to be the first MCP attack benchmark or the first tool-poisoning study. A candidate contribution to evaluate is the combined treatment of pre-use tool-definition assessment and provenance-aware runtime graph enforcement for distributed multi-tool attacks. Retain or revise that positioning after a systematic related-work search.

## Definition of done

1. Arbitrary test servers can be onboarded through supported transports and their tool inventories/version changes recorded.
2. Pre-use findings distinguish metadata/source evidence from observed runtime behavior and state coverage limits.
3. A synthetic, isolated lab includes poisoning, distributed, multi-stage, and benign scenarios.
4. Runtime enforcement blocks defined unsafe paths before the mock side effect and preserves benign task success at a measured rate.
5. Baselines, ablations, metrics, held-out tests, and reproducibility artifacts are complete.
6. The paper and demo make no unsupported safety or novelty claims.

## Progress

- [x] Phase 1: research scope, threat model, research questions, and acceptance contract.
- [x] Phase 2: MCP onboarding and inventory (stdio and Streamable HTTP inspection; persistent server/tool fingerprints and removal tracking; CLI inventory export; guarded remote onboarding API and review page).
- [ ] Phase 3: pre-use assessment (in progress: conservative direct-pattern scanning of tool descriptions; capability hints from name/title/description; structural checks for permissive schemas, external references, and annotation conflicts; evidence-backed reports persisted and shown in the dashboard; endpoint/artifact fingerprint pinning. This is triage only. Remaining: source/package provenance, richer permission analysis, and stated-versus-observed comparison after behavioral testing).
- [ ] Phase 4: isolated attack lab and prompt test runner (in progress: fixed benign/poisoned MCP fixture, synthetic prompt cases, fixture-only model-backed runner, non-executing preflight for arbitrary inventories, fake credential and in-memory egress sink; prompt mutations and full A–J runtime fixture coverage remain).
- [ ] Phase 5: runtime enforcement and evidence (in progress: approved Streamable HTTP call path, same-session re-inventory before each tool call, pinned input-schema validation, dynamic capability events, direct secret/credential exfiltration blocks, deny-overrides-approval, and expiring one-shot grants for localhost. Remaining: broader defensive coverage and internal side-effect observation. Per-user approval identity is needed for shared deployments.)
- [ ] Phase 6: experimental evaluation.
- [ ] Phase 7: paper and final demonstration.

### Current status — 2026-11-22

- **Dashboard checkpoint:** delivered and awaiting user verification. See "Delivered checkpoint — 2026-11-22" above and `docs/DASHBOARD_DEMO.md`.
- **Public catalog:** 24 snapshots, 20 approved, 80 approved tools. Four snapshots remain unapproved for documented smoke-test or CRITICAL-metadata reasons.
- **Not started by design:** repeated model benchmarking, held-out evaluation, ablations, uncertainty estimates, paper work, and later phases. These wait for explicit user verification.
