"""Pipeline boot manifest validation (fast path).

``validate_manifest`` enforces the **boot** field set required before stage
execution in ``run_pipeline``. It raises ``ValueError`` on failure.

For Issue #9 **full** reproducibility checks (owner, branch, commit_hash,
``pipeline_config``, ``baseline_or_ablation_tag``, …), use
``validators.validate_manifest_schema`` or ``validators.validate_manifest_by_mode(mode="full")``.
See ``docs/reproducibility-ops.md`` (Manifest validation modes).
"""

from __future__ import annotations

from typing import Any

BOOT_REQUIRED_MANIFEST_FIELDS: tuple[str, ...] = (
    "run_id",
    "created_at_utc",
    "seed",
    "domain_objective",
    "model_ids",
    "protocol_version",
    "artifact_schema_version",
)

MANIFEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": list(BOOT_REQUIRED_MANIFEST_FIELDS),
    "properties": {
        "run_id": {"type": "string", "minLength": 1},
        "created_at_utc": {"type": "string", "minLength": 1},
        "seed": {"type": "integer"},
        "domain_objective": {"type": "string", "minLength": 1},
        "model_ids": {"type": "object", "minProperties": 1},
        "protocol_version": {"type": "string", "minLength": 1},
        "artifact_schema_version": {"type": "string", "minLength": 1},
    },
}


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate manifest for pipeline boot (raises ``ValueError``).

    Does **not** require reproducibility-ops fields such as ``owner``,
    ``commit_hash``, or ``baseline_or_ablation_tag``. Optional keys present on
    the in-memory manifest (e.g. ``pipeline_config``) are not validated here.
    """
    for field in BOOT_REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            raise ValueError(f"Missing required manifest field: {field}")

    if not isinstance(manifest["run_id"], str) or not manifest["run_id"].strip():
        raise ValueError("Manifest field run_id must be a non-empty string")

    if not isinstance(manifest["created_at_utc"], str) or not manifest["created_at_utc"].strip():
        raise ValueError("Manifest field created_at_utc must be a non-empty string")

    if not isinstance(manifest["seed"], int):
        raise ValueError("Manifest field seed must be an integer")

    if not isinstance(manifest["domain_objective"], str) or not manifest["domain_objective"].strip():
        raise ValueError("Manifest field domain_objective must be a non-empty string")

    if not isinstance(manifest["model_ids"], dict) or not manifest["model_ids"]:
        raise ValueError("Manifest field model_ids must be a non-empty object")

    for version_field in ("protocol_version", "artifact_schema_version"):
        version_value = manifest[version_field]
        if not isinstance(version_value, str) or not version_value.strip():
            raise ValueError(f"Manifest field {version_field} must be a non-empty string")
