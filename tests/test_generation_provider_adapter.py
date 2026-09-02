from __future__ import annotations

import os
import unittest

from simula_research.generation_provider_adapter import (
    generation_providers_from_env,
    nvidia_complexification_provider,
    nvidia_json_completion,
    nvidia_local_diversification_provider,
    nvidia_taxonomy_provider,
)
from simula_research.provider_protocols import default_taxonomy_provider
from simula_research.stage_contracts import (
    validate_complexification_output,
    validate_local_diversification_output,
    validate_taxonomy_output,
)
from simula_research.taxonomy import TaxonomyConfig


class GenerationProviderAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_key = os.environ.get("NVIDIA_API_KEY")
        os.environ["NVIDIA_API_KEY"] = "test-key"

    def tearDown(self) -> None:
        if self._old_key is None:
            os.environ.pop("NVIDIA_API_KEY", None)
        else:
            os.environ["NVIDIA_API_KEY"] = self._old_key

    @staticmethod
    def _fake_transport(contents: list[str]):
        def _post(**_kwargs: object) -> dict[str, object]:
            return {"choices": [{"message": {"content": contents.pop(0)}}]}

        return _post

    def test_json_completion_parses_fenced_json_and_masks_injected_transport_auth(self) -> None:
        captured: dict[str, object] = {}

        def fake_post(**kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"choices": [{"message": {"content": "```json\n{\"ok\": true}\n```"}}]}

        result = nvidia_json_completion(
            system_prompt="system",
            user_content="user-secret",
            operation="test_generation",
            http_post_json=fake_post,
            max_retries=0,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["headers"]["Authorization"], "******")

    def test_taxonomy_provider_preserves_stage_contract(self) -> None:
        provider = nvidia_taxonomy_provider(
            http_post_json=self._fake_transport(['{"labels":["access control","detection"]}']),
            max_retries=0,
        )

        taxonomy = provider("cyber security", TaxonomyConfig(max_depth=1, branching_factor=2))

        validate_taxonomy_output(taxonomy)
        self.assertEqual(len(taxonomy["nodes"]), 3)
        self.assertEqual(taxonomy["generation_policy"]["provider"], "nvidia_nim")

    def test_local_provider_builds_lineage_and_rejects_duplicate_text(self) -> None:
        taxonomy = default_taxonomy_provider("security", TaxonomyConfig(max_depth=0, branching_factor=1))
        provider = nvidia_local_diversification_provider(
            http_post_json=self._fake_transport(
                ['[{"index":0,"text":"first scenario"},{"index":1,"text":"first scenario"}]']
            ),
            max_retries=0,
        )

        output = provider(
            taxonomy,
            options={"per_node_instantiation_count": 2, "overlap_rejection_threshold": 0.8},
        )

        validate_local_diversification_output(output)
        self.assertEqual(len(output["instantiations"]), 1)
        self.assertEqual(len(output["rejections"]), 1)
        self.assertEqual(
            output["instantiations"][0]["lineage"]["instantiation_id"],
            output["instantiations"][0]["instantiation_id"],
        )

    def test_complexification_provider_preserves_stage_contract(self) -> None:
        samples = [
            {
                "instantiation_id": "i1",
                "taxonomy_node_id": "t1",
                "meta_prompt_id": "m1",
                "text": "alpha beta",
            }
        ]
        provider = nvidia_complexification_provider(
            http_post_json=self._fake_transport(
                ['[{"instantiation_id":"i1","text":"alpha beta with reasoning"}]']
            ),
            max_retries=0,
        )

        output = provider(samples, complexify_fraction=1.0)

        validate_complexification_output(output)
        self.assertTrue(output["samples"][0]["is_complexified"])
        self.assertEqual(output["samples"][0]["complexity_source"], "nvidia_nim")

    def test_generation_backend_selection_is_explicit(self) -> None:
        old = os.environ.get("SIMULA_GENERATION_BACKEND")
        try:
            os.environ["SIMULA_GENERATION_BACKEND"] = "nim"
            providers = generation_providers_from_env()
            self.assertIsNotNone(providers)
            self.assertEqual(
                set(providers or {}),
                {"taxonomy", "local_diversification", "complexification"},
            )
        finally:
            if old is None:
                os.environ.pop("SIMULA_GENERATION_BACKEND", None)
            else:
                os.environ["SIMULA_GENERATION_BACKEND"] = old


if __name__ == "__main__":
    unittest.main()
