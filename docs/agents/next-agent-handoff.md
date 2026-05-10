# Next-agent handoff (Simula research repo)

Use this document as the **primary paste-in briefing** for a new coding agent. It reflects repository state **after Milestone 3** (GitHub **#27–#30**, **#10** closed) **and** post-Milestone-3 hardening merges **PR #32** / **PR #34** (Issues **#31**, **#33**) on `main`.

## Executive summary — what “done” means for this engineering cycle

The **first implementation cycle** (see `docs/implementation-plan.md`) is complete when:

1. **Milestone 1–2 evidence** exists and remains comparable: baseline + ablations, gate reports, reproducibility checks (`artifacts/reports/issue7/`, `issue8/`, `issue9/`).
2. **Milestone 3 seams** are on `main`: stage validators, artifact store protocol, critic verdict hook, comparability gate tests (**#27–#30**).
3. **Issue #10 (HITL)** is closed with an explicit decision: reusable-engine extraction scope, listed candidate interfaces, and approved follow-on issues or ADR updates—**without** waiving comparability unless formally recorded.

Optional engineering that **does not** block declaring the cycle “complete” for research ops but **does** block a clean “engine extraction” phase:

- Earlier-stage **generator protocols** (taxonomy, local diversification, complexification) with bit-identical defaults.
- **Manifest validation modes** documented or unified (`manifest.validate_manifest` vs `validators.validate_manifest_schema`).

---

## Recently merged (post–Milestone 3)

| PR | Issue | Summary |
| --- | --- | --- |
| **#32** | **#31** | `stage_contracts.py`: exported **TypedDict** shapes for Stages 1–4; test asserts default pipeline payloads validate after `typing.cast`. |
| **#34** | **#33** | `validators.REQUIRED_ARTIFACT_STAGES`: stage-4 dir **`40_dual_critic_quality`** aligned with `FileSystemRunArtifactStore`; `docs/reproducibility-ops.md` migration note; contract test. |

**Canonical on-disk stage-4 directory:** `40_dual_critic_quality/` (not `40_dual_critic/`).

---

## What was already completed (Milestone 3 baseline)

- **#27** — `src/simula_research/stage_contracts.py`: runtime validation for Stage 1–4 handoffs; `run_pipeline` calls `validate_stage_handoffs` after adjudication; tests `tests/test_stage_contracts.py`; see `docs/pipeline-spec.md`.
- **#28** — `src/simula_research/run_artifact_store.py`: `RunArtifactStore` protocol + `FileSystemRunArtifactStore`; `run_pipeline(..., artifact_store_factory=...)`.
- **#29** — `src/simula_research/provider_protocols.py`: `CriticVerdictFn`, `hash_based_critic_verdict`; `adjudicate_samples(..., critic_verdict=...)` and `run_pipeline(..., critic_verdict=...)`.
- **#30** — `evaluate_comparability_gate()` in `issue9_reproducibility.py`; tests `tests/test_issue30_comparability_gate.py`.

Landmark commits (historical): **`df88524`** (contracts + comparability tests), **`73a0dc9`** (artifact store + critic hook).

---

## Testing and environment prerequisites (read before running or extending tests)

### Required (minimal — default deterministic pipeline)

| Resource | Detail |
| --- | --- |
| **Python** | **3.11+** recommended (repo CI/agents have used 3.13; stdlib **TypedDict** `Required` / `NotRequired` need 3.11+). |
| **Stdlib only** | No `pip install` is required for the current test suite; tests use `unittest` only. |
| **Layout** | Run tests from repo root: `PYTHONPATH=src python3 -m unittest discover -s tests -v` |

### Optional but recommended

| Resource | Detail |
| --- | --- |
| **`gh` CLI** | For `gh issue create`, `gh pr create`, `gh pr merge`; authenticated GitHub user. See `docs/agents/issue-tracker.md`. |
| **Git** | For branches, merges, reproducibility checkout by `commit_hash` in manifests. |

### Not required today (future LLM-backed runs)

| Resource | When it becomes relevant |
| --- | --- |
| **API keys** (OpenAI, Anthropic, etc.) | Only when replacing deterministic stubs with real providers; default path is **hash-based** critic and in-repo generators—**no network keys** for unittest. |
| **GPU** | Not used by current code paths. |
| **Paid CI minutes** | If you attach GitHub Actions; local unittest is free. |

### Evidence paths (do not delete casually)

- `artifacts/reports/issue7/` — execution matrix outputs  
- `artifacts/reports/issue8/` — milestone gate review  
- `artifacts/reports/issue9/` — reproducibility hardening  

Regenerating runs: use `run_pipeline` / Issue #7 tooling; new runs land under `artifacts/runs/<run_id>/` (often gitignored or untracked—confirm `.gitignore` before committing large trees).

---

## Non-negotiables (read before changing behavior)

1. **Do not** change evaluation **thresholds**, **metric formulas**, **ablation definitions**, or **protocol semantics** without paper-grounded justification and explicit **ADR `docs/adr/0003-evaluation-protocol-and-thresholds.md`** impact notes.
2. Preserve **baseline/ablation comparability** for milestone-1 evidence (`artifacts/reports/issue7/`, `issue8/`, `issue9/`) unless formally waived with rationale.
3. **Structured comparability**: deliberate `mixed` axes must set `mixed_reason: documented_ablation` (see `docs/reproducibility-ops.md` and `src/simula_research/issue9_reproducibility.py`).
4. **Control axes** (ADR **0002**): keep coverage, local diversity, complexity, and quality **separate** at stage boundaries—no silent merging of stages in public surfaces.

---

## Prioritized follow-ups (pick up in order to “finish the project”)

### P0 — Close the engineering cycle (HITL)

1. **Issue #10 — Reusable-engine extraction scope (HITL)**  
   - **Goal:** List candidate interfaces, migration boundaries, and approved follow-on GitHub issues or ADRs.  
   - **Blocker:** Human decision; agent can draft options, not approve.  
   - **Acceptance:** Issue #10 acceptance criteria in `docs/issues-draft.md` all checked with links to ADR/issue updates.

### P1 — Strongly recommended before real LLM integration

2. **Sample-aware critic + execution fidelity + metadata (implemented together — verify PR / branch before relying on `main`)**  
   - **#22** `CriticSampleEvaluatorFn` + `sample_evaluator_from_text_fn` / `recorded_sample_evaluator`; `run_pipeline(..., critic_sample_evaluator=...)` (mutually exclusive with `critic_verdict`).  
   - **#41** optional `provider_runtime` on manifest + stage 4 echo; `provider_runtime_from_env()` for operator transport metadata (no secrets).  
   - **#42** `pipeline_config` presets passed from `execute_issue7_matrix` into `run_pipeline` (A1 shallow taxonomy, A4 `single_critic_mode`, etc.); reporting-only A1/A4 metric hacks removed.  
   - **Adapter:** `src/simula_research/critic_provider_adapter.py` — `SIMULA_CRITIC_BACKEND` (`stub` / `replay`), retry helper, failure logging wrapper.

3. **Generator / earlier-stage protocols**  
   - **#29** only injected **critic verdict**. Taxonomy, local diversification, and complexification are still deterministic in-repo logic.  
   - **Goal:** `Protocol` + factory hooks mirroring `critic_verdict` / `artifact_store_factory`, with **bit-identical** default factories.  
   - **Tests:** Same golden outputs as current `run_pipeline` for default factories.

4. **Stage 0 / manifest completeness**  
   - `manifest.validate_manifest` is **minimal** (pipeline boot).  
   - `validators.validate_manifest_schema` is the **full** reproducibility set (Issue #9).  
   - **Goal:** Document “fast boot” vs “full reproducibility” modes in code + `docs/reproducibility-ops.md`, or unify with explicit mode flag—**must** keep `tests/test_issue9_reproducibility.py` green.

### P2 — Done (reference only)

- ~~Artifact directory name drift~~ — **#33** merged (**#34**): validators + docs aligned to `40_dual_critic_quality/`.  
- ~~Optional typing on stage contracts~~ — **#31** merged (**#32**): TypedDict exports in `stage_contracts.py`.

---

## Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

---

## Workflow expectations (from `AGENTS.md` / repo rules)

- Medium/large work: align with **`docs/research_paper.pdf`**, ADRs **0001–0003**, `contexts/core/CONTEXT.md`, `contexts/eval/CONTEXT.md`, `docs/pipeline-spec.md`, `docs/evaluation-metrics.md`, `docs/reproducibility-ops.md`.
- Implementation: prefer **TDD** (red → green → refactor).
- Bugs/regressions: diagnose before speculative fixes (`/diagnose` skill when applicable).

---

## Paper Alignment Check (for your PR / issue comment)

Include: **traceability/auditability**, **protocol/comparability**, **control-axis impact**, **deviations** (or `none`).

---

## Issue tracker

Create new work as **GitHub Issues** (`gh issue create`); system of record is described in `docs/agents/issue-tracker.md`.

---

## Cross-references (planning pack)

| Document | Use |
| --- | --- |
| `docs/issues-draft.md` | Issue acceptance criteria + verification snapshot |
| `docs/implementation-plan.md` | Milestones 1–3 definitions and dependency map |
| `docs/parallel-agent-prompts.md` | Copy/paste agent prompts + wave status table |
| `docs/README.md` | Documentation index |
