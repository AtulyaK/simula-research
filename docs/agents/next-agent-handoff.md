# Next-agent handoff (Simula research repo)

Use this document as the **primary paste-in briefing** for a new coding agent. It reflects `main` as of **2026-05-26** (`242232e`): research **implementation** and **deterministic validation** are **COMPLETE**; Issue **#8** HITL addendum **signed conditional_pass** on packet `20260526T025931Z` (PR **#76**). Phase 4 NIM/provider validation is an **optional post-completion track**.

## Final project completion assessment (2026-05-26)

| Track | Status |
| --- | --- |
| **Implementation (Milestones 1–3 + ADR 0004 Option A)** | **Complete** on `main` |
| **Deterministic validation** | **Complete** — 98 unittest cases OK; Issue #7 packet **`20260526T025931Z`** (**B0/A1/A4 pass**); Issue #9 exact rerun; LLM readiness Phases 0–3 met |
| **Provider-backed validation (Phase 4)** | **Optional post-completion track** — org credentials / NIM keys (human); not required for engineering closure |
| **Issue #62 (engine-core refactor, Option B)** | **Closed — wontfix / deferred** per ADR 0004 (not required for research phase) |

### Optional post-completion (no agent engineering required)

1. **NVIDIA NIM / org policy (Phase 4)** — `NVIDIA_API_KEY` or `NVAPI_KEY`, budget guardrails, and optional live smoke before provider-backed B0/A1/A4 matrix runs (`docs/llm-validation-readiness.md`).

**Issue #8:** signed **conditional_pass** on [`milestone_gate_review_addendum_20260526T025931Z.json`](../artifacts/reports/issue8/milestone_gate_review_addendum_20260526T025931Z.json) (`project-owner-delegated`, `2026-05-26T03:08:34Z`). April 2026 **fail** preserved in `milestone_gate_review.md` and `decision_history`.

Agents should **not** reopen Milestone 1–3 implementation unless a regression is filed or ADR 0003 is formally revised.

---

## Historical completion summary — two “done” notions

## Active continuation: paper replication

The engineering closure described below is historical. The active task is now
to improve fidelity to `docs/research_paper.pdf`; see
[`docs/paper-replication-matrix.md`](../paper-replication-matrix.md) for the
claim-to-evidence inventory. The full executable matrix is B0/A1/A2/A3/A4/A5,
but only B0 is the reference run and A1-A5 are documented validation
ablations. A live NIM/Kimi batch judge is now connected to the BS/N Elo
scheduler, with deterministic replay coverage, and a configurable remote
embedding seam now fronts the deterministic diversity fallback. The next
high-value slices are validating a supported embedding deployment, remaining
dataset adapters, and a downstream evaluation seam.

### Research engineering + deterministic validation — **closed**

Per `docs/implementation-plan.md` and **ADR 0004**:

1. **Milestones 1–2 evidence** comparable: baseline + ablations, gate reports, reproducibility (`artifacts/reports/issue7/`, `issue8/`, `issue9/`).
2. **Milestone 3 seams** on `main`: stage validators, artifact store, critic hooks, comparability gates (**#27–#30**).
3. **Issue #10** closed with **ADR 0004** (Option A); **#60–#61** closed; **#62** closed deferred.
4. **Canonical M1 gate packet:** `artifacts/reports/issue7/20260526T025931Z/` (PRs **#69**, **#70**, **#76**).

| Preset | Overall gate (packet `20260526T025931Z`) |
| --- | --- |
| **B0** | **pass** |
| **A1** | **pass** (`complexify_fraction=1.0` ablation policy; ADR 0003 thresholds unchanged) |
| **A4** | **pass** |

**Issue #8:** April 2026 HITL review on packet `20260430T204744Z` remains **fail** historically (`decision_history`). Current milestone decision: addendum **`20260526T025931Z`** signed **conditional_pass**.

### Provider-backed validation cycle — **optional post-completion track**

Tracked in `docs/llm-validation-readiness.md` Phase 4. Requires human credentials/policy, then optional live B0/A1/A4 with provider critics and Issue #9 rerun classification on that packet — **no ADR 0003** threshold or metric formula changes. Not required to close engineering + deterministic validation.

---

## `main` health (2026-05-26)

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

| Check | Status |
| --- | --- |
| Unit tests | **98 tests, OK** (stdlib `unittest` only; no `pip install`) |
| Python | **3.11+** (3.13 used in CI/agents) |
| API keys (unittest) | **Not required** |
| API keys (live NIM critic) | `NVIDIA_API_KEY` or `NVAPI_KEY` when `SIMULA_CRITIC_BACKEND=nim` |

**Latest `main` tip:** `242232e` (merge PR **#77**).

---

## Recently merged (completion-relevant)

| PR | Summary |
| --- | --- |
| **#76** | Pin Issue #8/#9 to packet `20260526T025931Z`; B0/A1/A4 pass; Issue #9 exact rerun; HITL sign-off addendum JSON |
| **#70** | A1 ablation complexify policy + packet `20260526T025231Z`; completion docs |
| **#69** | M1 gate remediation phase 2; packet `20260526T024251Z` |
| **#66** / **#65** | **#60** Stage 1–3 protocol hooks; **#61** manifest validation modes |
| **#45**, **#54**, **#56**, **#58** | LLM Stage-4 seams, regeneration artifact, NIM fail-closed backend |

**Canonical on-disk stage-4 directory:** `40_dual_critic_quality/`.

---

## Issue #10 decision (ADR 0004)

**Approved scope:** Option A — minimal seam formalization (`docs/adr/0004-engine-seam-scope.md`).

| On `main` | Closed | Closed deferred |
| --- | --- | --- |
| Stage contracts, `RunArtifactStore`, critic hooks, comparability gate, `pipeline_config`, Stages 1–3 protocols (#60), manifest modes (#61) | **#60**, **#61**, **#10** | **#62** Option B refactor (wontfix/deferred) |

---

## LLM validation readiness (phase snapshot)

| Phase | Focus | Status on `main` |
| --- | --- | --- |
| **0** | Freeze protocol / run discipline | **Met** |
| **1** | Stage 4 critic surface | **Met** |
| **2** | Stages 1–3 provider hooks (#60) | **Met** (bit-identical defaults) |
| **3** | Ablation execution fidelity (#42) | **Met** |
| **4** | Provider-backed validation packet | **Optional post-completion** — human credentials + live runs |

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

## Cross-references

| Document | Use |
| --- | --- |
| `docs/implementation-plan.md` | Milestones + live status table |
| `docs/llm-validation-readiness.md` | Phase 4 operator checklist |
| `docs/adr/0004-engine-seam-scope.md` | Issue #10 scope + invariants |
| `docs/research-validation-playbook.md` | H1–H4 promotion (post–Phase 4) |

---

## Paper Alignment Check (for your PR / issue comment)

Include: **traceability/auditability**, **protocol/comparability**, **control-axis impact**, **deviations** (or `none`).
