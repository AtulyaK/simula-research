from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.pipeline import run_pipeline


class Issue2TaxonomyStageTest(unittest.TestCase):
    def test_taxonomy_graph_is_acyclic_and_has_no_orphans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_pipeline(
                seed=11,
                model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
                domain_objective="financial compliance automation",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 2, "branching_factor": 2},
            )

        taxonomy = result["taxonomy"]
        nodes = taxonomy["nodes"]
        edges = taxonomy["edges"]

        node_ids = {node["taxonomy_node_id"] for node in nodes}
        self.assertEqual(len(node_ids), len(nodes), "taxonomy_node_id values must be unique")
        self.assertEqual(len(edges), len(nodes) - 1, "tree expansion should produce node_count-1 edges")

        root_id = taxonomy["root_taxonomy_node_id"]
        self.assertIn(root_id, node_ids)

        parent_index = {node["taxonomy_node_id"]: node["parent_taxonomy_node_id"] for node in nodes}
        self.assertIsNone(parent_index[root_id])

        for node in nodes:
            node_id = node["taxonomy_node_id"]
            parent_id = node["parent_taxonomy_node_id"]
            if node_id == root_id:
                continue
            self.assertIsNotNone(parent_id, msg=f"non-root node {node_id} missing parent")
            self.assertIn(parent_id, node_ids, msg=f"orphan node {node_id}")

            visited: set[str] = set()
            cursor = node_id
            while cursor is not None:
                self.assertNotIn(cursor, visited, msg=f"cycle detected at {cursor}")
                visited.add(cursor)
                cursor = parent_index[cursor]
            self.assertIn(root_id, visited, msg=f"node {node_id} does not connect to root")

    def test_taxonomy_node_ids_are_stable_for_same_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            first = run_pipeline(
                seed=1,
                model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
                domain_objective="medical triage support",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 2, "branching_factor": 2},
            )
            second = run_pipeline(
                seed=999,
                model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
                domain_objective="medical triage support",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 2, "branching_factor": 2},
            )

        first_ids = [node["taxonomy_node_id"] for node in first["taxonomy"]["nodes"]]
        second_ids = [node["taxonomy_node_id"] for node in second["taxonomy"]["nodes"]]
        self.assertEqual(first_ids, second_ids)

    def test_taxonomy_artifacts_and_handoff_contract_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_pipeline(
                seed=5,
                model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
                domain_objective="customer support routing",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
            )

            stage_output = result["stage_outputs"]["stage_1_global_diversification"]
            self.assertEqual(stage_output["status"], "completed")

            graph_path = Path(stage_output["taxonomy_artifacts"]["taxonomy_graph"])
            nodes_path = Path(stage_output["taxonomy_artifacts"]["taxonomy_nodes"])
            self.assertTrue(graph_path.exists())
            self.assertTrue(nodes_path.exists())

            graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
            nodes_payload = json.loads(nodes_path.read_text(encoding="utf-8"))
            self.assertEqual(graph_payload["root_taxonomy_node_id"], result["taxonomy"]["root_taxonomy_node_id"])
            self.assertEqual(len(nodes_payload), stage_output["taxonomy_node_count"])

            handoff = stage_output["handoff_contract_issue_3"]
            self.assertIn("required_fields_per_taxonomy_node", handoff)
            self.assertIn("traceability_fields_for_local_diversification", handoff)


if __name__ == "__main__":
    unittest.main()
