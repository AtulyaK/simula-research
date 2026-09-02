from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from simula_research.dataset_adapters import load_cti_bench_tsv, load_gsm8k_jsonl
from simula_research.downstream_evaluation import (
    score_exact_match_predictions,
    score_multiple_choice_predictions,
)


def load_prediction_artifact(path: str | Path) -> dict[str, Any]:
    """Load a task-id-to-prediction JSON artifact."""
    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid prediction JSON: {source_path}") from error

    if isinstance(payload, dict) and "predictions" in payload:
        payload = payload["predictions"]
    if isinstance(payload, dict):
        predictions = payload
    elif isinstance(payload, list):
        predictions = {}
        for index, row in enumerate(payload):
            if not isinstance(row, dict) or "task_id" not in row or "prediction" not in row:
                raise ValueError(f"prediction row {index} must contain task_id and prediction")
            task_id = row["task_id"]
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError(f"prediction row {index} has an invalid task_id")
            if task_id in predictions:
                raise ValueError(f"duplicate prediction for task_id {task_id!r}")
            predictions[task_id] = row["prediction"]
    else:
        raise ValueError("prediction artifact must be an object or list")

    if any(not isinstance(task_id, str) or not task_id.strip() for task_id in predictions):
        raise ValueError("prediction artifact task IDs must be non-empty strings")
    return dict(predictions)


def score_local_benchmark(
    *,
    dataset_id: str,
    path: str | Path,
    predictions_path: str | Path,
    split: str,
    dataset_size: int,
    seed: int,
) -> dict[str, Any]:
    """Load a supported local benchmark and emit a persisted result record."""
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError("dataset_id must be a non-empty string")
    if isinstance(dataset_size, bool) or not isinstance(dataset_size, int) or dataset_size <= 0:
        raise ValueError("dataset_size must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    normalized_id = dataset_id.strip()
    if normalized_id.upper() in {"CTI-MCQ", "CTI-RCM"}:
        tasks = load_cti_bench_tsv(path, dataset_id=normalized_id, split=split)
        task_type = (
            "multiple_choice"
            if normalized_id.upper().startswith("CTI-MCQ")
            else "exact_match"
        )
    elif normalized_id.casefold() == "gsm8k":
        tasks = load_gsm8k_jsonl(path, split=split)
        task_type = "exact_match"
    else:
        raise ValueError(
            f"unsupported local benchmark {normalized_id!r}; "
            "parquet-backed benchmarks require an optional reader"
        )

    predictions = load_prediction_artifact(predictions_path)
    score = (
        score_multiple_choice_predictions(tasks, predictions)
        if task_type == "multiple_choice"
        else score_exact_match_predictions(tasks, predictions)
    )
    return {
        "schema_version": "0.1.0",
        "dataset_id": normalized_id,
        "split": split,
        "dataset_size": dataset_size,
        "seed": seed,
        "task_type": task_type,
        "accuracy": score["accuracy"],
        "task_count": score["task_count"],
        "correct_count": score["correct_count"],
        "missing_prediction_count": score["missing_prediction_count"],
        "score": score,
    }
