from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from simula_research.issue7_execution_reporting import execute_issue7_matrix
from simula_research.validators import validate_manifest_schema

# Must match keys emitted by evaluation_metrics.build_gate_report (issue7 gate_report.json).
METRIC_SECTIONS: tuple[str, ...] = ("coverage", "complexity", "quality")
ACCEPTABLE_DRIFT_MAX_DELTA = 0.02

# Canonical reason when `status: mixed` remains protocol-comparable (e.g. A4 single-critic ablation).
MIXED_REASON_DOCUMENTED_ABLATION = "documented_ablation"


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _collect_manifest_validation(gate_report_paths: list[str]) -> dict[str, dict[str, Any]]:
    validation_by_tag: dict[str, dict[str, Any]] = {}
    for gate_report_path in gate_report_paths:
        gate_path = Path(gate_report_path)
        run_report = _read_json(gate_path.with_name("run_report.json"))
        tag = run_report["protocol"]["baseline_or_ablation_tag"]
        manifest_path = Path(run_report.get("artifacts", {}).get("manifest", ""))
        if not manifest_path.is_file():
            validation_by_tag[tag] = {
                "ok": False,
                "issues": ["run_report artifacts.manifest must point to a persisted manifest file"],
                "manifest": None,
            }
            continue
        manifest_candidate = _read_json(manifest_path)
        validation = validate_manifest_schema(manifest_candidate)
        validation_by_tag[tag] = {
            "ok": validation["ok"],
            "issues": validation["issues"],
            "manifest": manifest_candidate,
        }
    return validation_by_tag


def _resolve_gate_report_path_for_preset(gate_report_paths: list[str], preset_tag: str = "B0") -> Path:
    """Pick baseline gate_report.json by directory name, not POSIX string fragments."""
    want = preset_tag.strip()
    if not want:
        raise ValueError("preset_tag must be non-empty")

    for raw in gate_report_paths:
        path = Path(raw)
        resolved = path
        try:
            if path.exists():
                resolved = path.resolve()
        except OSError:
            resolved = path
        parent = resolved.parent.name
        if parent == want and resolved.name.lower() == "gate_report.json":
            return resolved

        # Fallback: find preset segment adjacent to gate_report anywhere in the path parts.
        parts = resolved.parts
        for i in range(len(parts) - 1):
            if parts[i] == want and parts[i + 1].lower() == "gate_report.json":
                return resolved

    raise ValueError(
        f"No gate_report.json found under a {preset_tag!r} directory in gate_report_paths: {gate_report_paths!r}"
    )


def _numeric_metric_paths(payload: Any, prefix: tuple[str, ...] = ()) -> dict[str, float]:
    if isinstance(payload, dict):
        metrics: dict[str, float] = {}
        for key, value in payload.items():
            metrics.update(_numeric_metric_paths(value, (*prefix, str(key))))
        return metrics
    if isinstance(payload, (int, float)) and not isinstance(payload, bool):
        return {".".join(prefix): float(payload)}
    return {}


