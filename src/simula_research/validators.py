from __future__ import annotations

from pathlib import Path
from typing import Any

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
    "40_dual_critic",
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
