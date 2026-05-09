from __future__ import annotations

import tempfile
import unittest

from simula_research.complexification import apply_complexification
from simula_research.dual_critic import adjudicate_samples
from simula_research.local_diversification import build_local_diversification
from simula_research.pipeline import run_pipeline
from simula_research.provider_protocols import hash_based_critic_verdict
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy


class ProviderProtocolsTests(unittest.TestCase):
    def test_explicit_hash_based_matches_default_adjudication(self) -> None:
        taxonomy = build_taxonomy("z", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        comp = apply_complexification(samples=local["instantiations"])
        default_adj = adjudicate_samples(samples=comp["samples"])
        explicit_adj = adjudicate_samples(samples=comp["samples"], critic_verdict=hash_based_critic_verdict)
        self.assertEqual(default_adj["decisions"], explicit_adj["decisions"])
        self.assertEqual(default_adj["accepted_samples"], explicit_adj["accepted_samples"])

    def test_custom_critic_verdict_all_accept(self) -> None:
        taxonomy = build_taxonomy("z", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        comp = apply_complexification(samples=local["instantiations"])

        def always_accept(_text: str, _critic_id: str) -> str:
            return "accept"

        adj = adjudicate_samples(samples=comp["samples"], critic_verdict=always_accept)
        self.assertGreater(len(adj["accepted_samples"]), 0)
        for decision in adj["decisions"]:
            self.assertEqual(decision["critic_a_decision"], "accept")
            self.assertEqual(decision["critic_b_decision"], "accept")
            self.assertEqual(decision["quality_status"], "accepted")

    def test_run_pipeline_passes_critic_verdict(self) -> None:
        def always_reject(_text: str, _critic_id: str) -> str:
            return "reject"

        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=99,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
                critic_verdict=always_reject,
            )
        stage4 = result["stage_outputs"]["stage_4_dual_critic_quality_verification"]
        self.assertEqual(stage4["accepted_samples"], 0)


if __name__ == "__main__":
    unittest.main()
