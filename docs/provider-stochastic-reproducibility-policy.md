# Provider stochastic reproducibility policy (stub)

## Status

**Stub / operator policy** — not a code change to ADR 0003 thresholds or metric formulas. Classification logic for deterministic reruns lives in `src/simula_research/issue9_reproducibility.py` (`ACCEPTABLE_DRIFT_MAX_DELTA = 0.02`). This document states how **live LLM critics** (for example `SIMULA_CRITIC_BACKEND=nim`) map onto that classification when exact byte-level replay is not expected.

## Purpose

Provider-backed runs may differ across reruns even with identical seeds, manifests, and transport settings. Before interpreting gate failures or tuning thresholds, classify baseline reruns and document drift source.

## Classification outcomes

| Classification | When to use | Gate impact (Issue #9) |
| --- | --- | --- |
| **exact** | All comparable gate metric paths match within floating-point equality (`max_metric_delta == 0`). | Reproducibility hard gate **pass** |
| **acceptable_drift** | `max_metric_delta <= 0.02` on every comparable path; no missing metric paths. Drift is attributed to documented provider stochasticity or benign float noise. | Reproducibility hard gate **pass** |
| **mismatch** | Missing metric paths, no comparable paths, or `max_metric_delta > 0.02`. | Reproducibility hard gate **fail** until explained or config frozen |

Do **not** widen `ACCEPTABLE_DRIFT_MAX_DELTA` in code without ADR 0003 impact review.

## Provider backends and expected determinism

| `SIMULA_CRITIC_BACKEND` | Network | Expected rerun behavior |
| --- | --- | --- |
| *(unset)* / `hash` / `default` | No | **exact** (hash-based critic; Stages 1–3 deterministic) |
| `stub` | No | **exact** (hash parity via `sample_evaluator_from_text_fn`) |
| `replay` | No | **exact** when replay table unchanged |
| `nim` / `nvidia` | Yes | Often **acceptable_drift** or **mismatch**; treat **exact** as bonus |

Stages 1–3 remain deterministic in-repo unless future provider hooks (#60) are enabled with explicit comparability waiver.

## Operator workflow (Phase 4)

1. Run matrix with frozen env (see `scripts/run_issue7_matrix.sh` and `docs/research-validation-playbook.md`).
2. Persist `provider_runtime` on manifests and run reports (non-secret metadata only).
3. Re-run baseline (B0) with identical manifest inputs.
4. Call `run_issue9_reproducibility_check` or `scripts/run_issue9_comparability_check.sh`.
5. If classification is **acceptable_drift**, append a short drift note to the validation packet:
   - provider model ID and version (from `provider_runtime` / env aliases)
   - transport settings (`SIMULA_HTTP_*`)
   - which metric paths moved and by how much
6. If **mismatch**, stop batch per `docs/llm-validation-readiness.md` stop conditions; do not tune thresholds until hard gates pass.

## Comparability (unchanged)

Structured comparability for ablations is independent of provider drift:

- Use `mixed_reason: documented_ablation` when `status: mixed` (for example A4 single-critic).
- See `docs/reproducibility-ops.md` and `evaluate_comparability_gate()` in `issue9_reproducibility.py`.

## Secrets and logging

- Never persist API keys in manifests, `provider_runtime`, or incident logs.
- NIM adapter fail-closed: ambiguous model output → `reject` with sanitized events (no prompt text).

## Human / org actions required for live validation

- `NVIDIA_API_KEY` or `NVAPI_KEY` for `SIMULA_CRITIC_BACKEND=nim`
- Budget caps and retention policy per `docs/llm-validation-readiness.md`
