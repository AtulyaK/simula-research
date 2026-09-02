from __future__ import annotations

import ast
import csv
import json
from pathlib import Path
from typing import Any

TASK_SCHEMA_VERSION = "0.1.0"
GSM8K_DATASET_ID = "GSM8k"
SPLIT_MANIFEST_SCHEMA_VERSION = "0.1.0"
GLOBAL_MMLU_SELECTION_SCHEMA_VERSION = "0.1.0"


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


def _first_present(record: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in record and record[field] not in (None, ""):
            return record[field]
    return None


def _multiple_choice_options(record: dict[str, Any]) -> list[str]:
    raw_choices = _first_present(record, ("choices", "options", "Choices", "Options"))
    if isinstance(raw_choices, str) and raw_choices.strip().startswith("["):
        try:
            raw_choices = ast.literal_eval(raw_choices)
        except (SyntaxError, ValueError) as error:
            raise ValueError("multiple-choice choices string is not a valid list") from error
    if isinstance(raw_choices, (list, tuple)):
        choices = [_require_non_empty_text(choice, field="choice") for choice in raw_choices]
        if choices:
            return choices

    option_fields = (
        ("A", "B", "C", "D", "E"),
        ("a", "b", "c", "d", "e"),
        ("Option A", "Option B", "Option C", "Option D", "Option E"),
        ("option_a", "option_b", "option_c", "option_d", "option_e"),
    )
    for fields in option_fields:
        values = [record[field] for field in fields if field in record and record[field] not in (None, "")]
        if values:
            return [_require_non_empty_text(value, field="choice") for value in values]
    raise ValueError("multiple-choice record must contain choices or option fields")


def _format_multiple_choice_prompt(question: str, choices: list[str]) -> str:
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    options = "\n".join(f"{labels[index]}) {choice}" for index, choice in enumerate(choices))
    return f"{question}\n\nOptions:\n{options}"


def _adapt_multiple_choice_record(
    record: dict[str, Any],
    *,
    dataset_id: str,
    split: str,
    source_index: int,
    source_format: str,
    config: str | None = None,
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(f"{source_format} record must be an object")
    if not isinstance(source_index, int) or source_index < 0:
        raise ValueError("source_index must be a non-negative integer")
    dataset_id = _require_non_empty_text(dataset_id, field="dataset_id")
    split = _require_non_empty_text(split, field="split")
    question = _require_non_empty_text(
        _first_present(record, ("question", "Question", "prompt", "Prompt")),
        field="question",
    )
    choices = _multiple_choice_options(record)
    source_prompt = _first_present(record, ("prompt", "Prompt"))
    prompt = (
        _require_non_empty_text(source_prompt, field="prompt")
        if source_prompt is not None
        else _format_multiple_choice_prompt(question, choices)
    )
    answer = _first_present(record, ("answer", "Answer", "GT", "gold", "label", "target"))
    if isinstance(answer, bool) or answer is None:
        raise ValueError(f"{source_format} record must contain an answer")
    answer_text = _require_non_empty_text(str(answer), field="answer")
    task_id = str(
        _first_present(record, ("task_id", "id", "sample_id", "question_id"))
        or f"{dataset_id.lower()}-{split}-{source_index:06d}"
    )
    task = {
        "schema_version": TASK_SCHEMA_VERSION,
        "task_id": _require_non_empty_text(task_id, field="task_id"),
        "dataset_id": dataset_id,
        "split": split,
        "prompt": prompt,
        "answer": answer_text,
        "metadata": {
            "source_format": source_format,
            "source_index": source_index,
            "choices": choices,
            **({"config": config} if config is not None else {}),
            **{
                key: value
                for key, value in record.items()
                if key not in {"question", "Question", "prompt", "Prompt", "choices", "options", "Choices", "Options"}
            },
        },
    }
    validate_task_record(task)
    return task


def adapt_cti_bench_record(
    record: dict[str, Any],
    *,
    dataset_id: str,
    split: str,
    source_index: int,
) -> dict[str, Any]:
    """Adapt one CTIBench TSV row into the fixed task schema."""
    return _adapt_multiple_choice_record(
        record,
        dataset_id=dataset_id,
        split=split,
        source_index=source_index,
        source_format="ctibench_tsv",
    )


def load_cti_bench_tsv(
    path: str | Path,
    *,
    dataset_id: str,
    split: str,
) -> list[dict[str, Any]]:
    """Load a CTIBench TSV split without downloading or requiring extra packages."""
    source_path = Path(path)
    tasks: list[dict[str, Any]] = []
    with source_path.open(newline="", encoding="utf-8-sig") as file_handle:
        reader = csv.DictReader(file_handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError("CTIBench TSV is missing a header row")
        for line_number, record in enumerate(reader, start=2):
            if not any(value and value.strip() for value in record.values() if isinstance(value, str)):
                continue
            try:
                adapter = (
                    adapt_cti_rcm_record
                    if dataset_id.upper().startswith("CTI-RCM")
                    else adapt_cti_bench_record
                )
                tasks.append(
                    adapter(
                        record,
                        dataset_id=dataset_id,
                        split=split,
                        source_index=len(tasks),
                    )
                )
            except ValueError as error:
                raise ValueError(f"invalid CTIBench record on line {line_number}") from error
    return tasks


def adapt_cti_rcm_record(
    record: dict[str, Any],
    *,
    dataset_id: str,
    split: str,
    source_index: int,
) -> dict[str, Any]:
    """Adapt one CTIBench RCM TSV row into the fixed task schema."""
    if not isinstance(record, dict):
        raise ValueError("ctibench_rcm_tsv record must be an object")
    if not isinstance(source_index, int) or source_index < 0:
        raise ValueError("source_index must be a non-negative integer")
    dataset_id = _require_non_empty_text(dataset_id, field="dataset_id")
    split = _require_non_empty_text(split, field="split")
    description = _require_non_empty_text(record.get("Description"), field="description")
    prompt = _require_non_empty_text(record.get("Prompt"), field="prompt")
    answer = _require_non_empty_text(record.get("GT"), field="answer")
    task = {
        "schema_version": TASK_SCHEMA_VERSION,
        "task_id": f"{dataset_id.lower()}-{split}-{source_index:06d}",
        "dataset_id": dataset_id,
        "split": split,
        "prompt": prompt,
        "answer": answer,
        "metadata": {
            "source_format": "ctibench_rcm_tsv",
            "source_index": source_index,
            "description": description,
            **{
                key: value
                for key, value in record.items()
                if key not in {"Description", "Prompt", "GT"}
            },
        },
    }
    validate_task_record(task)
    return task


def adapt_global_mmlu_record(
    record: dict[str, Any],
    *,
    config: str,
    split: str,
    source_index: int,
) -> dict[str, Any]:
    """Adapt one Global MMLU multiple-choice record into the fixed task schema."""
    return _adapt_multiple_choice_record(
        record,
        dataset_id="Global-MMLU",
        split=split,
        source_index=source_index,
        source_format="global_mmlu",
        config=config,
    )


def validate_global_mmlu_selection(selection: dict[str, Any]) -> None:
    """Validate a paper-defined Global MMLU subject/language selection."""
    if not isinstance(selection, dict):
        raise ValueError("Global MMLU selection must be an object")
    if selection.get("schema_version") != GLOBAL_MMLU_SELECTION_SCHEMA_VERSION:
        raise ValueError("unsupported Global MMLU selection schema version")
    for field in ("selection_id", "dataset_id", "source", "revision", "split"):
        _require_non_empty_text(selection.get(field), field=field)
    if selection["dataset_id"] != "Global-MMLU":
        raise ValueError("Global MMLU selection dataset_id must be Global-MMLU")

    languages = selection.get("languages")
    if not isinstance(languages, list) or not languages:
        raise ValueError("Global MMLU selection must contain languages")
    language_configs: set[str] = set()
    for index, language in enumerate(languages):
        if not isinstance(language, dict):
            raise ValueError(f"Global MMLU selection language {index} must be an object")
        config = _require_non_empty_text(language.get("config"), field=f"languages[{index}].config")
        _require_non_empty_text(
            language.get("resource_tier"),
            field=f"languages[{index}].resource_tier",
        )
        expected_records = language.get("expected_records")
        if (
            isinstance(expected_records, bool)
            or not isinstance(expected_records, int)
            or expected_records <= 0
        ):
            raise ValueError(
                f"languages[{index}].expected_records must be a positive integer"
            )
        if config in language_configs:
            raise ValueError(f"Global MMLU selection repeats config {config!r}")
        language_configs.add(config)

    subjects = selection.get("subjects")
    if not isinstance(subjects, dict) or not subjects:
        raise ValueError("Global MMLU selection must contain subjects")
    subject_ids: set[str] = set()
    for category, values in subjects.items():
        _require_non_empty_text(category, field="subjects category")
        if not isinstance(values, list) or not values:
            raise ValueError(f"subjects[{category!r}] must be a non-empty list")
        for subject in values:
            normalized_subject = _require_non_empty_text(subject, field="subject")
            if normalized_subject in subject_ids:
                raise ValueError(f"Global MMLU selection repeats subject {normalized_subject!r}")
            subject_ids.add(normalized_subject)


def load_global_mmlu_selection(path: str | Path) -> dict[str, Any]:
    """Load and validate a paper-defined Global MMLU selection manifest."""
    source_path = Path(path)
    try:
        selection = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid Global MMLU selection JSON: {source_path}") from error
    validate_global_mmlu_selection(selection)
    return selection


def load_global_mmlu_jsonl(
    path: str | Path,
    *,
    config: str,
    split: str,
    selection: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Load Global MMLU JSONL and optionally apply a paper subject selection."""
    config = _require_non_empty_text(config, field="config")
    split = _require_non_empty_text(split, field="split")
    selected_subjects: set[str] | None = None
    expected_records: int | None = None
    if selection is not None:
        validate_global_mmlu_selection(selection)
        if selection["split"] != split:
            raise ValueError("Global MMLU selection split does not match requested split")
        language = next(
            (
                entry
                for entry in selection["languages"]
                if entry["config"] == config
            ),
            None,
        )
        if language is None:
            raise ValueError(f"Global MMLU selection does not include config {config!r}")
        selected_subjects = {
            subject
            for category in selection["subjects"].values()
            for subject in category
        }
        expected_records = int(language["expected_records"])

    source_path = Path(path)
    tasks: list[dict[str, Any]] = []
    source_index = 0
    with source_path.open(encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid Global MMLU JSON on line {line_number}") from error
            if not isinstance(record, dict):
                raise ValueError(f"Global MMLU record on line {line_number} must be an object")
            if selected_subjects is None or record.get("subject") in selected_subjects:
                tasks.append(
                    adapt_global_mmlu_record(
                        record,
                        config=config,
                        split=split,
                        source_index=source_index,
                    )
                )
            source_index += 1
    if expected_records is not None and len(tasks) != expected_records:
        raise ValueError(
            f"Global MMLU selection expected {expected_records} records for {config!r}, "
            f"found {len(tasks)}"
        )
    return tasks


def adapt_lexam_record(
    record: dict[str, Any],
    *,
    config: str,
    split: str,
    source_index: int,
) -> dict[str, Any]:
    """Adapt one LEXam record into the fixed task schema."""
    return _adapt_multiple_choice_record(
        record,
        dataset_id="LEXam",
        split=split,
        source_index=source_index,
        source_format="lexam",
        config=config,
    )


def validate_split_manifest(manifest: dict[str, Any]) -> None:
    """Validate the repository's fixed benchmark split manifest."""
    if not isinstance(manifest, dict):
        raise ValueError("split manifest must be an object")
    if manifest.get("schema_version") != SPLIT_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported split manifest schema version")
    splits = manifest.get("splits")
    if not isinstance(splits, list) or not splits:
        raise ValueError("split manifest must contain a non-empty splits list")
    required_fields = (
        "dataset_id",
        "source",
        "revision",
        "format",
        "split",
        "expected_records",
        "selection_status",
    )
    for index, entry in enumerate(splits):
        if not isinstance(entry, dict):
            raise ValueError(f"split manifest entry {index} must be an object")
        missing = [field for field in required_fields if field not in entry]
        if missing:
            raise ValueError(f"split manifest entry {index} is missing fields {missing}")
        for field in ("dataset_id", "source", "revision", "format", "split", "selection_status"):
            _require_non_empty_text(entry[field], field=f"splits[{index}].{field}")
        expected_records = entry["expected_records"]
        if not isinstance(expected_records, int) or isinstance(expected_records, bool) or expected_records <= 0:
            raise ValueError(f"splits[{index}].expected_records must be a positive integer")
        if "config" in entry:
            _require_non_empty_text(entry["config"], field=f"splits[{index}].config")


def load_split_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate a fixed split manifest from JSON."""
    source_path = Path(path)
    try:
        manifest = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid split manifest JSON: {source_path}") from error
    validate_split_manifest(manifest)
    return manifest
