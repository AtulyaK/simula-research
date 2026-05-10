from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from simula_research.critic_provider_adapter import (
    critic_sample_evaluator_from_env,
    logging_critic_sample_evaluator,
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


if __name__ == "__main__":
    unittest.main()
