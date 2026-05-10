# Next-agent handoff (Simula research repo)

Use this document as the **primary paste-in briefing** for a new coding agent. It reflects state after **Milestone 3** (GitHub **#27–#30**, **#10** closed) on `main`.

## What was just completed

- **#27** — `src/simula_research/stage_contracts.py`: runtime validation for Stage 1–4 handoffs; `run_pipeline` calls `validate_stage_handoffs` after adjudication; tests `tests/test_stage_contracts.py`; see `docs/pipeline-spec.md` (machine-readable contracts).
- **#28** — `src/simula_research/run_artifact_store.py`: `RunArtifactStore` protocol + `FileSystemRunArtifactStore`; `run_pipeline(..., artifact_store_factory=...)`.
- **#29** — `src/simula_research/provider_protocols.py`: `CriticVerdictFn`, `hash_based_critic_verdict`; `adjudicate_samples(..., critic_verdict=...)` and `run_pipeline(..., critic_verdict=...)`.
- **#30** — `evaluate_comparability_gate()` in `issue9_reproducibility.py`; tests `tests/test_issue30_comparability_gate.py`.

Relevant commits: **`df88524`** (contracts + comparability tests), **`73a0dc9`** (artifact store + critic hook).

## Non-negotiables (read before changing behavior)

1. **Do not** change evaluation **thresholds**, **metric formulas**, **ablation definitions**, or **protocol semantics** without paper-grounded justification and explicit **ADR `docs/adr/0003-evaluation-protocol-and-thresholds.md`** impact notes.
2. Preserve **baseline/ablation comparability** for milestone-1 evidence (`artifacts/reports/issue7/`, `issue8/`, `issue9/`) unless formally waived with rationale.
3. **Structured comparability**: deliberate `mixed` axes must set `mixed_reason: documented_ablation` (see `docs/reproducibility-ops.md` and `src/simula_research/issue9_reproducibility.py`).
4. **Control axes** (ADR **0002**): keep coverage, local diversity, complexity, and quality **separate** at stage boundaries—no silent merging of stages in public surfaces.

## Known follow-up (pick up in order)

1. **Artifact directory name drift** — `validators.REQUIRED_ARTIFACT_STAGES` lists `40_dual_critic` but the pipeline persists to **`40_dual_critic_quality`**. Fixing this touches **paths** and possibly **Issue #7–#9** evidence comparability. Do it only with: explicit decision, optional `artifact_schema_version` bump, migration note, and rerun of a **small** reproducibility smoke (manifest + comparability structure), not a silent rename.
2. **Generator / earlier-stage protocols** — **#29** only wired **critic verdict** injection. Taxonomy, local diversification, and complexification still use deterministic in-repo logic. When adding real LLM calls, inject behind **Protocols** with defaults that preserve **bit-identical** behavior on the default path.
3. **Stage 0 / manifest completeness** — `manifest.validate_manifest` is minimal; `validators.validate_manifest_schema` is the full reproducibility set. If you unify them, document the two modes and keep Issue **#9** gates passing.
4. **Optional typing** — TypedDict (or similar) **on top of** `stage_contracts` validators is a small, low-risk enhancement if you want editor-time checks.

## Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Workflow expectations (from `AGENTS.md` / repo rules)

- Medium/large work: align with **`docs/research_paper.pdf`**, ADRs **0001–0003**, `contexts/core/CONTEXT.md`, `contexts/eval/CONTEXT.md`, `docs/pipeline-spec.md`, `docs/evaluation-metrics.md`, `docs/reproducibility-ops.md`.
- Implementation: prefer **TDD** (red → green → refactor).
- Bugs/regressions: diagnose before speculative fixes.

## Paper Alignment Check (for your PR / issue comment)

Include: **traceability/auditability**, **protocol/comparability**, **control-axis impact**, **deviations** (or `none`).

## Issue tracker

Create new work as **GitHub Issues** (`gh issue create`); system of record is described in `docs/agents/issue-tracker.md`.
