from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from simula_research.dataset_adapters import (
    load_cti_bench_tsv,
    load_global_mmlu_jsonl,
    load_gsm8k_jsonl,
)
from simula_research.dataset_verification import verify_local_dataset_file
from simula_research.downstream_evaluation import (
    score_exact_match_predictions,
    score_multiple_choice_predictions,
)
from simula_research.generation_provider_adapter import nvidia_json_completion


def _load_local_tasks(
    *,
    dataset_id: str,
    path: str | Path,
    split: str,
    local_dataset_manifest: dict[str, Any] | None,
    global_mmlu_config: str | None,
    global_mmlu_selection: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str]:
    normalized_id = dataset_id.strip()
    if local_dataset_manifest is not None:
        verify_local_dataset_file(local_dataset_manifest, normalized_id, path)
    if normalized_id.upper() in {"CTI-MCQ", "CTI-RCM"}:
        return (
            load_cti_bench_tsv(path, dataset_id=normalized_id, split=split),
            "multiple_choice"
            if normalized_id.upper() == "CTI-MCQ"
            else "exact_match",
        )
    if normalized_id.casefold() == "gsm8k":
        return load_gsm8k_jsonl(path, split=split), "exact_match"
    if normalized_id.casefold() == "global-mmlu":
        config = (global_mmlu_config or "").strip()
        if not config:
            raise ValueError("Global-MMLU local loading requires --global-mmlu-config")
        return (
            load_global_mmlu_jsonl(
                path,
                config=config,
                split=split,
                selection=global_mmlu_selection,
            ),
            "multiple_choice",
        )
    raise ValueError(
        f"unsupported local benchmark {normalized_id!r}; "
        "parquet-backed benchmarks require an optional reader"
    )


def generate_nvidia_predictions(
    tasks: Iterable[dict[str, Any]],
    *,
    task_type: str,
    model: str | None = None,
    completion: Callable[..., Any] = nvidia_json_completion,
    event_log: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Generate one strict JSON prediction per task through NVIDIA NIM."""
    if task_type not in {"multiple_choice", "exact_match"}:
        raise ValueError("task_type is unsupported")
    predictions: dict[str, str] = {}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"task {index} must be an object")
        task_id = task.get("task_id")
        prompt = task.get("prompt")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"task {index} has an invalid task_id")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"task {index} has an invalid prompt")
        response = completion(
            system_prompt=(
                "Answer the benchmark task. Return exactly one JSON object with exactly "
                'one string field named "prediction". Do not include reasoning or other fields.'
            ),
            user_content=prompt,
            operation="benchmark_prediction",
            model=model,
            event_log=event_log,
        )
        if not isinstance(response, dict) or set(response) != {"prediction"}:
            raise ValueError(f"benchmark prediction response {index} must contain exactly prediction")
        prediction = response["prediction"]
        if not isinstance(prediction, str) or not prediction.strip():
            raise ValueError(f"benchmark prediction response {index} has an invalid prediction")
        if task_id in predictions:
            raise ValueError(f"duplicate task_id {task_id!r}")
        predictions[task_id] = prediction.strip()
    return predictions


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
    local_dataset_manifest: dict[str, Any] | None = None,
    global_mmlu_config: str | None = None,
    global_mmlu_selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a supported local benchmark and emit a persisted result record."""
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError("dataset_id must be a non-empty string")
    if isinstance(dataset_size, bool) or not isinstance(dataset_size, int) or dataset_size <= 0:
        raise ValueError("dataset_size must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    normalized_id = dataset_id.strip()
    tasks, task_type = _load_local_tasks(
        dataset_id=normalized_id,
        path=path,
        split=split,
        local_dataset_manifest=local_dataset_manifest,
        global_mmlu_config=global_mmlu_config,
        global_mmlu_selection=global_mmlu_selection,
    )

    predictions = load_prediction_artifact(predictions_path)
    score = (
        score_multiple_choice_predictions(tasks, predictions)
        if task_type == "multiple_choice"
        else score_exact_match_predictions(tasks, predictions)
    )
    result = {
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
    if global_mmlu_selection is not None:
        result["selection"] = {
            "selection_id": global_mmlu_selection["selection_id"],
            "revision": global_mmlu_selection["revision"],
            "config": (global_mmlu_config or "").strip(),
        }
    return result


def predict_local_benchmark(
    *,
    dataset_id: str,
    path: str | Path,
    split: str,
    dataset_size: int,
    seed: int,
    model: str | None = None,
    local_dataset_manifest: dict[str, Any] | None = None,
    global_mmlu_config: str | None = None,
    global_mmlu_selection: dict[str, Any] | None = None,
    completion: Callable[..., Any] = nvidia_json_completion,
) -> dict[str, Any]:
    """Generate a model-labeled prediction artifact for a supported local benchmark."""
    if isinstance(dataset_size, bool) or not isinstance(dataset_size, int) or dataset_size <= 0:
        raise ValueError("dataset_size must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    normalized_id = dataset_id.strip()
    tasks, task_type = _load_local_tasks(
        dataset_id=normalized_id,
        path=path,
        split=split,
        local_dataset_manifest=local_dataset_manifest,
        global_mmlu_config=global_mmlu_config,
        global_mmlu_selection=global_mmlu_selection,
    )
    event_log: list[dict[str, Any]] = []
    resolved_model = (
        (model or "").strip()
        or (os.environ.get("SIMULA_GENERATION_MODEL") or "").strip()
        or (os.environ.get("SIMULA_NIM_MODEL") or "").strip()
        or "moonshotai/kimi-k3"
    )
    predictions = generate_nvidia_predictions(
        tasks,
        task_type=task_type,
        model=resolved_model,
        completion=completion,
        event_log=event_log,
    )
    artifact = {
        "schema_version": "0.1.0",
        "dataset_id": normalized_id,
        "split": split,
        "dataset_size": dataset_size,
        "seed": seed,
        "task_type": task_type,
        "backend": "nvidia_nim",
        "model": resolved_model,
        "predictions": predictions,
        "provider_events": event_log,
    }
    if global_mmlu_selection is not None:
        artifact["selection"] = {
            "selection_id": global_mmlu_selection["selection_id"],
            "revision": global_mmlu_selection["revision"],
            "config": (global_mmlu_config or "").strip(),
        }
    return artifact
