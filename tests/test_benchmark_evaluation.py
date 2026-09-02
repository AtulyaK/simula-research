from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.benchmark_evaluation import (
    load_prediction_artifact,
    score_local_benchmark,
)
from simula_research.dataset_verification import build_local_dataset_manifest


class BenchmarkEvaluationTests(unittest.TestCase):
    def test_load_prediction_artifact_accepts_mapping_and_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mapping_path = root / "mapping.json"
            rows_path = root / "rows.json"
            mapping_path.write_text(json.dumps({"task-1": "A"}), encoding="utf-8")
            rows_path.write_text(
                json.dumps([{"task_id": "task-1", "prediction": "A"}]),
                encoding="utf-8",
            )

            self.assertEqual(load_prediction_artifact(mapping_path), {"task-1": "A"})
            self.assertEqual(load_prediction_artifact(rows_path), {"task-1": "A"})

    def test_score_local_cti_mcq_emits_protocol_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_path = root / "cti.tsv"
            predictions_path = root / "predictions.json"
            dataset_path.write_text(
                "Question\tA\tB\tC\tD\tGT\n"
                "Which choice?\tfirst\tsecond\tthird\tfourth\tB\n",
                encoding="utf-8",
            )
            predictions_path.write_text(
                json.dumps({"cti-mcq-test-000000": "The answer is B."}),
                encoding="utf-8",
            )

            result = score_local_benchmark(
                dataset_id="CTI-MCQ",
                path=dataset_path,
                predictions_path=predictions_path,
                split="test",
                dataset_size=1,
                seed=0,
            )

        self.assertEqual(result["task_type"], "multiple_choice")
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["missing_prediction_count"], 0)

    def test_score_local_gsm8k_reports_missing_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_path = root / "gsm8k.jsonl"
            predictions_path = root / "predictions.json"
            dataset_path.write_text(
                json.dumps({"question": "one", "answer": "#### 5"}) + "\n",
                encoding="utf-8",
            )
            predictions_path.write_text("{}", encoding="utf-8")

            result = score_local_benchmark(
                dataset_id="GSM8k",
                path=dataset_path,
                predictions_path=predictions_path,
                split="test",
                dataset_size=1,
                seed=0,
            )

        self.assertEqual(result["task_type"], "exact_match")
        self.assertEqual(result["accuracy"], 0.0)
        self.assertEqual(result["missing_prediction_count"], 1)

    def test_score_local_benchmark_can_require_verified_manifest(self) -> None:
        split_manifest = {
            "schema_version": "0.1.0",
            "manifest_id": "test-splits",
            "splits": [
                {
                    "dataset_id": "CTI-MCQ",
                    "source": "https://example.test/cti",
                    "revision": "abc123",
                    "source_path": "cti.tsv",
                    "format": "tsv",
                    "split": "test",
                    "expected_records": 1,
                    "selection_status": "test",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_path = root / "cti.tsv"
            predictions_path = root / "predictions.json"
            dataset_path.write_text(
                "Question\tA\tB\tC\tD\tGT\n"
                "Which choice?\tfirst\tsecond\tthird\tfourth\tB\n",
                encoding="utf-8",
            )
            predictions_path.write_text(
                json.dumps({"cti-mcq-test-000000": "B"}),
                encoding="utf-8",
            )
            local_manifest = build_local_dataset_manifest(
                split_manifest,
                {"CTI-MCQ": dataset_path},
            )

            result = score_local_benchmark(
                dataset_id="CTI-MCQ",
                path=dataset_path,
                predictions_path=predictions_path,
                split="test",
                dataset_size=1,
                seed=0,
                local_dataset_manifest=local_manifest,
            )

        self.assertEqual(result["accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
