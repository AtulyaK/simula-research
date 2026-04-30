import unittest

from simula_research.pipeline import run_pipeline


class Issue1TracerBulletTest(unittest.TestCase):
    def test_pipeline_shell_emits_manifest_and_stage_contracts(self) -> None:
        result = run_pipeline(
            seed=7,
            model_ids={"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
        )

        self.assertIn("manifest", result)
        self.assertIn("stage_outputs", result)

        manifest = result["manifest"]
        self.assertEqual(manifest["seed"], 7)
        self.assertEqual(manifest["protocol_version"], "0.1.0")
        self.assertEqual(manifest["artifact_schema_version"], "0.1.0")
        self.assertEqual(
            manifest["model_ids"],
            {"generator": "gpt-4.1-mini", "critic_a": "gpt-4.1", "critic_b": "gpt-4.1"},
        )

        stage_outputs = result["stage_outputs"]
        self.assertEqual(
            list(stage_outputs.keys()),
            [
                "stage_0_domain_run_spec",
                "stage_1_global_diversification",
                "stage_2_local_diversification",
                "stage_3_complexification",
                "stage_4_dual_critic_quality_verification",
                "stage_5_evaluation_handoff",
            ],
        )

        for stage_name, stage_output in stage_outputs.items():
            self.assertEqual(stage_output["run_id"], manifest["run_id"], msg=stage_name)
            if stage_name == "stage_1_global_diversification":
                self.assertEqual(stage_output["status"], "completed")
                self.assertIn("taxonomy_root_node_id", stage_output)
            elif stage_name == "stage_2_local_diversification":
                self.assertEqual(stage_output["status"], "completed")
                self.assertTrue(stage_output["anti_collapse_checks"]["executed"])
            elif stage_name == "stage_3_complexification":
                self.assertEqual(stage_output["status"], "completed")
                self.assertIn("complexification_policy", stage_output)
            else:
                self.assertEqual(stage_output["status"], "placeholder")


if __name__ == "__main__":
    unittest.main()
