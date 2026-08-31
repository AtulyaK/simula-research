from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from simula_research.critic_provider_adapter import nvidia_critic_sample_evaluator
from simula_research.issue7_execution_reporting import execute_issue7_matrix


class Issue7ProviderMatrixTests(unittest.TestCase):
    def test_matrix_with_stub_backend_records_provider_runtime(self) -> None:
        env = os.environ
        old = {
            "SIMULA_CRITIC_BACKEND": env.get("SIMULA_CRITIC_BACKEND"),
            "SIMULA_HTTP_TIMEOUT_SECONDS": env.get("SIMULA_HTTP_TIMEOUT_SECONDS"),
        }
        try:
            env["SIMULA_CRITIC_BACKEND"] = "stub"
            env["SIMULA_HTTP_TIMEOUT_SECONDS"] = "30"
            with tempfile.TemporaryDirectory() as tmp_dir:
                output = execute_issue7_matrix(
                    artifact_root=tmp_dir,
                    report_root=tmp_dir,
                    branch_name="provider-matrix-stub",
                    commit_hash="cafebabe",
                )
                protocol = output["run_reports"]["B0"]["protocol"]
                self.assertEqual(protocol["provider_runtime"]["critic_backend"], "stub")
                self.assertEqual(protocol["provider_runtime"]["http_transport"]["timeout_s"], 30.0)
        finally:
            for key, value in old.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value

    def test_matrix_with_nim_backend_uses_mocked_http(self) -> None:
        env = os.environ
        old = {
            "SIMULA_CRITIC_BACKEND": env.get("SIMULA_CRITIC_BACKEND"),
            "SIMULA_NIM_MODEL": env.get("SIMULA_NIM_MODEL"),
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
        }
        try:
            env["SIMULA_CRITIC_BACKEND"] = "nim"
            env["SIMULA_NIM_MODEL"] = "some-kimi-model"
            env["NVIDIA_API_KEY"] = "test-key"

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                return {"choices": [{"message": {"content": "accept"}}]}

            mocked_evaluator = nvidia_critic_sample_evaluator(http_post_json=fake_post_json)
            with mock.patch(
                "simula_research.issue7_execution_reporting.critic_sample_evaluator_from_env",
                return_value=mocked_evaluator,
            ):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    output = execute_issue7_matrix(
                        artifact_root=tmp_dir,
                        report_root=tmp_dir,
                        branch_name="provider-matrix-nim-mock",
                        commit_hash="deadbeef",
                    )
                    protocol = output["run_reports"]["A4"]["protocol"]
                    self.assertEqual(protocol["provider_runtime"]["critic_backend"], "nim")
                    self.assertIn("nim_critic", protocol["provider_runtime"])
                    manifest_path = Path(output["run_reports"]["B0"]["artifacts"]["manifest"])
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    self.assertEqual(manifest["model_ids"]["generator"], "gpt-4.1-mini")
                    self.assertEqual(manifest["model_ids"]["critic_a"], "some-kimi-model")
                    self.assertEqual(manifest["model_ids"]["critic_b"], "some-kimi-model")

                    gate_path = Path(output["run_reports"]["B0"]["artifacts"]["gate_report"])
                    gate = json.loads(gate_path.read_text(encoding="utf-8"))
                    self.assertIn("gate_decision", gate)
        finally:
            for key, value in old.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value


if __name__ == "__main__":
    unittest.main()
