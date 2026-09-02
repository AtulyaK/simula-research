from __future__ import annotations

import unittest

from simula_research.evaluation_metrics import compute_intrinsic_diversity_metrics


class IntrinsicDiversityMetricTests(unittest.TestCase):
    def test_global_and_local_distances_use_injected_embeddings(self) -> None:
        samples = [{"text": "zero"}, {"text": "one"}, {"text": "diagonal"}]

        def provider(texts: list[str]) -> list[list[float]]:
            vectors = {
                "zero": [1.0, 0.0],
                "one": [0.0, 1.0],
                "diagonal": [1.0, 1.0],
            }
            return [vectors[text] for text in texts]

        metrics = compute_intrinsic_diversity_metrics(
            samples,
            embedding_provider=provider,
            local_k=1,
        )

        expected_nearest_distance = 1.0 - 1.0 / 2.0**0.5
        self.assertEqual(metrics["embedding_provider"], "custom")
        self.assertEqual(metrics["embedding_dimension"], 2)
        self.assertEqual(metrics["global_pairwise_comparison_count"], 3)
        self.assertAlmostEqual(
            metrics["global_pairwise_cosine_distance"],
            (1.0 + expected_nearest_distance * 2) / 3,
        )
        self.assertAlmostEqual(metrics["local_knn_cosine_distance"], expected_nearest_distance)
        self.assertEqual(metrics["effective_local_neighbor_count"], 1.0)

    def test_default_provider_is_deterministic_and_single_sample_has_no_local_distance(self) -> None:
        samples = [{"text": "same text"}]

        first = compute_intrinsic_diversity_metrics(samples)
        second = compute_intrinsic_diversity_metrics(samples)

        self.assertEqual(first, second)
        self.assertEqual(first["embedding_provider"], "hash_sha256_v1")
        self.assertEqual(first["global_pairwise_cosine_distance"], 0.0)
        self.assertIsNone(first["local_knn_cosine_distance"])

    def test_empty_samples_are_not_evaluable(self) -> None:
        metrics = compute_intrinsic_diversity_metrics([])

        self.assertEqual(metrics["evaluation_status"], "not_evaluable")
        self.assertEqual(metrics["not_evaluable_reason"], "missing_samples")

    def test_provider_must_return_one_finite_equal_dimension_vector_per_sample(self) -> None:
        with self.assertRaisesRegex(ValueError, "one vector per sample"):
            compute_intrinsic_diversity_metrics(
                [{"text": "one"}, {"text": "two"}],
                embedding_provider=lambda texts: [[1.0, 0.0]],
            )

        with self.assertRaisesRegex(ValueError, "finite numbers"):
            compute_intrinsic_diversity_metrics(
                [{"text": "one"}],
                embedding_provider=lambda texts: [[float("nan")]],
            )


if __name__ == "__main__":
    unittest.main()
