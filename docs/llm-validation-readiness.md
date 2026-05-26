# LLM Validation Readiness Guide

## Purpose

This guide explains how to make the repository ready for end-to-end validation with real LLM providers and real persisted datasets, while preserving the research protocol guardrails.

Use this together with:

- `docs/research_paper.pdf` (research intent and validation framing)
- `docs/research-validation-playbook.md` (hypotheses H1-H4, B0/A1/A4 matrix, run checklist)
- `docs/pipeline-spec.md` (stage contracts)
- `docs/evaluation-metrics.md` (metric definitions and gates)
- `docs/reproducibility-ops.md` (manifest/artifact/rerun protocol)
- `docs/adr/0002-control-axes-as-first-class.md` and `docs/adr/0003-evaluation-protocol-and-thresholds.md` (non-negotiable comparability constraints)
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
- **Env-based critic wiring:** `critic_sample_evaluator_from_env()` returns `None` (hash default), or a **non-network** `stub` / `replay` evaluator for smoke tests (`SIMULA_CRITIC_BACKEND`, `SIMULA_CRITIC_REPLAY_JSON`). See `docs/research-validation-playbook.md` for the operator snippet.
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

### Live Stage-4 critic backend: NVIDIA NIM (OpenAI-compatible)

This repo supports a **live** Stage-4 critic backend via NVIDIA NIM behind `SIMULA_CRITIC_BACKEND=nim` (alias: `nvidia`).

**Default model** (if you do not override it): **`llama-4-maverick-17b-128e-instruct`**.

**Required secrets (do not log):**

- `NVIDIA_API_KEY` (preferred) or `NVAPI_KEY`

**Non-secret transport/model knobs (safe to record in `provider_runtime`):**

- `SIMULA_CRITIC_BACKEND=nim` (or `nvidia`)
- `SIMULA_NIM_BASE_URL` (or `SIMULA_NVIDIA_BASE_URL`)  
  Defaults to `https://integrate.api.nvidia.com/v1/chat/completions`
- `SIMULA_NIM_MODEL` (or `SIMULA_NVIDIA_MODEL`)  
  Defaults to `llama-4-maverick-17b-128e-instruct`
- `SIMULA_CRITIC_MODEL_A`, `SIMULA_CRITIC_MODEL_B`  
  Optional per-critic overrides (recommended for explicitness)
- `SIMULA_NVIDIA_MAX_TOKENS`  
  Max tokens for the critic response (defaults to 16; the critic is instructed to return exactly one token: `accept` or `reject`)
- `SIMULA_HTTP_TIMEOUT_SECONDS` (defaults to 30)
- `SIMULA_HTTP_MAX_RETRIES` (defaults to 2)
- `SIMULA_HTTP_BACKOFF_BASE_SECONDS` (defaults to 0.5)

**Safety invariants (by design):**

- The live NIM evaluator **does not print prompts/responses**.
- Errors raised by the transport wrapper are **sanitized** (no raw provider payloads).
- Operator-facing structured logs should only contain **IDs + error types**, never sample text.

**Stop conditions (operator guardrails):**

- If you cannot confirm budget caps for the run, **do not start** live validation.
- If you observe repeated `nvidia_critic_request_failed:*` errors beyond your retry budget, **stop the batch** and capture an incident note (without raw text).
- If acceptance/rejection becomes unstable and dominates quality metrics, **stop** and run a focused diagnosis before continuing (do not “average it out”).

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

### Deterministic `stub`/`replay` vs live `nim` (reproducibility expectations)

Stage-4 critic non-determinism is handled explicitly via **backend selection**:

- **`SIMULA_CRITIC_BACKEND=stub`**: deterministic, non-network “provider-shaped” path. Uses a hash-based verdict on text and is suitable for CI and baseline reproducibility checks.
- **`SIMULA_CRITIC_BACKEND=replay`**: deterministic, non-network path that looks up verdicts from a fixed table (`SIMULA_CRITIC_REPLAY_JSON`). Use this when you need to **re-run exactly** against a previously captured critic decision table without re-contacting a provider.
- **`SIMULA_CRITIC_BACKEND=nim`**: live provider-backed path. Even with `temperature=0`, you should treat it as **potentially drift-prone**. For “auditability”, always record:
  - commit hash + branch,
  - backend + base URL,
  - explicit critic model IDs per critic (`SIMULA_CRITIC_MODEL_A` / `SIMULA_CRITIC_MODEL_B`),
  - transport knobs (timeouts/retries),
  - and any incident log about failures/retries (without raw text).

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
- [ ] stage 1-3 provider plan is either implemented or explicitly out-of-scope
- [x] ablation behavior fidelity is validated at execution level (`pipeline_config` → `run_pipeline`; tests `test_issue42_pipeline_config_execution.py`)
- [ ] reproducibility policy for stochastic drift is documented
- [ ] Paper/ADR constraints acknowledged in run packet

## Notes on thresholds and formulas

This guide does not modify metric formulas, thresholds, or ablation definitions. If you need those changes:

1. justify from `docs/research_paper.pdf` evidence and current run outcomes,
2. assess impact against `docs/adr/0003-evaluation-protocol-and-thresholds.md`,
3. update ADR/docs before applying changes in code.
