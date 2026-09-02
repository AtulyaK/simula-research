from __future__ import annotations

import unittest

from simula_research.complexity_judgments import (
    calibrate_elo_ratings,
    collect_batchwise_complexity_judgments,
    prepare_complexity_batch_schedule,
)


class ComplexityJudgmentTests(unittest.TestCase):
    def test_batch_schedule_gives_each_item_n_varied_appearances(self) -> None:
        schedule = prepare_complexity_batch_schedule(
            ["a", "b", "c", "d"],
            batch_size=2,
            samples_per_item=5,
            seed=2,
        )

        appearances = {item_id: 0 for item_id in ("a", "b", "c", "d")}
        for batch in schedule:
            for item_id in batch["item_ids"]:
                appearances[item_id] += 1

        self.assertEqual(appearances, {"a": 5, "b": 5, "c": 5, "d": 5})
        self.assertGreater(len({tuple(batch["item_ids"]) for batch in schedule}), 2)

    def test_batchwise_scoring_persists_raw_scores_comparisons_and_elo(self) -> None:
        samples = [{"instantiation_id": item_id, "text": item_id} for item_id in ("easy", "hard", "mid")]

        def provider(batch: list[dict[str, object]]) -> list[dict[str, object]]:
            score_by_id = {"easy": 0.1, "mid": 0.5, "hard": 0.9}
            return [
                {"item_id": sample["instantiation_id"], "score": score_by_id[sample["instantiation_id"]]}
                for sample in batch
            ]

        result = collect_batchwise_complexity_judgments(
            samples,
            provider,
            batch_size=5,
            samples_per_item=5,
            seed=0,
        )

        self.assertEqual(result["protocol"]["batch_size"], 5)
        self.assertEqual(result["protocol"]["samples_per_item"], 5)
        self.assertEqual(result["protocol"]["appearance_counts"], {"easy": 5, "hard": 5, "mid": 5})
        self.assertEqual(len(result["raw_scores"]), 15)
        self.assertEqual(len(result["comparisons"]), 15)
        self.assertGreater(
            result["elo_calibration"]["ratings"]["hard"],
            result["elo_calibration"]["ratings"]["mid"],
        )
        self.assertGreater(
            result["elo_calibration"]["ratings"]["mid"],
            result["elo_calibration"]["ratings"]["easy"],
        )

    def test_batchwise_provider_must_return_scores_in_batch_order(self) -> None:
        with self.assertRaisesRegex(ValueError, "batch order"):
            collect_batchwise_complexity_judgments(
                [{"instantiation_id": "a"}, {"instantiation_id": "b"}],
                lambda batch: [
                    {"item_id": "b", "score": 1.0},
                    {"item_id": "a", "score": 0.0},
                ],
                batch_size=2,
                samples_per_item=1,
            )

    def test_elo_calibration_ranks_consistently_harder_items_higher(self) -> None:
        comparisons = [
            {"left_item_id": "hard", "right_item_id": "easy", "winner": "left"}
            for _ in range(5)
        ]

        ratings = calibrate_elo_ratings(
            comparisons,
            initial_rating=1000,
            k_factor=32,
        )

        self.assertGreater(ratings["hard"], ratings["easy"])
        self.assertAlmostEqual(ratings["hard"] + ratings["easy"], 2000.0)

    def test_elo_calibration_is_deterministic_for_ties(self) -> None:
        comparisons = [
            {"left_item_id": "left", "right_item_id": "right", "winner": "tie"}
        ]

        ratings = calibrate_elo_ratings(comparisons)

        self.assertEqual(ratings, {"left": 1000.0, "right": 1000.0})


if __name__ == "__main__":
    unittest.main()
