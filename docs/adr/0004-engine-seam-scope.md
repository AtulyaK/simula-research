# ADR 0004: Engine seam scope (Issue #10 — Option A)

## Status

Accepted (HITL, 2026-05-26)

## Context

Milestone 3 delivered reusable seams for stage handoff contracts, artifact persistence, and critic verdict injection (#27–#30). Issue #10 asked which additional boundaries become stable interfaces without invalidating Milestone 1–3 evidence (`artifacts/reports/issue7/`, `issue8/`, `issue9/`) or ADR 0003 evaluation protocol semantics.

## Decision

**Option A — Minimal seam formalization.**

- Keep current stage implementations in-repo; do **not** pursue a standalone “engine package” or broad module relocation (Options B/C) in this phase.
- **Already in scope (done on `main`):**
  - Stage 1–4 handoff contracts (`stage_contracts.py`, TypedDict exports)
  - `RunArtifactStore` + `FileSystemRunArtifactStore` (`run_pipeline(..., artifact_store_factory=...)`)
  - Critic injection (`CriticVerdictFn`, `CriticSampleEvaluatorFn` via #22 / PR #45)
  - Comparability hard-gates (`evaluate_comparability_gate`, structured `mixed_reason`)
- **Approved next extraction (follow-on issues):**
  - Protocol + factory hooks for **Stages 1–3** (taxonomy, local diversification, complexification), mirroring the critic/artifact pattern
  - Default factories must remain **bit-identical** to current deterministic logic (golden / contract tests required)
  - Operator clarity for **manifest validation modes** (boot vs full reproducibility schema)
- **Explicitly deferred:** “engine core” refactor into a separate module tree (Option B) until P1 seams are stable under repeated runs.

## Do-not-break invariants

### Comparability and protocol

- No changes to evaluation **thresholds**, **metric formulas**, **ablation definitions**, or **gate semantics** without ADR 0003-grounded justification.
- Intentionally non-uniform axes must record `status: mixed` **and** `mixed_reason: documented_ablation` (Issue #9 hard-gates).
- Comparable runs require fixed: domain objective, taxonomy eligibility policy, complexity judgment protocol, critic configuration + adjudication policy, artifact schema version (`v1`).

### Artifact schema and on-disk layout

- Manifest required fields remain semantically consistent (see `validators.validate_manifest_schema` and `docs/reproducibility-ops.md`).
- Stage 4 directory name remains **`40_dual_critic_quality/`** (validator + `FileSystemRunArtifactStore` aligned).
- Metrics are computed from **persisted artifacts**, not transient logs.

### Stage contracts and control axes

- Default pipeline execution must satisfy existing Stage 1–4 TypedDict handoff shapes.
- Stage boundary independence (ADR 0002): no silent merging of coverage, complexity, and quality responsibilities across public seams.

## Alternatives considered

- **Option B:** Moderate in-repo “engine core” module boundary (orchestration + registry + relocated stages). Rejected for this phase — higher contract-drift risk, limited research signal.
- **Option C:** Externalizable engine + CLI/config system. Rejected — premature per ADR 0001; highest comparability risk.

## Consequences

- First implementation cycle can be declared closed once this ADR and follow-on issues are linked from Issue #10.
- LLM/provider integration proceeds via existing critic seams; Stage 1–3 swaps remain a bounded P1 slice.
- Option B refactor remains optional and must re-validate Issue #9 tests and milestone evidence comparability.

## Follow-up triggers

Revisit this ADR when:

- Stage 1–3 protocol hooks ship with bit-identical defaults and green golden tests, or
- A second domain/pilot requires a shared import surface beyond Protocol injection.

## References

- Issue #10 (scope decision), Milestone 3 issues #27–#30
- Follow-on issues: **#60** (Stage 1–3 protocols), **#61** (manifest validation modes), **#62** (optional engine core refactor — deferred)
- `docs/agents/next-agent-handoff.md`
- `docs/pipeline-spec.md`, `docs/reproducibility-ops.md`
