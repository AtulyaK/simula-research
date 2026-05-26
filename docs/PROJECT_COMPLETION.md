# Simula Research — Project Completion Status

**Branch:** `main` @ `fc43471` (2026-05-26) · **Scope:** research-phase **engineering** (ADR 0001–0004, Milestones 1–3)

## Verdict

**Yes — the research-phase engineering scope is complete.**

Deterministic milestone evidence, reproducibility hard gates, LLM critic seams (stub/replay/NIM path), and operator scripts for a future provider batch are on `main`. What remains is **optional** live NIM validation and **post-engineering** playbook promotion to integration planning—not blockers for closing the implementation cycle.

---

## Done (engineering)

| Area | Status | Evidence |
| --- | --- | --- |
| **Milestone 1** — runnable B0/A1/A4 + gates | **Complete** | Canonical packet `artifacts/reports/issue7/20260526T025931Z/` — **B0/A1/A4 all pass** (PR #70 A1 `complexify_fraction` policy; commit-pinned rerun) |
| **Milestone 2** — manifest + rerun classification | **Complete** | Issue #9 hard gates **pass**; baseline rerun **`exact`** (Δ=0.0) on 2026-05-26 rerun |
| **Milestone 3** — reusable seams | **Complete** | Stage contracts, artifact store, critic hooks, comparability gate (#27–#30); ADR 0004 Option A closed (#60–#61) |
| **Unit tests** | **98 tests OK** | `PYTHONPATH=src python3 -m unittest discover -s tests -v` |
| **LLM readiness Phases 0–3** | **Met** | Seams, ablation fidelity, Stages 1–3 hooks, operator docs (PRs #45–#58, #73) |
| **Phase 4 operator wiring** | **Met (deterministic)** | `scripts/run_issue7_matrix.sh`, `scripts/run_issue9_comparability_check.sh`; drift policy in `docs/provider-stochastic-reproducibility-policy.md` |

**Issue #9 comparability check (2026-05-26, main):**

```text
baseline_rerun_classification exact
max_metric_delta 0.0
hard_gates_all_pass True
```

Baseline gate reference: `artifacts/reports/issue7/20260526T025931Z/B0/gate_report.json` (default `./scripts/run_issue9_comparability_check.sh` on `main`).

---

## Optional (not required to close engineering)

| Item | Notes |
| --- | --- |
| **Live NIM smoke** | `SIMULA_CRITIC_BACKEND=nim` + `NVIDIA_API_KEY`; recommended before a **provider-backed** validation packet, not for deterministic milestone closure |
| **Provider-backed Phase 4 matrix** | Full B0/A1/A4 with live critics, gate/comparison artifacts, and Issue #9 rerun under `acceptable_drift` policy — tracked in `docs/llm-validation-readiness.md` |
| **Playbook promotion → integration planning** | Requires H1–H4 hypothesis acceptance or bounded interpretation, ≥2 stable baseline trends, and documented provider risks (`docs/research-validation-playbook.md`) — **after** optional provider batch |
| **#62 engine-core refactor** | Deferred (ADR 0004 Option B) |

---

## Human actions

**None required** to mark **engineering** complete if Issue #8 addendum sign-off is recorded.

| Action | Status |
| --- | --- |
| Issue #8 HITL sign-off | **Pending** — `artifacts/reports/issue8/milestone_gate_review_addendum_20260526T025931Z.json` (`human_sign_off.status`: `pending`); agent recommends **conditional pass** for B0/A1/A4 on packet `20260526T025931Z` |
| Org credentials / budget for NIM | Optional — only for live provider validation |

---

## Checklist — research-validation-playbook promotion criteria

| Criterion | Engineering (deterministic) | Provider promotion |
| --- | --- | --- |
| H1–H4 accepted or bounded | Directional contrasts in comparison tables (e.g. A1 single-node vs B0 depth profile); hash-default critics limit H4 signal | Re-evaluate with live critics |
| ≥2 stable baseline runs | **Yes** — B0 packets `20260526T024251Z`, `20260526T025231Z` (both pass) | Repeat on provider packet |
| Reproducibility without manual reconstruction | **Yes** — Issue #9 **`exact`** rerun | Classify under stochastic drift policy |
| Risks documented with owners | A1 ablation small-*n* policy documented; provider drift/cost in readiness guide | Update after NIM batch |

---

## Checklist — llm-validation-readiness Phase 4

| Step | Status |
| --- | --- |
| Execute B0, A1, A4 | **Done (deterministic/hash)** — Issue #7 matrix packets on `main` |
| Run/gate/comparison reports persisted | **Done** — `artifacts/reports/issue7/` |
| Baseline rerun classification | **Done** — `exact` via `./scripts/run_issue9_comparability_check.sh` |
| Milestone gate recommendation | **Conditional pass** recommended (all presets pass on `20260526T025931Z`; HITL JSON pending) |
| **Provider-backed** equivalent packet | **Not done** — optional; requires keys + org policy |

---

## Paper Alignment Check

- **Traceability/Auditability:** Run IDs, gate/run reports, comparison tables, and manifest fields preserved under `artifacts/reports/` and `artifacts/runs/`.
- **Protocol/Comparability:** ADR 0003 thresholds and formulas unchanged; A4 `mixed_reason: documented_ablation`; A1 uses documented preset-only `complexify_fraction` variance.
- **Control-axis impact:** Coverage/complexity/quality evaluated independently; remediation targeted sample budget and A1 ablation policy without cross-axis metric edits.
- **Deviations:** none on thresholds or metric formulas.

---

## References

- `docs/implementation-plan.md` · `docs/agents/next-agent-handoff.md`
- `docs/research-validation-playbook.md` · `docs/llm-validation-readiness.md`
- Latest gate packet: `artifacts/reports/issue7/20260526T025931Z/`
