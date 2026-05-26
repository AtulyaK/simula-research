#!/usr/bin/env bash
# Re-run Issue #7 matrix under artifacts/reports/issue9 and evaluate Issue #9 hard gates.
#
# Optional: export SIMULA_CRITIC_BACKEND=stub|nim for provider-shaped reruns (see
# docs/provider-stochastic-reproducibility-policy.md). Leave unset for hash-default
# parity with milestone-1 matrix evidence.
#
# Milestone review: SIMULA_MILESTONE_REVIEW_JSON (default: artifacts/reports/issue8/milestone_gate_review.json)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

export SIMULA_MILESTONE_REVIEW_JSON="${SIMULA_MILESTONE_REVIEW_JSON:-artifacts/reports/issue8/milestone_gate_review.json}"

python3 - <<'PY'
import json
import os
import subprocess
from pathlib import Path

from simula_research.issue9_reproducibility import run_issue9_reproducibility_check

milestone = Path(os.environ["SIMULA_MILESTONE_REVIEW_JSON"])
if not milestone.is_file():
    raise SystemExit(f"Missing milestone review: {milestone}")

try:
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
except Exception:
    branch = "unknown"
try:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
except Exception:
    commit = "unknown"

result = run_issue9_reproducibility_check(
    milestone_review_json_path=milestone,
    issue9_report_root=os.environ.get("SIMULA_ISSUE9_REPORT_ROOT", "artifacts/reports/issue9"),
    artifact_root=os.environ.get("SIMULA_ARTIFACT_ROOT", "artifacts/runs"),
    branch_name=branch,
    commit_hash=commit,
)
print("rerun_matrix_root", result["rerun_matrix_root"])
print("baseline_rerun_classification", result["baseline_rerun"]["classification"])
print("max_metric_delta", result["baseline_rerun"]["max_metric_delta"])

review = json.loads(milestone.read_text(encoding="utf-8"))
gates = review["evidence_intake"]["reproducibility_status"]["hard_gates"]
print("hard_gates_all_pass", gates["all_pass"])
for name in ("reproducibility", "audit_trace_completeness", "fixed_protocol_comparability"):
    g = gates[name]
    print(f"  {name}: ok={g['ok']}")
PY
