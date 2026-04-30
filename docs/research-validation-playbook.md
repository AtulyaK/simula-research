# Research Validation Playbook

## Purpose

This playbook defines how to run and evaluate the initial Simula-style validation program. It standardizes hypotheses, ablations, acceptance checks, and iteration decisions.

## Validation hypotheses

### H1: Global diversification improves coverage

Compared with non-taxonomy or shallow-taxonomy baselines, hierarchical global diversification increases node and depth coverage.

### H2: Local diversification reduces mode collapse

Within-node sample variation improves when explicit multi-instantiation local diversification is used.

### H3: Complexification shifts difficulty without breaking semantics

Complexification increases calibrated complexity while preserving coverage alignment and acceptable quality rates.

### H4: Dual-critic checks improve quality reliability

Independent dual-critic verification reduces incorrect accepted samples versus single-critic or no-critic variants.

## Experiment matrix

Use one domain objective at a time. Run baseline first, then ablations.

| Run ID | Configuration | Expected effect |
| --- | --- | --- |
| B0 | Full pipeline (all stages enabled) | Reference run |
| A1 | No global diversification | Lower coverage and depth profile |
| A2 | No local diversification | Higher local mode collapse |
| A3 | No complexification | Lower complexity distribution |
| A4 | Single critic only | Lower quality reliability |
| A5 | Full pipeline with reduced critic strictness | Higher acceptance but lower agreement |

If resources are limited, prioritize `B0`, `A1`, and `A4`.

## Per-run checklist

Before run:

- Freeze run config and seed.
- Confirm domain objective and task format.
- Confirm metric protocol version.
- Confirm baseline/ablation label.

During run:

- Persist stage outputs and rejection/disagreement logs.
- Record any interruptions and retries.
- Track sample counts by taxonomy depth and branch.

After run:

- Compute all metrics in `docs/evaluation-metrics.md`.
- Fill the standard run report.
- Evaluate thresholds and write gate decision.

## Acceptance criteria

A run is considered a validation success when:

- all required thresholds are met (coverage, complexity, quality)
- no critical protocol violations are present
- run is reproducible from artifacts and manifest

For hypothesis-level acceptance:

- **H1 accepted** if B0 outperforms A1 on node coverage and depth profile.
- **H2 accepted** if B0 outperforms A2 on local diversity indicators.
- **H3 accepted** if B0 outperforms A3 on calibrated complexity and preserves quality bounds.
- **H4 accepted** if B0 outperforms A4 on quality reliability metrics.

## Failure analysis rubric

When runs fail gates or hypotheses:

1. **Locate axis failure**
   - Coverage, complexity, quality, or protocol.
2. **Trace stage origin**
   - Determine earliest stage where signal degraded.
3. **Classify failure type**
   - taxonomy design issue
   - diversification issue
   - complexification drift
   - critic disagreement pathology
   - reproducibility gap
4. **Define smallest next change**
   - one parameter or one policy change per retry.

## Iteration loop

1. Run baseline.
2. Run ablations.
3. Compare metrics and gate outcomes.
4. Diagnose failures using rubric.
5. Apply smallest targeted adjustment.
6. Re-run affected matrix cells.
7. Update decision notes and ADRs if policy changed.

## Promotion criteria for next phase

Promote from initial validation to integration planning only when:

- hypotheses H1-H4 are accepted or convincingly bounded
- metric trends are stable across at least two repeated baseline runs
- reproducibility checks pass without manual reconstruction
- unresolved risks are documented with owners and mitigation plans
