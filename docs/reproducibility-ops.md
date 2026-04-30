# Reproducibility and Ops Guide

## Purpose

Define operational requirements so any reported validation result can be reproduced from persisted artifacts.

## Reproducibility guarantees

Each run must be:

- **traceable**: complete lineage from inputs to metrics.
- **replayable**: same config + seed + model versions can rerun deterministically where possible.
- **auditable**: enough metadata exists to explain any deviation.

## Required run metadata

Every run manifest must include:

- `run_id`
- `created_at_utc`
- `owner`
- `branch`
- `commit_hash`
- `artifact_schema_version`
- `domain_objective`
- `seed`
- `model_ids` (generator and critics)
- `pipeline_config` (full resolved config)
- `protocol_version` (evaluation and judging)
- `baseline_or_ablation_tag`

## Artifact layout convention

Use a stable, timestamped structure:

`artifacts/runs/<run_id>/`

Recommended subdirectories:

- `00_spec/` - frozen run config and manifest
- `10_taxonomy/` - taxonomy graph and node metadata
- `20_local_diversification/` - meta-prompts and instantiations
- `30_complexification/` - transformed samples and tags
- `40_dual_critic/` - critic decisions, disagreements, rejection logs
- `50_curated_dataset/` - accepted dataset outputs
- `60_evaluation/` - metrics and run report
- `70_diagnostics/` - failure analyses and debug summaries

## Run manifest schema (minimum)

```json
{
  "run_id": "string",
  "seed": 0,
  "commit_hash": "string",
  "model_ids": {
    "generator": "string",
    "critic_a": "string",
    "critic_b": "string"
  },
  "pipeline_config": {},
  "protocol_version": "string",
  "artifact_schema_version": "v1",
  "baseline_or_ablation_tag": "B0"
}
```

## Deterministic rerun protocol

1. Checkout the recorded `commit_hash`.
2. Load the exact manifest and frozen config.
3. Use identical seeds and model identifiers.
4. Re-run pipeline and evaluation without config edits.
5. Compare output signatures and metric deltas.
6. Record rerun result as:
   - exact match
   - acceptable drift (with explanation)
   - mismatch requiring investigation

## Drift policy

Some model providers can introduce nondeterminism. When exact matching fails:

- classify drift source:
  - model version drift
  - runtime environment drift
  - hidden configuration drift
- document quantified impact on gate metrics
- mark run comparability status explicitly

## Operational checks before any report publication

- Manifest complete and schema-valid.
- Artifact tree complete for all required stages.
- Metrics generated from persisted artifacts, not transient logs.
- Gate decision references metric files by path.
- At least one rerun check has been performed for baseline.

## Incident handling

Trigger an ops incident note when:

- run artifacts are missing or corrupted
- protocol version is absent
- metric computation cannot be reproduced
- disagreement/rejection logs are unavailable

Incident notes should include timeline, impact, root cause, and corrective action.
