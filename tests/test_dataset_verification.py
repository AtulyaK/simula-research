from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.dataset_adapters import load_split_manifest
from simula_research.dataset_verification import (
    build_local_dataset_manifest,
    validate_local_dataset_manifest,
    verify_local_split,
)


class DatasetVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.split_manifest = load_split_manifest(
            Path(__file__).parents[1] / "configs" / "paper_dataset_splits.json"
        )

    def test_verify_local_tsv_counts_nonblank_data_rows_and_hashes_file(self) -> None:
        entry = next(row for row in self.split_manifest["splits"] if row["dataset_id"] == "CTI-MCQ")
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "cti-mcq.tsv"
            path.write_text("Question\tGT\none\tA\n\ntwo\tB\n", encoding="utf-8")
            result = verify_local_split({**entry, "expected_records": 2}, path)

        self.assertEqual(result["observed_records"], 2)
        self.assertTrue(result["count_matches"])
        self.assertEqual(len(result["sha256"]), 64)

    def test_verify_local_jsonl_rejects_invalid_json(self) -> None:
        entry = next(row for row in self.split_manifest["splits"] if row["dataset_id"] == "GSM8k")
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "gsm8k.jsonl"
            path.write_text(json.dumps({"question": "one"}) + "\nnot-json\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSONL"):
                verify_local_split(entry, path)

    def test_parquet_requires_explicit_observed_count_without_optional_dependency(self) -> None:
        entry = next(row for row in self.split_manifest["splits"] if row["dataset_id"] == "LEXam")
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "lexam.parquet"
            path.write_bytes(b"placeholder")
            with self.assertRaisesRegex(ValueError, "optional reader"):
                verify_local_split(entry, path)
            result = verify_local_split(entry, path, observed_records=1655)

        self.assertEqual(result["observed_records"], 1655)
        self.assertTrue(result["count_matches"])

    def test_build_local_manifest_requires_every_pinned_dataset_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing local path"):
            build_local_dataset_manifest(self.split_manifest, {})

    def test_build_local_manifest_records_all_pinned_sources(self) -> None:
        split_manifest = {
            **self.split_manifest,
            "splits": [
                {
                    **entry,
                    "expected_records": (
                        1
                        if entry["dataset_id"] in {"CTI-MCQ", "CTI-RCM", "GSM8k"}
                        else entry["expected_records"]
                    ),
                }
                for entry in self.split_manifest["splits"]
            ],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            paths = {
                "CTI-MCQ": root / "cti-mcq.tsv",
                "CTI-RCM": root / "cti-rcm.tsv",
                "LEXam": root / "lexam.parquet",
                "GSM8k": root / "gsm8k.jsonl",
                "Global-MMLU": root / "global-mmlu.parquet",
            }
            paths["CTI-MCQ"].write_text("Question\tGT\none\tA\n", encoding="utf-8")
            paths["CTI-RCM"].write_text("Description\tPrompt\tGT\none\tmap\tCWE-1\n", encoding="utf-8")
            paths["LEXam"].write_bytes(b"lexam")
            paths["GSM8k"].write_text(json.dumps({"question": "one"}) + "\n", encoding="utf-8")
            paths["Global-MMLU"].write_bytes(b"mmlu")
            manifest = build_local_dataset_manifest(
                split_manifest,
                paths,
                observed_counts={
                    "CTI-MCQ": 1,
                    "CTI-RCM": 1,
                    "LEXam": 1655,
                    "GSM8k": 1,
                    "Global-MMLU": 14042,
                },
            )
            validate_local_dataset_manifest(manifest)

        self.assertTrue(manifest["all_count_matches"])
        self.assertEqual(len(manifest["splits"]), 5)


if __name__ == "__main__":
    unittest.main()
