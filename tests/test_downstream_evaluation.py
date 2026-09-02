from __future__ import annotations

import json
import unittest
from pathlib import Path

from simula_research.dataset_adapters import load_split_manifest
from simula_research.downstream_evaluation import (
    aggregate_seed_accuracies,
    build_paper_downstream_evaluation_plan,
    score_exact_match_predictions,
    score_multiple_choice_predictions,
    validate_downstream_evaluation_plan,
    validate_downstream_evaluation_results,
)


class DownstreamEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.split_manifest = load_split_manifest(
            Path(__file__).parents[1] / "configs" / "paper_dataset_splits.json"
        )

    def test_paper_plan_pins_models_lora_ten_seeds_and_scaling(self) -> None:
        plan = build_paper_downstream_evaluation_plan(
            self.split_manifest,
            dataset_sizes=[1000, 2000],
            lora_config={"r": 16, "alpha": 32},
        )

        self.assertEqual(plan["student"]["model_id"], "google/gemma-3-4b-it")
        self.assertEqual(plan["teacher"]["model_id"], "gemini-2.5-flash")
        self.assertEqual(plan["student"]["training_method"], "lora")
        self.assertEqual(plan["seeds"], list(range(10)))
        validate_downstream_evaluation_plan(plan)

    def test_multiple_choice_scoring_handles_letter_and_zero_based_gold(self) -> None:
        tasks = [
            {
                "task_id": "global-1",
                "answer": "B",
                "metadata": {"choices": ["first", "second", "third", "fourth"]},
            },
            {
                "task_id": "lexam-1",
                "answer": 2,
                "metadata": {"choices": ["first", "second", "third", "fourth"]},
            },
        ]

        result = score_multiple_choice_predictions(
            tasks,
            {"global-1": "The answer is B.", "lexam-1": "C"},
        )

        self.assertEqual(result["task_count"], 2)
        self.assertEqual(result["correct_count"], 2)
        self.assertEqual(result["missing_prediction_count"], 0)
        self.assertEqual(result["accuracy"], 1.0)

    def test_exact_match_scoring_reports_missing_predictions(self) -> None:
        result = score_exact_match_predictions(
            [
                {"task_id": "gsm-1", "answer": "5"},
                {"task_id": "gsm-2", "answer": "12"},
            ],
            {"gsm-1": " 5 "},
        )

        self.assertEqual(result["correct_count"], 1)
        self.assertEqual(result["missing_prediction_count"], 1)
        self.assertEqual(result["accuracy"], 0.5)

    def test_seed_aggregation_is_explicit_and_deterministic(self) -> None:
        result = aggregate_seed_accuracies(
            [{"seed": 0, "accuracy": 0.5}, {"seed": 1, "accuracy": 0.75}]
        )

        self.assertEqual(result["seed_count"], 2)
        self.assertEqual(result["mean_accuracy"], 0.625)
        self.assertAlmostEqual(result["stddev_accuracy"], 0.125)
        json.dumps(result)

    def test_downstream_results_are_bound_to_plan_protocol(self) -> None:
        plan = build_paper_downstream_evaluation_plan(
            self.split_manifest,
            dataset_sizes=[1000],
        )
        validate_downstream_evaluation_results(
            plan,
            [
                {
                    "dataset_id": "GSM8k",
                    "dataset_size": 1000,
                    "seed": 0,
                    "task_type": "exact_match",
                    "accuracy": 0.5,
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "dataset_id"):
            validate_downstream_evaluation_results(
                plan,
                [
                    {
                        "dataset_id": "unknown",
                        "dataset_size": 1000,
                        "seed": 0,
                        "task_type": "exact_match",
                        "accuracy": 0.5,
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
