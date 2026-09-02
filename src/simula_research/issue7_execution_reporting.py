from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from simula_research.evaluation_metrics import (
    build_gate_report,
    compute_complexity_metrics,
    compute_coverage_metrics,
    compute_quality_metrics,
)
from simula_research.complexity_judgments import (
    build_elo_comparisons,
    calibrate_elo_ratings,
)
from simula_research.critic_provider_adapter import (
    critic_sample_evaluator_from_env,
    provider_runtime_from_env,
)
from simula_research.pipeline import run_pipeline
from simula_research.provider_protocols import ComplexityJudgmentProviderFn
from simula_research.run_config_presets import PRESET_IDS, build_run_request, validate_all_presets
from simula_research.validators import validate_artifact_tree

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


def _compute_not_evaluable_complexity_metrics(
    samples: list[dict[str, Any]],
    *,
    reason: str = _COMPLEXITY_NOT_EVALUABLE_REASON,
    pairwise_count: int = 0,
) -> dict[str, Any]:
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
        "complexification_pairs_evaluated": pairwise_count,
        "evaluation_status": "not_evaluable",
        "not_evaluable_reason": reason,
        "proxy_metrics": {
            "sample_count": sample_count,
            "complexified_sample_count": complexified_count,
            "uncomplexified_sample_count": sample_count - complexified_count,
            "complexified_sample_ratio": _safe_ratio(complexified_count, sample_count),
            "semantic_preservation_fallback_count": fallback_count,
        },
    }


def _compute_complexity_metrics_from_judgments(
    samples: list[dict[str, Any]],
    pairwise_judgments: list[dict[str, Any]],
    minimum_comparisons_per_sample: int,
    initial_rating: int,
    k_factor: int,
) -> dict[str, Any]:
    complexified_samples = [
        sample for sample in samples if bool(sample.get("is_complexified"))
    ]
    if not pairwise_judgments:
        return _compute_not_evaluable_complexity_metrics(samples)

    judgments_by_sample: dict[str, list[dict[str, Any]]] = {}
    for judgment in pairwise_judgments:
        if not isinstance(judgment, dict):
            raise ValueError("persisted complexity judgments must contain objects")
        sample_id = str(judgment.get("instantiation_id", ""))
        judgments_by_sample.setdefault(sample_id, []).append(judgment)

    insufficient_sample_ids = [
        str(sample.get("instantiation_id", ""))
        for sample in complexified_samples
        if len(judgments_by_sample.get(str(sample.get("instantiation_id", "")), []))
        < minimum_comparisons_per_sample
    ]
    if insufficient_sample_ids:
        return _compute_not_evaluable_complexity_metrics(
            samples,
            reason="insufficient_pairwise_complexity_judgments",
            pairwise_count=len(pairwise_judgments),
        )

    run_scores = [
        sum(float(judgment["complexified_score"]) for judgment in judgments)
        / len(judgments)
        for judgments in judgments_by_sample.values()
    ]
    baseline_scores = [
        sum(float(judgment["baseline_score"]) for judgment in judgments)
        / len(judgments)
        for judgments in judgments_by_sample.values()
    ]
    complexity = compute_complexity_metrics(
        run_complexity_scores=run_scores,
        baseline_complexity_scores=baseline_scores,
        complexification_pairs=pairwise_judgments,
    )
    elo_ratings = calibrate_elo_ratings(
        build_elo_comparisons(pairwise_judgments),
        initial_rating=initial_rating,
        k_factor=k_factor,
    )
    elo_values = list(elo_ratings.values())
    elo_min = min(elo_values)
    elo_max = max(elo_values)
    elo_span = elo_max - elo_min
    normalized_elo_ratings = {
        item_id: (
            50.0
            if elo_span == 0
            else (rating - elo_min) / elo_span * 100.0
        )
        for item_id, rating in elo_ratings.items()
    }
    complexity["elo_calibration"] = {
        "method": "elo_v1",
        "initial_rating": initial_rating,
        "k_factor": k_factor,
        "comparison_count": len(pairwise_judgments),
        "ratings": elo_ratings,
        "normalized_ratings": normalized_elo_ratings,
    }
    complexity["proxy_metrics"] = _compute_not_evaluable_complexity_metrics(samples)["proxy_metrics"]
    complexity["judgment_sample_count"] = len(judgments_by_sample)
    return complexity


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


