from __future__ import annotations

import argparse
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from simula_research.issue7_execution_reporting import execute_issue7_matrix


def _git_value(*args: str, fallback: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or fallback
    except (OSError, subprocess.CalledProcessError):
        return fallback


def _run_matrix(args: argparse.Namespace) -> int:
    result = execute_issue7_matrix(
        artifact_root=args.artifact_root,
        report_root=args.report_root,
        branch_name=args.branch,
        commit_hash=args.commit,
    )
    print("execution_id", result["execution_id"])
    print("matrix_root", result["matrix_root"])
    print("comparison_tables", result["comparison_tables_path"])
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Simula research validation workflows.")
    commands = parser.add_subparsers(dest="command", required=True)

    matrix = commands.add_parser("matrix", help="Execute the Issue 7 B0/A1/A4 matrix.")
    matrix.add_argument(
        "--artifact-root",
        default=os.environ.get("SIMULA_ARTIFACT_ROOT", "artifacts/runs"),
    )
    matrix.add_argument(
        "--report-root",
        default=os.environ.get("SIMULA_REPORT_ROOT", "artifacts/reports"),
    )
    matrix.add_argument(
        "--branch",
        default=_git_value("rev-parse", "--abbrev-ref", "HEAD", fallback="unknown"),
    )
    matrix.add_argument(
        "--commit",
        default=_git_value("rev-parse", "HEAD", fallback="unknown"),
    )
    matrix.set_defaults(handler=_run_matrix)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args: Any = _build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
