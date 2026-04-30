from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.validators import (
    REQUIRED_ARTIFACT_STAGES,
    validate_artifact_tree,
    validate_manifest_schema,
)


class ValidatorTests(unittest.TestCase):
    def _valid_manifest(self) -> dict[str, object]:
        return {
            "run_id": "run-20260430T190000Z-abcd1234",
            "created_at_utc": "2026-04-30T19:00:00Z",
            "owner": "agent",
            "branch": "main",
            "commit_hash": "abc123def456",
            "artifact_schema_version": "v1",
            "domain_objective": "synthetic data generation",
            "seed": 7,
            "model_ids": {
                "generator": "gpt-4.1-mini",
                "critic_a": "gpt-4.1",
                "critic_b": "gpt-4.1",
            },
            "pipeline_config": {"max_nodes": 10},
            "protocol_version": "0.1.0",
            "baseline_or_ablation_tag": "B0",
        }

    def test_manifest_validation_success(self) -> None:
        result = validate_manifest_schema(self._valid_manifest())
        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "manifest")
        self.assertEqual(result["issues"], [])

    def test_manifest_validation_reports_missing_field(self) -> None:
        manifest = self._valid_manifest()
        manifest.pop("owner")
        result = validate_manifest_schema(manifest)
        self.assertFalse(result["ok"])
        self.assertIn("missing required field: owner", result["issues"])

    def test_artifact_tree_validation_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-1"
            run_root.mkdir(parents=True, exist_ok=True)
            for stage_name in REQUIRED_ARTIFACT_STAGES:
                (run_root / stage_name).mkdir()

            result = validate_artifact_tree(run_root)

        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "artifacts")
        self.assertEqual(result["issues"], [])

    def test_artifact_tree_validation_reports_missing_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-2"
            run_root.mkdir(parents=True, exist_ok=True)
            (run_root / REQUIRED_ARTIFACT_STAGES[0]).mkdir()

            result = validate_artifact_tree(run_root)

        self.assertFalse(result["ok"])
        self.assertGreater(len(result["issues"]), 0)
        self.assertTrue(
            any("missing required artifact stage directory" in issue for issue in result["issues"])
        )

    def test_end_to_end_cli_like_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_root = Path(tmp_dir) / "run-3"
            run_root.mkdir(parents=True, exist_ok=True)
            for stage_name in REQUIRED_ARTIFACT_STAGES:
                (run_root / stage_name).mkdir()
            manifest_path = run_root / "manifest.json"
            manifest_path.write_text(json.dumps(self._valid_manifest()), encoding="utf-8")

            manifest_result = validate_manifest_schema(json.loads(manifest_path.read_text("utf-8")))
            artifact_result = validate_artifact_tree(run_root)

        self.assertTrue(manifest_result["ok"])
        self.assertTrue(artifact_result["ok"])


if __name__ == "__main__":
    unittest.main()
