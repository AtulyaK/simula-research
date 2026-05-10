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

The codebase already supports a deterministic full pipeline and milestone evidence, but LLM integration is partial:

- Stage 4 critic verdict is injectable through `CriticVerdictFn` in `src/simula_research/provider_protocols.py`.
- `run_pipeline(...)` accepts `critic_verdict` and passes it into adjudication in `src/simula_research/pipeline.py`.
- Stages 1-3 (`build_taxonomy`, `build_local_diversification`, `apply_complexification`) are still deterministic in-repo logic by default.

### Issue #7 matrix caveat

`src/simula_research/issue7_execution_reporting.py` calls `run_pipeline(...)` with core run args, but does not currently pass preset `pipeline_config` toggles into stage behavior. The report protocol includes ablation labels, and selected A1/A4 effects are represented through reporting-time adjustments.

Implication: for strict "entire playbook as designed" LLM validation, you should plan one engineering slice to ensure ablation toggles actually alter pipeline behavior, not only report interpretation.

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

1. Implement a production `CriticVerdictFn` wrapper for each critic identity.
2. Keep deterministic fallback path available for debugging and reproducibility comparisons.
3. Add structured provider metadata to run outputs (model name/version, temperature, max tokens, timeout, retry settings).
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

1. Ensure ablation presets (B0/A1/A4) change actual runtime stage behavior, not only reporting metadata.
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

- [ ] baseline test suite is green
- [ ] provider credentials and budget guardrails are configured
- [ ] run manifest and artifact conventions are enforced
- [ ] critic provider integration is operational
- [ ] stage 1-3 provider plan is either implemented or explicitly out-of-scope
- [ ] ablation behavior fidelity is validated (execution, not report-only)
- [ ] reproducibility policy for stochastic drift is documented
- [ ] Paper/ADR constraints acknowledged in run packet

## Notes on thresholds and formulas

This guide does not modify metric formulas, thresholds, or ablation definitions. If you need those changes:

1. justify from `docs/research_paper.pdf` evidence and current run outcomes,
2. assess impact against `docs/adr/0003-evaluation-protocol-and-thresholds.md`,
3. update ADR/docs before applying changes in code.
