from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from simula_research.benchmark_evaluation import (
    predict_local_benchmark,
    score_local_benchmark,
)
from simula_research.dataset_adapters import load_global_mmlu_selection, load_split_manifest
from simula_research.dataset_verification import build_local_dataset_manifest
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
    matrix_kwargs: dict[str, Any] = {
        "artifact_root": args.artifact_root,
        "report_root": args.report_root,
        "branch_name": args.branch,
        "commit_hash": args.commit,
    }
    if args.per_node_instantiations is not None:
        matrix_kwargs["per_node_instantiation_count"] = args.per_node_instantiations
    result = execute_issue7_matrix(
        **matrix_kwargs,
    )
    print("execution_id", result["execution_id"])
    print("matrix_root", result["matrix_root"])
    print("comparison_tables", result["comparison_tables_path"])
    return 0


def _parse_assignment(value: str) -> tuple[str, str]:
    dataset_id, separator, assigned_value = value.partition("=")
    if not separator or not dataset_id.strip() or not assigned_value.strip():
        raise argparse.ArgumentTypeError("expected DATASET_ID=VALUE")
    return dataset_id.strip(), assigned_value.strip()


def _parse_count_assignment(value: str) -> tuple[str, int]:
    dataset_id, raw_count = _parse_assignment(value)
    try:
        count = int(raw_count)
    except ValueError as error:
        raise argparse.ArgumentTypeError("count must be an integer") from error
    if count < 0:
        raise argparse.ArgumentTypeError("count must be non-negative")
    return dataset_id, count


