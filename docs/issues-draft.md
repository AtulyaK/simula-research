# Simula Issues Draft (Vertical Slices)

## Purpose

This is the working issue pack for implementation sequencing. Slices are intentionally thin and end-to-end so each one yields a verifiable outcome.

## Verification snapshot

- Issue #1: complete on `main` (PR #12)
- Issue #2: complete on `main` (PR #15)
- Wave 1 support slices (prompt B/C): integrated in `main` via commits `86f9ce8` (validators) and `27e7e0c` (harness)
- Issue #3: complete on `main` (PR #16)
- Issue #4: complete on `main` (PR #18)
- Issue #5: complete on `main` (PR #21)
- Issue #6 skeleton: complete on `main` (PR #19)
- Issue #7: complete on `main` (PR #23)
- Issue #8: **HITL addendum pending** — April review **fail** (`20260430T204744Z`); remediated packet **`20260526T024251Z`** on `main` (PR **#69**): **B0 pass**, **A4 pass**, **A1 fail** (`complexification_precision`); sign-off JSON `artifacts/reports/issue8/milestone_gate_review_addendum_20260526T024251Z.json`
- Issue #9: complete on `main` (PR #25); reproducibility evidence in `artifacts/reports/issue9/`
- Issue #10: **closed** (ADR **0004** Option A — `docs/adr/0004-engine-seam-scope.md`)
- ADR 0004 P1: **#60**, **#61** closed; **#62** deferred (`ready-for-human`)
- Milestone 3 follow-ons **#27–#30**: complete on `main` (commits `df88524`, `73a0dc9`)
- Post–Milestone 3 hardening: **#31** / **PR #32**, **#33** / **PR #34** — merged
- M1 gate remediation: **PR #69** merged (`af9be6f`)
- LLM / correctness wave: **PR #45**, **#54**, **#56**, **#58** — merged
- **`main` tests:** 93 unittest cases, OK (no API keys)
- Agent briefing: **`docs/agents/next-agent-handoff.md`** (implementation cycle closed; provider Phase 4 + Issue #8 sign-off open)

## Slice index

| # | Title | Type | Blocked by |
| --- | --- | --- | --- |
| 1 | Scaffold runnable pipeline shell and run contracts | AFK | None |
| 2 | Implement global diversification taxonomy stage | AFK | #1 |
| 3 | Implement local diversification with anti-collapse checks | AFK | #2 |
| 4 | Implement complexification with semantic-preservation checks | AFK | #3 |
| 5 | Implement dual-critic adjudication and regeneration logs | AFK | #4 |
| 6 | Implement metric computation and gate report generation | AFK | #5 |
| 7 | Execute baseline and ablations with artifacted report outputs | AFK | #6 |
| 8 | Milestone-1 gate review and threshold adjustment decision | HITL | #7 |
| 9 | Reproducibility hardening and deterministic rerun checks | AFK | #8 |
| 10 | Decide reusable-engine extraction scope and boundaries | HITL | #9 |

## Draft issue bodies

---

### Issue 1: Scaffold runnable pipeline shell and run contracts

**Type**: AFK  
**Blocked by**: None - can start immediately

## What to build

Create a minimal executable pipeline skeleton that wires stage boundaries and persists a canonical run manifest. Include frozen run configuration contracts so downstream stages can rely on stable lineage fields.

## Acceptance criteria

- [x] Pipeline shell runs end-to-end with placeholder stage outputs.
- [x] Run manifest contains run ID, seed, model IDs, protocol version, and artifact schema version.
- [x] Stage handoff contracts align with `docs/pipeline-spec.md`.

## Implementation notes (completed tracer bullet)

- **Branch**: `feature/issue-1-tracer-bullet-manifest`
- **Goal delivered**: one thin end-to-end tracer bullet proving Stage 0 through Stage 5 wiring and run-level contract stability.
- **Public entrypoint**: `run_pipeline(seed, model_ids)` in `src/simula_research/pipeline.py`.
- **Manifest contract fields**: `run_id`, `seed`, `model_ids`, `protocol_version`, `artifact_schema_version`.
- **Manifest schema validation**: added `MANIFEST_SCHEMA` and `validate_manifest()` in `src/simula_research/manifest.py` with required-field and type checks.
- **Stage handoff skeleton**: placeholder outputs for:
  - `stage_0_domain_run_spec`
  - `stage_1_global_diversification`
  - `stage_2_local_diversification`
  - `stage_3_complexification`
  - `stage_4_dual_critic_quality_verification`
  - `stage_5_evaluation_handoff`
- **Traceability guarantee in tracer bullet**: each stage output stores the same `run_id` as the manifest.
- **Test strategy (TDD)**: integration-style test via public API in `tests/test_issue1_tracer_bullet.py`, asserting manifest contents and stage boundary contracts.
- **Verification command**: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- **Result**: passing (1 test, 0 failures).

## Follow-on notes for Issue 2

- This tracer bullet intentionally keeps stage behavior as placeholders to preserve a thin vertical slice.
- Issue 2 can implement real taxonomy graph generation inside `stage_1_global_diversification` without changing the Issue 1 contract surface.

---

### Issue 2: Implement global diversification taxonomy stage

**Type**: AFK  
**Blocked by**: Issue 1

## What to build

Implement recursive taxonomy generation with merge/filter checks and output a valid taxonomy graph with stable node IDs for downstream sampling.

## Acceptance criteria

- [x] Taxonomy output is acyclic and has no orphan nodes.
- [x] Every node has a stable `taxonomy_node_id`.
- [x] Taxonomy artifacts are persisted in the run artifact layout.

## Implementation notes (completed in mainline)

- **Branch**: `feature/issue-2-global-taxonomy-stage`
- **Merged PR**: #15
- **Delivered**:
  - recursive taxonomy generation with merge/filter checks
  - deterministic `taxonomy_node_id` generation
  - persisted taxonomy artifacts under `10_taxonomy/`
  - handoff contract for issue #3 in stage output

---

### Issue 3: Implement local diversification with anti-collapse checks

**Type**: AFK  
**Blocked by**: Issue 2

## What to build

Generate meta-prompts and multiple within-node instantiations, then enforce local diversity checks to reduce mode collapse.

## Acceptance criteria

- [x] Every sample is traceable to `taxonomy_node_id` and `meta_prompt_id`.
- [x] Local diversity checks run before complexification.
- [x] Rejected low-diversity candidates are logged.

---

### Issue 4: Implement complexification with semantic-preservation checks

**Type**: AFK  
**Blocked by**: Issue 3

## What to build

Apply complexification to a controlled sample fraction while preserving source intent and taxonomy assignment.

## Acceptance criteria

- [x] Complexification policy supports configurable fraction and strategy.
- [x] Complexified samples retain taxonomy linkage.
- [x] Semantic-preservation checks run and failures are recorded.

---

### Issue 5: Implement dual-critic adjudication and regeneration logs

**Type**: AFK  
**Blocked by**: Issue 4

## What to build

Add dual-critic evaluation, disagreement handling, and regeneration pathways to produce a curated dataset with auditable quality decisions.

## Acceptance criteria

- [x] Critic A and Critic B decisions are stored per sample.
- [x] Disagreement path is deterministic under configured policy.
- [x] Rejection/regeneration logs are persisted as artifacts.

---

### Issue 6: Implement metric computation and gate report generation

**Type**: AFK  
**Blocked by**: Issue 5

## What to build

Compute coverage, complexity, and quality metrics per `docs/evaluation-metrics.md` and generate a structured gate report.

## Acceptance criteria

- [x] Coverage metrics include node ratio and depth profile.
- [x] Complexity metrics include calibrated score and complexity shift.
- [x] Quality metrics include acceptance, agreement, and regeneration burden.
- [x] Gate report maps thresholds to pass/fail outcomes.

---

### Issue 7: Execute baseline and ablations with artifacted report outputs

**Type**: AFK  
**Blocked by**: Issue 6

## What to build

Run `B0` and at least `A1` and `A4` as defined in the playbook, then publish run comparison outputs under artifacts.

## Acceptance criteria

- [x] Baseline and required ablation runs complete under fixed protocol.
- [x] Comparison tables are generated and persisted.
- [x] Failure analysis notes are included for any failed gate.

---

### Issue 8: Milestone-1 gate review and threshold adjustment decision

**Type**: HITL  
**Blocked by**: Issue 7

## What to build

Conduct a human review of milestone-1 evidence, confirm pass/fail status, and explicitly decide whether threshold adjustments are needed.

## Acceptance criteria

- [x] Review includes coverage, complexity, and quality evidence (April packet + addendum `20260526T024251Z`).
- [ ] Decision recorded as pass, conditional pass, or fail for **current** packet — **pending human** on `milestone_gate_review_addendum_20260526T024251Z.json` (agent recommends **conditional pass**: B0/A4 pass, A1 documented complexity gap).
- [x] Any threshold change is justified and linked to ADR workflow (**keep thresholds**; no ADR edit proposed).

**Evidence:**

- Original: `artifacts/reports/issue8/milestone_gate_review.md` + `.json` → **fail** (`20260430T204744Z`)
- Addendum: `artifacts/reports/issue8/milestone_gate_review_addendum_20260526T024251Z.{md,json}` → gate tables from `artifacts/reports/issue7/20260526T024251Z/`

---

### Issue 9: Reproducibility hardening and deterministic rerun checks

**Type**: AFK  
**Blocked by**: Issue 8

## What to build

Enforce manifest completeness and execute deterministic rerun protocol on baseline to confirm replayability.
Treat reproducibility, audit traces, and fixed-protocol comparability as hard gates before any threshold tuning.

## Acceptance criteria

- [x] Manifest schema validation passes for all compared runs.
- [x] Baseline rerun is executed and classified (exact/acceptable drift/mismatch).
- [x] Reproducibility status is attached to milestone evidence.
- [x] Threshold tuning guard blocks changes unless reproducibility/audit/comparability hard gates pass.

---

### Issue 10: Decide reusable-engine extraction scope and boundaries

**Type**: HITL  
**Blocked by**: Issue 9

## What to build

Define which stage seams become reusable interfaces in next phase while preserving comparability guarantees from milestone 1.

## Acceptance criteria

- [x] Candidate interfaces are listed with rationale (ADR **0004**).
- [x] Migration scope excludes any change that invalidates baseline comparability.
- [x] Follow-up issue set approved (**#60–#62**).

## Recommendations: where to prompt next

1. **Issue #8 HITL sign-off (current)** — Review addendum JSON; record `human_sign_off`; confirm conditional pass for B0/A4 and A1 complexity documentation.
2. **Provider Phase 4** — `docs/llm-validation-readiness.md`: credentials, optional NIM smoke, provider-backed B0/A1/A4 matrix, Issue #9 rerun on provider packet.
3. **Playbook promotion** — After Phase 4, evaluate H1–H4 and second baseline stability per `docs/research-validation-playbook.md`.

For detailed wave-by-wave copy/paste prompts, use [`docs/parallel-agent-prompts.md`](./parallel-agent-prompts.md).
