from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _gate_metric(gate_report: dict[str, Any], key: str) -> float | None:
    decision = gate_report.get("gate_decision") or {}
    entry = decision.get(key)
    if not isinstance(entry, dict):
        return None
    actual = entry.get("actual")
    if actual is None:
        return None
    try:
        return float(actual)
    except (TypeError, ValueError):
        return None


def _compare_direction(
    baseline_val: float | None,
    ablation_val: float | None,
    *,
    higher_is_better: bool,
) -> str:
    if baseline_val is None or ablation_val is None:
        return "insufficient_data"
    if baseline_val == ablation_val:
        return "no_difference"
    if higher_is_better:
        return "supports_hypothesis" if baseline_val > ablation_val else "contradicts_hypothesis"
    return "supports_hypothesis" if baseline_val < ablation_val else "contradicts_hypothesis"


def build_promotion_assessment(
    *,
    matrix_root: str | Path,
    deterministic_baseline_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Track B checklist: directional H1–H4 signals from B0/A1/A4 comparison tables.

    Does not change ADR 0003 thresholds; reads persisted gate reports only.
    """
    root = Path(matrix_root)
    tables_path = root / "comparison_tables.json"
    if not tables_path.is_file():
        raise FileNotFoundError(f"Missing comparison tables: {tables_path}")

    tables = _read_json(tables_path)
    gate_reports: dict[str, dict[str, Any]] = {}
    for preset in ("B0", "A1", "A4"):
        gate_path = root / preset / "gate_report.json"
        if gate_path.is_file():
            gate_reports[preset] = _read_json(gate_path)

    b0 = gate_reports.get("B0", {})
    a1 = gate_reports.get("A1", {})
    a4 = gate_reports.get("A4", {})

    h1_status = _compare_direction(
        _gate_metric(b0, "coverage.node_coverage_ratio"),
        _gate_metric(a1, "coverage.node_coverage_ratio"),
        higher_is_better=True,
    )
    h1_depth = _compare_direction(
        _gate_metric(b0, "coverage.min_depth_coverage"),
        _gate_metric(a1, "coverage.min_depth_coverage"),
        higher_is_better=True,
    )
    h1 = "accepted" if h1_status == "supports_hypothesis" and h1_depth != "contradicts_hypothesis" else (
        "bounded" if h1_status in {"supports_hypothesis", "no_difference"} else "not_accepted"
    )

    h4_status = _compare_direction(
        _gate_metric(b0, "quality.critic_agreement"),
        _gate_metric(a4, "quality.critic_agreement"),
        higher_is_better=True,
    )
    h4_accept = _compare_direction(
        _gate_metric(b0, "quality.acceptance_rate"),
        _gate_metric(a4, "quality.acceptance_rate"),
        higher_is_better=True,
    )
    h4 = "accepted" if h4_status == "supports_hypothesis" or h4_accept == "supports_hypothesis" else (
        "bounded" if h4_status != "contradicts_hypothesis" else "not_accepted"
    )

    # H2/H3 need A2/A3 cells; mark bounded when matrix is B0/A1/A4 only.
    h2 = "bounded"
    h3 = "bounded"

    b0_pass = (b0.get("gate_decision") or {}).get("overall_status") == "pass"
    stable_baselines = b0_pass and deterministic_baseline_root is not None

    hypotheses = [
        {
            "hypothesis": "H1",
            "status": h1,
            "rationale": f"B0 vs A1 coverage signals ({h1_status}, depth {h1_depth}).",
        },
        {
            "hypothesis": "H2",
            "status": h2,
            "rationale": "A2 not in matrix; local diversity contrast not executed in this packet.",
        },
        {
            "hypothesis": "H3",
            "status": h3,
            "rationale": "A3 not in matrix; complexification ablation not executed in this packet.",
        },
        {
            "hypothesis": "H4",
            "status": h4,
            "rationale": f"B0 vs A4 quality signals (agreement {h4_status}, acceptance {h4_accept}).",
        },
    ]

    all_accepted_or_bounded = all(row["status"] in {"accepted", "bounded"} for row in hypotheses)
    ready = all_accepted_or_bounded and stable_baselines and b0_pass

    return {
        "matrix_root": str(root),
        "comparison_tables": str(tables_path),
        "deterministic_baseline_packet": str(deterministic_baseline_root) if deterministic_baseline_root else None,
        "hypothesis_assessment": hypotheses,
        "playbook_criteria": {
            "h1_h4_accepted_or_bounded": all_accepted_or_bounded,
            "deterministic_baseline_reference_recorded": deterministic_baseline_root is not None,
            "b0_gate_pass_on_this_packet": b0_pass,
            "reproducibility_note": "Run Issue #9 comparability on provider packet; accept acceptable_drift per provider policy.",
        },
        "summary": {
            "ready_for_integration_planning": ready,
            "blocking_gaps": [] if ready else [
                "Complete H2/H3 ablations (A2/A3) or document explicit waiver.",
                "Ensure B0 gate pass and Issue #9 classification on provider packet.",
                "Human sign-off on provider addendum if promoting past research phase.",
            ],
        },
        "paper_alignment": {
            "traceability_auditability": "Assessment derived from persisted gate reports only.",
            "protocol_comparability": "No threshold or formula changes.",
            "control_axis_impact": "Hypotheses evaluated per-axis using B0 contrasts.",
            "deviations": "none",
        },
    }