def _load_persisted_run_inputs(
    artifact_root: str | Path,
    pipeline_result: dict[str, Any],
) -> dict[str, Any]:
    manifest = pipeline_result["manifest"]
    run_id = str(manifest["run_id"])
    run_root = Path(artifact_root) / run_id
    canonical_manifest_path = run_root / "00_spec" / "manifest.json"
    if not canonical_manifest_path.is_file():
        stage_outputs = pipeline_result["stage_outputs"]
        stage3 = stage_outputs["stage_3_complexification"]
        stage4 = stage_outputs["stage_4_dual_critic_quality_verification"]
        stage3_artifacts = stage3["complexification_artifacts"]
        stage4_artifacts = stage4["stage4_artifacts"]
        stage4_decisions = _read_json(stage4_artifacts["critic_decisions"])
        pairwise_path = stage3_artifacts.get("pairwise_judgments")
        return {
            "manifest": manifest,
            "stage_outputs": stage_outputs,
            "taxonomy_nodes": list(pipeline_result["taxonomy"]["nodes"]),
            "stage3_samples": _read_json(stage3_artifacts["samples"]),
            "stage4_decisions": stage4_decisions,
            "accepted_samples": [
                decision
                for decision in stage4_decisions
                if decision.get("quality_status") == "accepted"
            ],
            "regenerations": (
                _read_json(stage4_artifacts["regenerations"])
                if stage4_artifacts.get("regenerations")
                else []
            ),
            "pairwise_judgments": _read_json(pairwise_path) if pairwise_path else [],
            "manifest_path": str(canonical_manifest_path),
            "artifact_validation": None,
        }

    artifact_validation = validate_artifact_tree(run_root)
    if not artifact_validation["ok"]:
        raise ValueError(
            f"Persisted artifact validation failed for {run_id}: "
            f"{artifact_validation['issues']}"
        )

    persisted_manifest = _read_json(canonical_manifest_path)
    stage_outputs_path = run_root / "00_spec" / "stage_outputs.json"
    stage_outputs = _read_json(stage_outputs_path)
    stage4_decisions = _read_json(run_root / "40_dual_critic_quality" / "critic_decisions.json")
    return {
        "manifest": persisted_manifest,
        "stage_outputs": stage_outputs,
        "taxonomy_nodes": _read_json(run_root / "10_taxonomy" / "taxonomy_nodes.json"),
        "stage3_samples": _read_json(run_root / "30_complexification" / "samples.json"),
        "stage4_decisions": stage4_decisions,
        "accepted_samples": _read_json(run_root / "50_curated_dataset" / "accepted_samples.json"),
        "regenerations": _read_json(run_root / "40_dual_critic_quality" / "regenerations.json"),
        "pairwise_judgments": _read_json(run_root / "30_complexification" / "pairwise_judgments.json"),
        "manifest_path": str(canonical_manifest_path),
        "artifact_validation": artifact_validation,
    }


