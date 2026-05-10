from __future__ import annotations

import copy
import tempfile
import unittest
from typing import cast

from simula_research.complexification import apply_complexification
from simula_research.dual_critic import adjudicate_samples
from simula_research.local_diversification import build_local_diversification
from simula_research.pipeline import run_pipeline
from simula_research.stage_contracts import (
    Stage1TaxonomyOutput,
    Stage2LocalDiversificationOutput,
    Stage3ComplexificationOutput,
    Stage4AdjudicationOutput,
    validate_adjudication_output,
    validate_complexification_output,
    validate_local_diversification_output,
    validate_stage_handoffs,
    validate_taxonomy_output,
)
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy


class StageContractsTests(unittest.TestCase):
    def test_validate_stage_handoffs_passes_on_default_pipeline_chain(self) -> None:
        taxonomy = build_taxonomy("pilot-domain", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        complexification = apply_complexification(samples=local["instantiations"])
        adjudication = adjudicate_samples(samples=complexification["samples"])
        validate_stage_handoffs(
            taxonomy=taxonomy,
            local_diversification=local,
            complexification=complexification,
            adjudication=adjudication,
        )

    def test_exported_typed_dict_shapes_pass_validators_on_default_pipeline(self) -> None:
        """Contract TypedDicts stay aligned with deterministic pipeline outputs (issue #31)."""
        taxonomy = build_taxonomy("pilot-domain", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        complexification = apply_complexification(samples=local["instantiations"])
        adjudication = adjudicate_samples(samples=complexification["samples"])
        validate_taxonomy_output(cast(Stage1TaxonomyOutput, taxonomy))
        validate_local_diversification_output(cast(Stage2LocalDiversificationOutput, local))
        validate_complexification_output(cast(Stage3ComplexificationOutput, complexification))
        validate_adjudication_output(cast(Stage4AdjudicationOutput, adjudication))

    def test_validate_taxonomy_output_rejects_duplicate_node_ids(self) -> None:
        taxonomy = build_taxonomy("x", TaxonomyConfig(max_depth=1, branching_factor=2))
        bad = copy.deepcopy(taxonomy)
        if len(bad["nodes"]) < 2:
            self.skipTest("need at least two nodes")
        nid = str(bad["nodes"][1]["taxonomy_node_id"])
        bad["nodes"][0]["taxonomy_node_id"] = nid
        with self.assertRaises(ValueError) as ctx:
            validate_taxonomy_output(bad)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_validate_local_diversification_rejects_lineage_mismatch(self) -> None:
        taxonomy = build_taxonomy("y", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        bad = copy.deepcopy(local)
        if not bad["instantiations"]:
            self.skipTest("need instantiations")
        bad["instantiations"][0]["lineage"]["taxonomy_node_id"] = "wrong"
        with self.assertRaises(ValueError) as ctx:
            validate_local_diversification_output(bad)
        self.assertIn("lineage", str(ctx.exception))

    def test_validate_complexification_rejects_missing_complexity_source(self) -> None:
        taxonomy = build_taxonomy("z", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        comp = apply_complexification(samples=local["instantiations"])
        bad = copy.deepcopy(comp)
        del bad["samples"][0]["complexity_source"]
        with self.assertRaises(ValueError):
            validate_complexification_output(bad)

    def test_validate_adjudication_rejects_bad_critic_decision(self) -> None:
        taxonomy = build_taxonomy("w", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        comp = apply_complexification(samples=local["instantiations"])
        adj = adjudicate_samples(samples=comp["samples"])
        bad = copy.deepcopy(adj)
        bad["decisions"][0]["critic_a_decision"] = "maybe"
        with self.assertRaises(ValueError):
            validate_adjudication_output(bad)

    def test_run_pipeline_invokes_stage_contract_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_pipeline(
                seed=7,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
            )


if __name__ == "__main__":
    unittest.main()
