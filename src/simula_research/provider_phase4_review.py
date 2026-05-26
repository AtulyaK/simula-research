from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PRESET_IDS: tuple[str, ...] = ("B0", "A1", "A4")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _status_for_uniform(values: set[str], detail: str) -> dict[str, str]:
    if len(values) == 1:
        return {"status": "pass", "details": detail}
    return {"status": "fail", "details": f"Values differ: {sorted(values)}"}


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _comparability_constraints(gate_reports: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    protocols = {
        preset: gate.get("protocol") if isinstance(gate.get("protocol"), dict) else {}
        for preset, gate in gate_reports.items()
    }
    artifact_versions = {str(protocol.get("artifact_schema_version", "")) for protocol in protocols.values()}
    domain_objectives = {str(protocol.get("domain_objective", "")) for protocol in protocols.values()}
    taxonomy_policies = {str(protocol.get("taxonomy_eligibility_policy", "")) for protocol in protocols.values()}
    complexity_protocols = {
        _json_key(protocol.get("complexity_judgment_protocol", {})) for protocol in protocols.values()
    }
    provider_runtimes = {_json_key(protocol.get("provider_runtime", {})) for protocol in protocols.values()}

    critic_modes = {
        preset: str((protocol.get("critic_adjudication_config") or {}).get("mode", ""))
        for preset, protocol in protocols.items()
    }
    critic_policies = {
        str((protocol.get("critic_adjudication_config") or {}).get("policy", ""))
        for protocol in protocols.values()
    }
    if (
        critic_modes.get("B0") == "dual_critic"
        and critic_modes.get("A1") == "dual_critic"
        and critic_modes.get("A4") == "single_critic"
        and len(critic_policies) == 1
    ):
        critic_check: dict[str, Any] = {
            "status": "mixed",
            "mixed_reason": "documented_ablation",
            "details": "B0/A1 use dual_critic; A4 uses single_critic by design as ablation.",
        }
    else:
        critic_check = _status_for_uniform(
            {f"{mode}:{policy}" for mode in critic_modes.values() for policy in critic_policies},
            "Critic adjudication configuration is uniform.",
        )

    return {
        "artifact_schema_version": _status_for_uniform(artifact_versions, "All runs report one artifact schema version."),
        "domain_objective": _status_for_uniform(domain_objectives, "All runs report one domain objective."),
        "taxonomy_eligibility_policy": _status_for_uniform(
            taxonomy_policies,
            "All runs report one taxonomy eligibility policy.",
        ),
        "complexity_judgment_protocol": _status_for_uniform(
            complexity_protocols,
            "All runs report one complexity judgment protocol.",
        ),
        "critic_adjudication_configuration": critic_check,
        "provider_runtime": _status_for_uniform(provider_runtimes, "All runs report one provider runtime."),
    }


def build_provider_phase4_review(
    *,
    matrix_root: str | Path,
    deterministic_baseline_packet: str | Path = "artifacts/reports/issue7/20260526T025931Z",
    commit_hash: str = "unknown",
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Build the provider addendum as an Issue #9-compatible review document."""
    root = Path(matrix_root)
    comparison_tables_path = root / "comparison_tables.json"
    if not comparison_tables_path.is_file():
        raise FileNotFoundError(f"Missing comparison tables: {comparison_tables_path}")

    timestamp = timestamp_utc or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    gate_reports: dict[str, dict[str, Any]] = {}
    gate_report_paths: list[str] = []
    run_ids: dict[str, str] = {}
    coverage_evidence: dict[str, Any] = {}
    complexity_evidence: dict[str, Any] = {}
    quality_evidence: dict[str, Any] = {}
    gate_outcomes: dict[str, Any] = {}

    for preset in PRESET_IDS:
        gate_path = root / preset / "gate_report.json"
        if not gate_path.is_file():
            raise FileNotFoundError(f"Missing {preset} gate report: {gate_path}")
        gate = _read_json(gate_path)
        gate_reports[preset] = gate
        gate_report_paths.append(str(gate_path))
        run_identity = gate.get("run_identity") if isinstance(gate.get("run_identity"), dict) else {}
        gate_decision = gate.get("gate_decision") if isinstance(gate.get("gate_decision"), dict) else {}
        run_ids[preset] = str(run_identity.get("run_id", ""))
        coverage = gate.get("coverage") if isinstance(gate.get("coverage"), dict) else {}
        complexity = gate.get("complexity") if isinstance(gate.get("complexity"), dict) else {}
        quality = gate.get("quality") if isinstance(gate.get("quality"), dict) else {}
        coverage_evidence[preset] = {
            "node_coverage_ratio": coverage.get("node_coverage_ratio"),
            "min_depth_coverage": gate_decision.get("coverage.min_depth_coverage", {}).get("actual")
            if isinstance(gate_decision.get("coverage.min_depth_coverage"), dict)
            else None,
            "coverage_balance": coverage.get("coverage_balance"),
        }
        complexity_evidence[preset] = {
            "complexity_shift": complexity.get("complexity_shift"),
            "complexification_precision": complexity.get("complexification_precision"),
            "pairs_evaluated": complexity.get("complexification_pairs_evaluated"),
        }
        quality_evidence[preset] = {
            "acceptance_rate": quality.get("acceptance_rate"),
            "critic_agreement": quality.get("critic_agreement"),
            "regen_burden": quality.get("regen_burden"),
        }
        gate_outcomes[preset] = {
            "overall_status": gate_decision.get("overall_status"),
            "run_id": run_identity.get("run_id"),
            "failed_thresholds": [
                key
                for key, value in gate_decision.items()
                if key != "overall_status" and isinstance(value, dict) and value.get("status") == "fail"
            ],
        }

    return {
        "addendum_metadata": {
            "addendum_id": f"provider_{root.name}",
            "issue_id": 8,
            "review_type": "milestone-1-provider-phase4-addendum",
            "evidence_packet": str(root),
            "review_timestamp_utc": timestamp,
            "agent_recommendation": "pending_human_review",
            "human_sign_off": {
                "required": True,
                "status": "pending",
                "recommended_decision": "conditional_pass",
                "reviewer": None,
                "signed_at_utc": None,
                "notes": "Provider-backed packet; compare to deterministic 20260526T025931Z before sign-off.",
                "fields": ["decision", "reviewer", "signed_at_utc", "notes"],
            },
            "deterministic_baseline_packet": str(deterministic_baseline_packet),
            "provider_runtime_source": "environment",
            "main_commit": commit_hash,
        },
        "evidence_intake": {
            "sources": {
                "comparison_tables": str(comparison_tables_path),
                "gate_reports": gate_report_paths,
            },
            "run_ids": run_ids,
            "coverage_evidence": coverage_evidence,
            "complexity_evidence": complexity_evidence,
            "quality_evidence": quality_evidence,
        },
        "comparability_constraints_check": _comparability_constraints(gate_reports),
        "gate_outcomes": gate_outcomes,
        "paper_alignment": {
            "traceability_auditability": "Separate provider packet with comparison tables and gate reports.",
            "protocol_comparability": "ADR 0003 thresholds unchanged; preset comparability fields frozen.",
            "control_axis_impact": "Live critics may shift quality axis; coverage and complexity stages remain deterministic.",
            "deviations": "none on thresholds or metric formulas",
        },
    }
