#!/usr/bin/env bash
# Track B — promotion assessment from latest Issue #7 comparison tables (+ optional provider packet).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=src

MATRIX_ROOT="${1:-}"
if [[ -z "$MATRIX_ROOT" ]]; then
  MATRIX_ROOT="$(ls -td artifacts/reports/issue7/*/ 2>/dev/null | head -1)"
fi
if [[ -z "$MATRIX_ROOT" || ! -d "$MATRIX_ROOT" ]]; then
  echo "Usage: $0 [matrix_root]" >&2
  echo "  e.g. artifacts/reports/issue7/20260526T025931Z" >&2
  exit 1
fi

BASELINE_PACKET="${SIMULA_DETERMINISTIC_BASELINE:-artifacts/reports/issue7/20260526T025931Z}"
OUT="${SIMULA_TRACK_B_REPORT:-artifacts/reports/track-b/promotion_assessment.json}"

python3 - <<PY
import json
import os
from pathlib import Path

from simula_research.track_b_promotion import build_promotion_assessment

matrix_root = Path("${MATRIX_ROOT}".rstrip("/"))
baseline = Path("${BASELINE_PACKET}")
out = Path("${OUT}")
out.parent.mkdir(parents=True, exist_ok=True)
report = build_promotion_assessment(matrix_root=matrix_root, deterministic_baseline_root=baseline)
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("promotion_report", out)
print("ready_for_integration_planning", report["summary"]["ready_for_integration_planning"])
for row in report["hypothesis_assessment"]:
    print(f"  {row['hypothesis']}: {row['status']} — {row['rationale']}")
PY
