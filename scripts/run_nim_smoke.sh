#!/usr/bin/env bash
# Minimal live NIM smoke (one small pipeline run). Requires NVIDIA_API_KEY or NVAPI_KEY.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src
# shellcheck source=/dev/null
source "$ROOT/scripts/nim_env_defaults.sh"
# shellcheck source=/dev/null
source "$ROOT/scripts/verbose_lib.sh"
simula_log "nim smoke start"

if [[ -z "${NVIDIA_API_KEY:-}" && -z "${NVAPI_KEY:-}" ]]; then
  echo "Set NVIDIA_API_KEY or NVAPI_KEY before running NIM smoke." >&2
  exit 1
fi

SMOKE_ROOT="${SIMULA_SMOKE_ARTIFACT_ROOT:-artifacts/reports/llm-smoke}"
mkdir -p "$SMOKE_ROOT"

python3 - <<'PY'
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from simula_research.critic_provider_adapter import critic_sample_evaluator_from_env, provider_runtime_from_env
from simula_research.pipeline import run_pipeline

smoke_root = Path(os.environ.get("SIMULA_SMOKE_ARTIFACT_ROOT", "artifacts/reports/llm-smoke"))
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
run_dir = smoke_root / stamp
run_dir.mkdir(parents=True, exist_ok=True)

try:
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
except Exception:
    branch = "unknown"
try:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
except Exception:
    commit = "unknown"

result = run_pipeline(
    seed=7,
    model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
    domain_objective="pilot-domain",
    artifact_root=run_dir / "runs",
    taxonomy_config={"max_depth": 1, "branching_factor": 1},
    local_diversification_config={"instantiations_per_prompt": 1},
    provider_runtime=provider_runtime_from_env(),
    critic_sample_evaluator=critic_sample_evaluator_from_env(),
)
manifest = result["manifest"]
incident = {
    "smoke_id": stamp,
    "run_id": manifest["run_id"],
    "branch": branch,
    "commit_hash": commit,
    "provider_runtime": manifest.get("provider_runtime"),
    "critic_backend": os.environ.get("SIMULA_CRITIC_BACKEND"),
}
(out := smoke_root / f"nim_smoke_{stamp}.json").write_text(json.dumps(incident, indent=2), encoding="utf-8")
print("smoke_report", out)
print("run_id", manifest["run_id"])
print("nim_model", (manifest.get("provider_runtime") or {}).get("nim_critic", {}).get("default_model"))
print("max_rpm", (manifest.get("provider_runtime") or {}).get("nim_critic", {}).get("max_rpm"))
PY
simula_log "nim smoke finished"
