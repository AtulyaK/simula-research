from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.complexification import apply_complexification
from simula_research.local_diversification import build_local_diversification
from simula_research.pipeline import run_pipeline
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy


class TrackDGateRemediationTests(unittest.TestCase):
    def test_pipeline_default_complexify_fraction_is_075(self) -> None:
        taxonomy = build_taxonomy("z", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=11,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
            )
            stage3 = result["stage_outputs"]["stage_3_complexification"]
            samples_path = Path(stage3["complexification_artifacts"]["samples"])
            samples = json.loads(samples_path.read_text(encoding="utf-8"))
        expected = apply_complexification(
            samples=local["instantiations"],
            complexify_fraction=0.75,
        )
        complexified_count = sum(1 for sample in samples if sample["is_complexified"])
        expected_count = sum(1 for sample in expected["samples"] if sample["is_complexified"])
        self.assertEqual(complexified_count, expected_count)


if __name__ == "__main__":
    unittest.main()
