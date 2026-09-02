from __future__ import annotations

import unittest

from simula_research.decontamination import (
    deduplicate_and_decontaminate,
    ngram_jaccard_similarity,
)


class DecontaminationTests(unittest.TestCase):
    def test_thirteen_gram_jaccard_detects_exact_short_text_matches(self) -> None:
        self.assertEqual(
            ngram_jaccard_similarity("Exact answer", " exact   answer "),
            1.0,
        )
        self.assertEqual(ngram_jaccard_similarity("different", "answer"), 0.0)

    def test_deduplication_and_test_contamination_are_reported_separately(self) -> None:
        samples = [
            {"task_id": "generated-1", "text": "A unique generated task"},
            {"task_id": "generated-2", "text": "A unique generated task"},
            {"task_id": "generated-3", "text": "A held out task"},
        ]
        reference = [{"task_id": "test-1", "text": "A held out task"}]

        result = deduplicate_and_decontaminate(samples, reference)

        self.assertEqual([sample["task_id"] for sample in result["accepted_samples"]], ["generated-1"])
        self.assertEqual(result["report"]["duplicate_rejection_count"], 1)
        self.assertEqual(result["report"]["contamination_rejection_count"], 1)
        self.assertEqual(
            [entry["reason"] for entry in result["rejection_log"]],
            ["duplicate_generated", "test_set_contamination"],
        )

    def test_threshold_can_retain_low_overlap_samples(self) -> None:
        result = deduplicate_and_decontaminate(
            [{"task_id": "generated-1", "text": "short prompt"}],
            [{"task_id": "test-1", "text": "different prompt"}],
            threshold=1.0,
        )

        self.assertEqual(len(result["accepted_samples"]), 1)
        self.assertEqual(result["report"]["protocol_version"], "13gram_jaccard_v1")

    def test_invalid_parameters_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ngram_size"):
            ngram_jaccard_similarity("a", "b", ngram_size=0)
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            deduplicate_and_decontaminate([], [], threshold=1.1)


if __name__ == "__main__":
    unittest.main()
