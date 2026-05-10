from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.issue7_execution_reporting import execute_issue7_matrix
from simula_research.pipeline import run_pipeline
from simula_research.run_config_presets import build_run_request


class Issue42PipelineConfigExecutionTests(unittest.TestCase):
    def test_a1_pipeline_config_reduces_taxonomy_nodes_vs_b0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            b0 = run_pipeline(
                seed=7,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                pipeline_config=build_run_request("B0")["pipeline_config"],
            )
            a1 = run_pipeline(
                seed=7,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                pipeline_config=build_run_request("A1")["pipeline_config"],
            )
        b0_nodes = len(b0["taxonomy"]["nodes"])
        a1_nodes = len(a1["taxonomy"]["nodes"])
        self.assertGreater(b0_nodes, a1_nodes)
        self.assertEqual(a1_nodes, 1)

    def test_a4_single_critic_mirrors_decisions_in_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a4 = run_pipeline(
                seed=7,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
                pipeline_config=build_run_request("A4")["pipeline_config"],
            )
            stage4 = a4["stage_outputs"]["stage_4_dual_critic_quality_verification"]
            self.assertEqual(stage4["adjudication_policy"].get("single_critic_mode"), "critic_a")
            path = Path(stage4["stage4_artifacts"]["critic_decisions"])
            rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual(row["critic_a_decision"], row["critic_b_decision"])

    def test_issue7_matrix_passes_preset_pipeline_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = execute_issue7_matrix(artifact_root=tmp, report_root=tmp)
        b0_tax = out["run_reports"]["B0"]["coverage"]["eligible_nodes"]
        a1_tax = out["run_reports"]["A1"]["coverage"]["eligible_nodes"]
        self.assertGreater(b0_tax, a1_tax)


if __name__ == "__main__":
    unittest.main()
