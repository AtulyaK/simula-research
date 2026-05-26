# Next-agent handoff (Simula research repo)

Use this document as the **primary paste-in briefing** for a new coding agent. It reflects `main` as of **2026-05-26** (`af9be6f`): Milestones **1–3** complete, Issue **#10** closed with **ADR 0004**, post-M3 hardening, LLM/correctness merges (**PRs #45**, **#54**, **#56**, **#58**), P1 follow-ons **#60–#61** closed, and Milestone-1 gate remediation **PR #69** merged.

## Executive summary — two “done” notions

### First implementation cycle (engineering) — **closed**

Per `docs/implementation-plan.md` and **ADR 0004**:

1. **Milestones 1–2 evidence** remains comparable: baseline + ablations, gate reports, reproducibility (`artifacts/reports/issue7/`, `issue8/`, `issue9/`).
2. **Milestone 3 seams** on `main`: stage validators, artifact store, critic hooks, comparability gates (**#27–#30**).
3. **Issue #10** closed with **ADR 0004** (Option A); **#60–#61** closed; **#62** deferred (Option B refactor).

### Milestone-1 gate evidence on `main` (packet `20260526T024251Z`, PR **#69**)

| Preset | Overall gate | Notes |
| --- | --- | --- |
| **B0** | **pass** | All six ADR 0003 thresholds pass |
| **A4** | **pass** | All six thresholds pass (`single_critic` ablation) |
| **A1** | **fail** | `complexity.complexification_precision` = 0.667 &lt; 0.70 (3-sample, single-node ablation) |

**Issue #8:** April 2026 HITL review remains **fail** on older packet (`20260430T204744Z`). Addendum **`20260526T024251Z`** supersedes gate tables for the remediated packet only; **human sign-off pending** on [`milestone_gate_review_addendum_20260526T024251Z.json`](../artifacts/reports/issue8/milestone_gate_review_addendum_20260526T024251Z.json) (recommended: **conditional pass** for B0/A4, document A1 gap).

### Full provider-backed validation cycle — **not closed**

Tracked in `docs/llm-validation-readiness.md` (Phase 4). Remaining before a defensible **provider-backed** milestone packet:

- Org credentials / budget guardrails (human policy).
- Optional live **NIM** smoke (`SIMULA_CRITIC_BACKEND=nim`).
- Provider-backed **B0 / A1 / A4** matrix with persisted gate + comparison artifacts and baseline rerun classification — **no ADR 0003** threshold or metric formula changes.

---

## `main` health (2026-05-26)

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

| Check | Status |
| --- | --- |
| Unit tests | **93 tests, OK** (stdlib `unittest` only; no `pip install`) |
| Python | **3.11+** (3.13 used in CI/agents) |
| API keys (unittest) | **Not required** (hash/stub/replay critics; deterministic Stages 1–3) |
| API keys (live NIM critic) | `NVIDIA_API_KEY` or `NVAPI_KEY` when `SIMULA_CRITIC_BACKEND=nim` |

**Latest `main` tip:** `af9be6f` (merge PR #69).

---

## Recently merged

### Milestone-1 gate remediation

| PR | Summary |
| --- | --- |
| **#69** | Lane-diversified local instantiations + lineage-keyed offline critic evaluator; Issue #7 packet `20260526T024251Z` (**B0/A4 pass**, **A1 fail** on complexity precision). |

### P1 engineering (ADR 0004 follow-ons)

| PR | Issue | Summary |
| --- | --- | --- |
| (direct) | **#60** | Protocol hooks for Stages 1–3 (bit-identical defaults). |
| **#61** | **#61** | Manifest boot vs full-schema operator clarity. |

### Post–Milestone 3 hardening

| PR | Issue | Summary |
| --- | --- | --- |
| **#32** | **#31** | `stage_contracts.py`: exported **TypedDict** shapes for Stages 1–4. |
| **#34** | **#33** | `validators.REQUIRED_ARTIFACT_STAGES` → **`40_dual_critic_quality/`** aligned with artifact store. |

### LLM seams, correctness, operator docs

| PR | Issue(s) | Summary |
| --- | --- | --- |
| **#45** | **#22**, **#41**, **#42** | `CriticSampleEvaluatorFn`, `provider_runtime` metadata, `pipeline_config` execution fidelity for B0/A1/A4. |
| **#54** | **#51** | Regenerated accepted samples persist final text + critic decisions. |
| **#56** | **#39**, **#50** | `docs/llm-validation-readiness.md`: NIM env vars, smoke commands, phase checklist. |
| **#58** | **#47** | Fail-closed **NIM** critic backend; `provider_runtime.json` under stage 4. |

**Canonical on-disk stage-4 directory:** `40_dual_critic_quality/` (not `40_dual_critic/`).

---

## Issue #10 decision (ADR 0004)

**Approved scope:** Option A — minimal seam formalization (`docs/adr/0004-engine-seam-scope.md`).

| On `main` today | Closed follow-ons | Deferred |
| --- | --- | --- |
| Stage contracts, `RunArtifactStore`, critic verdict + sample evaluator, comparability gate, `pipeline_config` ablations, Stages 1–3 protocol hooks (#60), manifest validation modes (#61) | **#60**, **#61** | **#62** engine-core refactor (Option B) |

**Do-not-break:** ADR **0003** thresholds/metrics/gates; Issue **#9** comparability + `mixed_reason`; artifact layout; default TypedDict handoffs; metrics from **persisted artifacts** only.

---

## LLM validation readiness (phase snapshot)

See `docs/llm-validation-readiness.md` for full checklist. Summary:

| Phase | Focus | Status on `main` |
| --- | --- | --- |
| **0** | Freeze protocol / run discipline | Met for deterministic pilot evidence |
| **1** | Smallest real-LLM surface (Stage 4 critics) | **Met** (seams + stub/replay/NIM path) |
| **2** | Stages 1–3 provider hooks | **Met — #60** (bit-identical defaults) |
| **3** | True ablation execution fidelity | **Met — #42** |
| **4** | Full provider-backed validation packet | **Not met** — live matrix + gate/comparison + rerun on provider runs |

---

## Prioritized follow-ups

### P0 — Human (`ready-for-human`)

1. **Issue #8 addendum sign-off** — review `artifacts/reports/issue8/milestone_gate_review_addendum_20260526T024251Z.{md,json}`; record `human_sign_off` in JSON; confirm **conditional pass** vs fail.

### P2 — Human / deferred

- **#62 — Engine core refactor (Option B)** — deferred per ADR 0004.

### P3 — Provider validation batch (Phase 4)

- Configure org credentials/budget guardrails.
- Optional NIM smoke, then provider-backed B0 → A1 → A4 with persisted `artifacts/runs/` + reports.
- Re-run Issue #9 baseline rerun classification on provider packet; gate recommendation — **no ADR 0003** changes.

**Open PRs (2026-05-26):** draft **#68** (dual-critic correctness) — not required for deterministic milestone evidence.

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