def _collect_numeric_metrics(gate_report: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for section in METRIC_SECTIONS:
        section_metrics = _numeric_metric_paths(gate_report.get(section, {}))
        metrics.update({f"{section}.{path}": value for path, value in section_metrics.items()})
    return metrics


def _metric_delta_summary(
    baseline_gate_report: dict[str, Any],
    rerun_gate_report: dict[str, Any],
) -> dict[str, Any]:
    baseline_metrics = _collect_numeric_metrics(baseline_gate_report)
    rerun_metrics = _collect_numeric_metrics(rerun_gate_report)
    comparable_paths = sorted(set(baseline_metrics).intersection(rerun_metrics))
    missing_metric_paths = sorted(set(baseline_metrics).symmetric_difference(rerun_metrics))

    max_delta = 0.0
    for path in comparable_paths:
        max_delta = max(max_delta, abs(baseline_metrics[path] - rerun_metrics[path]))

    return {
        "max_metric_delta": max_delta,
        "metric_paths_compared": len(comparable_paths),
        "missing_metric_paths": missing_metric_paths,
    }


def _classify_baseline_rerun(
    baseline_gate_report: dict[str, Any],
    rerun_gate_report: dict[str, Any],
) -> dict[str, Any]:
    delta_summary = _metric_delta_summary(baseline_gate_report, rerun_gate_report)
    max_delta = float(delta_summary["max_metric_delta"])
    missing_metric_paths = list(delta_summary["missing_metric_paths"])
    metric_paths_compared = int(delta_summary["metric_paths_compared"])
    if missing_metric_paths or metric_paths_compared == 0:
        classification = "mismatch"
    elif max_delta == 0.0:
        classification = "exact"
    elif max_delta <= ACCEPTABLE_DRIFT_MAX_DELTA:
        classification = "acceptable_drift"
    else:
        classification = "mismatch"
    return {
        "classification": classification,
        "max_metric_delta": max_delta,
        "drift_threshold": ACCEPTABLE_DRIFT_MAX_DELTA,
        "metric_paths_compared": metric_paths_compared,
        "missing_metric_paths": missing_metric_paths,
    }


def evaluate_comparability_gate(milestone_review: dict[str, Any]) -> dict[str, Any]:
    """Evaluate Issue #9 fixed-protocol comparability hard gate (public API for tests and tooling)."""
    return _evaluate_comparability_gate(milestone_review)


def _evaluate_comparability_gate(milestone_review: dict[str, Any]) -> dict[str, Any]:
    checks = milestone_review.get("comparability_constraints_check", {})
    if not checks:
        return {
            "ok": False,
            "details": "Missing comparability_constraints_check evidence.",
        }

    failing_axes: list[str] = []
    for axis, axis_payload in checks.items():
        status = str(axis_payload.get("status", "")).lower()
        if status == "pass":
            continue
        if status == "mixed":
            mixed_reason = str(axis_payload.get("mixed_reason", "")).strip()
            # Structured field avoids brittle substring matching on free-text `details`.
            if mixed_reason == MIXED_REASON_DOCUMENTED_ABLATION:
                continue
            failing_axes.append(axis)
            continue
        failing_axes.append(axis)

    if failing_axes:
        return {
            "ok": False,
            "details": (
                f"Comparability gate failed for: {', '.join(sorted(failing_axes))}. "
                f"When status is mixed, set mixed_reason={MIXED_REASON_DOCUMENTED_ABLATION!r} for deliberate ablations."
            ),
        }
    return {
        "ok": True,
        "details": "Comparability constraints pass; any mixed axes declare mixed_reason=documented_ablation.",
    }


def _evaluate_audit_trace_gate(milestone_review: dict[str, Any], manifest_validation: dict[str, Any]) -> dict[str, Any]:
    intake = milestone_review.get("evidence_intake", {})
    sources = intake.get("sources", {})
    has_comparison_tables = bool(sources.get("comparison_tables"))
    gate_reports = sources.get("gate_reports", [])
    has_gate_reports = isinstance(gate_reports, list) and len(gate_reports) >= 3
    has_run_ids = isinstance(intake.get("run_ids"), dict) and len(intake.get("run_ids", {})) >= 3
    has_manifests = all("manifest" in payload for payload in manifest_validation.values())

    ok = has_comparison_tables and has_gate_reports and has_run_ids and has_manifests
    details = (
        "Audit traces include comparison tables, per-run gate reports, run IDs, and reconstructed manifests."
        if ok
        else "Audit trace evidence is incomplete."
    )
    return {"ok": ok, "details": details}


def run_issue9_reproducibility_check(
    milestone_review_json_path: str | Path = "artifacts/reports/issue8/milestone_gate_review.json",
    issue9_report_root: str | Path = "artifacts/reports/issue9",
    artifact_root: str | Path = "artifacts/runs",
    branch_name: str = "unknown",
    commit_hash: str = "unknown",
) -> dict[str, Any]:
    milestone_path = Path(milestone_review_json_path)
    milestone_review = _read_json(milestone_path)
    gate_report_paths = list(milestone_review["evidence_intake"]["sources"]["gate_reports"])

    manifest_validation = _collect_manifest_validation(gate_report_paths)
    baseline_gate_path = _resolve_gate_report_path_for_preset(gate_report_paths, "B0")
    baseline_gate_report = _read_json(baseline_gate_path)

    rerun_output = execute_issue7_matrix(
        artifact_root=artifact_root,
        report_root=issue9_report_root,
        branch_name=branch_name,
        commit_hash=commit_hash,
    )
    rerun_baseline_gate_report = rerun_output["run_reports"]["B0"]["gate_report"]
    baseline_rerun = _classify_baseline_rerun(
        baseline_gate_report=baseline_gate_report,
        rerun_gate_report=rerun_baseline_gate_report,
    )

    all_manifests_ok = all(item["ok"] for item in manifest_validation.values())
    reproducibility_gate_ok = all_manifests_ok and baseline_rerun["classification"] in {
        "exact",
        "acceptable_drift",
    }
    audit_trace_gate = _evaluate_audit_trace_gate(
        milestone_review=milestone_review,
        manifest_validation=manifest_validation,
    )
    comparability_gate = _evaluate_comparability_gate(milestone_review=milestone_review)
    hard_gates = {
        "reproducibility": {
            "ok": reproducibility_gate_ok,
            "details": (
                "Manifest validation passed and baseline rerun classified as exact/acceptable_drift."
                if reproducibility_gate_ok
                else "Manifest validation or baseline rerun classification failed hard gate."
            ),
        },
        "audit_trace_completeness": audit_trace_gate,
        "fixed_protocol_comparability": comparability_gate,
    }
    hard_gates["all_pass"] = all(
        bool(hard_gates[gate]["ok"])
        for gate in ("reproducibility", "audit_trace_completeness", "fixed_protocol_comparability")
    )

    threshold_tuning_guard = {
        "eligible": hard_gates["all_pass"],
        "policy": (
            "Threshold tuning is allowed only after reproducibility, audit trace, "
            "and comparability hard gates pass."
        ),
        "blocking_reasons": [
            hard_gates[gate]["details"]
            for gate in ("reproducibility", "audit_trace_completeness", "fixed_protocol_comparability")
            if not hard_gates[gate]["ok"]
        ],
    }
    paper_alignment = {
        "traceability_auditability": audit_trace_gate["details"],
        "fixed_protocol_comparability": comparability_gate["details"],
        "control_axis_interpretability": (
            "Coverage/complexity/quality axes are interpreted only under fixed protocol and "
            "reproducible rerun evidence."
        ),
    }

    reproducibility_status = {
        "status": baseline_rerun["classification"],
        "detail": (
            "Issue #9 completed manifest validation for B0/A1/A4 and executed "
            "deterministic baseline rerun classification."
        ),
        "manifest_validation": {
            "all_ok": all_manifests_ok,
            "by_run": manifest_validation,
        },
        "baseline_rerun": {
            **baseline_rerun,
            "rerun_matrix_root": rerun_output["matrix_root"],
        },
        "comparability_constraints": "unchanged",
        "hard_gates": hard_gates,
        "threshold_tuning_guard": threshold_tuning_guard,
        "paper_alignment": paper_alignment,
        "blocked_by_issue": None,
    }
    milestone_review["evidence_intake"]["reproducibility_status"] = reproducibility_status
    if not threshold_tuning_guard["eligible"]:
        milestone_review["threshold_adjustment_recommendation"] = {
            "recommendation": "keep_thresholds_as_is",
            "rationale": (
                "Rejected threshold tuning because Issue #9 hard gates are not all satisfied. "
                "Resolve reproducibility, audit-trace, and comparability evidence first."
            ),
            "proposed_changes": [],
            "adr_required": False,
            "adr_note": "Safe alternative: maintain existing thresholds until hard gates pass.",
        }
    _write_json(milestone_path, milestone_review)

    return {
        "manifest_validation": manifest_validation,
        "baseline_rerun": baseline_rerun,
        "milestone_review_json_path": str(milestone_path),
        "rerun_matrix_root": rerun_output["matrix_root"],
    }