def _assignment_dict(
    assignments: list[tuple[str, Any]],
    *,
    option_name: str,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for dataset_id, value in assignments:
        if dataset_id in values:
            raise ValueError(f"{option_name} was provided more than once for {dataset_id!r}")
        values[dataset_id] = value
    return values


def _run_verify_datasets(args: argparse.Namespace) -> int:
    local_paths = _assignment_dict(args.dataset_path, option_name="--dataset-path")
    observed_counts = _assignment_dict(args.observed_count, option_name="--observed-count")
    split_manifest = load_split_manifest(args.split_manifest)
    local_manifest = build_local_dataset_manifest(
        split_manifest,
        local_paths,
        observed_counts=observed_counts,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(local_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("local_manifest", output_path)
    print("all_count_matches", local_manifest["all_count_matches"])
    return 0 if local_manifest["all_count_matches"] else 2


def _run_score_benchmark(args: argparse.Namespace) -> int:
    local_dataset_manifest = None
    if args.local_manifest:
        try:
            local_dataset_manifest = json.loads(
                Path(args.local_manifest).read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid local dataset manifest JSON: {args.local_manifest}") from error
    global_mmlu_selection = (
        load_global_mmlu_selection(args.selection_manifest)
        if args.selection_manifest
        else None
    )
    result = score_local_benchmark(
        dataset_id=args.dataset_id,
        path=args.dataset_path,
        predictions_path=args.predictions,
        split=args.split,
        dataset_size=args.dataset_size,
        seed=args.seed,
        local_dataset_manifest=local_dataset_manifest,
        global_mmlu_config=args.global_mmlu_config,
        global_mmlu_selection=global_mmlu_selection,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("benchmark_result", output_path)
    print("accuracy", result["accuracy"])
    return 0


def _run_predict_benchmark(args: argparse.Namespace) -> int:
    local_dataset_manifest = None
    if args.local_manifest:
        try:
            local_dataset_manifest = json.loads(
                Path(args.local_manifest).read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid local dataset manifest JSON: {args.local_manifest}") from error
    global_mmlu_selection = (
        load_global_mmlu_selection(args.selection_manifest)
        if args.selection_manifest
        else None
    )
    artifact = predict_local_benchmark(
        dataset_id=args.dataset_id,
        path=args.dataset_path,
        split=args.split,
        dataset_size=args.dataset_size,
        seed=args.seed,
        model=args.model,
        local_dataset_manifest=local_dataset_manifest,
        global_mmlu_config=args.global_mmlu_config,
        global_mmlu_selection=global_mmlu_selection,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("prediction_artifact", output_path)
    print("prediction_count", len(artifact["predictions"]))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Simula research validation workflows.")
    commands = parser.add_subparsers(dest="command", required=True)

    matrix = commands.add_parser("matrix", help="Execute the Issue 7 full ablation matrix.")
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
    matrix.add_argument(
        "--per-node-instantiations",
        type=int,
        default=None,
        help="Override samples generated per taxonomy node for smaller provider runs.",
    )
    matrix.set_defaults(handler=_run_matrix)

    verify_datasets = commands.add_parser(
        "verify-datasets",
        help="Build a hash/count manifest for downloaded benchmark files.",
    )
    verify_datasets.add_argument(
        "--split-manifest",
        default="configs/paper_dataset_splits.json",
        help="Pinned benchmark split manifest to verify against.",
    )
    verify_datasets.add_argument(
        "--dataset-path",
        action="append",
        type=_parse_assignment,
        required=True,
        metavar="DATASET_ID=PATH",
        help="Local benchmark file path; repeat once for every pinned dataset.",
    )
    verify_datasets.add_argument(
        "--observed-count",
        action="append",
        type=_parse_count_assignment,
        default=[],
        metavar="DATASET_ID=COUNT",
        help="Observed row count for formats without a local reader, such as parquet.",
    )
    verify_datasets.add_argument(
        "--output",
        default="artifacts/datasets/local_manifest.json",
        help="Path for the generated local-source manifest.",
    )
    verify_datasets.set_defaults(handler=_run_verify_datasets)

    score_benchmark = commands.add_parser(
        "score-benchmark",
        help="Score a local benchmark split from prediction JSON.",
    )
    score_benchmark.add_argument("--dataset-id", required=True)
    score_benchmark.add_argument("--dataset-path", required=True)
    score_benchmark.add_argument("--predictions", required=True)
    score_benchmark.add_argument("--split", default="test")
    score_benchmark.add_argument("--dataset-size", type=int, required=True)
    score_benchmark.add_argument("--seed", type=int, required=True)
    score_benchmark.add_argument(
        "--global-mmlu-config",
        help="Global-MMLU language/config name, such as en, ko, or ne.",
    )
    score_benchmark.add_argument(
        "--selection-manifest",
        help="Optional paper Global-MMLU selection manifest.",
    )
    score_benchmark.add_argument(
        "--local-manifest",
        help="Optional verified local dataset manifest to recheck before scoring.",
    )
    score_benchmark.add_argument(
        "--output",
        default="artifacts/datasets/benchmark_result.json",
    )
    score_benchmark.set_defaults(handler=_run_score_benchmark)

    predict_benchmark = commands.add_parser(
        "predict-benchmark",
        help="Generate task-id predictions for a local benchmark through NVIDIA NIM.",
    )
    predict_benchmark.add_argument("--dataset-id", required=True)
    predict_benchmark.add_argument("--dataset-path", required=True)
    predict_benchmark.add_argument("--split", default="test")
    predict_benchmark.add_argument("--dataset-size", type=int, required=True)
    predict_benchmark.add_argument("--seed", type=int, required=True)
    predict_benchmark.add_argument("--model")
    predict_benchmark.add_argument(
        "--global-mmlu-config",
        help="Global-MMLU language/config name, such as en, ko, or ne.",
    )
    predict_benchmark.add_argument(
        "--selection-manifest",
        help="Optional paper Global-MMLU selection manifest.",
    )
    predict_benchmark.add_argument(
        "--local-manifest",
        help="Optional verified local dataset manifest to recheck before prediction.",
    )
    predict_benchmark.add_argument(
        "--output",
        default="artifacts/datasets/benchmark_predictions.json",
    )
    predict_benchmark.set_defaults(handler=_run_predict_benchmark)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args: Any = _build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
