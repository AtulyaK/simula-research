from __future__ import annotations

import os
import unittest

from simula_research.embedding_provider_adapter import (
    embedding_provider_from_env,
    nvidia_embedding_provider,
)
from simula_research.evaluation_metrics import compute_intrinsic_diversity_metrics


class EmbeddingProviderAdapterTests(unittest.TestCase):
    def test_nvidia_embedding_provider_parses_indexed_vectors(self) -> None:
        env = os.environ
        old = {
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "SIMULA_EMBEDDING_MODEL": env.get("SIMULA_EMBEDDING_MODEL"),
        }
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            env["SIMULA_EMBEDDING_MODEL"] = "embedding-model"
            captured: dict[str, object] = {}

            def fake_post_json(
                *,
                url: str,
                headers: dict[str, str],
                payload: dict[str, object],
                timeout_s: float,
            ) -> dict[str, object]:
                captured.update(payload)
                self.assertEqual(headers["Authorization"], "******")
                return {
                    "data": [
                        {"index": 1, "embedding": [0.0, 1.0]},
                        {"index": 0, "embedding": [1.0, 0.0]},
                    ]
                }

            provider = nvidia_embedding_provider(
                http_post_json=fake_post_json,
                max_retries=0,
            )
            self.assertEqual(provider(["first", "second"]), [[1.0, 0.0], [0.0, 1.0]])
            metrics = compute_intrinsic_diversity_metrics(
                [{"text": "first"}, {"text": "second"}],
                embedding_provider=provider,
            )
            self.assertEqual(metrics["embedding_provider"], "nim:embedding-model")
            self.assertEqual(captured["model"], "embedding-model")
            self.assertEqual(captured["input_type"], "passage")
            self.assertEqual(getattr(provider, "__simula_embedding_provider_name__"), "nim:embedding-model")
        finally:
            for key, value in old.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value

    def test_nvidia_embedding_provider_fails_closed_and_sanitizes_events(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        events: list[dict[str, object]] = []
        try:
            env["NVIDIA_API_KEY"] = "test-key"

            def fake_post_json(
                *,
                url: str,
                headers: dict[str, str],
                payload: dict[str, object],
                timeout_s: float,
            ) -> dict[str, object]:
                return {"data": [{"embedding": ["not-a-number prompt-secret"]}]}

            provider = nvidia_embedding_provider(
                http_post_json=fake_post_json,
                max_retries=0,
                event_log=events,
            )
            with self.assertRaises(RuntimeError):
                provider(["prompt-secret"])
            self.assertEqual(events[0]["error_code"], "nvidia_embedding_request_failed")
            self.assertNotIn("prompt-secret", str(events))
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]

    def test_embedding_provider_from_env_is_opt_in(self) -> None:
        env = os.environ
        old = {"SIMULA_EMBEDDING_BACKEND": env.get("SIMULA_EMBEDDING_BACKEND")}
        try:
            env["SIMULA_EMBEDDING_BACKEND"] = "hash_default"
            self.assertIsNone(embedding_provider_from_env())
        finally:
            if old["SIMULA_EMBEDDING_BACKEND"] is None:
                env.pop("SIMULA_EMBEDDING_BACKEND", None)
            else:
                env["SIMULA_EMBEDDING_BACKEND"] = old["SIMULA_EMBEDDING_BACKEND"]


if __name__ == "__main__":
    unittest.main()
