#!/usr/bin/env bash
# Track A — provider-backed Phase 4: B0/A1/A4 matrix + Issue #9 comparability rerun.
# Requires NVIDIA_API_KEY or NVAPI_KEY. Respects SIMULA_NIM_MAX_RPM (default 40).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src
# shellcheck source=/dev/null
source "$ROOT/scripts/nim_env_defaults.sh"
# shellcheck source=/dev/null
source "$ROOT/scripts/verbose_lib.sh"
simula_log "track A phase4 start"

if [[ -z "${NVIDIA_API_KEY:-}" && -z "${NVAPI_KEY:-}" ]]; then
  echo "Set NVIDIA_API_KEY or NVAPI_KEY before Track A Phase 4." >&2
  exit 1
fi

export SIMULA_REPORT_ROOT="${SIMULA_REPORT_ROOT:-artifacts/reports}"
export SIMULA_ISSUE9_REPORT_ROOT="${SIMULA_ISSUE9_REPORT_ROOT:-artifacts/reports/issue9}"

echo "=== Track A Phase 4: Issue #7 matrix (NIM critics) ==="
"$ROOT/scripts/run_issue7_matrix.sh"

MATRIX_ROOT="$(ls -td "$SIMULA_REPORT_ROOT"/issue7/*/ 2>/dev/null | head -1)"
if [[ -z "$MATRIX_ROOT" ]]; then
  echo "Could not locate latest issue7 matrix root under $SIMULA_REPORT_ROOT/issue7" >&2
  exit 1
fi
echo "matrix_root $MATRIX_ROOT"

ADDENDUM_JSON="${SIMULA_PROVIDER_ADDENDUM_JSON:-artifacts/reports/issue8/milestone_gate_review_addendum_provider_template.json}"
python3 - <<PY
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

matrix_root = Path("${MATRIX_ROOT}".rstrip("/"))
execution_id = matrix_root.name
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
try:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
except Exception:
    commit = "unknown"

addendum = {
    "addendum_metadata": {
        "addendum_id": f"provider_{execution_id}",
        "issue_id": 8,
        "review_type": "milestone-1-provider-phase4-addendum",
        "evidence_packet": str(matrix_root),
        "review_timestamp_utc": stamp,
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
        "deterministic_baseline_packet": "artifacts/reports/issue7/20260526T025931Z/",
        "provider_runtime_source": "environment",
        "main_commit": commit,
    },
    "gate_outcomes": {},
    "paper_alignment": {
        "traceability_auditability": "Separate provider packet; does not amend April fail or signed deterministic addendum.",
        "protocol_comparability": "ADR 0003 thresholds unchanged; preset comparability fields frozen.",
        "control_axis_impact": "Live critics may shift quality axis; interpret under stochastic drift policy.",
        "deviations": "none on thresholds or metric formulas",
    },
}
for preset in ("B0", "A1", "A4"):
    gate_path = matrix_root / preset / "gate_report.json"
    if gate_path.is_file():
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        addendum["gate_outcomes"][preset] = {
            "overall_status": gate.get("overall_status"),
            "run_id": gate.get("run_id"),
            "failed_thresholds": [
                k for k, v in gate.get("gate_decision", {}).items()
                if k != "overall_status" and isinstance(v, dict) and v.get("status") == "fail"
            ],
        }
out = Path("${ADDENDUM_JSON}")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(addendum, indent=2), encoding="utf-8")
print("provider_addendum_template", out)
PY

echo "=== Track A Phase 4: Issue #9 comparability (provider rerun) ==="
export SIMULA_MILESTONE_REVIEW_JSON="${ADDENDUM_JSON}"
"$ROOT/scripts/run_issue9_comparability_check.sh"

simula_log "track A phase4 finished matrix_root=$MATRIX_ROOT"
echo "Done. Review gate reports under $MATRIX_ROOT and classification above."
