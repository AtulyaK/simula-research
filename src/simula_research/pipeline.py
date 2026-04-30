from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from simula_research.manifest import validate_manifest

PROTOCOL_VERSION = "0.1.0"
ARTIFACT_SCHEMA_VERSION = "0.1.0"

STAGE_NAMES = [
    "stage_0_domain_run_spec",
    "stage_1_global_diversification",
    "stage_2_local_diversification",
    "stage_3_complexification",
    "stage_4_dual_critic_quality_verification",
    "stage_5_evaluation_handoff",
]


def run_pipeline(seed: int, model_ids: dict[str, str]) -> dict[str, object]:
    run_id = f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

    manifest = {
        "run_id": run_id,
        "seed": seed,
        "model_ids": model_ids,
        "protocol_version": PROTOCOL_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
    }
    validate_manifest(manifest)

    stage_outputs = {
        stage_name: {"status": "placeholder", "run_id": run_id} for stage_name in STAGE_NAMES
    }

    return {"manifest": manifest, "stage_outputs": stage_outputs}
