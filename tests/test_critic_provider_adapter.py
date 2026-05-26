from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from simula_research.critic_provider_adapter import (
    critic_sample_evaluator_from_env,
    logging_critic_sample_evaluator,
    nvidia_critic_sample_evaluator,
    retry_with_backoff,
)


class CriticProviderAdapterTests(unittest.TestCase):
    def test_retry_with_backoff_succeeds_after_transient_failure(self) -> None:
        calls = {"n": 0}

        def op() -> int:
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("transient")
            return 7

        result = retry_with_backoff(
            op,
            max_retries=3,
            backoff_base_s=0.01,
            rng=__import__("random").Random(0),
            sleep_fn=lambda _s: None,
        )
        self.assertEqual(result, 7)

    def test_logging_evaluator_records_failure_metadata(self) -> None:
        log: list[dict[str, object]] = []

        def boom(_sample: dict[str, object], _cid: str) -> str:
            raise ValueError("no")

        wrapped = logging_critic_sample_evaluator(boom, log)
        with self.assertRaises(ValueError):
            wrapped({"instantiation_id": "i1"}, "critic_a")
        self.assertEqual(log[0]["instantiation_id"], "i1")
        self.assertEqual(log[0]["critic_id"], "critic_a")
        self.assertEqual(log[0]["error_type"], "ValueError")

    def test_critic_sample_evaluator_from_env_stub(self) -> None:
        env = os.environ
        old = env.get("SIMULA_CRITIC_BACKEND")
        try:
            env["SIMULA_CRITIC_BACKEND"] = "stub"
            ev = critic_sample_evaluator_from_env()
            assert ev is not None
            v = ev({"text": "x", "instantiation_id": "1"}, "critic_a")
            self.assertIn(v, ("accept", "reject"))
        finally:
            if old is None:
                env.pop("SIMULA_CRITIC_BACKEND", None)
            else:
                env["SIMULA_CRITIC_BACKEND"] = old

    def test_critic_sample_evaluator_from_env_replay(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(
                [
                    ["s1", "critic_a", "hello", "accept"],
                    ["s1", "critic_b", "hello", "accept"],
                ],
                f,
            )
            path = f.name
        env = os.environ
        old_backend = env.get("SIMULA_CRITIC_BACKEND")
        old_path = env.get("SIMULA_CRITIC_REPLAY_JSON")
        try:
            env["SIMULA_CRITIC_BACKEND"] = "replay"
            env["SIMULA_CRITIC_REPLAY_JSON"] = path
            ev = critic_sample_evaluator_from_env()
            assert ev is not None
            self.assertEqual(ev({"instantiation_id": "s1", "text": "hello"}, "critic_a"), "accept")
        finally:
            Path(path).unlink(missing_ok=True)
            if old_backend is None:
                env.pop("SIMULA_CRITIC_BACKEND", None)
            else:
                env["SIMULA_CRITIC_BACKEND"] = old_backend
            if old_path is None:
                env.pop("SIMULA_CRITIC_REPLAY_JSON", None)
            else:
                env["SIMULA_CRITIC_REPLAY_JSON"] = old_path

    def test_nvidia_evaluator_happy_path_accept(self) -> None:
        import simula_research.critic_provider_adapter as adapter

        env = os.environ
        old = {
            "SIMULA_CRITIC_BACKEND": env.get("SIMULA_CRITIC_BACKEND"),
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "SIMULA_CRITIC_MODEL_A": env.get("SIMULA_CRITIC_MODEL_A"),
        }
        try:
            env["SIMULA_CRITIC_BACKEND"] = "nim"
            env["NVIDIA_API_KEY"] = "test-key"
            env["SIMULA_CRITIC_MODEL_A"] = "critic-a-model"

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                self.assertIn("Authorization", headers)
                self.assertTrue(headers["Authorization"].startswith("Bearer "))
                self.assertEqual(payload["model"], "critic-a-model")
                return {"choices": [{"message": {"content": "accept"}}]}

            ev = nvidia_critic_sample_evaluator(http_post_json=fake_post_json)
            verdict = ev({"instantiation_id": "i1", "text": "hello world"}, "critic_a")
            self.assertEqual(verdict, "accept")
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

    def test_nvidia_evaluator_retries_on_timeout_then_succeeds(self) -> None:
        import simula_research.critic_provider_adapter as adapter

        env = os.environ
        old = {
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "SIMULA_HTTP_MAX_RETRIES": env.get("SIMULA_HTTP_MAX_RETRIES"),
            "SIMULA_HTTP_BACKOFF_BASE_SECONDS": env.get("SIMULA_HTTP_BACKOFF_BASE_SECONDS"),
        }
        prev_sleep = adapter.time.sleep
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            env["SIMULA_HTTP_MAX_RETRIES"] = "1"
            env["SIMULA_HTTP_BACKOFF_BASE_SECONDS"] = "0.001"
            adapter.time.sleep = lambda _s: None
            calls = {"n": 0}

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise TimeoutError("network timeout with prompt secret")
                return {"choices": [{"message": {"content": "reject"}}]}

            ev = nvidia_critic_sample_evaluator(http_post_json=fake_post_json)
            verdict = ev({"instantiation_id": "i1", "text": "prompt secret"}, "critic_b")
            self.assertEqual(verdict, "reject")
            self.assertEqual(calls["n"], 2)
        finally:
            adapter.time.sleep = prev_sleep
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

    def test_nvidia_evaluator_missing_api_key_raises(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"), "NVAPI_KEY": env.get("NVAPI_KEY")}
        try:
            env.pop("NVIDIA_API_KEY", None)
            env.pop("NVAPI_KEY", None)
            with self.assertRaises(ValueError):
                nvidia_critic_sample_evaluator()({"text": "x", "instantiation_id": "i"}, "critic_a")
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

    def test_nvidia_evaluator_invalid_model_output_is_sanitized(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                return {"choices": [{"message": {"content": "maybe"}}]}

            ev = nvidia_critic_sample_evaluator(http_post_json=fake_post_json, max_retries=0)
            with self.assertRaises(RuntimeError) as ctx:
                ev({"instantiation_id": "i1", "text": "super secret sample"}, "critic_a")
            # Ensure the raised error does not leak the prompt.
            self.assertNotIn("super secret sample", str(ctx.exception))
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

    def test_nvidia_evaluator_rejects_substring_accept_output(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                return {"choices": [{"message": {"content": "unacceptable"}}]}

            ev = nvidia_critic_sample_evaluator(http_post_json=fake_post_json, max_retries=0)
            with self.assertRaises(RuntimeError):
                ev({"instantiation_id": "i1", "text": "bad sample"}, "critic_a")
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v


if __name__ == "__main__":
    unittest.main()
