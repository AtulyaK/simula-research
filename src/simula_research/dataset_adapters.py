from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TASK_SCHEMA_VERSION = "0.1.0"
GSM8K_DATASET_ID = "GSM8k"


def _require_non_empty_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def validate_task_record(record: dict[str, Any]) -> None:
    """Validate the fixed task shape used by dataset adapters."""
    if not isinstance(record, dict):
        raise ValueError("task record must be an object")
    required_fields = ("task_id", "dataset_id", "split", "prompt", "answer", "metadata")
    missing = [field for field in required_fields if field not in record]
    if missing:
        raise ValueError(f"task record is missing fields {missing}")
    for field in required_fields[:-1]:
        _require_non_empty_text(record[field], field=field)
    if not isinstance(record["metadata"], dict):
        raise ValueError("metadata must be an object")
    schema_version = record.get("schema_version", TASK_SCHEMA_VERSION)
    _require_non_empty_text(schema_version, field="schema_version")


def _extract_gsm8k_answer(raw_answer: str) -> str:
    if "####" not in raw_answer:
        return raw_answer.strip()
    return raw_answer.rsplit("####", 1)[1].strip()


def adapt_gsm8k_record(
    record: dict[str, Any],
    *,
    split: str,
    source_index: int,
) -> dict[str, Any]:
    """Adapt one GSM8k JSON record into the repository task schema."""
    if not isinstance(source_index, int) or source_index < 0:
        raise ValueError("source_index must be a non-negative integer")
    if not isinstance(record, dict):
        raise ValueError("GSM8k record must be an object")
    split = _require_non_empty_text(split, field="split")
    question = _require_non_empty_text(record.get("question"), field="question")
    raw_answer = _require_non_empty_text(record.get("answer"), field="answer")
    task_id = str(record.get("id", f"gsm8k-{split}-{source_index:06d}")).strip()
    task = {
        "schema_version": TASK_SCHEMA_VERSION,
        "task_id": _require_non_empty_text(task_id, field="task_id"),
        "dataset_id": GSM8K_DATASET_ID,
        "split": split,
        "prompt": question,
        "answer": _extract_gsm8k_answer(raw_answer),
        "rationale": raw_answer,
        "metadata": {
            "source_format": "gsm8k_json",
            "source_index": source_index,
        },
    }
    validate_task_record(task)
    return task


def load_gsm8k_jsonl(path: str | Path, *, split: str) -> list[dict[str, Any]]:
    """Load and validate GSM8k JSONL records without downloading external data."""
    source_path = Path(path)
    tasks: list[dict[str, Any]] = []
    with source_path.open(encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON on line {line_number}") from error
            tasks.append(adapt_gsm8k_record(record, split=split, source_index=len(tasks)))
    return tasks
