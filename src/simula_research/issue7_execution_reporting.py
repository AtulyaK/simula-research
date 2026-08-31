from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from simula_research.evaluation_metrics import (
    build_gate_report,
    compute_coverage_metrics,
    compute_quality_metrics,
)
from simula_research.critic_provider_adapter import (
    critic_sample_evaluator_from_env,
    provider_runtime_from_env,
)
from simula_research.pipeline import run_pipeline
from simula_research.run_config_presets import PRESET_IDS, build_run_request, validate_all_presets

_TAXONOMY_ELIGIBILITY_POLICY = "all-taxonomy-nodes-from-run-policy"
_COMPLEXITY_NOT_EVALUABLE_REASON = "missing_pairwise_complexity_judgments"


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _augment_coverage_with_stage3_visibility(
    coverage: dict[str, Any],
    stage3_samples: list[dict[str, Any]],
    taxonomy_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    taxonomy_node_ids = [str(node["taxonomy_node_id"]) for node in taxonomy_nodes]
    stage3_node_ids: set[str] = set()
    stage3_sample_counts_by_node = {node_id: 0 for node_id in taxonomy_node_ids}
    for sample in stage3_samples:
        node_id = str(sample.get("taxonomy_node_id", ""))
        if node_id in stage3_sample_counts_by_node:
            stage3_node_ids.add(node_id)
            stage3_sample_counts_by_node[node_id] += 1
    return {
        **coverage,
        "taxonomy_eligibility_policy": _TAXONOMY_ELIGIBILITY_POLICY,
        "eligible_node_ids": taxonomy_node_ids,
        "stage3_sampled_nodes": sorted(stage3_node_ids),
        "stage3_sample_counts_by_node": stage3_sample_counts_by_node,
        "nodes_without_stage3_samples": [
            node_id for node_id in taxonomy_node_ids if node_id not in stage3_node_ids
        ],
    }


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _compute_not_evaluable_complexity_metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
    complexified_count = sum(1 for sample in samples if bool(sample.get("is_complexified")))
    fallback_count = sum(
        1
        for sample in samples
        if str(sample.get("complexity_source", "")) == "fallback_original_due_to_semantic_failure"
    )
    sample_count = len(samples)
    return {
        "calibrated_score_distribution": {"p25": None, "p50": None, "p75": None},
        "complexity_shift": None,
        "complexification_precision": None,
        "complexification_pairs_evaluated": 0,
        "evaluation_status": "not_evaluable",
        "not_evaluable_reason": _COMPLEXITY_NOT_EVALUABLE_REASON,
        "proxy_metrics": {
            "sample_count": sample_count,
            "complexified_sample_count": complexified_count,
            "uncomplexified_sample_count": sample_count - complexified_count,
            "complexified_sample_ratio": _safe_ratio(complexified_count, sample_count),
            "semantic_preservation_fallback_count": fallback_count,
        },
    }


def _overall_gate_status(gates: dict[str, Any]) -> str:
    gate_status_values = [
        entry["status"]
        for gate_name, entry in gates.items()
        if gate_name != "overall_status"
    ]
    if "fail" in gate_status_values:
        return "fail"
    if "not_evaluable" in gate_status_values:
        return "not_evaluable"
    if "todo" in gate_status_values:
        return "todo"
    return "pass"


def _mark_complexity_gate_not_evaluable(gate_report: dict[str, Any], reason: str) -> None:
    gate = gate_report["gate_decision"]["complexity.complexification_precision"]
    gate["status"] = "not_evaluable"
    gate["actual"] = None
    gate["not_evaluable_reason"] = reason
    gate_report["gate_decision"]["overall_status"] = _overall_gate_status(gate_report["gate_decision"])


def _build_failure_analysis(gate_decision: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for gate_name, gate_status in gate_decision.items():
        if gate_name == "overall_status":
            continue
        if gate_status["status"] == "fail":
            notes.append(
                f"Failed threshold: {gate_name} "
                f"({gate_status['actual']} {gate_status['comparator']} {gate_status['threshold']})."
            )
        elif gate_status["status"] == "not_evaluable":
            notes.append(
                f"Not evaluable threshold: {gate_name} "
                f"({gate_status.get('not_evaluable_reason', 'missing evidence')})."
            )
    if not notes:
        notes.append("No threshold failures detected for this run.")
    return notes


def execute_issue7_matrix(
    artifact_root: str | Path = "artifacts/runs",
    report_root: str | Path = "artifacts/reports",
    branch_name: str = "unknown",
    commit_hash: str = "unknown",
    per_node_instantiation_count: int | None = None,
) -> dict[str, Any]:
    if per_node_instantiation_count is not None and (
        isinstance(per_node_instantiation_count, bool)
        or not isinstance(per_node_instantiation_count, int)
        or per_node_instantiation_count <= 0
    ):
        raise ValueError("per_node_instantiation_count must be a positive integer")

    preset_validation = validate_all_presets()
    if not preset_validation["ok"]:
        raise ValueError(f"Preset validation failed: {preset_validation['issues']}")

    execution_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    matrix_root = Path(report_root) / "issue7" / execution_id
    matrix_root.mkdir(parents=True, exist_ok=True)
    run_reports: dict[str, dict[str, Any]] = {}

    for preset_id in PRESET_IDS:
        request = build_run_request(preset_id)
        provider_runtime = provider_runtime_from_env()
        backend = str(provider_runtime.get("critic_backend", "")).strip().lower()
        provider_event_log: list[dict[str, Any]] | None = (
            [] if backend in {"nim", "nvidia"} else None
        )
        critic_sample_evaluator = critic_sample_evaluator_from_env(event_log=provider_event_log)
        model_ids = dict(request["model_ids"])
        nim_critic = provider_runtime.get("nim_critic")
        critic_models = nim_critic.get("critic_models") if isinstance(nim_critic, dict) else None
        if isinstance(critic_models, dict):
            for critic_id in ("critic_a", "critic_b"):
                model_id = critic_models.get(critic_id)
                if isinstance(model_id, str) and model_id:
                    model_ids[critic_id] = model_id
        pipeline_kwargs: dict[str, Any] = {
            "seed": int(request["seed"]),
            "model_ids": model_ids,
            "domain_objective": str(request["domain_objective"]),
            "artifact_root": artifact_root,
            "pipeline_config": dict(request["pipeline_config"]),
            "manifest_metadata": {
                "owner": os.environ.get("SIMULA_RUN_OWNER", "simula-research"),
                "branch": branch_name,
                "commit_hash": commit_hash,
                **dict(request["manifest_metadata"]),
            },
            "provider_runtime": provider_runtime,
            "provider_event_log": provider_event_log,
            "critic_sample_evaluator": critic_sample_evaluator,
        }
        local_diversification_config = request.get("local_diversification_config")
        if per_node_instantiation_count is not None:
            local_diversification_config = dict(local_diversification_config or {})
            local_diversification_config["per_node_instantiation_count"] = (
                per_node_instantiation_count
            )
        if local_diversification_config is not None:
            pipeline_kwargs["local_diversification_config"] = dict(local_diversification_config)
        if request.get("complexification_config") is not None:
            pipeline_kwargs["complexification_config"] = dict(request["complexification_config"])
        pipeline_result = run_pipeline(**pipeline_kwargs)

        stage4 = pipeline_result["stage_outputs"]["stage_4_dual_critic_quality_verification"]
        stage3 = pipeline_result["stage_outputs"]["stage_3_complexification"]
        stage3_samples = _read_json(stage3["complexification_artifacts"]["samples"])
        stage4_decisions = _read_json(stage4["stage4_artifacts"]["critic_decisions"])
        accepted_samples = [entry for entry in stage4_decisions if entry["quality_status"] == "accepted"]
        taxonomy_nodes = list(pipeline_result["taxonomy"]["nodes"])
        coverage = _augment_coverage_with_stage3_visibility(
            compute_coverage_metrics(
                eligible_nodes=taxonomy_nodes,
                accepted_samples=accepted_samples,
            ),
            stage3_samples=stage3_samples,
            taxonomy_nodes=taxonomy_nodes,
        )

        decisions_by_instantiation_id = {
            str(decision["instantiation_id"]): decision for decision in stage4_decisions
        }
        complexity_samples = [
            {
                **sample,
                "quality_status": decisions_by_instantiation_id.get(
                    str(sample["instantiation_id"]), {}
                ).get("quality_status", sample.get("quality_status")),
            }
            for sample in stage3_samples
        ]
        complexity = _compute_not_evaluable_complexity_metrics(complexity_samples)

        quality = compute_quality_metrics(issue5_outputs=stage4)

        protocol = {
            "domain_objective": request["domain_objective"],
            "taxonomy_eligibility_policy": _TAXONOMY_ELIGIBILITY_POLICY,
            "complexity_judgment_protocol": {
                "version": "milestone-1",
                "k_factor": 32,
                "initial_rating": 1000,
                "minimum_comparisons_per_sample": 5,
                "evidence_status": "not_evaluable",
                "not_evaluable_reason": _COMPLEXITY_NOT_EVALUABLE_REASON,
            },
            "critic_adjudication_config": {
                "mode": "dual_critic" if request["pipeline_config"]["dual_critic_enabled"] else "single_critic",
                "policy": "reject_on_disagreement",
            },
            "artifact_schema_version": pipeline_result["manifest"]["artifact_schema_version"],
            **request["manifest_metadata"],
        }
        if provider_runtime:
            protocol["provider_runtime"] = provider_runtime
        if per_node_instantiation_count is not None:
            protocol["matrix_overrides"] = {
                "per_node_instantiation_count": per_node_instantiation_count,
            }
        run_identity = {
            "run_id": pipeline_result["manifest"]["run_id"],
            "seed": pipeline_result["manifest"]["seed"],
            "branch": branch_name,
            "commit_hash": commit_hash,
            "timestamp_utc": datetime.now(UTC).isoformat(),
        }
        gate_report = build_gate_report(
            run_identity=run_identity,
            protocol=protocol,
            coverage_metrics=coverage,
            complexity_metrics=complexity,
            quality_metrics=quality,
            notes=[],
        )
        gate_report["complexity"] = complexity
        _mark_complexity_gate_not_evaluable(
            gate_report,
            reason=_COMPLEXITY_NOT_EVALUABLE_REASON,
        )
        failure_analysis = _build_failure_analysis(gate_report["gate_decision"])
        gate_report["notes"] = failure_analysis

        run_dir = matrix_root / preset_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_report_path = run_dir / "run_report.json"
        gate_report_path = run_dir / "gate_report.json"
        stage0_outputs = pipeline_result["stage_outputs"].get("stage_0_domain_run_spec", {})
        spec_artifacts = stage0_outputs.get("spec_artifacts", {})
        manifest_path = spec_artifacts.get("manifest") or str(
            Path(artifact_root) / str(pipeline_result["manifest"]["run_id"]) / "00_spec" / "manifest.json"
        )
        run_report_payload = {
            "run_identity": run_identity,
            "protocol": protocol,
            "coverage_evidence": coverage,
            "complexity_evidence": complexity,
            "quality_evidence": quality,
            "gate_summary": gate_report["gate_decision"],
            "failure_analysis": failure_analysis,
            "artifacts": {"manifest": manifest_path},
        }
        run_report_path.write_text(json.dumps(run_report_payload, indent=2, sort_keys=True), encoding="utf-8")
        gate_report_path.write_text(json.dumps(gate_report, indent=2, sort_keys=True), encoding="utf-8")

        run_reports[preset_id] = {
            "run_identity": run_identity,
            "protocol": protocol,
            "coverage": coverage,
            "complexity": complexity,
            "quality": quality,
            "gate_report": gate_report,
            "failure_analysis": failure_analysis,
            "artifacts": {
                "run_report": str(run_report_path),
                "gate_report": str(gate_report_path),
                "manifest": manifest_path,
            },
        }

    comparison_tables = {
        "coverage_comparison": [
            {
                "preset_id": preset_id,
                "node_coverage_ratio": run_reports[preset_id]["coverage"]["node_coverage_ratio"],
                "coverage_balance": run_reports[preset_id]["coverage"]["coverage_balance"],
            }
            for preset_id in PRESET_IDS
        ],
        "complexity_comparison": [
            {
                "preset_id": preset_id,
                "complexity_shift": run_reports[preset_id]["complexity"]["complexity_shift"],
                "complexification_precision": run_reports[preset_id]["complexity"]["complexification_precision"],
                "complexity_evaluation_status": run_reports[preset_id]["complexity"]["evaluation_status"],
                "complexity_proxy_metrics": run_reports[preset_id]["complexity"]["proxy_metrics"],
            }
            for preset_id in PRESET_IDS
        ],
        "quality_comparison": [
            {
                "preset_id": preset_id,
                "acceptance_rate": run_reports[preset_id]["quality"]["acceptance_rate"],
                "critic_agreement": run_reports[preset_id]["quality"]["critic_agreement"],
                "regen_burden": run_reports[preset_id]["quality"]["regen_burden"],
            }
            for preset_id in PRESET_IDS
        ],
        "gate_comparison": [
            {
                "preset_id": preset_id,
                "overall_status": run_reports[preset_id]["gate_report"]["gate_decision"]["overall_status"],
            }
            for preset_id in PRESET_IDS
        ],
    }
    comparison_tables_path = matrix_root / "comparison_tables.json"
    comparison_tables_path.write_text(
        json.dumps(comparison_tables, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "execution_id": execution_id,
        "matrix_root": str(matrix_root),
        "run_reports": run_reports,
        "comparison_tables_path": str(comparison_tables_path),
    }
