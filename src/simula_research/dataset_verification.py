from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from simula_research.dataset_adapters import validate_split_manifest


def _count_local_records(path: Path, file_format: str) -> int:
    if file_format == "tsv":
        with path.open(newline="", encoding="utf-8-sig") as file_handle:
            reader = csv.DictReader(file_handle, delimiter="\t")
            if reader.fieldnames is None:
                raise ValueError(f"TSV file is missing a header row: {path}")
            return sum(
                1
                for row in reader
                if any(value and value.strip() for value in row.values() if isinstance(value, str))
            )
    if file_format == "jsonl":
        count = 0
        with path.open(encoding="utf-8") as file_handle:
            for line_number, line in enumerate(file_handle, start=1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid JSONL on line {line_number}: {path}") from error
                count += 1
        return count
    raise ValueError(
        f"record counting for {file_format!r} requires an optional reader; "
        "supply observed_records for parquet"
    )


def verify_local_split(
    split_entry: dict[str, Any],
    path: str | Path,
    *,
    observed_records: int | None = None,
) -> dict[str, Any]:
    """Verify a local benchmark split against one fixed-manifest entry."""
    wrapper = {"schema_version": "0.1.0", "splits": [split_entry]}
    validate_split_manifest(wrapper)
    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    file_format = str(split_entry["format"]).lower()
    record_count = (
        _count_local_records(source_path, file_format)
        if observed_records is None
        else observed_records
    )
    if isinstance(record_count, bool) or not isinstance(record_count, int) or record_count < 0:
        raise ValueError("observed_records must be a non-negative integer")
    digest = hashlib.sha256()
    with source_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    expected_records = int(split_entry["expected_records"])
    return {
        "dataset_id": split_entry["dataset_id"],
        "config": split_entry.get("config"),
        "split": split_entry["split"],
        "source": split_entry["source"],
        "revision": split_entry["revision"],
        "source_path": split_entry.get("source_path"),
        "format": file_format,
        "expected_records": expected_records,
        "observed_records": record_count,
        "count_matches": record_count == expected_records,
        "local_path": str(source_path),
        "sha256": digest.hexdigest(),
        "license_note": split_entry.get("license_note"),
    }


def build_local_dataset_manifest(
    split_manifest: dict[str, Any],
    local_paths: dict[str, str | Path],
    *,
    observed_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build an auditable local-source manifest without downloading benchmark data."""
    validate_split_manifest(split_manifest)
    observed_counts = observed_counts or {}
    records: list[dict[str, Any]] = []
    for entry in split_manifest["splits"]:
        dataset_id = str(entry["dataset_id"])
        if dataset_id not in local_paths:
            raise ValueError(f"missing local path for dataset {dataset_id!r}")
        records.append(
            verify_local_split(
                entry,
                local_paths[dataset_id],
                observed_records=observed_counts.get(dataset_id),
            )
        )
    return {
        "schema_version": "0.1.0",
        "manifest_id": split_manifest.get("manifest_id"),
        "source_split_manifest": split_manifest,
        "splits": records,
        "all_count_matches": all(record["count_matches"] for record in records),
    }


def verify_local_dataset_file(
    manifest: dict[str, Any],
    dataset_id: str,
    path: str | Path,
) -> dict[str, Any]:
    """Recheck one local file against a previously generated local manifest."""
    validate_local_dataset_manifest(manifest)
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise ValueError("dataset_id must be a non-empty string")
    records = [
        record for record in manifest["splits"] if record["dataset_id"] == dataset_id
    ]
    if len(records) != 1:
        raise ValueError(f"local dataset manifest must contain exactly one {dataset_id!r} entry")
    record = records[0]
    if not record["count_matches"]:
        raise ValueError(f"local dataset manifest count does not match for {dataset_id!r}")
    source_path = Path(path)
    if Path(record["local_path"]).resolve() != source_path.resolve():
        raise ValueError(f"local dataset path does not match manifest for {dataset_id!r}")
    split_entries = [
        entry
        for entry in manifest["source_split_manifest"]["splits"]
        if entry["dataset_id"] == dataset_id
    ]
    if len(split_entries) != 1:
        raise ValueError(f"split manifest must contain exactly one {dataset_id!r} entry")
    verified = verify_local_split(
        split_entries[0],
        source_path,
        observed_records=record["observed_records"],
    )
    if verified["sha256"] != record["sha256"]:
        raise ValueError(f"local dataset sha256 does not match manifest for {dataset_id!r}")
    if verified["observed_records"] != record["observed_records"]:
        raise ValueError(f"local dataset count does not match manifest for {dataset_id!r}")
    return record


def validate_local_dataset_manifest(manifest: dict[str, Any]) -> None:
    """Validate a hash/count manifest produced by ``build_local_dataset_manifest``."""
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "0.1.0":
        raise ValueError("unsupported local dataset manifest")
    validate_split_manifest(manifest.get("source_split_manifest"))
    records = manifest.get("splits")
    if not isinstance(records, list) or not records:
        raise ValueError("local dataset manifest must contain a non-empty splits list")
    required = (
        "dataset_id",
        "split",
        "expected_records",
        "observed_records",
        "count_matches",
        "local_path",
        "sha256",
    )
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"local dataset manifest entry {index} must be an object")
        missing = [field for field in required if field not in record]
        if missing:
            raise ValueError(f"local dataset manifest entry {index} is missing fields {missing}")
        if not isinstance(record["dataset_id"], str) or not record["dataset_id"].strip():
            raise ValueError(f"local dataset manifest entry {index} has invalid dataset_id")
        for field in ("expected_records", "observed_records"):
            if isinstance(record[field], bool) or not isinstance(record[field], int) or record[field] < 0:
                raise ValueError(f"local dataset manifest entry {index} has invalid {field}")
        if not isinstance(record["count_matches"], bool):
            raise ValueError(f"local dataset manifest entry {index} has invalid count_matches")
        if not isinstance(record["sha256"], str) or len(record["sha256"]) != 64:
            raise ValueError(f"local dataset manifest entry {index} has invalid sha256")
    expected_all_match = all(record["count_matches"] for record in records)
    if manifest.get("all_count_matches") is not expected_all_match:
        raise ValueError("local dataset manifest all_count_matches is inconsistent")
