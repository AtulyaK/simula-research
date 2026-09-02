# Reproducibility and Ops Guide

## Purpose

Define operational requirements so any reported validation result can be reproduced from persisted artifacts.

## Reproducibility guarantees

Each run must be:

- **traceable**: complete lineage from inputs to metrics.
- **replayable**: same config + seed + model versions can rerun deterministically where possible.
- **auditable**: enough metadata exists to explain any deviation.

## Manifest validation modes (boot vs full)

Two validators apply at different lifecycle points. Do not confuse them when debugging missing-field errors.

| Mode | Entry point | When it runs | On failure |
|------|-------------|--------------|------------|
| **boot** | `manifest.validate_manifest` or `validators.validate_manifest_by_mode(mode="boot")` | Start of `run_pipeline`, before stages execute | `ValueError` (boot wrapper returns `ok: false`) |
| **full** | `validators.validate_manifest_schema` or `validate_manifest_by_mode(mode="full")` | Issue #9 reproducibility checks, pre-publication ops, CLI-style disk validation | Structured `{"ok": false, "issues": [...]}` |

### Boot-required fields (`manifest.validate_manifest`)

Used by the default pipeline only. Required keys:

- `run_id`, `created_at_utc`, `seed`, `domain_objective`, `model_ids`
- `protocol_version`, `artifact_schema_version`

`run_pipeline` also attaches `pipeline_config` (and optional `provider_runtime`) on the in-memory manifest, but **boot validation does not require or type-check those keys**. They are required only under **full** validation below.

### Full reproducibility fields (`validators.validate_manifest_schema`)

Required for persisted `00_spec/manifest.json` under `artifacts/runs/<run_id>/` when running Issue #9 checks or the operational checklist in this guide. Includes all boot fields **plus**:

- `owner`, `branch`, `commit_hash`
- `pipeline_config` (non-empty object)
- `baseline_or_ablation_tag`

`model_ids` values must be non-empty strings in full mode (boot only requires a non-empty object).

`00_spec/run_config.json` stores the resolved configuration used by the
pipeline, including `pipeline_config`, `taxonomy_config`,
`local_diversification_config`, `complexification_config`, and
`dual_critic_config`, alongside the run identity and provider runtime metadata.
`00_spec/artifact_integrity.json` records SHA-256 digests and byte sizes for
every other file in the run root; artifact-tree validation checks for tampered,
missing, and untracked files.

### Operator guidance

1. **Local pipeline / smoke runs** — `run_pipeline` boot validation is sufficient; returned manifest may fail full schema until you add Issue #9 metadata before archival.
2. **Matrix / milestone evidence** — use manifests produced by `execute_issue7_matrix` or extend smoke manifests per the JSON example below; run `validate_manifest_schema` on disk.
3. **Single entry point** — `validate_manifest_by_mode(manifest, mode="boot"|"full")` selects the mode explicitly without changing default pipeline behavior.

## Required run metadata

Every run manifest must include (full reproducibility mode):

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

- `00_spec/` - frozen resolved run config, manifest, and stage outputs
- `10_taxonomy/` - taxonomy graph and node metadata
- `20_local_diversification/` - meta-prompts and instantiations
- `30_complexification/` - transformed samples and tags
- `40_dual_critic_quality/` - critic decisions, disagreements, rejection logs (matches `FileSystemRunArtifactStore` / default pipeline)
- `50_curated_dataset/` - accepted dataset outputs
- `60_evaluation/` - metrics and run report
- `70_diagnostics/` - failure analyses and debug summaries

### Stage 4 directory name (validator alignment)

`validate_artifact_tree` requires the same directory names the default pipeline persists via `FileSystemRunArtifactStore`. Stage 4 uses **`40_dual_critic_quality/`** (not `40_dual_critic/`). Older docs or out-of-tree layouts that used `40_dual_critic/` should rename to `40_dual_critic_quality/` or add a symlink so reproducibility checks match the default store.

### Artifact tree validation contract

`validate_artifact_tree` validates the run root, full `00_spec/manifest.json`, resolved
configuration, artifact integrity metadata, required stage directories, and canonical JSON artifacts:

- `10_taxonomy/taxonomy_graph.json`, `10_taxonomy/taxonomy_nodes.json`
- `20_local_diversification/instantiations.json`, `20_local_diversification/rejections.json`
- `30_complexification/samples.json`, `30_complexification/semantic_preservation_failures.json`
- `40_dual_critic_quality/critic_decisions.json`, `40_dual_critic_quality/rejections.json`, `40_dual_critic_quality/regenerations.json`
- `50_curated_dataset/accepted_samples.json`, `50_curated_dataset/dataset_manifest.json`
- Optional `50_curated_dataset/decontamination_report.json` and
  `decontamination_rejections.json` when a held-out reference set is supplied.
- Optional `30_complexification/batchwise_complexity.json` when a batch
  complexity provider is supplied.
- `60_evaluation/evaluation_handoff.json`
- Optional `60_evaluation/downstream_evaluation_results.json` when benchmark
  results have been recorded against a downstream evaluation plan.
- `70_diagnostics/diagnostics_summary.json`

It also checks taxonomy graph acyclicity, node/edge parent consistency, unique IDs, lineage references, Stage 2→3→4 completeness, and accepted/rejected decision consistency. The public result shape remains `{"ok", "kind", "issues", "assumptions"}`.

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
  "pipeline_config": {"dual_critic_enabled": true},
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

See **`docs/provider-stochastic-reproducibility-policy.md`** for provider-backed critic classification (`exact` / `acceptable_drift` / `mismatch`) and Phase 4 operator workflow. Code uses `ACCEPTABLE_DRIFT_MAX_DELTA = 0.02` in `issue9_reproducibility.py` (not configurable without ADR 0003 review).

Some model providers can introduce nondeterminism. When exact matching fails:

- classify drift source:
  - model version drift
  - runtime environment drift
  - hidden configuration drift
- document quantified impact on gate metrics
- mark run comparability status explicitly

## Milestone comparability (structured `mixed`)

When a comparability axis is intentionally not uniform across runs (for example, a designed ablation such as A4 single-critic), record `status: mixed` **and** `mixed_reason: documented_ablation` on that axis in `comparability_constraints_check`.

Issue #9 comparability hard gates treat prose in `details` as human-readable only; they require the structured `mixed_reason` so reviews do not rely on substring matching in free text.

## Operational checks before any report publication

- Manifest complete and **full**-mode schema-valid (`validate_manifest_schema` or `validate_manifest_by_mode(mode="full")`).
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
