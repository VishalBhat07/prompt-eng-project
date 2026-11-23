# CrossToolGuard next goal

Baseline is local `main` at `075b2cd`. The existing demo guide and research roadmap are the reference for the committed dashboard.

## Checkpoint 1 · Dashboard and inventory

- [x] Add a reversible inventory approval control with exact fingerprint checks. Preserve metadata and exclude revoked tools from new runs.
- [x] Verify that the dashboard Grant once action reaches the gateway through the development proxy and exercise the matching grant in the gateway integration test.
- [x] Refresh approved server choices, show missing inventory states, and distinguish incomplete Findings results from empty results.
- [x] Add and pass the browser walkthrough with an empty temporary registry. It covers inventory review and revocation, an ordinary task, grant and deny, graph and Findings, and saved graph evidence after a gateway restart.
- [x] Review loading, error, and empty states. Verify keyboard navigation and five routes at a 390-pixel viewport.
- [x] Enable bounded automatic discovery with optional server scope. Verify two benign tasks retain the relevant candidates in an oversized 12-tool test catalog, and retain the explicit scope regression test.

The browser walkthrough passed with Microsoft Edge, a fresh temporary registry,
and a scripted model. The dashboard build passed, and 105 Python tests passed
with one optional embedding test skipped. The discovery check measures which tools
reach the model. Live model selection rates across larger catalogs remain an
evaluation question. Full clean checkout reproduction of the research package
is part of final delivery.

## Checkpoint 2 · Evaluation design

The [draft evaluation protocol](../../EVALUATION_PROTOCOL.md) is ready for
review. It specifies the defensive claims, datasets, controls, outcome
denominators, and reproducibility artifacts. Freeze the case manifest and
begin measurements at checkpoint 3 after sign-off.
The [evaluation guide](../../EVALUATION_GUIDE.md) explains what each dataset
contains, where it lives, and how a case becomes a dashboard result.

## Checkpoint 3 · Results

- [x] Verify the offline reporting pipeline on the 19-case development set, with one row per case and explicit metric denominators. See the [development pilot](../../EVALUATION_GUIDE.md#development-pilot).
- [x] Freeze the [synthetic replay cases](../../../crosstoolguard/evaluation/data/REPLAY_V1.yaml) and the [benign tasks](../../../crosstoolguard/evaluation/data/BENIGN_TASKS_V1.yaml) before measurement. The replay labels had a single-author review rather than independent review.
- [x] Run the frozen synthetic replay and all 48 scheduled benign trials. Validate the individual records, report uncertainty and limitations, and pause for results review before updating the dashboard.

The [results log](../../EVALUATION_RESULTS.md) has the offline replay, approval
counter, and live model comparison. The aggregate export was checked against
24 replay records and 48 trial records.

## Checkpoint 4 · Dashboard results before the paper

- [x] Publish the aggregate replay and benign-trial summaries in separate
  Benchmark sections. Include development latency in milliseconds, sample
  count, and case-level expected and observed values.
- [x] Add and replay six matched pairs. Each pair changes a single recorded
  field. Benchmark shows both detectors' views of the same server and tool
  events, with controls and false alerts visible.
- [x] Show approval reasons and an unavailable destination state when the
  gateway has no reviewed label. Keep raw arguments out of the approval view.
- [x] Verify the graph comparison, a false-alert control, and the narrow
  dashboard layout in the browser walkthrough.

Review the [evaluation results](../../EVALUATION_RESULTS.md) and the Benchmark
tab before drafting. M03 illustrates changed lineage and M06 shows a shared
false alert.

Dashboard changes verified by the user on November 23, 2026, including
call-level explanations in Findings and collapsed server rows in Inventory.

## Revised benchmark review

The Benchmark page now shows the [V3 replay](../../SESSION_BENCHMARK_V3.md)
with the single-output and session-rule baselines, a dependency-link ablation,
and CrossToolGuard. The Graph page continues to compare views of one live or
saved run. V3 presents bar comparisons and example evidence for 100 replay
records, including 24 matched pairs, and links the external research used
to design the expansion. It documents misses, false alerts, and policy
disagreements.

Before making general claims in the paper, obtain independent label review
and test genuinely new workflow shapes on a fresh frozen set. Keep the
earlier benign model runs as a separate utility experiment.

## Final delivery

Deliver the paper draft, methods, tables, versioned inputs, and repeatable instructions. Check each paper claim against the evaluation artifacts and complete a clean-checkout reproduction pass.

Frame the paper as a tool and methodology contribution. The matched case
evidence supports a claim about inspecting cross-tool decisions and their
failure modes. The benign provider batch measures task utility. Treat both
experiments as limited pilots, and include the quoted-text false alert,
provider errors, fixture input limitations, and missing independent labeling.
