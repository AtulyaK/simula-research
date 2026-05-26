from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from simula_research.complexification import apply_complexification
from simula_research.local_diversification import build_local_diversification
from simula_research.pipeline import run_pipeline
from simula_research.provider_protocols import (
    default_complexification_provider,
    default_local_diversification_provider,
    default_taxonomy_provider,
)
from simula_research.stage_contracts import validate_stage_handoffs
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy

FIXTURES = Path(__file__).parent / "fixtures" / "issue60"
GOLDEN_DOMAIN = "pilot-domain"
GOLDEN_TAXONOMY_CONFIG = TaxonomyConfig(max_depth=2, branching_factor=2)
GOLDEN_LOCAL_OPTIONS: dict[str, Any] = {"per_node_instantiation_count": 3}
GOLDEN_COMPLEX_KWARGS: dict[str, Any] = {
    "complexify_fraction": 0.75,
    "semantic_overlap_threshold": 0.55,
    "strategy": "append_reasoning",
}


def _load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Issue60StageProviderProtocolsTests(unittest.TestCase):
    def test_default_taxonomy_provider_matches_build_taxonomy(self) -> None:
        direct = build_taxonomy(GOLDEN_DOMAIN, GOLDEN_TAXONOMY_CONFIG)
        via_provider = default_taxonomy_provider(GOLDEN_DOMAIN, GOLDEN_TAXONOMY_CONFIG)
        self.assertEqual(_canonical_json(direct), _canonical_json(via_provider))

    def test_default_local_diversification_provider_matches_build(self) -> None:
        taxonomy = build_taxonomy(GOLDEN_DOMAIN, GOLDEN_TAXONOMY_CONFIG)
        direct = build_local_diversification(taxonomy=taxonomy, options=GOLDEN_LOCAL_OPTIONS)
        via_provider = default_local_diversification_provider(taxonomy=taxonomy, options=GOLDEN_LOCAL_OPTIONS)
        self.assertEqual(_canonical_json(direct), _canonical_json(via_provider))

    def test_default_complexification_provider_matches_apply(self) -> None:
        taxonomy = build_taxonomy(GOLDEN_DOMAIN, GOLDEN_TAXONOMY_CONFIG)
        local = build_local_diversification(taxonomy=taxonomy, options=GOLDEN_LOCAL_OPTIONS)
        direct = apply_complexification(samples=local["instantiations"], **GOLDEN_COMPLEX_KWARGS)
        via_provider = default_complexification_provider(
            samples=local["instantiations"], **GOLDEN_COMPLEX_KWARGS
        )
        self.assertEqual(_canonical_json(direct), _canonical_json(via_provider))

    def test_golden_fixtures_match_default_providers(self) -> None:
        taxonomy = default_taxonomy_provider(GOLDEN_DOMAIN, GOLDEN_TAXONOMY_CONFIG)
        local = default_local_diversification_provider(taxonomy=taxonomy, options=GOLDEN_LOCAL_OPTIONS)
        comp = default_complexification_provider(samples=local["instantiations"], **GOLDEN_COMPLEX_KWARGS)
        self.assertEqual(_canonical_json(taxonomy), _canonical_json(_load_fixture("taxonomy_pilot_domain_depth2.json")))
        self.assertEqual(
            _canonical_json(local),
            _canonical_json(_load_fixture("local_diversification_pilot_domain_depth2.json")),
        )
        self.assertEqual(
            _canonical_json(comp),
            _canonical_json(_load_fixture("complexification_pilot_domain_depth2.json")),
        )

    def test_run_pipeline_implicit_defaults_match_golden_chain(self) -> None:
        captured: dict[str, Any] = {}

        class CapturingStore:
            def __init__(self, run_root: Path) -> None:
                self.run_root = run_root

            def persist_taxonomy(self, taxonomy: dict[str, Any]) -> dict[str, str]:
                captured["taxonomy"] = taxonomy
                return {"taxonomy_graph": str(self.run_root / "g.json"), "taxonomy_nodes": str(self.run_root / "n.json")}

            def persist_local_diversification(self, local_diversification: dict[str, Any]) -> dict[str, str]:
                captured["local_diversification"] = local_diversification
                return {"instantiations": str(self.run_root / "i.json"), "rejections": str(self.run_root / "r.json")}

            def persist_complexification(self, complexification: dict[str, Any]) -> dict[str, str]:
                captured["complexification"] = complexification
                return {"samples": str(self.run_root / "s.json"), "semantic_preservation_failures": str(self.run_root / "f.json")}

            def persist_dual_critic(self, adjudication: dict[str, Any]) -> dict[str, str]:
                captured["adjudication"] = adjudication
                return {
                    "critic_decisions": str(self.run_root / "d.json"),
                    "rejections": str(self.run_root / "rj.json"),
                    "regenerations": str(self.run_root / "rg.json"),
                }

        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=60,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective=GOLDEN_DOMAIN,
                artifact_root=tmp,
                taxonomy_config={"max_depth": 2, "branching_factor": 2},
                artifact_store_factory=lambda root: CapturingStore(root),
            )

        self.assertEqual(
            _canonical_json(captured["taxonomy"]),
            _canonical_json(_load_fixture("taxonomy_pilot_domain_depth2.json")),
        )
        self.assertEqual(
            _canonical_json(captured["local_diversification"]),
            _canonical_json(_load_fixture("local_diversification_pilot_domain_depth2.json")),
        )
        self.assertEqual(
            _canonical_json(captured["complexification"]),
            _canonical_json(_load_fixture("complexification_pilot_domain_depth2.json")),
        )
        validate_stage_handoffs(
            taxonomy=captured["taxonomy"],
            local_diversification=captured["local_diversification"],
            complexification=captured["complexification"],
            adjudication=captured["adjudication"],
        )
        self.assertEqual(
            result["taxonomy"]["root_taxonomy_node_id"],
            captured["taxonomy"]["root_taxonomy_node_id"],
        )

    def test_run_pipeline_explicit_default_providers_match_implicit(self) -> None:
        implicit: dict[str, Any] = {}
        explicit: dict[str, Any] = {}

        def _capturing(target: dict[str, Any]):
            class CapturingStore:
                def __init__(self, run_root: Path) -> None:
                    self.run_root = run_root

                def persist_taxonomy(self, taxonomy: dict[str, Any]) -> dict[str, str]:
                    target["taxonomy"] = taxonomy
                    return {"taxonomy_graph": "g", "taxonomy_nodes": "n"}

                def persist_local_diversification(self, local_diversification: dict[str, Any]) -> dict[str, str]:
                    target["local_diversification"] = local_diversification
                    return {"instantiations": "i", "rejections": "r"}

                def persist_complexification(self, complexification: dict[str, Any]) -> dict[str, str]:
                    target["complexification"] = complexification
                    return {"samples": "s", "semantic_preservation_failures": "f"}

                def persist_dual_critic(self, adjudication: dict[str, Any]) -> dict[str, str]:
                    target["adjudication"] = adjudication
                    return {"critic_decisions": "d", "rejections": "rj", "regenerations": "rg"}

            return CapturingStore

        common = dict(
            seed=60,
            model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
            domain_objective=GOLDEN_DOMAIN,
            taxonomy_config={"max_depth": 2, "branching_factor": 2},
        )

        with tempfile.TemporaryDirectory() as tmp:
            run_pipeline(**common, artifact_root=tmp, artifact_store_factory=lambda root: _capturing(implicit)(root))
            run_pipeline(
                **common,
                artifact_root=tmp,
                artifact_store_factory=lambda root: _capturing(explicit)(root),
                taxonomy_provider=default_taxonomy_provider,
                local_diversification_provider=default_local_diversification_provider,
                complexification_provider=default_complexification_provider,
            )

        for key in ("taxonomy", "local_diversification", "complexification"):
            self.assertEqual(
                _canonical_json(implicit[key]),
                _canonical_json(explicit[key]),
                msg=f"{key} differs between implicit and explicit default providers",
            )

    def test_custom_taxonomy_provider_is_invoked(self) -> None:
        seen: list[str] = []

        def stub_taxonomy(domain_objective: str, config: TaxonomyConfig | None = None) -> dict[str, Any]:
            seen.append(domain_objective)
            return build_taxonomy(domain_objective, TaxonomyConfig(max_depth=0, branching_factor=1))

        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=1,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="custom-domain",
                artifact_root=tmp,
                taxonomy_provider=stub_taxonomy,
            )

        self.assertEqual(seen, ["custom-domain"])
        self.assertEqual(result["stage_outputs"]["stage_1_global_diversification"]["taxonomy_node_count"], 1)


if __name__ == "__main__":
    unittest.main()
