# Parallel Agent Prompts (Iteration 1)

This document provides copy/paste-ready prompts for running multiple agents against the first Simula implementation wave plan.

## Wave execution status (verified against `origin/main`)

Use this table as the source of truth for what is actually integrated in `main`.

| Wave | Slice | Linked issue/PR | Status on `main` | Notes |
| --- | --- | --- | --- | --- |
| Wave 0 | Issue #1 tracer bullet | Issue #1, PR #12 | Complete | Manifest + pipeline skeleton are in `main`. |
| Wave 1 | Prompt A: taxonomy stage | Issue #2, PR #15 | Complete | Taxonomy stage + tests are in `main`. |
| Wave 1 | Prompt B: harness support | PR #13 (+ commit `27e7e0c` integration) | Complete | Harness fixtures/assertions and integration notes are now in `main`. |
| Wave 1 | Prompt C: validator utilities | PR #14 (+ commit `86f9ce8` integration) | Complete | Validator APIs and tests are now in `main`. |
| Wave 2 | Prompt A: local diversification | Issue #3, PR #16 | In review | Merge first in Wave 2 sequence. |
| Wave 2 | Prompt B: config scaffolding | Issue #7, PR #17 | In review | Rebase on latest `main` after PR #16 merges. |

## How to use this file

- Treat prompt blocks below as the prompt library.
- Check the status table before starting a new wave.
- When a slice lands in `main`, update both this table and `docs/issues-draft.md`.

## Operating model

- Use one PR branch per issue or wave.
- Keep each agent focused on one issue outcome.
- Require each agent to return:
  - changed files
  - tests added/updated
  - run instructions
  - blockers and assumptions

## Wave 0

### Agent prompt: Issue #1

```text
Implement GitHub issue #1: "Scaffold runnable pipeline shell and run contracts".

Goals:
1) Create a minimal end-to-end runnable pipeline skeleton.
2) Define and validate run manifest contracts (run_id, seed, model IDs, protocol version, artifact schema version).
3) Ensure stage handoffs align with docs/pipeline-spec.md.

Constraints:
- Use TDD (red -> green -> refactor) for core contracts.
- Keep implementation thin; placeholders are acceptable where downstream stages are not ready.
- Persist artifacts using current repository conventions.

Deliverables:
- Code changes and tests.
- Short run command that executes the tracer bullet.
- Notes on what remains for issue #2.
```

## Wave 1 (parallel)

### Agent prompt A: Issue #2 (taxonomy stage)

```text
Implement GitHub issue #2: "Implement global diversification taxonomy stage".

Goals:
1) Implement recursive taxonomy generation with merge/filter checks.
2) Produce a valid acyclic taxonomy graph with stable taxonomy_node_id values.
3) Persist taxonomy artifacts in the run artifact layout.

Constraints:
- Build on the contracts from issue #1.
- Add tests for acyclic graph and orphan-node prevention.
- Keep interfaces simple for downstream local diversification.

Deliverables:
- Code + tests.
- Example artifact output from one run.
- Clear handoff contract for issue #3.
```

### Agent prompt B: test harness support (for #2/#3)

```text
Create supporting test harness and fixtures that accelerate issue #2 and issue #3.

Goals:
1) Add reusable fixtures for taxonomy nodes and meta-prompt lineage.
2) Add helper assertions for traceability fields (taxonomy_node_id, meta_prompt_id, instantiation lineage).
3) Keep harness independent from concrete model providers.

Constraints:
- Do not implement issue #2 or #3 business logic itself.
- Focus on deep, reusable testing modules.

Deliverables:
- New/updated test utility modules.
- Example tests demonstrating harness usage.
- Notes on integration points expected by #2/#3 agents.
```

### Agent prompt C: artifact/manifest validator utilities

```text
Implement artifact and manifest validator utilities to support issue #6 and issue #9.

Goals:
1) Validate required manifest fields and schema shape.
2) Validate required artifact folder structure by stage.
3) Produce machine-readable validation output suitable for CI or run reports.

Constraints:
- Reuse terminology from docs/reproducibility-ops.md.
- Keep validators decoupled from pipeline stage internals.

Deliverables:
- Validator module(s) + tests.
- Example command or function call for validation.
- List of assumptions about artifact conventions.
```

## Wave 2 (parallel after #2)

### Agent prompt A: Issue #3

