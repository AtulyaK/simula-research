"""Reproducibility validators for on-disk runs (Issue #9).

``validate_manifest_schema`` applies the **full** manifest field set from
``docs/reproducibility-ops.md``. ``manifest.validate_manifest`` is the narrower
**boot** check used by ``run_pipeline`` before stages run.

Use ``validate_manifest_by_mode`` when operators need a single entry point with
explicit ``mode="boot"`` or ``mode="full"``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from simula_research.manifest import validate_manifest

ManifestValidationMode = Literal["boot", "full"]

# Reproducibility-ops required manifest fields.
REQUIRED_MANIFEST_FIELDS: tuple[str, ...] = (
    "run_id",
    "created_at_utc",
    "owner",
    "branch",
    "commit_hash",
    "artifact_schema_version",
    "domain_objective",
    "seed",
    "model_ids",
    "pipeline_config",
    "protocol_version",
    "baseline_or_ablation_tag",
)

# Reproducibility-ops stable artifact layout conventions.
REQUIRED_ARTIFACT_STAGES: tuple[str, ...] = (
    "00_spec",
    "10_taxonomy",
    "20_local_diversification",
    "30_complexification",
    "40_dual_critic_quality",
    "50_curated_dataset",
    "60_evaluation",
    "70_diagnostics",
)


def _validation_result(kind: str, issues: list[str], assumptions: list[str]) -> dict[str, Any]:
    return {
        "ok": len(issues) == 0,
        "kind": kind,
        "issues": issues,
        "assumptions": assumptions,
    }


def validate_manifest_schema(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate manifest against the full reproducibility-ops field set.

    Returns a structured result dict (does not raise). Boot-only manifests from
    ``run_pipeline`` are expected to fail until Issue #9 fields are added on disk.
    """
    issues: list[str] = []
    assumptions = [
        "Manifest payload is already parsed as JSON object",
        "Model identifiers are represented as strings in model_ids",
        "pipeline_config can be any JSON object shape as long as it is present",
    ]

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            issues.append(f"missing required field: {field}")

    if "run_id" in manifest and (not isinstance(manifest["run_id"], str) or not manifest["run_id"].strip()):
        issues.append("field run_id must be a non-empty string")

    if "seed" in manifest and not isinstance(manifest["seed"], int):
        issues.append("field seed must be an integer")

    if "model_ids" in manifest:
        model_ids = manifest["model_ids"]
        if not isinstance(model_ids, dict) or not model_ids:
            issues.append("field model_ids must be a non-empty object")
        elif any(not isinstance(value, str) or not value.strip() for value in model_ids.values()):
            issues.append("field model_ids must map to non-empty string identifiers")

    for field in ("protocol_version", "artifact_schema_version", "baseline_or_ablation_tag"):
        if field in manifest and (not isinstance(manifest[field], str) or not manifest[field].strip()):
            issues.append(f"field {field} must be a non-empty string")

    if "pipeline_config" in manifest and not isinstance(manifest["pipeline_config"], dict):
        issues.append("field pipeline_config must be an object")

    return _validation_result(kind="manifest", issues=issues, assumptions=assumptions)


def validate_manifest_by_mode(
    manifest: dict[str, Any],
    *,
    mode: ManifestValidationMode = "boot",
) -> dict[str, Any]:
    """Validate manifest in boot or full reproducibility mode.

    - ``boot``: delegates to ``manifest.validate_manifest`` (pipeline default).
    - ``full``: delegates to ``validate_manifest_schema`` (Issue #9 / ops).
    """
    if mode == "full":
        result = validate_manifest_schema(manifest)
        result["validation_mode"] = "full"
        return result

    try:
        validate_manifest(manifest)
    except ValueError as exc:
        return {
            **_validation_result(
                kind="manifest",
                issues=[str(exc)],
                assumptions=[
                    "Boot mode uses manifest.validate_manifest (raises converted to issues)",
                ],
            ),
            "validation_mode": "boot",
        }

    return {
        **_validation_result(
            kind="manifest",
            issues=[],
            assumptions=[
                "Boot mode uses manifest.validate_manifest",
                "Does not require owner, branch, commit_hash, or baseline_or_ablation_tag",
            ],
        ),
        "validation_mode": "boot",
    }


def validate_artifact_tree(run_root: str | Path) -> dict[str, Any]:
    root_path = Path(run_root)
    issues: list[str] = []
    assumptions = [
        "run_root points to artifacts/runs/<run_id>",
        "Required stages are represented as directories directly under run_root",
        "Validation checks folder presence only, not internal file completeness",
    ]

    if not root_path.exists():
        issues.append(f"run root does not exist: {root_path}")
        return _validation_result(kind="artifacts", issues=issues, assumptions=assumptions)

    if not root_path.is_dir():
        issues.append(f"run root is not a directory: {root_path}")
        return _validation_result(kind="artifacts", issues=issues, assumptions=assumptions)

    for stage_dir in REQUIRED_ARTIFACT_STAGES:
        stage_path = root_path / stage_dir
        if not stage_path.exists() or not stage_path.is_dir():
            issues.append(f"missing required artifact stage directory: {stage_dir}")

    return _validation_result(kind="artifacts", issues=issues, assumptions=assumptions)
