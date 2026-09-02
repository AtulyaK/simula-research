from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.evaluation_metrics import compute_quality_metrics
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
            self.assertFalse(row["agreement_evaluable"])
            self.assertEqual(row["agreement_status"], "not_evaluable_single_critic")
        self.assertEqual(stage4["agreement_evaluable_samples"], 0)
        self.assertEqual(stage4["agreement_non_evaluable_samples"], stage4["reviewed_samples"])
        self.assertEqual(stage4["agreements"], 0)
        self.assertEqual(stage4["disagreements"], 0)
        quality = compute_quality_metrics(issue5_outputs=stage4)
        self.assertIsNone(quality["critic_agreement"])
        self.assertIsNone(quality["disagreement_rate"])

    def test_issue7_matrix_passes_preset_pipeline_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = execute_issue7_matrix(artifact_root=tmp, report_root=tmp)
            b0_tax = out["run_reports"]["B0"]["coverage"]["eligible_nodes"]
            a1_tax = out["run_reports"]["A1"]["coverage"]["eligible_nodes"]
            self.assertGreaterEqual(b0_tax, a1_tax)
            b0_protocol = out["run_reports"]["B0"]["protocol"]["taxonomy_eligibility_policy"]
            self.assertEqual(b0_protocol, "all-taxonomy-nodes-from-run-policy")
            b0_samples_path = (
                Path(tmp)
                / out["run_reports"]["B0"]["run_identity"]["run_id"]
                / "30_complexification"
                / "samples.json"
            )
            b0_samples = json.loads(b0_samples_path.read_text(encoding="utf-8"))
            b0_instantiated_nodes = {str(s["taxonomy_node_id"]) for s in b0_samples}
            self.assertGreaterEqual(b0_tax, len(b0_instantiated_nodes))
            b0_pairs = out["run_reports"]["B0"]["complexity"]["complexification_pairs_evaluated"]
            a1_pairs = out["run_reports"]["A1"]["complexity"]["complexification_pairs_evaluated"]
            b0_samples_path = (
                Path(tmp)
                / out["run_reports"]["B0"]["run_identity"]["run_id"]
                / "30_complexification"
                / "samples.json"
            )
            a1_samples_path = (
                Path(tmp)
                / out["run_reports"]["A1"]["run_identity"]["run_id"]
                / "30_complexification"
                / "samples.json"
            )
            b0_samples = json.loads(b0_samples_path.read_text(encoding="utf-8"))
            a1_samples = json.loads(a1_samples_path.read_text(encoding="utf-8"))
            self.assertEqual(b0_pairs, 0)
            self.assertEqual(a1_pairs, 0)
            self.assertEqual(
                out["run_reports"]["B0"]["complexity"]["proxy_metrics"]["sample_count"],
                len(b0_samples),
            )
            self.assertEqual(
                out["run_reports"]["A1"]["complexity"]["proxy_metrics"]["sample_count"],
                len(a1_samples),
            )

    def test_full_ablation_matrix_changes_the_intended_runtime_axes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = execute_issue7_matrix(
                artifact_root=tmp,
                report_root=tmp,
                per_node_instantiation_count=2,
            )

            a2_report = out["run_reports"]["A2"]
            a2_root = Path(tmp) / a2_report["run_identity"]["run_id"]
            a2_samples = json.loads(
                (a2_root / "30_complexification" / "samples.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                len(a2_samples),
                a2_report["coverage"]["eligible_nodes"],
            )

            a3_report = out["run_reports"]["A3"]
            a3_root = Path(tmp) / a3_report["run_identity"]["run_id"]
            a3_samples = json.loads(
                (a3_root / "30_complexification" / "samples.json").read_text(encoding="utf-8")
            )
            self.assertTrue(a3_samples)
            self.assertTrue(all(not sample["is_complexified"] for sample in a3_samples))
            a3_config = json.loads(
                (a3_root / "00_spec" / "run_config.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                a3_config["complexification_config"]["complexify_fraction"],
                0.0,
            )

            self.assertEqual(
                out["run_reports"]["A5"]["protocol"]["critic_adjudication_config"]["mode"],
                "dual_critic",
            )
            self.assertEqual(
                out["run_reports"]["A5"]["protocol"]["critic_adjudication_config"]["policy"],
                "accept_on_disagreement",
            )
            self.assertGreaterEqual(
                out["run_reports"]["A5"]["quality"]["acceptance_rate"],
                out["run_reports"]["B0"]["quality"]["acceptance_rate"],
            )


if __name__ == "__main__":
    unittest.main()
