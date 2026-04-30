import unittest

from support.traceability import (
    assert_instantiation_traceability,
    assert_meta_prompt_traceability,
)
from support.fixtures import make_instantiation, make_meta_prompt, make_taxonomy_node


class HarnessFixturesTest(unittest.TestCase):
    def test_fixture_builders_create_lineage_without_provider_coupling(self) -> None:
        root = make_taxonomy_node("root", label="Root Topic")
        child = make_taxonomy_node("child", parent_node_id=root["taxonomy_node_id"])
        meta_prompt = make_meta_prompt("mp-1", taxonomy_node_id=child["taxonomy_node_id"])
        instantiation = make_instantiation(
            "inst-1",
            meta_prompt_id=meta_prompt["meta_prompt_id"],
            taxonomy_node_id=meta_prompt["taxonomy_node_id"],
        )

        self.assertEqual(root["taxonomy_node_id"], "tax-root")
        self.assertEqual(child["parent_taxonomy_node_id"], "tax-root")
        self.assertEqual(meta_prompt["taxonomy_node_id"], "tax-child")
        self.assertEqual(instantiation["meta_prompt_id"], "mp-1")
        self.assertEqual(instantiation["lineage"]["taxonomy_node_id"], "tax-child")


class HarnessAssertionsTest(unittest.TestCase):
    def test_traceability_assertions_validate_expected_lineage(self) -> None:
        node = make_taxonomy_node("finance")
        meta_prompt = make_meta_prompt("mp-2", taxonomy_node_id=node["taxonomy_node_id"])
        instantiation = make_instantiation(
            "inst-2",
            meta_prompt_id=meta_prompt["meta_prompt_id"],
            taxonomy_node_id=meta_prompt["taxonomy_node_id"],
        )

        assert_meta_prompt_traceability(
            meta_prompt,
            expected_taxonomy_node_id="tax-finance",
        )
        assert_instantiation_traceability(
            instantiation,
            expected_meta_prompt_id="mp-2",
            expected_taxonomy_node_id="tax-finance",
        )


if __name__ == "__main__":
    unittest.main()
