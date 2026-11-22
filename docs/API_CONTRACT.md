# Dashboard API Contract v1

Base: proxy origin (`http://localhost:8000`; Vite dev proxies `/api`, `/ws`).

## `GET /tools/list` → `{tools: [{server, tool, description}]}`

## `GET /api/tools/list`

Same shape as `/tools/list` (namespaced alias for the dashboard).

## `POST /api/agent/run`

Playground: `{task, session_id?, provider?, model?, max_steps? (≤10)}` → full ReAct trace:
`{session_id, steps: [{server, tool, arguments, verdict, observation, approval_id?}], halted, done, provider, model}`.
Every step goes through the same enforce path as `/tools/call`. Halts on
`BLOCK` / `APPROVAL` / `ERROR`. Single-user v1: server-side keys.

## `GET /api/llm/providers`

`{providers: [{id, name, configured, models}]}` — configured means the
server holds that provider's key. Keys never leave the server.

## `GET /api/registry/inventories?server_id=ID`

Reads inventories gathered explicitly with `python -m crosstoolguard.registry.mcp_inspector`.
Without `server_id`, returns `{inventories: [...]}`; with it, returns zero or one inventory.
Each inventory includes server metadata, protocol version, capabilities, inventory hash,
version/status, current complete tool definitions with fingerprints/capabilities, and tools
no longer advertised by the server. The route is read-only: it does not
connect to servers or launch configured stdio commands. It reads `REGISTRY_DB` or
`registry.db` in the current working directory.

## `POST /api/registry/inspect`

Remote Streamable HTTP inventory only; body `{server_id, url, bearer_token?}`.
Disabled unless `MCP_INVENTORY_API_ENABLED=true`. The hostname must exactly match an entry in the configured
comma-separated `MCP_INVENTORY_ALLOWED_HOSTS`. HTTPS is mandatory for remote hosts. HTTP is accepted only for loopback test hosts when `MCP_INVENTORY_ALLOW_PRIVATE_NETWORK=true`; private/reserved address
results are rejected unless the operator explicitly sets `MCP_INVENTORY_ALLOW_PRIVATE_NETWORK=true`.
Only port 443 is accepted by default; `MCP_INVENTORY_ALLOWED_PORTS` can explicitly allow other ports.
The endpoint lists tool definitions and persists the snapshot; it never calls tools. Stdio
profiles remain CLI-only because they launch local processes. The deployment must still apply
network egress controls; a DNS pre-check is not a substitute for network isolation.

The response also contains a deterministic metadata-only assessment. New and changed inventory
statuses remain `NEW` or `MODIFIED` across identical rescans; they are not cleared automatically.

## `POST /api/registry/approve`

Body: `{server_id, inventory_hash}`. Review the report and approve the exact current fingerprint.
The endpoint returns HTTP 409 if the stored fingerprint changed since review. Approval is a
version pin, not a safety certification. A later change returns the server to `MODIFIED`.

## `POST /api/mcp/tools/call`

Body: `{session_id, server_id, tool, arguments, bearer_token?, approval_id?}`. This route supports
approved Streamable HTTP servers only. The server must have an operator-approved inventory and an
exact allowlisted endpoint (HTTPS except controlled loopback HTTP). Before each tool call, CrossToolGuard re-lists definitions on the
same MCP session; a changed fingerprint is saved as `MODIFIED` and the requested call is blocked.
The bearer token is sent only in the request and is not stored. Arguments are validated against the
pinned `inputSchema` before the upstream call; non-local schema references and malformed schemas fail
closed. In `MODE=enforcing`, the graph policy runs before approval; direct secret or credential flows
to an external-transfer tool are blocked, and a policy `BLOCK` cannot be overridden. Other calls
carrying classified secret or credential data require one-shot human approval. The proxy cannot
observe side effects hidden inside a remote server, and matching metadata cannot prove its behavior safe.

## `POST /tools/call`

Body: `{session_id, server, tool, arguments, approval_id?}`
Reply: `{verdict, result, reason, approval_id?}`
- `BLOCK` → `result: null`, call never executed.
- `APPROVAL` → `result: null` + `approval_id`; re-POST with `approval_id`
  after an operator grants it through `POST /approvals/grant` executes once (one-shot).

## `POST /approvals/grant`

Body: `{approval_id}` → `{granted: true, approval_id}`. Grants are accepted only for a
matching, live approval request, expire after five minutes, and are consumed by one matching call.
The approval request itself expires after five minutes.

## `GET /api/graph?session=ID`

`{nodes: [{id, type, ...}], edges: [{source, target, type}], paths: [{pattern, severity, risk, tools, node_ids}], signals: [{node_id, origin_tool, explanation}], potential_paths: [{source, destination, trigger_events, explanation}]}`.
Node `type`: TOOL | SERVER | INSTRUCTION | DATA | DESTINATION.
`node_ids` marks the suspicious path for red highlighting.
`POSSIBLE_FLOW` and `POSSIBLE_INFLUENCE` edges are hypothetical projections from approved tool capabilities and suspicious observed output; they do not assert execution.
`signals` report observed suspicious instructions in tool output even when the agent did not take a later harmful action.

## `GET /api/sessions` and `GET /api/sessions/{session_id}`

The list route returns `{sessions: [{id, tools, events, findings, blocked, maxRisk, status}]}`
for sessions currently held by this gateway process. The detail route returns
`{session, nodes, edges, paths, events}` for one live session, with the same graph
as `/api/graph` and the gateway's redacted event records. An unknown session is 404.
Saved run snapshots under `CTG_RUNS_DIR` are also returned, so a recorded model or scripted fixture run remains available after restart. Live sessions take precedence when both exist. Ad hoc calls that were never saved as runs remain in memory only.

## `POST /api/mcp/agent/run`

Multi-server agent run. Body includes `task`, `provider`, `model`, `policy`, `max_steps`, and `max_calls_per_tool`. The server automatically exposes approved tool inventories to the agent; each model-selected call uses `/api/mcp/tools/call`. Returns `{session_id, status: "running", approved_tool_count}` immediately. Poll `GET /api/mcp/agent/runs/{session_id}` for status and the final hashed report. A pending sensitive call changes status to `awaiting_approval`; a grant through `/approvals/grant` resumes that exact call. Completed runs save a redacted session snapshot.
The status response includes the final answer while the gateway process holds the run in memory; saved reports contain only its hash.

## `GET /api/runs`

Returns saved model and scripted fixture reports for the Benchmark page. Reports contain hashes, tool names, verdicts, policy, and model information rather than raw task/argument/result contents.

## `DELETE /api/sessions`

Clears saved run snapshots and live session state when no run is active. Approved MCP inventories remain available. Intended for resetting a local dashboard demo.

## `GET /api/approvals` and `POST /api/approvals/{approval_id}/deny`

The list contains live pending request IDs, session, server, tool, and expiry. Deny removes a pending request; grants still use `/approvals/grant`.

## `GET /api/alerts?session=ID`

`{alerts: [{pattern, severity, risk, tools, policy, verdict, explanation}]}`.
`explanation` is one NL paragraph (origin → chain → policy → decision).

## `WS /ws/events`

Server-push JSON per recorded event (`TOOL_CALL` + `TOOL_OUTPUT`):
`{event_id, timestamp, session_id, server, tool, event_type, ...}`.
No auth in lab (isolated network); production needs a token.
