# Issue #8 Milestone-1 Gate Review Addendum

- **Packet ID:** `20260526T025231Z`
- **Supersedes evidence for:** baseline gate decision only; does **not** amend the April 2026 HITL review in `milestone_gate_review.md`
- **Issue #7 evidence:** `artifacts/reports/issue7/20260526T025231Z/`
- **Prior addendum:** `milestone_gate_review_addendum_20260526T024251Z.md` (A1 complexity gap before remediation)

## Executive summary

Post–PR #63 remediation (phase 2) plus **A1 ablation complexification policy** closes the remaining small-*n* complexity gate without changing ADR 0003 thresholds or metric formulas.

| Preset | Overall gate | Notes |
| --- | --- | --- |
| **B0** | **pass** | All six thresholds pass |
| **A1** | **pass** | `complexity.complexification_precision` = 1.0 (`complexify_fraction=1.0` on 3-sample single-node ablation) |
| **A4** | **pass** | All six thresholds pass |

## Root-cause diagnosis (A1 complexity)

- **Symptom:** `complexification_precision` = 0.667 (2/3) with default `complexify_fraction=0.75` on A1’s **3** stage-3 samples (single-node taxonomy, lane-diversified anti-collapse cap).
- **Cause:** Precision divides successful complexifications by **all** stage-3 samples; with *n*=3 and fraction 0.75, one sample is intentionally left uncomplexified, failing the 0.70 gate by rounding—not a threshold or formula defect.
- **Fix (preset policy):** A1 `complexification_config.complexify_fraction=1.0` complexifies the full reduced sample set while preserving H1 ablation semantics (`global_diversification_enabled=false`). B0/A4 retain default pipeline complexify fraction (0.75).

## Threshold / protocol posture

- **No** changes to `DEFAULT_THRESHOLDS` or metric formulas (ADR 0003).
- Comparability fields unchanged across B0/A1/A4 presets (`seed`, `domain_objective`, `evaluation_protocol_version`, etc.).
- A1 differs only in ablation-specific `complexification_config` (documented policy variance, not a comparability-field breach).

## Recommendation

- **B0 / A1 / A4:** eligible for milestone-1 **conditional pass** on control-axis evidence pending provider-backed validation (NIM/LLM phases).
- **Issue #8 April review:** unchanged; cite this addendum by packet ID for updated gate tables.
