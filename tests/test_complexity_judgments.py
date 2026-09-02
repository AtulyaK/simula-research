from __future__ import annotations

import unittest

from simula_research.complexity_judgments import calibrate_elo_ratings


class ComplexityJudgmentTests(unittest.TestCase):
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
