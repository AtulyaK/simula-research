# LLM Validation Readiness Guide

## Purpose

This guide explains how to make the repository ready for end-to-end validation with real LLM providers and real persisted datasets, while preserving the research protocol guardrails.

Use this together with:

- `docs/research_paper.pdf` (research intent and validation framing)
- `docs/research-validation-playbook.md` (hypotheses H1-H4, B0/A1/A4 matrix, run checklist)
- `docs/pipeline-spec.md` (stage contracts)
- `docs/evaluation-metrics.md` (metric definitions and gates)
- `docs/reproducibility-ops.md` (manifest/artifact/rerun protocol)
- `docs/adr/0002-control-axes-as-first-class.md`, `docs/adr/0003-evaluation-protocol-and-thresholds.md`, and `docs/adr/0004-engine-seam-scope.md` (comparability and seam constraints)
- `docs/agents/next-agent-handoff.md` (current project status and prioritized follow-ups)

## What "ready for LLM validation" means

The project is "LLM-validation ready" when all of the following are true:

1. You can run baseline and ablations with explicit, versioned provider settings.
2. Runs produce complete artifacts and manifests that can be audited and rerun.
3. Coverage, complexity, and quality remain independent control axes.
4. Gate decisions are made against the current metric protocol without silent formula/threshold drift.
5. Any non-determinism from providers is handled under the reproducibility policy (exact match vs acceptable drift vs mismatch).

## Current state (important before planning real runs)

The codebase supports a deterministic full pipeline and milestone evidence. LLM-oriented seams are now wired as follows:

