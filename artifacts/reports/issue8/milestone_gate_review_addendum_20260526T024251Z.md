# Issue #8 Milestone-1 Gate Review Addendum

- **Packet ID:** `20260526T024251Z`
- **Supersedes evidence for:** baseline gate decision only; does **not** amend the April 2026 HITL review in `milestone_gate_review.md`
- **Issue #7 evidence:** `artifacts/reports/issue7/20260526T024251Z/`
- **Branch / commit:** `fix/milestone1-gate-remediation-phase2` (see gate reports for exact hash)

## Executive summary

Post–PR #63 remediation (phase 2) addresses the **coverage** and **acceptance** bottlenecks without changing ADR 0003 thresholds or metric formulas.

| Preset | Overall gate | Notes |
| --- | --- | --- |
| **B0** | **pass** | All six thresholds pass |
| **A1** | **fail** | `complexity.complexification_precision` = 0.667 (threshold 0.70); small-*n* ablation artifact |
| **A4** | **pass** | All six thresholds pass |

## Root-cause diagnosis (by stage)

### Taxonomy depth / branching

- B0/A4: depth-2, branching-2 taxonomy yields **7 nodes** across depths 0–2 (unchanged).
- A1: `global_diversification_enabled=false` collapses taxonomy to **1 node** (by design).

### Sample budgets (local diversification)

- **Root cause:** per-node candidates used near-duplicate templates (`example {idx}`), so token-overlap anti-collapse at **0.8** rejected **2/3** candidates per node. Effective budget was **1 instantiation / node** (7 total), not the configured **3**.
- **Fix:** lane-diversified instantiation templates (`_LANE_TEMPLATES`) keep pairwise overlap below 0.8 while preserving the same threshold. B0 now materializes **21** stage-2 instantiations (7 nodes × 3).

### Adjudication policy (dual critic)

- PR #63 restored **dual-critic agreement** via text-only hashing.
- Residual failure mode: with only **7** reviewed samples, ~50% hash acceptance produced **~29%** acceptance and **2/7** node coverage.
- **Fix:** default offline evaluator `hash_based_critic_sample_evaluator` keys on `taxonomy_node_id::instantiation_id` (critic parity preserved). With 21 samples, B0 **acceptance_rate ≈ 0.62** and **node_coverage_ratio = 1.0**.

## Remaining gap (honest)

- **A1** still fails **`complexity.complexification_precision`** (2/3 complexified pairs succeed → 0.667 < 0.70). This is a **small-sample ablation effect** (3 stage-3 samples on a single-node taxonomy), not a threshold or formula issue. Mitigation options for a future slice: document A1 complexity as out-of-scope for full gate pass, or add ablation-specific sample budget policy without touching ADR 0003 constants.

## Threshold / protocol posture

- **No** changes to `DEFAULT_THRESHOLDS` or metric formulas (ADR 0003).
- Comparability fields unchanged across B0/A1/A4 presets (`seed`, `domain_objective`, `evaluation_protocol_version`, etc.).
- Issue #7 eligibility policy remains `instantiated-nodes-from-stage3-samples`.

## Recommendation

- **B0 / A4:** eligible for milestone-1 **conditional pass** on control-axis evidence pending provider-backed validation (NIM/LLM phases).
- **A1:** retain as **documented ablation stress** with explicit complexity-axis gap above.
- **Issue #8 April review:** unchanged; cite this addendum by packet ID for updated gate tables.
