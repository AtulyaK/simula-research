from __future__ import annotations

from copy import deepcopy
from typing import Any

PRESET_IDS: tuple[str, ...] = ("B0", "A1", "A4")
COMPARABILITY_FIELDS: tuple[str, ...] = (
    "domain_objective",
    "seed",
    "model_ids",
    "protocol_version",
    "artifact_schema_version",
    "evaluation_protocol_version",
)
REQUIRED_PRESET_FIELDS: tuple[str, ...] = (
    "baseline_or_ablation_tag",
    "run_label",
    "hypothesis_focus",
    "protocol_version",
    "artifact_schema_version",
    "evaluation_protocol_version",
)

_COMMON_COMPARABILITY = {
    "domain_objective": "pilot-domain",
    "seed": 7,
    "model_ids": {
        "generator": "gpt-4.1-mini",
        "critic_a": "gpt-4.1",
        "critic_b": "gpt-4.1",
    },
    "protocol_version": "0.1.0",
    "artifact_schema_version": "v1",
    "evaluation_protocol_version": "milestone-1",
}

_PRESETS: dict[str, dict[str, Any]] = {
    "B0": {
        **_COMMON_COMPARABILITY,
        "baseline_or_ablation_tag": "B0",
        "run_label": "baseline-full-pipeline",
        "hypothesis_focus": ["H1", "H2", "H3", "H4"],
        "pipeline_config": {
            "global_diversification_enabled": True,
            "local_diversification_enabled": True,
            "complexification_enabled": True,
            "dual_critic_enabled": True,
        },
    },
    "A1": {
        **_COMMON_COMPARABILITY,
        "baseline_or_ablation_tag": "A1",
        "run_label": "ablation-no-global-diversification",
        "hypothesis_focus": ["H1"],
        "pipeline_config": {
            "global_diversification_enabled": False,
            "local_diversification_enabled": True,
            "complexification_enabled": True,
            "dual_critic_enabled": True,
        },
    },
    "A4": {
        **_COMMON_COMPARABILITY,
        "baseline_or_ablation_tag": "A4",
        "run_label": "ablation-single-critic",
        "hypothesis_focus": ["H4"],
        "pipeline_config": {
            "global_diversification_enabled": True,
            "local_diversification_enabled": True,
            "complexification_enabled": True,
            "dual_critic_enabled": False,
            "single_critic_mode": "critic_a",
        },
    },
}


def get_config_preset(preset_id: str) -> dict[str, Any]:
    if preset_id not in _PRESETS:
        raise ValueError(f"Unsupported preset_id: {preset_id}")
    return deepcopy(_PRESETS[preset_id])


def validate_all_presets() -> dict[str, Any]:
    issues: list[str] = []
    missing_fields: dict[str, list[str]] = {}
    non_comparable_fields: list[str] = []

    for preset_id in PRESET_IDS:
        preset = _PRESETS[preset_id]
        missing = [field for field in REQUIRED_PRESET_FIELDS if field not in preset]
        if missing:
            missing_fields[preset_id] = missing
            issues.append(f"{preset_id} missing required fields: {', '.join(missing)}")

    baseline = _PRESETS["B0"]
    for field in COMPARABILITY_FIELDS:
        for preset_id in PRESET_IDS:
            if _PRESETS[preset_id].get(field) != baseline.get(field):
                non_comparable_fields.append(field)
                issues.append(f"Comparability field {field} differs for preset {preset_id}")
                break

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "missing_fields": missing_fields,
        "non_comparable_fields": non_comparable_fields,
    }


def build_run_request(preset_id: str) -> dict[str, Any]:
    preset = get_config_preset(preset_id)
    return {
        "domain_objective": preset["domain_objective"],
        "seed": preset["seed"],
        "model_ids": preset["model_ids"],
        "pipeline_config": preset["pipeline_config"],
        "manifest_metadata": {
            field: preset[field]
            for field in REQUIRED_PRESET_FIELDS
        },
    }