- Stage 4 critic verdict is injectable in two ways (see `src/simula_research/provider_protocols.py`, `dual_critic.adjudicate_samples`, `pipeline.run_pipeline`):
  - **`CriticVerdictFn` (Issue #29):** `(text, critic_id) -> verdict` — smallest surface; sufficient for hash stubs and text-only wrappers.
  - **`CriticSampleEvaluatorFn` (Issue #22):** `(sample, critic_id) -> verdict` — **provider-facing** path: full Stage-3 sample dict (lineage, `is_complexified`, regenerated `text`, …) without changing Stage 4 JSON artifact field names.
- Helpers for rollout: `sample_evaluator_from_text_fn` (parity / replay vs hash path), `recorded_sample_evaluator` (offline replay from a fixed verdict table). `critic_verdict` and `critic_sample_evaluator` are **mutually exclusive** at the pipeline boundary.
- **Provider/runtime metadata (Issue #41):** optional `provider_runtime` dict is merged into the run `manifest` and echoed under `stage_outputs.stage_4_dual_critic_quality_verification.provider_runtime` when supplied. `provider_runtime_from_env()` in `critic_provider_adapter.py` collects **non-secret** transport knobs from environment variables for operator runs.
- **Execution fidelity (Issue #42):** `execute_issue7_matrix` passes each preset’s `pipeline_config` into `run_pipeline`, which maps toggles to taxonomy/local/complexification/dual-critic execution (A1 shallow taxonomy, A4 `single_critic_mode`, etc.). Reporting-time metric hacks for A1/A4 have been removed; matrix metrics now reflect actual stage outputs.
- **Env-based critic wiring:** `critic_sample_evaluator_from_env()` returns `None` (hash default), or a **non-network** `stub` / `replay` evaluator for smoke tests (`SIMULA_CRITIC_BACKEND`, `SIMULA_CRITIC_REPLAY_JSON`). The live NVIDIA NIM backend is available behind `SIMULA_CRITIC_BACKEND=nim` (requires `NVIDIA_API_KEY` or `NVAPI_KEY`) and is **fail-closed** on ambiguous outputs (invalid/unclear verdicts become `reject` with structured event logging). **`execute_issue7_matrix`** passes both `provider_runtime_from_env()` and `critic_sample_evaluator_from_env()` into `run_pipeline` for B0/A1/A4. See `docs/research-validation-playbook.md` and `scripts/run_issue7_matrix.sh`.
- Stages 1–3 remain deterministic in-repo logic by default (Phase 2 of this guide).

### Issue #7 matrix

`src/simula_research/issue7_execution_reporting.py` passes preset `pipeline_config` into `run_pipeline` so B0/A1/A4 differ in persisted artifacts and downstream metrics without report-only adjustments.

## Prerequisites Checklist

## 1) Runtime and tools

- Python 3.11+ (3.13 works in this repo)
- `gh` CLI authenticated to the repository (issue/PR workflows)
- Git configured for branch/commit traceability

## 2) Provider resources

- Provider accounts for target LLM vendors
- API keys with explicit environment variable names
- Cost controls:
  - hard spend cap per day
  - per-run budget target
  - alerting threshold (for example, 50%, 80%, 100% of budget)
- Rate-limit handling strategy:
  - retries
  - backoff policy
  - max retry budget per run

### Critic backend selection (env)

Stage-4 critic integration is selected via `SIMULA_CRITIC_BACKEND` in `src/simula_research/critic_provider_adapter.py`:

- `SIMULA_CRITIC_BACKEND=stub`: non-network, hash-parity evaluator for provider-shaped smoke.
- `SIMULA_CRITIC_BACKEND=replay`: non-network deterministic replay (requires `SIMULA_CRITIC_REPLAY_JSON`).
- `SIMULA_CRITIC_BACKEND=nim` (alias `nvidia`): **live** NVIDIA NIM backend (OpenAI-compatible chat completions).

NIM backend env vars:

- Required (one of):
  - `NVIDIA_API_KEY`
  - `NVAPI_KEY`
- Optional endpoint/model:
  - `SIMULA_NIM_BASE_URL` (or `SIMULA_NVIDIA_BASE_URL`)
  - `SIMULA_NIM_MODEL` (or `SIMULA_NVIDIA_MODEL`)
  - `SIMULA_CRITIC_MODEL_A`, `SIMULA_CRITIC_MODEL_B` (per-critic override)
- Optional transport knobs (also recorded into `provider_runtime` metadata; **never** store the key itself):
  - `SIMULA_HTTP_TIMEOUT_SECONDS`
  - `SIMULA_HTTP_MAX_RETRIES`
  - `SIMULA_HTTP_BACKOFF_BASE_SECONDS`

## 3) Data and compliance controls

- Define whether prompts/responses may contain sensitive or regulated content.
- Decide logging policy for prompt/response payloads:
  - full text
  - redacted text
  - hashes only
- Confirm retention period for raw model outputs.
- Confirm whether model provider data usage settings satisfy your policy.

## 4) Reproducibility controls

- Persist complete run identity (`run_id`, seed, model IDs, protocol version, artifact schema version, commit hash, branch).
- Persist artifacts under `artifacts/runs/<run_id>/...` following `docs/reproducibility-ops.md`.
- Ensure stage-4 path alignment with current convention: `40_dual_critic_quality/`.

## 5) Baseline repo health gate

Run and pass:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Do not start provider-backed validation until this baseline gate is green.

## Concrete Rollout Plan

## Phase 0 - Freeze protocol and run discipline

1. Freeze pilot objective and task format.
2. Freeze baseline/ablation set (minimum: B0, A1, A4 per playbook).
3. Freeze evaluation protocol version and artifact schema version.
4. Record these in a run checklist template before first provider-backed run.
5. Confirm no threshold or metric formula changes are proposed (ADR 0003 constraint).

Deliverable:

- A single approved run checklist doc for this validation batch.

## Phase 1 - Introduce the smallest real-LLM surface (Stage 4 critics)

1. Implement production critic adapters (per critic identity **A** / **B**) behind the **`CriticSampleEvaluatorFn`** seam when the model needs full sample context; use **`CriticVerdictFn`** only when a text-only wrapper is enough, bridged via `sample_evaluator_from_text_fn` for adjudication.
2. Keep deterministic fallback path available for debugging and reproducibility comparisons (`critic_verdict` / `critic_sample_evaluator` unset → hash-based stub; or explicit `recorded_sample_evaluator` / wrapped hash for replay).
3. Add structured provider metadata to run outputs via optional `provider_runtime` on `run_pipeline` (manifest + stage 4 echo) and `provider_runtime_from_env()` for transport/model aliases — GitHub **#41**.
4. Execute a small smoke run and validate that:
   - artifacts persist,
   - stage handoff contracts pass,
   - gate report generation still succeeds.

Deliverable:

- One provider-backed smoke run with complete artifacts and a short incident log (timeouts/retries/cost).

## Phase 2 - Expand provider seams to Stages 1-3 (recommended)

1. Add protocol-based hooks for:
   - taxonomy generation
   - local diversification
   - complexification
2. Keep defaults bit-identical to current deterministic behavior.
3. Add tests that prove default path remains unchanged.
4. Document boot-vs-full manifest validation expectations if touching `manifest` and `validators`.

Deliverable:

- Provider seams for all generation stages with deterministic defaults preserved.

## Phase 3 - Enforce true ablation behavior

1. Ensure ablation presets (B0/A1/A4) change actual runtime stage behavior, not only reporting metadata — **#42** implemented via `pipeline_config` in `run_pipeline` and `execute_issue7_matrix`.
2. Validate that run reports reflect real stage toggles and no simulated-only effects.
3. Re-run comparison matrix and verify expected directional effects against H1-H4 framing.

Deliverable:

- Matrix evidence where ablation semantics are implemented in execution logic.

## Phase 4 - Full validation cycle with real data

1. Execute B0.
2. Execute A1 and A4 (or full matrix if budget permits).
3. Produce and persist:
   - run reports,
   - gate reports,
   - comparison outputs,
   - failure analysis notes.
4. Run reproducibility classification on baseline rerun.
5. Record milestone gate recommendation (pass/conditional pass/fail) with evidence links.

Deliverable:

- A complete validation packet equivalent to Issue #7/#8/#9 evidence, but provider-backed.

Operator commands (from repo root):

```bash
chmod +x scripts/run_issue7_matrix.sh scripts/run_issue9_comparability_check.sh
export PYTHONPATH=src
export SIMULA_CRITIC_BACKEND=stub   # or nim + NVIDIA_API_KEY for live critics
./scripts/run_issue7_matrix.sh
./scripts/run_issue9_comparability_check.sh
```

Stochastic drift classification for provider reruns: `docs/provider-stochastic-reproducibility-policy.md`.

## Resource Planning Template

Before each validation batch, fill this table:

| Category | Required input |
| --- | --- |
| Provider models | model IDs for generator, critic_a, critic_b |
| API config | key names, endpoint, timeout, retries, backoff |
| Budget | max total spend, per-run spend target |
| Throughput | target samples/run, expected runtime |
| Observability | logs, traces, failure counters |
| Reproducibility | seed policy, protocol version, commit hash pin |
| Governance | PII policy, retention policy, access controls |

## Stop Conditions and Escalation

Stop the batch and escalate if any of these occur:

- repeated provider failures invalidate run completeness
- disagreement/regeneration behavior becomes unstable and dominates quality metrics
- reproducibility check yields mismatch without explainable provider drift
- protocol/threshold changes are requested without ADR 0003 impact process

When stopped:

1. Run a focused diagnosis pass.
2. Propose one smallest next change.
3. Re-run only affected cells of the matrix.

## Definition of Readiness (Checklist)

You are ready to run full LLM-backed validation when all are checked:

- [x] baseline test suite is green (`PYTHONPATH=src python3 -m unittest discover -s tests -v`)
- [ ] provider credentials and budget guardrails are configured (human / org policy)
- [x] run manifest and artifact conventions are enforced for stage trees (`artifacts/runs/<run_id>/`); full `validate_manifest_schema` on disk requires Issue #9 fields (`created_at_utc`, `domain_objective`, …) — use `execute_issue7_matrix` or extend smoke `manifest.json` per `docs/reproducibility-ops.md`
- [x] critic provider integration path is operational for **stub/replay** (`critic_provider_adapter`, sample evaluator seam, metadata echo); live HTTP vendors require keys and org approval
- [x] provider-shaped smoke validated (stub backend, incident logs under `artifacts/reports/llm-smoke/`; reproducibility `exact` at gate-metric level for same seed)
- [ ] NIM smoke validated (optional but recommended): `SIMULA_CRITIC_BACKEND=nim` with `NVIDIA_API_KEY` set, small run completes and manifests include `nim_critic` metadata (no secrets logged)
- [ ] stage 1-3 provider plan is either implemented or explicitly out-of-scope
- [x] ablation behavior fidelity is validated at execution level (`pipeline_config` → `run_pipeline`; tests `test_issue42_pipeline_config_execution.py`)
- [x] reproducibility policy for stochastic drift is documented (`docs/provider-stochastic-reproducibility-policy.md`)
- [ ] Paper/ADR constraints acknowledged in run packet

## Notes on thresholds and formulas

This guide does not modify metric formulas, thresholds, or ablation definitions. If you need those changes:

1. justify from `docs/research_paper.pdf` evidence and current run outcomes,
2. assess impact against `docs/adr/0003-evaluation-protocol-and-thresholds.md`,
3. update ADR/docs before applying changes in code.
