# Next-agent handoff (Simula research repo)

Use this document as the **primary paste-in briefing** for a new coding agent. It reflects `main` as of **2026-05-26**: Milestones **1–3** complete, Issue **#10** closed with **ADR 0004**, post-M3 hardening (**#31–#34** / PRs **#32**, **#34**), and LLM/correctness merges **PRs #45**, **#54**, **#56**, **#58**.

## Executive summary — two “done” notions

### First implementation cycle (engineering) — **closed**

Per `docs/implementation-plan.md` and **ADR 0004**:

1. **Milestones 1–2 evidence** remains comparable: baseline + ablations, gate reports, reproducibility (`artifacts/reports/issue7/`, `issue8/`, `issue9/`).
2. **Milestone 3 seams** on `main`: stage validators, artifact store, critic hooks, comparability gates (**#27–#30**).
3. **Issue #10** closed with **ADR 0004** (Option A): minimal seam formalization; follow-ons **#60–#62** filed; engine-core refactor deferred.

### Full provider-backed validation cycle — **not closed**

Tracked in `docs/llm-validation-readiness.md` (Phases 0–4). Remaining before a defensible **provider-backed** milestone packet:

- Optional live **NIM** smoke (`SIMULA_CRITIC_BACKEND=nim` + API key; org policy).
- **#60** / **#61** (recommended before swapping Stages 1–3): protocol hooks with bit-identical defaults; manifest boot vs full-schema operator clarity.
- Execute provider-backed **B0 / A1 / A4**, persist gate + comparison artifacts, baseline rerun classification, and gate recommendation — without changing ADR **0003** thresholds or metric formulas.

---

## `main` health (2026-05-26)

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

| Check | Status |
| --- | --- |
| Unit tests | **74 tests, OK** (stdlib `unittest` only; no `pip install`) |
| Python | **3.11+** (3.13 used in CI/agents) |
| API keys (unittest) | **Not required** (hash/stub/replay critics; deterministic Stages 1–3) |
| API keys (live NIM critic) | `NVIDIA_API_KEY` or `NVAPI_KEY` when `SIMULA_CRITIC_BACKEND=nim` |

---

## Recently merged

### Post–Milestone 3 hardening

| PR | Issue | Summary |
| --- | --- | --- |
| **#32** | **#31** | `stage_contracts.py`: exported **TypedDict** shapes for Stages 1–4. |
| **#34** | **#33** | `validators.REQUIRED_ARTIFACT_STAGES` → **`40_dual_critic_quality/`** aligned with artifact store. |

### LLM seams, correctness, operator docs

| PR | Issue(s) | Summary |
| --- | --- | --- |
| **#45** | **#22**, **#41**, **#42** | `CriticSampleEvaluatorFn`, `provider_runtime` metadata, `pipeline_config` execution fidelity for B0/A1/A4 (no report-only ablation hacks). |
| **#54** | **#51** | Regenerated accepted samples persist final text + critic decisions in `accepted_samples`. |
| **#56** | **#39**, **#50** | `docs/llm-validation-readiness.md`: NIM env vars, smoke commands, phase checklist updates. |
| **#58** | **#47** | Fail-closed **NIM** critic backend; `provider_runtime.json` under stage 4; network-free NIM smoke test. |

**Canonical on-disk stage-4 directory:** `40_dual_critic_quality/` (not `40_dual_critic/`).

---

## Issue #10 decision (ADR 0004)

**Approved scope:** Option A — minimal seam formalization (`docs/adr/0004-engine-seam-scope.md`).

| On `main` today | Open P1 follow-ons | Deferred |
| --- | --- | --- |
| Stage contracts, `RunArtifactStore`, critic verdict + sample evaluator, comparability gate, `pipeline_config` ablations | **#60** Stage 1–3 protocols (bit-identical defaults); **#61** manifest boot vs full schema | **#62** engine-core refactor (Option B) |

**Do-not-break:** ADR **0003** thresholds/metrics/gates; Issue **#9** comparability + `mixed_reason`; artifact layout; default TypedDict handoffs; metrics from **persisted artifacts** only.

---

## LLM validation readiness (phase snapshot)

See `docs/llm-validation-readiness.md` for full checklist. Summary:

| Phase | Focus | Status on `main` |
| --- | --- | --- |
| **0** | Freeze protocol / run discipline | Met for deterministic pilot evidence; reuse playbook for provider batch |
| **1** | Smallest real-LLM surface (Stage 4 critics) | **Mostly met**: sample evaluator seam, env adapter (`stub` / `replay` / `nim`), fail-closed NIM, provider metadata echo |
| **2** | Stages 1–3 provider hooks | **Open — #60** (defaults must stay bit-identical) |
| **3** | True ablation execution fidelity | **Met — #42** via `pipeline_config` in `execute_issue7_matrix` |
| **4** | Full provider-backed validation packet | **Not met** — needs live matrix runs + gate/comparison artifacts + rerun classification |

**Operator backends:** `SIMULA_CRITIC_BACKEND` in `critic_provider_adapter.py` — `stub` / `replay` (no network); `nim` / `nvidia` (live, fail-closed). Details in `docs/research-validation-playbook.md` and `docs/llm-validation-readiness.md`.

---

## Prioritized follow-ups

### P1 — Ready for agents (`ready-for-agent`)

1. **#60 — Protocol hooks for Stages 1–3** — mirror `critic_verdict` / `artifact_store_factory`; golden tests vs current `run_pipeline` outputs.

2. **#61 — Manifest validation modes** — document and/or unify `manifest.validate_manifest` (pipeline boot) vs `validators.validate_manifest_schema` (Issue #9 full set); keep `tests/test_issue9_reproducibility.py` green.

### P2 — Human / deferred

- **#62 — Engine core refactor (Option B)** — deferred per ADR 0004; requires explicit human approval before large refactors.

### P3 — Provider validation batch (after P1 or explicit waiver)

- Configure org credentials/budget guardrails.
- Run optional NIM smoke, then B0 → A1 → A4 with persisted `artifacts/runs/` + reports under `artifacts/reports/`.
- Record reproducibility classification and gate recommendation; no threshold changes without ADR **0003** process.

---

## What was already completed (Milestone 3 baseline)

- **#27** — `stage_contracts.py`: runtime validation for Stage 1–4 handoffs.
- **#28** — `RunArtifactStore` + `FileSystemRunArtifactStore`.
- **#29** — `CriticVerdictFn`, `hash_based_critic_verdict`.
- **#30** — `evaluate_comparability_gate()`; `tests/test_issue30_comparability_gate.py`.

Landmark commits (historical): **`df88524`**, **`73a0dc9`**.

---

## Testing and environment prerequisites

### Required (default deterministic pipeline)

| Resource | Detail |
| --- | --- |
| **Python** | **3.11+** |
| **Stdlib only** | No `pip install` for unittest |
| **Command** | `PYTHONPATH=src python3 -m unittest discover -s tests -v` |

### Optional

| Resource | Detail |
| --- | --- |
| **`gh` CLI** | Issues/PRs; see `docs/agents/issue-tracker.md` |
| **Git** | Branch/commit traceability in manifests |

### Provider-backed runs (not unittest)

| Resource | Detail |
| --- | --- |
| **NVIDIA NIM** | `SIMULA_CRITIC_BACKEND=nim`, `NVIDIA_API_KEY` or `NVAPI_KEY` |
| **Budget / policy** | Org guardrails per `docs/llm-validation-readiness.md` |

### Evidence paths (do not delete casually)

- `artifacts/reports/issue7/`, `issue8/`, `issue9/`
- `artifacts/reports/llm-smoke/` — stub/replay smoke incidents
- `artifacts/runs/<run_id>/` — per-run stage trees (often untracked)

---

## Non-negotiables

1. **No** ADR **0003** threshold/metric/gate changes without paper-grounded justification + ADR impact notes.
2. Preserve milestone-1 comparability evidence unless formally waived.
3. Structured comparability: `mixed` axes need `mixed_reason: documented_ablation`.
4. **ADR 0002:** independent coverage, complexity, quality at stage boundaries.
5. **ADR 0004:** new Protocol hooks use **bit-identical** default factories unless comparability is waived in writing.

---

## Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

---

## Workflow expectations

- Align with `docs/research_paper.pdf`, ADRs **0001–0004**, `contexts/core/CONTEXT.md`, `contexts/eval/CONTEXT.md`, `docs/pipeline-spec.md`, `docs/evaluation-metrics.md`, `docs/reproducibility-ops.md`, `docs/llm-validation-readiness.md`.
- Implementation: prefer **TDD**.
- Bugs: **/diagnose** before speculative fixes.

---

## Paper Alignment Check (for your PR / issue comment)

Include: **traceability/auditability**, **protocol/comparability**, **control-axis impact**, **deviations** (or `none`).

---

## Cross-references

| Document | Use |
| --- | --- |
| `docs/adr/0004-engine-seam-scope.md` | Issue #10 scope + invariants |
| `docs/llm-validation-readiness.md` | Provider rollout phases + readiness checklist |
| `docs/issues-draft.md` | Issue acceptance criteria + verification snapshot |
| `docs/implementation-plan.md` | Milestones + live status table |
| `docs/parallel-agent-prompts.md` | Agent prompt library |
