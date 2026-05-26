#!/usr/bin/env bash
# Execute Issue #7 B0/A1/A4 matrix.
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

# shellcheck source=/dev/null
source "$ROOT/scripts/verbose_lib.sh"
simula_log "issue7 matrix script start backend=${SIMULA_CRITIC_BACKEND}"

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

output = execute_issue7_matrix(
    artifact_root=os.environ.get("SIMULA_ARTIFACT_ROOT", "artifacts/runs"),
    report_root=os.environ.get("SIMULA_REPORT_ROOT", "artifacts/reports"),
    branch_name=branch,
    commit_hash=commit,
)
print("execution_id", output["execution_id"])
print("matrix_root", output["matrix_root"])
print("comparison_tables", output["comparison_tables_path"])
print("critic_backend", os.environ.get("SIMULA_CRITIC_BACKEND", "hash_default"))
PY
simula_log "issue7 matrix script finished"
