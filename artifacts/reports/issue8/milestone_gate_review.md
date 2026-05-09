# Issue #8 Milestone-1 HITL Gate Review

- Evidence packet: `artifacts/reports/issue7/20260430T204744Z`
- Reviewed runs: `B0`, `A1`, `A4`
- Final decision: **fail**

## Decision rationale

The milestone gate fails with high confidence because five of six required thresholds fail across all compared runs, with large margins from threshold (coverage, complexity precision, critic agreement, and acceptance rate). The only passing threshold (`regen_burden`) does not compensate for broad control-axis failure. Evidence is internally consistent across run-level gate reports and aggregate comparison tables.

## Threshold mapping

| Metric | Observed (B0 / A1 / A4) | Threshold | Status | Comment |
| --- | --- | --- | --- | --- |
| `coverage.node_coverage_ratio` | `0.1429 / 0.1429 / 0.1429` | `>= 0.80` | Fail | Severe under-coverage; only 1/7 eligible nodes covered. |
| `coverage.min_depth_coverage` | `0.0 / 0.0 / 0.0` | `>= 0.60` | Fail | At least one depth level remains unrepresented in all runs. |
| `complexity.complexification_precision` | `0.0 / 0.0 / 0.0` | `>= 0.70` | Fail | Complexification is not producing harder samples in judged pairs. |
| `quality.critic_agreement` | `0.4286 / 0.4286 / 0.1786` | `>= 0.75` | Fail | Critic reliability is weak; A4 degrades further as expected ablation stress. |
| `quality.acceptance_rate` | `0.1429 / 0.1429 / 0.1429` | `>= 0.50` | Fail | Throughput below milestone viability level. |
| `quality.regen_burden` | `0.0 / 0.0 / 0.0` | `<= 1.00` | Pass | No regeneration pressure observed. |

## Comparability check

Comparability constraints are preserved for:
- domain objective (`pilot-domain`)
- taxonomy eligibility policy (`default-eligible-all-taxonomy-nodes`)
- complexity judgment protocol (`milestone-1`, fixed Elo defaults)
- artifact schema version (`v1`)

Critic configuration differs for `A4` (`single_critic`) by design as an ablation; adjudication policy stays `reject_on_disagreement`.

## Reproducibility status

Issue #9 reproducibility hardening is now complete.

- Manifest schema validation passes for all compared runs (`B0`, `A1`, `A4`).
- Baseline rerun classification is **exact** (`max_metric_delta = 0.0`).
- Rerun evidence packet: `artifacts/reports/issue9/issue7/20260509T160651Z`
- Comparability constraints remain unchanged.
- Hard-gate policy is active: no threshold tuning unless reproducibility, audit-trace completeness, and fixed-protocol comparability all pass.

## Threshold adjustment recommendation

Recommendation: **keep thresholds unchanged** for now.

Reasoning:
- Misses are not borderline; they are large and systematic across all primary axes.
- Lowering thresholds now would weaken gate semantics without isolating root cause.

ADR note:
- No threshold value changes are proposed in Issue #8, so no ADR is required at this step.
- If thresholds are later revised after Issue #9 and diagnosis follow-up, trigger ADR workflow to document trade-offs and comparability impact.

## Issue #9 handoff

Issue #9 complete. Proceed to Issue #10 scope decision for reusable-engine extraction while preserving milestone-1 comparability constraints.
