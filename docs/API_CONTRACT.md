# Dashboard API Contract v1

Base: proxy origin (`http://localhost:8000`; Vite dev proxies `/api`, `/ws`).

## `GET /tools/list` → `{tools: [{server, tool, description}]}`

## `GET /api/tools/list`

Same shape as `/tools/list` (namespaced alias for the dashboard).

## `POST /api/agent/run`

Playground: `{task, session_id?, model?, max_steps? (≤10)}` → full ReAct trace:
`{session_id, steps: [{server, tool, arguments, verdict, observation, approval_id?}], halted, done, model}`.
Every step goes through the same enforce path as `/tools/call`. Halts on
`BLOCK` / `APPROVAL` / `ERROR`. Single-user v1: server-side Groq key.

## `POST /tools/call`

Body: `{session_id, server, tool, arguments, approval_id?}`
Reply: `{verdict, result, reason, approval_id?}`
- `BLOCK` → `result: null`, call never executed.
- `APPROVAL` → `result: null` + `approval_id`; re-POST with `approval_id`
  after `POST /approvals/grant` executes once (one-shot).

## `POST /approvals/grant`

Body: `{approval_id}` → `{granted: true, approval_id}` (human seam).

## `GET /api/graph?session=ID`

`{nodes: [{id, type, ...}], edges: [{source, target, type}], paths: [{pattern, severity, risk, tools, node_ids}]}`.
Node `type`: TOOL | SERVER | INSTRUCTION | DATA | DESTINATION.
`node_ids` marks the suspicious path for red highlighting.

## `GET /api/alerts?session=ID`

`{alerts: [{pattern, severity, risk, tools, policy, verdict, explanation}]}`.
`explanation` is one NL paragraph (origin → chain → policy → decision).

## `WS /ws/events`

Server-push JSON per recorded event (`TOOL_CALL` + `TOOL_OUTPUT`):
`{event_id, timestamp, session_id, server, tool, event_type, ...}`.
No auth in lab (isolated network); production needs a token.