def execute_issue7_matrix(
    artifact_root: str | Path = "artifacts/runs",
    report_root: str | Path = "artifacts/reports",
    branch_name: str = "unknown",
    commit_hash: str = "unknown",
    per_node_instantiation_count: int | None = None,
    complexity_judgment_provider: ComplexityJudgmentProviderFn | None = None,
    complexity_judgment_config: dict[str, int] | None = None,
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
            "complexity_judgment_provider": complexity_judgment_provider,
            "complexity_judgment_config": complexity_judgment_config,
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
        if request.get("dual_critic_config") is not None:
            pipeline_kwargs["dual_critic_config"] = dict(request["dual_critic_config"])
        pipeline_result = run_pipeline(**pipeline_kwargs)

        persisted = _load_persisted_run_inputs(artifact_root, pipeline_result)
        persisted_manifest = persisted["manifest"]
        stage3_samples = persisted["stage3_samples"]
        stage4_decisions = persisted["stage4_decisions"]
        accepted_samples = persisted["accepted_samples"]
        taxonomy_nodes = persisted["taxonomy_nodes"]
        agreement_evaluable_samples = sum(
            1 for decision in stage4_decisions if bool(decision.get("agreement_evaluable", True))
        )
        agreements = sum(
            1 for decision in stage4_decisions if decision.get("agreement_status") == "agree"
        )
        disagreements = sum(
            1 for decision in stage4_decisions if decision.get("agreement_status") == "disagree"
        )
        stage4 = {
            "reviewed_samples": len(stage4_decisions),
            "accepted_samples": len(accepted_samples),
            "agreements": agreements,
            "disagreements": disagreements,
            "agreement_evaluable_samples": agreement_evaluable_samples,
            "agreement_non_evaluable_samples": len(stage4_decisions) - agreement_evaluable_samples,
            "regenerated_samples": len(persisted["regenerations"]),
        }
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
        pairwise_judgments = persisted["pairwise_judgments"]
        if not isinstance(pairwise_judgments, list):
            raise ValueError("persisted pairwise complexity judgments must be a list")
        run_config = persisted_manifest.get("run_config", {})
        judgment_config = (
            run_config.get("complexity_judgment_config", {})
            if isinstance(run_config, dict)
            else {}
        )
        minimum_comparisons = int(
            judgment_config.get("minimum_comparisons_per_sample", 5)
        )
        complexity = _compute_complexity_metrics_from_judgments(
            samples=complexity_samples,
            pairwise_judgments=pairwise_judgments,
            minimum_comparisons_per_sample=minimum_comparisons,
            initial_rating=int(judgment_config.get("initial_rating", 1000)),
            k_factor=int(judgment_config.get("k_factor", 32)),
        )

        quality = compute_quality_metrics(issue5_outputs=stage4)

        complexity_judgment_protocol = {
            "version": "milestone-1",
            "k_factor": int(judgment_config.get("k_factor", 32)),
            "initial_rating": int(judgment_config.get("initial_rating", 1000)),
            "minimum_comparisons_per_sample": minimum_comparisons,
            "evidence_status": complexity["evaluation_status"],
        }
        if complexity["evaluation_status"] != "evaluated":
            complexity_judgment_protocol["not_evaluable_reason"] = complexity.get(
                "not_evaluable_reason",
                _COMPLEXITY_NOT_EVALUABLE_REASON,
            )
        protocol = {
            "domain_objective": request["domain_objective"],
            "taxonomy_eligibility_policy": _TAXONOMY_ELIGIBILITY_POLICY,
            "complexity_judgment_protocol": complexity_judgment_protocol,
            "critic_adjudication_config": {
                "mode": "dual_critic" if request["pipeline_config"]["dual_critic_enabled"] else "single_critic",
                "policy": (
                    f"{request.get('dual_critic_config', {}).get('disagreement_policy', 'reject')}"
                    "_on_disagreement"
                ),
            },
            "artifact_schema_version": persisted_manifest["artifact_schema_version"],
            **request["manifest_metadata"],
        }
        if provider_runtime:
            protocol["provider_runtime"] = provider_runtime
        if per_node_instantiation_count is not None:
            protocol["matrix_overrides"] = {
                "per_node_instantiation_count": per_node_instantiation_count,
            }
        run_identity = {
            "run_id": persisted_manifest["run_id"],
            "seed": persisted_manifest["seed"],
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
        if complexity["evaluation_status"] != "evaluated":
            _mark_complexity_gate_not_evaluable(
                gate_report,
                reason=complexity.get(
                    "not_evaluable_reason",
                    _COMPLEXITY_NOT_EVALUABLE_REASON,
                ),
            )
        failure_analysis = _build_failure_analysis(gate_report["gate_decision"])
        gate_report["notes"] = failure_analysis

        run_dir = matrix_root / preset_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_report_path = run_dir / "run_report.json"
        gate_report_path = run_dir / "gate_report.json"
        manifest_path = persisted["manifest_path"]
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
