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

Agree on the defensive claims, benign tasks, labeled recorded traces, held-out split, policy settings, metrics, and reproducibility manifest. Define how to count provider errors, false alerts, approvals, and blocked decisions. Review the protocol before running the evaluation.

## Checkpoint 3 · Results

Run the agreed evaluation with benign tasks and inert or recorded evidence. Report per-case outcomes, summary metrics with uncertainty, and limits of the evidence. Connect the evaluation results to the dashboard and review the results before drafting conclusions.

## Final delivery

Deliver the paper draft, methods, tables, versioned inputs, and repeatable instructions. Check each paper claim against the evaluation artifacts and complete a clean-checkout reproduction pass.
