from __future__ import annotations

import os
import tempfile
import unittest

from simula_research.critic_provider_adapter import nvidia_critic_sample_evaluator
from simula_research.pipeline import run_pipeline


class Issue47NimBackendSmokeTests(unittest.TestCase):
    def test_pipeline_runs_with_nim_evaluator_stubbed_no_network(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            events: list[dict[str, object]] = []

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                # Deterministic stub: always accept.
                return {"choices": [{"message": {"content": "accept"}}]}

            evaluator = nvidia_critic_sample_evaluator(
                http_post_json=fake_post_json,
                max_retries=0,
                event_log=events,
            )

            with tempfile.TemporaryDirectory() as tmp:
                out = run_pipeline(
                    seed=1,
                    model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                    artifact_root=tmp,
                    taxonomy_config={"max_depth": 1, "branching_factor": 2},
                    critic_sample_evaluator=evaluator,
                    provider_runtime={"critic_backend": "nim", "source": "test"},
                    provider_event_log=events,
                )
                stage4 = out["stage_outputs"]["stage_4_dual_critic_quality_verification"]
                self.assertTrue(
                    os.path.exists(stage4["stage4_artifacts"]["nim_event_log"])
                )

            self.assertIn("stage4_artifacts", stage4)
            self.assertEqual(out["manifest"]["provider_runtime"]["critic_backend"], "nim")
            self.assertEqual(events, [])
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v


if __name__ == "__main__":
    unittest.main()
