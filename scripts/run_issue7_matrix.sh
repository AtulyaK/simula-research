#!/usr/bin/env bash
# Execute the full Issue #7 B0/A1/A2/A3/A4/A5 matrix.
#
# Provider critic backend (Stage 4):
#   SIMULA_CRITIC_BACKEND=stub   — non-network hash parity (default)
#   SIMULA_CRITIC_BACKEND=replay — requires SIMULA_CRITIC_REPLAY_JSON
#   SIMULA_CRITIC_BACKEND=nim    — live NIM; requires NVIDIA_API_KEY or NVAPI_KEY
#
# Live NIM example:
#   export SIMULA_CRITIC_BACKEND=nim NVIDIA_API_KEY='...'
#   ./scripts/run_issue7_matrix.sh
#
# See docs/research-validation-playbook.md and docs/llm-validation-readiness.md.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

: "${SIMULA_CRITIC_BACKEND:=stub}"

python3 - <<'PY'
import os
import subprocess

from simula_research.issue7_execution_reporting import execute_issue7_matrix

try:
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
except Exception:
    branch = "unknown"
try:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
except Exception:
    commit = "unknown"

matrix_kwargs = {
    "artifact_root": os.environ.get("SIMULA_ARTIFACT_ROOT", "artifacts/runs"),
    "report_root": os.environ.get("SIMULA_REPORT_ROOT", "artifacts/reports"),
    "branch_name": branch,
    "commit_hash": commit,
}
raw_limit = os.environ.get("SIMULA_MATRIX_PER_NODE_INSTANTIATIONS")
if raw_limit:
    limit = int(raw_limit)
    if limit <= 0:
        raise ValueError("SIMULA_MATRIX_PER_NODE_INSTANTIATIONS must be a positive integer")
    matrix_kwargs["per_node_instantiation_count"] = limit

output = execute_issue7_matrix(**matrix_kwargs)
print("execution_id", output["execution_id"])
print("matrix_root", output["matrix_root"])
print("comparison_tables", output["comparison_tables_path"])
print("critic_backend", os.environ.get("SIMULA_CRITIC_BACKEND", "hash_default"))
PY
