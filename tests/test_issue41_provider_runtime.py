from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from simula_research.critic_provider_adapter import provider_runtime_from_env
from simula_research.pipeline import run_pipeline


class Issue41ProviderRuntimeTests(unittest.TestCase):
    def test_manifest_and_stage4_echo_provider_runtime(self) -> None:
        runtime = {
            "critic_transport": {"timeout_s": 12.0, "max_retries": 2, "backoff_base_s": 0.5},
            "models": {"critic_a": "stub-a", "critic_b": "stub-b"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
                provider_runtime=runtime,
            )
        self.assertEqual(result["manifest"]["provider_runtime"], runtime)
        stage4 = result["stage_outputs"]["stage_4_dual_critic_quality_verification"]
        self.assertEqual(stage4["provider_runtime"], runtime)

    def test_provider_runtime_from_env_reads_transport_numbers(self) -> None:
        env = os.environ
        old = {
            k: env.get(k)
            for k in (
                "SIMULA_HTTP_TIMEOUT_SECONDS",
                "SIMULA_HTTP_MAX_RETRIES",
                "SIMULA_HTTP_MIN_INTERVAL_SECONDS",
                "SIMULA_CRITIC_BACKEND",
                "SIMULA_GENERATION_BACKEND",
                "SIMULA_GENERATION_MODEL",
            )
        }
        try:
            env["SIMULA_HTTP_TIMEOUT_SECONDS"] = "30"
            env["SIMULA_HTTP_MAX_RETRIES"] = "4"
            env["SIMULA_HTTP_MIN_INTERVAL_SECONDS"] = "0.25"
            env["SIMULA_CRITIC_BACKEND"] = "stub"
            meta = provider_runtime_from_env()
            self.assertEqual(meta["http_transport"]["timeout_s"], 30.0)
            self.assertEqual(meta["http_transport"]["max_retries"], 4)
            self.assertEqual(meta["http_transport"]["min_interval_s"], 0.25)
            self.assertEqual(meta["critic_backend"], "stub")
            self.assertEqual(meta["generation_backend"], "hash_default")
        finally:
            for key, val in old.items():
                if val is None:
                    env.pop(key, None)
                else:
                    env[key] = val

    def test_provider_runtime_from_env_includes_nvidia_non_secret_fields(self) -> None:
        env = os.environ
        old = {
            "SIMULA_CRITIC_BACKEND": env.get("SIMULA_CRITIC_BACKEND"),
            "SIMULA_NVIDIA_BASE_URL": env.get("SIMULA_NVIDIA_BASE_URL"),
            "SIMULA_NVIDIA_MODEL": env.get("SIMULA_NVIDIA_MODEL"),
            "SIMULA_CRITIC_MODEL_A": env.get("SIMULA_CRITIC_MODEL_A"),
            "SIMULA_CRITIC_MODEL_B": env.get("SIMULA_CRITIC_MODEL_B"),
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "NVAPI_KEY": env.get("NVAPI_KEY"),
            "SIMULA_GENERATION_BACKEND": env.get("SIMULA_GENERATION_BACKEND"),
            "SIMULA_GENERATION_MODEL": env.get("SIMULA_GENERATION_MODEL"),
            "SIMULA_NIM_STREAM": env.get("SIMULA_NIM_STREAM"),
        }
        try:
            env["SIMULA_CRITIC_BACKEND"] = "nim"
            env["SIMULA_NVIDIA_BASE_URL"] = "https://example.com/v1/chat/completions"
            env["SIMULA_NVIDIA_MODEL"] = "some-model"
            env["SIMULA_CRITIC_MODEL_A"] = "critic-a-model"
            env.pop("SIMULA_CRITIC_MODEL_B", None)
            env["NVIDIA_API_KEY"] = "test-key"
            env.pop("NVAPI_KEY", None)
            env["SIMULA_GENERATION_BACKEND"] = "nim"
            env["SIMULA_GENERATION_MODEL"] = "generation-model"
            env["SIMULA_NIM_STREAM"] = "false"
            meta = provider_runtime_from_env()
            self.assertEqual(meta["critic_backend"], "nim")
            self.assertEqual(meta["nim_critic"]["base_url"], "https://example.com/v1/chat/completions")
            self.assertEqual(meta["nim_critic"]["default_model"], "some-model")
            self.assertEqual(meta["nim_critic"]["max_tokens"], 16384)
            self.assertEqual(meta["nim_critic"]["reasoning_effort"], "max")
            self.assertFalse(meta["nim_critic"]["stream"])
            self.assertEqual(
                meta["nim_critic"]["critic_models"],
                {"critic_a": "critic-a-model", "critic_b": "some-model"},
            )
            self.assertEqual(meta["nim_critic"]["api_key_env"], "NVIDIA_API_KEY")
            self.assertEqual(meta["generation_backend"], "nim")
            self.assertEqual(meta["nim_generation"]["model"], "generation-model")
            self.assertFalse(meta["nim_generation"]["stream"])
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v


if __name__ == "__main__":
    unittest.main()
