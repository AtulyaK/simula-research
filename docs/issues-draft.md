# Simula Issues Draft (Vertical Slices)

## Purpose

This is a draft issue pack for implementation sequencing. These are not published yet. Slices are intentionally thin and end-to-end so each one yields a verifiable outcome.

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

- [ ] Taxonomy output is acyclic and has no orphan nodes.
- [ ] Every node has a stable `taxonomy_node_id`.
- [ ] Taxonomy artifacts are persisted in the run artifact layout.

---

### Issue 3: Implement local diversification with anti-collapse checks

**Type**: AFK  
**Blocked by**: Issue 2

## What to build

Generate meta-prompts and multiple within-node instantiations, then enforce local diversity checks to reduce mode collapse.

## Acceptance criteria

- [ ] Every sample is traceable to `taxonomy_node_id` and `meta_prompt_id`.
- [ ] Local diversity checks run before complexification.
- [ ] Rejected low-diversity candidates are logged.

---

### Issue 4: Implement complexification with semantic-preservation checks

**Type**: AFK  
**Blocked by**: Issue 3

## What to build

Apply complexification to a controlled sample fraction while preserving source intent and taxonomy assignment.

## Acceptance criteria

- [ ] Complexification policy supports configurable fraction and strategy.
- [ ] Complexified samples retain taxonomy linkage.
- [ ] Semantic-preservation checks run and failures are recorded.

---

### Issue 5: Implement dual-critic adjudication and regeneration logs

**Type**: AFK  
**Blocked by**: Issue 4

## What to build

Add dual-critic evaluation, disagreement handling, and regeneration pathways to produce a curated dataset with auditable quality decisions.

## Acceptance criteria

- [ ] Critic A and Critic B decisions are stored per sample.
- [ ] Disagreement path is deterministic under configured policy.
- [ ] Rejection/regeneration logs are persisted as artifacts.

---

### Issue 6: Implement metric computation and gate report generation

**Type**: AFK  
**Blocked by**: Issue 5

## What to build

Compute coverage, complexity, and quality metrics per `docs/evaluation-metrics.md` and generate a structured gate report.

## Acceptance criteria

- [ ] Coverage metrics include node ratio and depth profile.
- [ ] Complexity metrics include calibrated score and complexity shift.
- [ ] Quality metrics include acceptance, agreement, and regeneration burden.
- [ ] Gate report maps thresholds to pass/fail outcomes.

---

### Issue 7: Execute baseline and ablations with artifacted report outputs

**Type**: AFK  
**Blocked by**: Issue 6

## What to build

Run `B0` and at least `A1` and `A4` as defined in the playbook, then publish run comparison outputs under artifacts.

## Acceptance criteria

- [ ] Baseline and required ablation runs complete under fixed protocol.
- [ ] Comparison tables are generated and persisted.
- [ ] Failure analysis notes are included for any failed gate.

---

### Issue 8: Milestone-1 gate review and threshold adjustment decision

**Type**: HITL  
**Blocked by**: Issue 7

## What to build

Conduct a human review of milestone-1 evidence, confirm pass/fail status, and explicitly decide whether threshold adjustments are needed.

## Acceptance criteria

- [ ] Review includes coverage, complexity, and quality evidence.
- [ ] Decision is recorded as pass, conditional pass, or fail.
- [ ] Any threshold change is justified and linked to ADR workflow.

---

### Issue 9: Reproducibility hardening and deterministic rerun checks

**Type**: AFK  
**Blocked by**: Issue 8

## What to build

Enforce manifest completeness and execute deterministic rerun protocol on baseline to confirm replayability.

## Acceptance criteria

- [ ] Manifest schema validation passes for all compared runs.
- [ ] Baseline rerun is executed and classified (exact/acceptable drift/mismatch).
- [ ] Reproducibility status is attached to milestone evidence.

---

### Issue 10: Decide reusable-engine extraction scope and boundaries

**Type**: HITL  
**Blocked by**: Issue 9

## What to build

Define which stage seams become reusable interfaces in next phase while preserving comparability guarantees from milestone 1.

## Acceptance criteria

- [ ] Candidate interfaces are listed with rationale.
- [ ] Migration scope excludes any change that invalidates baseline comparability.
- [ ] Follow-up issue set or ADR updates are approved.

## Recommendations: where to prompt next

Use these prompts in order as you execute:

1. **Build start**  
   `Implement Issue 1 with TDD. Deliver one thin end-to-end tracer bullet for the pilot domain.`
2. **Core validation run**  
   `Implement Issues 2-6 in order, then run B0 + A1 + A4 and produce a milestone gate report.`
3. **If signals are weak**  
   `Use /diagnose to identify whether coverage, complexity, or quality is the bottleneck and propose smallest parameter-level change.`
4. **If issue size is too large**  
   `Split the current blocked issue into thinner AFK vertical slices with updated dependencies and revised acceptance criteria.`
5. **Promotion to next phase**  
   `Propose ADR updates and a follow-on issue set for reusable engine interfaces without breaking milestone-1 comparability.`

For detailed wave-by-wave copy/paste prompts, use [`docs/parallel-agent-prompts.md`](./parallel-agent-prompts.md).
