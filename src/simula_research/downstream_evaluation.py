from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

from simula_research.dataset_adapters import validate_split_manifest

DOWNSTREAM_EVALUATION_SCHEMA_VERSION = "0.1.0"
PAPER_STUDENT_MODEL = "google/gemma-3-4b-it"
PAPER_TEACHER_MODEL = "gemini-2.5-flash"


def _require_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _positive_ints(values: Iterable[int], *, field: str) -> list[int]:
    result = list(values)
    if not result or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in result):
        raise ValueError(f"{field} must contain positive integers")
    if len(set(result)) != len(result):
        raise ValueError(f"{field} must not contain duplicates")
    return result


def _seed_values(values: Iterable[int]) -> list[int]:
    result = list(values)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in result):
        raise ValueError("seeds must contain non-negative integers")
    if len(set(result)) != len(result):
        raise ValueError("seeds must not contain duplicates")
    return result


def build_paper_downstream_evaluation_plan(
    split_manifest: dict[str, Any],
    *,
    dataset_sizes: Iterable[int],
    seeds: Iterable[int] = range(10),
    student_model: str = PAPER_STUDENT_MODEL,
    teacher_model: str = PAPER_TEACHER_MODEL,
    lora_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the paper's downstream training/evaluation protocol metadata."""
    validate_split_manifest(split_manifest)
    resolved_seeds = _seed_values(seeds)
    if len(resolved_seeds) != 10:
        raise ValueError("paper downstream evaluation requires exactly ten seeds")
    plan = {
        "schema_version": DOWNSTREAM_EVALUATION_SCHEMA_VERSION,
        "status": "planned",
        "dataset_split_manifest": split_manifest,
        "student": {
            "model_id": _require_text(student_model, field="student_model"),
            "training_method": "lora",
            "lora_config": dict(lora_config or {}),
        },
        "teacher": {
            "model_id": _require_text(teacher_model, field="teacher_model"),
        },
        "seeds": resolved_seeds,
        "dataset_size_scaling": _positive_ints(dataset_sizes, field="dataset_sizes"),
        "results": [],
    }
    validate_downstream_evaluation_plan(plan)
    return plan


def validate_downstream_evaluation_results(
    plan: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    """Validate benchmark results against the pinned downstream protocol."""
    if not isinstance(results, list):
        raise ValueError("downstream evaluation results must be a list")
    split_manifest = plan.get("dataset_split_manifest")
    validate_split_manifest(split_manifest)
    dataset_ids = {entry["dataset_id"] for entry in split_manifest["splits"]}
    dataset_sizes = set(plan.get("dataset_size_scaling", []))
    seeds = set(plan.get("seeds", []))
    seen: set[tuple[str, int, int]] = set()
    required_fields = ("dataset_id", "dataset_size", "seed", "task_type", "accuracy")
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValueError(f"downstream evaluation result {index} must be an object")
        missing = [field for field in required_fields if field not in result]
        if missing:
            raise ValueError(f"downstream evaluation result {index} is missing fields {missing}")
        dataset_id = _require_text(result["dataset_id"], field=f"results[{index}].dataset_id")
        if dataset_id not in dataset_ids:
            raise ValueError(f"results[{index}].dataset_id is not in the split manifest")
        dataset_size = result["dataset_size"]
        if (
            isinstance(dataset_size, bool)
            or not isinstance(dataset_size, int)
            or dataset_size not in dataset_sizes
        ):
            raise ValueError(f"results[{index}].dataset_size is not in the evaluation plan")
        seed = result["seed"]
        if isinstance(seed, bool) or not isinstance(seed, int) or seed not in seeds:
            raise ValueError(f"results[{index}].seed is not in the evaluation plan")
        task_type = _require_text(result["task_type"], field=f"results[{index}].task_type")
        if task_type not in {"multiple_choice", "exact_match"}:
            raise ValueError(f"results[{index}].task_type is unsupported")
        accuracy = result["accuracy"]
        if (
            isinstance(accuracy, bool)
            or not isinstance(accuracy, (int, float))
            or not math.isfinite(float(accuracy))
            or not 0 <= accuracy <= 1
        ):
            raise ValueError(f"results[{index}].accuracy must be a finite number from 0 to 1")
        identity = (dataset_id, dataset_size, seed)
        if identity in seen:
            raise ValueError(f"duplicate downstream evaluation result for {identity!r}")
        seen.add(identity)


def validate_downstream_evaluation_plan(plan: dict[str, Any]) -> None:
    """Validate persisted downstream protocol metadata before execution."""
    if not isinstance(plan, dict):
        raise ValueError("downstream evaluation plan must be an object")
    if plan.get("schema_version") != DOWNSTREAM_EVALUATION_SCHEMA_VERSION:
        raise ValueError("unsupported downstream evaluation schema version")
    if plan.get("status") not in {"planned", "running", "completed"}:
        raise ValueError("downstream evaluation plan has an invalid status")
    split_manifest = plan.get("dataset_split_manifest")
    validate_split_manifest(split_manifest)
    student = plan.get("student")
    teacher = plan.get("teacher")
    if not isinstance(student, dict) or not isinstance(teacher, dict):
        raise ValueError("downstream evaluation plan must define student and teacher")
    _require_text(student.get("model_id"), field="student.model_id")
    if student.get("training_method") != "lora":
        raise ValueError("downstream student training_method must be lora")
    if not isinstance(student.get("lora_config"), dict):
        raise ValueError("student.lora_config must be an object")
    _require_text(teacher.get("model_id"), field="teacher.model_id")
    seeds = plan.get("seeds")
    if not isinstance(seeds, list) or len(seeds) != 10 or len(set(seeds)) != 10:
        raise ValueError("downstream evaluation plan must contain ten unique seeds")
    _seed_values(seeds)
    _positive_ints(plan.get("dataset_size_scaling", []), field="dataset_size_scaling")
    validate_downstream_evaluation_results(plan, plan.get("results"))


def _normalise_prediction(value: Any) -> str:
    return " ".join(str(value).strip().split()).casefold()


def _normalise_multiple_choice_answer(value: Any, choices: list[str]) -> str:
    text = _normalise_prediction(value)
    if text.isdigit():
        index = int(text)
        if 0 <= index < len(choices):
            return f"index:{index}"
    letter_match = re.fullmatch(r"[\(\[]?([a-z])[\)\].:]?", text)
    if letter_match:
        index = ord(letter_match.group(1)) - ord("a")
        if 0 <= index < len(choices):
            return f"index:{index}"
    phrase_match = re.search(r"\b(?:answer|option|choice)\b\s*(?:is|:)?\s*[\(\[]?([a-z])\b", text)
    if phrase_match:
        index = ord(phrase_match.group(1)) - ord("a")
        if 0 <= index < len(choices):
            return f"index:{index}"
    for index, choice in enumerate(choices):
        if _normalise_prediction(choice) == text:
            return f"index:{index}"
    return f"text:{text}"


def score_multiple_choice_predictions(
    tasks: Iterable[dict[str, Any]],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    """Score predictions against fixed-schema MCQ tasks with explicit missing rows."""
    rows: list[dict[str, Any]] = []
    for task in tasks:
        task_id = _require_text(task.get("task_id"), field="task_id")
        metadata = task.get("metadata")
        choices = metadata.get("choices") if isinstance(metadata, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ValueError(f"{task_id} is missing metadata.choices")
        expected = _normalise_multiple_choice_answer(task.get("answer"), choices)
        has_prediction = task_id in predictions
        prediction = predictions.get(task_id)
        predicted = _normalise_multiple_choice_answer(prediction, choices) if has_prediction else None
        rows.append(
            {
                "task_id": task_id,
                "expected": task.get("answer"),
                "prediction": prediction,
                "correct": bool(has_prediction and predicted == expected),
                "missing_prediction": not has_prediction,
            }
        )
    correct_count = sum(1 for row in rows if row["correct"])
    missing_count = sum(1 for row in rows if row["missing_prediction"])
    return {
        "task_count": len(rows),
        "correct_count": correct_count,
        "missing_prediction_count": missing_count,
        "accuracy": correct_count / len(rows) if rows else None,
        "rows": rows,
    }


def score_exact_match_predictions(
    tasks: Iterable[dict[str, Any]],
    predictions: Mapping[str, Any],
) -> dict[str, Any]:
    """Score normalized exact-match answers, suitable for GSM8k-style outputs."""
    rows: list[dict[str, Any]] = []
    for task in tasks:
        task_id = _require_text(task.get("task_id"), field="task_id")
        has_prediction = task_id in predictions
        expected = _normalise_prediction(task.get("answer"))
        prediction = predictions.get(task_id)
        rows.append(
            {
                "task_id": task_id,
                "expected": task.get("answer"),
                "prediction": prediction,
                "correct": bool(has_prediction and _normalise_prediction(prediction) == expected),
                "missing_prediction": not has_prediction,
            }
        )
    correct_count = sum(1 for row in rows if row["correct"])
    missing_count = sum(1 for row in rows if row["missing_prediction"])
    return {
        "task_count": len(rows),
        "correct_count": correct_count,
        "missing_prediction_count": missing_count,
        "accuracy": correct_count / len(rows) if rows else None,
        "rows": rows,
    }


def aggregate_seed_accuracies(seed_results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-seed accuracy artifacts without hiding missing results."""
    results = list(seed_results)
    if not results:
        raise ValueError("seed_results must not be empty")
    accuracies = [result.get("accuracy") for result in results]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in accuracies):
        raise ValueError("every seed result must contain numeric accuracy")
    mean = sum(accuracies) / len(accuracies)
    variance = sum((value - mean) ** 2 for value in accuracies) / len(accuracies)
    return {
        "seed_count": len(accuracies),
        "mean_accuracy": mean,
        "stddev_accuracy": math.sqrt(variance),
        "min_accuracy": min(accuracies),
        "max_accuracy": max(accuracies),
        "seed_results": results,
    }