```text
Implement GitHub issue #3: "Implement local diversification with anti-collapse checks".

Goals:
1) Generate meta-prompts from taxonomy nodes.
2) Generate multiple instantiations per node.
3) Enforce anti-collapse checks before complexification.

Constraints:
- Preserve traceability lineage required by pipeline-spec.
- Add tests proving low-diversity candidates are rejected/logged.

Deliverables:
- Code + tests.
- Example run output showing diversity checks.
- Handoff notes for issue #4.
```

### Agent prompt B: baseline/ablation config scaffolding

```text
Create configuration scaffolding for B0, A1, and A4 runs from the research-validation-playbook.

Goals:
1) Add explicit baseline and ablation config presets.
2) Ensure protocol comparability fields are frozen across variants.
3) Include run labels and metadata needed by evaluation reporting.

Constraints:
- Do not execute full experiments yet.
- Keep config naming and structure consistent with issue #7 needs.

Deliverables:
- Config files/templates for B0, A1, A4.
- Validation checks for required fields.
- Notes on how these configs are invoked by the runner.
```

## Wave 3 (parallel)

### Agent prompt A: Issue #4

```text
Implement GitHub issue #4: "Implement complexification with semantic-preservation checks".

Goals:
1) Apply complexification to configurable sample fractions.
2) Preserve taxonomy linkage and source intent.
3) Record semantic-preservation failures for analysis.

Constraints:
- Respect complexity controls in docs/pipeline-spec.md.
- Add tests for policy behavior and lineage preservation.

Deliverables:
- Code + tests.
- Example before/after sample trace with tags.
- Handoff notes for issue #5.
```

### Agent prompt B: Issue #6 skeleton (metrics pipeline)

```text
Start GitHub issue #6 by implementing the evaluation pipeline skeleton and metric interfaces.

Goals:
1) Build metric computation scaffolding for coverage, complexity, quality.
2) Add reporting structure for gate decisions.
3) Leave clearly marked stubs where issue #5 outputs are required.

Constraints:
- Use formulas and threshold semantics from docs/evaluation-metrics.md.
- Avoid hard-coding run-specific assumptions.

Deliverables:
- Metric pipeline skeleton + tests for available inputs.
- Gate report schema/template.
- Explicit TODO points to finalize after issue #5 lands.
```

## Wave 4-8 (sequential prompts)

### Agent prompt: Issue #5

```text
Implement GitHub issue #5: "Implement dual-critic adjudication and regeneration logs".

Goals:
1) Store independent critic decisions per sample.
2) Implement deterministic disagreement handling under configured policy.
3) Persist rejection/regeneration logs.

After completion, integrate outputs into the issue #6 metrics pipeline and finalize gate report generation.
```

### Agent prompt: Issue #7

```text
Implement GitHub issue #7: execute B0 + A1 + A4 and publish artifacted report outputs.

Goals:
1) Run baseline and required ablations under fixed protocol.
2) Produce comparison tables and milestone gate report.
3) Include failure analysis notes where thresholds fail.
```

### HITL prompt: Issue #8

```text
Run a milestone-1 gate review from issue #7 outputs.

Review packet must include:
- Coverage evidence
- Complexity evidence
- Quality evidence
- Reproducibility status

Decision options:
- Pass
- Conditional pass
- Fail

If thresholds change, record rationale and trigger ADR update workflow.
```

### Agent prompt: Issue #9

```text
Implement GitHub issue #9: reproducibility hardening and deterministic rerun checks.

Goals:
1) Validate manifest schema across compared runs.
2) Execute and classify baseline rerun (exact/acceptable drift/mismatch).
3) Attach reproducibility status to milestone evidence.
```

### HITL prompt: Issue #10

```text
Run scope decision for reusable-engine extraction.

Goals:
1) Identify candidate stage interfaces for reuse.
2) Exclude changes that would break milestone-1 comparability.
3) Approve follow-on issue set and ADR updates for phase 2.
```

## Fast fallback prompts

### If a slice is too large

```text
Split the current issue into thinner AFK vertical slices with explicit dependencies and updated acceptance criteria. Keep each slice independently verifiable.
```

### If signals are weak

```text
Use /diagnose on the latest baseline+ablation outputs to identify the primary bottleneck axis (coverage, complexity, or quality), then propose the smallest parameter-level change.
```
