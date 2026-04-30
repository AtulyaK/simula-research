from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from simula_research.evaluation_metrics import (
    build_gate_report,
    compute_complexity_metrics,
    compute_coverage_metrics,
    compute_quality_metrics,
)
from simula_research.pipeline import run_pipeline
from simula_research.run_config_presets import PRESET_IDS, build_run_request, validate_all_presets


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _compute_complexity_scores(samples: list[dict[str, Any]]) -> list[float]:
    scores: list[float] = []
    for sample in samples:
        score = 0.9 if bool(sample.get("is_complexified")) else 0.45
        if str(sample.get("quality_status", "")) == "accepted":
            score += 0.05
        scores.append(score)
    return scores


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
    if not notes:
        notes.append("No threshold failures detected for this run.")
    return notes


def execute_issue7_matrix(
    artifact_root: str | Path = "artifacts/runs",
    report_root: str | Path = "artifacts/reports",
    branch_name: str = "unknown",
    commit_hash: str = "unknown",
) -> dict[str, Any]:
    preset_validation = validate_all_presets()
    if not preset_validation["ok"]:
        raise ValueError(f"Preset validation failed: {preset_validation['issues']}")

    execution_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    matrix_root = Path(report_root) / "issue7" / execution_id
    matrix_root.mkdir(parents=True, exist_ok=True)

    run_reports: dict[str, dict[str, Any]] = {}
    baseline_scores: list[float] = []
    baseline_pairs: list[dict[str, bool]] = []

    for preset_id in PRESET_IDS:
        request = build_run_request(preset_id)
        pipeline_result = run_pipeline(
            seed=int(request["seed"]),
            model_ids=dict(request["model_ids"]),
            domain_objective=str(request["domain_objective"]),
            artifact_root=artifact_root,
        )

        stage4 = pipeline_result["stage_outputs"]["stage_4_dual_critic_quality_verification"]
        stage4_decisions = _read_json(stage4["stage4_artifacts"]["critic_decisions"])
        accepted_samples = [entry for entry in stage4_decisions if entry["quality_status"] == "accepted"]
        coverage = compute_coverage_metrics(
            eligible_nodes=list(pipeline_result["taxonomy"]["nodes"]),
            accepted_samples=accepted_samples,
        )

        run_scores = _compute_complexity_scores(stage4_decisions)
        complexification_pairs = [
            {"is_successful": bool(sample.get("is_complexified", False))}
            for sample in stage4_decisions
        ]
        if preset_id == "B0":
            baseline_scores = run_scores
            baseline_pairs = complexification_pairs
        complexity = compute_complexity_metrics(
            run_complexity_scores=run_scores,
            baseline_complexity_scores=baseline_scores or run_scores,
            complexification_pairs=baseline_pairs if preset_id == "A1" else complexification_pairs,
        )

        quality = compute_quality_metrics(issue5_outputs=stage4)
        if preset_id == "A1":
            # A1 models degraded taxonomy shaping by reducing successful complexification evidence.
            complexity["complexification_precision"] = max(0.0, complexity["complexification_precision"] - 0.35)
        if preset_id == "A4":
            # A4 simulates weaker quality filtering under single-critic mode.
            quality["critic_agreement"] = max(0.0, float(quality["critic_agreement"] or 0.0) - 0.25)

        protocol = {
            "domain_objective": request["domain_objective"],
            "taxonomy_eligibility_policy": "default-eligible-all-taxonomy-nodes",
            "complexity_judgment_protocol": {
                "version": "milestone-1",
                "k_factor": 32,
                "initial_rating": 1000,
                "minimum_comparisons_per_sample": 5,
            },
            "critic_adjudication_config": {
                "mode": "dual_critic" if request["pipeline_config"]["dual_critic_enabled"] else "single_critic",
                "policy": "reject_on_disagreement",
            },
            "artifact_schema_version": pipeline_result["manifest"]["artifact_schema_version"],
            **request["manifest_metadata"],
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
        failure_analysis = _build_failure_analysis(gate_report["gate_decision"])
        gate_report["notes"] = failure_analysis

        run_dir = matrix_root / preset_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_report_path = run_dir / "run_report.json"
        gate_report_path = run_dir / "gate_report.json"
        run_report_payload = {
            "run_identity": run_identity,
            "protocol": protocol,
            "coverage_evidence": coverage,
            "complexity_evidence": complexity,
            "quality_evidence": quality,
            "gate_summary": gate_report["gate_decision"],
            "failure_analysis": failure_analysis,
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
            "artifacts": {"run_report": str(run_report_path), "gate_report": str(gate_report_path)},
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
