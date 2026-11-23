# Session benchmark

The Benchmark tab compares four methods on 100 synthetic replay records.
There are 52 standalone cases and 24 two-variant matched pairs. Every method
receives the same recorded events. A pair shares an initial sequence and
changes a dependency, argument label, output fragment, or proposed action.
The two variants are related observations. The matched-pair metric scores
the two variants together.

## Data and scoring

The [original cases](../crosstoolguard/evaluation/data/SESSION_BENCHMARK_V3.yaml)
and [expansion cases](../crosstoolguard/evaluation/data/SESSION_BENCHMARK_EXPANSION.yaml)
specify the sequences and their expected signal, risk path, and offline policy
decision. They contain recorded proposals and inert previews. Examples
include an output that quotes a suspicious phrase, two output fragments that
form a marker, a proposal with restricted arguments, and public delivery using
a separate branch from a restricted local operation.

| Method | Expected alerts found | Controls falsely flagged | Both alert labels correct |
| --- | ---: | ---: | ---: |
| Single-output detector | 16 / 48 | 5 / 47 | 4 / 22 |
| Session rule | 31 / 48 | 15 / 47 | 8 / 22 |
| CrossToolGuard without dependency links | 27 / 48 | 5 / 47 | 9 / 22 |
| CrossToolGuard | 42 / 48 | 5 / 47 | 19 / 22 |

An alert means the method observed a suspicious output signal or a risk
pattern. The session rule also alerts when a restricted output appears before
an external-transfer proposal. Five cases with uncertain dependency evidence
are excluded from the composite alert, path, and policy totals. Two pairs
have an uncertain variant and are excluded from the matched tally. The
matched tally checks alert presence or absence on both variants. Cases with
the same expected alert on both variants can still differ in path or policy.
Output signals have their own scoring and denominators in the JSON.

| Graph method | Expected paths found | False paths | Policy agreement |
| --- | ---: | ---: | ---: |
| CrossToolGuard without dependency links | 5 / 29 | 0 / 66 | 71 / 95 |
| CrossToolGuard | 27 / 29 | 2 / 66 | 91 / 95 |

The ablation retains argument classification, so it can still find a path
when restricted arguments appear directly in a proposal. The five false
alerts include quoted, glossary, and cautionary text. Four policy mismatches
are in the privileged-proposal cases. They include missed approval for the
later proposal in a session with two privileged proposals and incorrect
approval attribution around an intervening or separate output. They remain
in the published totals. The earlier classified-data chronology fix remains
in place, and the detector rules were kept fixed for this expansion.

## Published test sources

| Source | What is available and where it fits |
| --- | --- |
| [Official MCP conformance suite](https://github.com/modelcontextprotocol/conformance) | Runnable client and server protocol scenarios. Use it first to check a server against the protocol and inspect its behavior on validation, lifecycle, and tool invocation. Replays tagged with this source model ordinary tool behavior and do not perform wire checks. |
| [MCPMark paper](https://proceedings.iclr.cc/paper_files/paper/2026/hash/8138d211ce8790fdfbeeeb9781838a37-Abstract-Conference.html) and [public tasks](https://github.com/eval-sys/mcpmark) | 127 tasks with initial states and verifiers. The local file-size and itinerary cases are simplified synthetic analogues of task designs listed in the repository. |
| [MCP-Bench paper](https://arxiv.org/abs/2508.20453) and [public code and tasks](https://github.com/Accenture/mcp-bench) | Agent tool selection and multi-step workflows spanning MCP servers. Informed the benign cross-server reconciliation control. |
| [MSB paper](https://arxiv.org/abs/2510.15994) and [public case index](https://huggingface.co/datasets/DongsenZhang/MSB) | Pipeline-oriented MCP security scenarios. The linked case index describes instances built by its runtime pipeline. It informed local replay coverage around returned content, proposed arguments, and downstream decisions. |
| [MCPSecBench paper](https://arxiv.org/abs/2508.13220) | An MCP security taxonomy and playground. Used as a coverage reference for tool-originated signals. |

The per-case `source` field records design inspiration. The report contains
local synthetic events and project-authored labels, with no imported upstream
traces or upstream benchmark scores.

## Reproduce

Run this from the repository root in PowerShell:

```powershell
.\.venv-phase2\Scripts\python.exe scripts/export_session_benchmark.py
```

The exporter writes the [dashboard report](../dashboard/public/data/session-benchmark-v3.json)
with expected and observed outcomes, source and record fingerprints, and warmed
latency measurements. Refresh **Benchmark** to see its bar comparisons. A few
examples are expandable on the page. The JSON contains the full case set.

This is a designed replay suite with independent label review pending.
The cases use pre-labeled data, capabilities, and dependency links. These
results measure what the detectors do given that evidence. Generalizing to
production requires evaluating live provenance, real classification quality,
and agent task utility separately. The behavioral group count is descriptive
and does not establish statistical independence.
