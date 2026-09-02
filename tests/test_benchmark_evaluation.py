from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.benchmark_evaluation import (
    generate_nvidia_predictions,
    load_prediction_artifact,
    predict_local_benchmark,
    score_local_benchmark,
)
from simula_research.dataset_verification import build_local_dataset_manifest


class BenchmarkEvaluationTests(unittest.TestCase):
    def test_generate_nvidia_predictions_requires_strict_prediction_objects(self) -> None:
        responses = iter([{"prediction": "B"}, {"prediction": "5"}])

        predictions = generate_nvidia_predictions(
            [
                {"task_id": "task-1", "prompt": "Choose.", "metadata": {}},
                {"task_id": "task-2", "prompt": "Calculate.", "metadata": {}},
            ],
            task_type="multiple_choice",
            completion=lambda **_: next(responses),
        )

        self.assertEqual(predictions, {"task-1": "B", "task-2": "5"})

    def test_generate_nvidia_predictions_rejects_extra_json_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly"):
            generate_nvidia_predictions(
                [{"task_id": "task-1", "prompt": "Choose.", "metadata": {}}],
                task_type="multiple_choice",
                completion=lambda **_: {"prediction": "B", "reason": "extra"},
            )

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

    def test_predict_local_benchmark_emits_model_labeled_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_path = root / "cti.tsv"
            dataset_path.write_text(
                "Question\tA\tB\tC\tD\tGT\n"
                "Which choice?\tfirst\tsecond\tthird\tfourth\tB\n",
                encoding="utf-8",
            )
            artifact = predict_local_benchmark(
                dataset_id="CTI-MCQ",
                path=dataset_path,
                split="test",
                dataset_size=1,
                seed=0,
                model="test-model",
                completion=lambda **_: {"prediction": "B"},
            )

        self.assertEqual(artifact["backend"], "nvidia_nim")
        self.assertEqual(artifact["model"], "test-model")
        self.assertEqual(artifact["predictions"]["cti-mcq-test-000000"], "B")

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

    def test_score_local_global_mmlu_applies_selection_manifest(self) -> None:
        selection = {
            "schema_version": "0.1.0",
            "selection_id": "test-selection",
            "dataset_id": "Global-MMLU",
            "source": "https://example.test/global-mmlu",
            "revision": "revision",
            "split": "test",
            "languages": [
                {"config": "en", "resource_tier": "high", "expected_records": 1}
            ],
            "subjects": {"mathematics": ["elementary_mathematics"]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_path = root / "global-mmlu.jsonl"
            predictions_path = root / "predictions.json"
            dataset_path.write_text(
                "\n".join(
                    json.dumps(record)
                    for record in [
                        {
                            "sample_id": "selected",
                            "question": "One plus one?",
                            "choices": ["1", "2"],
                            "answer": "B",
                            "subject": "elementary_mathematics",
                        },
                        {
                            "sample_id": "excluded",
                            "question": "Who am I?",
                            "choices": ["A", "B"],
                            "answer": "A",
                            "subject": "philosophy",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            predictions_path.write_text(json.dumps({"selected": "B"}), encoding="utf-8")

            result = score_local_benchmark(
                dataset_id="Global-MMLU",
                path=dataset_path,
                predictions_path=predictions_path,
                split="test",
                dataset_size=1,
                seed=0,
                global_mmlu_config="en",
                global_mmlu_selection=selection,
            )

        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["missing_prediction_count"], 0)

    def test_score_local_lexam_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_path = root / "lexam.jsonl"
            predictions_path = root / "predictions.json"
            dataset_path.write_text(
                json.dumps(
                    {
                        "id": "lexam-1",
                        "question": "Which choice?",
                        "choices": ["first", "second"],
                        "gold": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            predictions_path.write_text(json.dumps({"lexam-1": "B"}), encoding="utf-8")

            result = score_local_benchmark(
                dataset_id="LEXam",
                path=dataset_path,
                predictions_path=predictions_path,
                split="test",
                dataset_size=1,
                seed=0,
                lexam_config="mcq_4_choices",
            )

        self.assertEqual(result["task_type"], "multiple_choice")
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["missing_prediction_count"], 0)

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
