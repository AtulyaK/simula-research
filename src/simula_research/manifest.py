from __future__ import annotations

from typing import Any

MANIFEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "run_id",
        "created_at_utc",
        "seed",
        "domain_objective",
        "model_ids",
        "protocol_version",
        "artifact_schema_version",
    ],
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
    for field in MANIFEST_SCHEMA["required"]:
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
