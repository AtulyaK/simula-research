from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import patch

from simula_research.critic_provider_adapter import (
    batch_complexity_judgment_provider_from_env,
    critic_sample_evaluator_from_env,
    logging_critic_sample_evaluator,
    nvidia_batch_complexity_scorer,
    nvidia_critic_sample_evaluator,
    retry_with_backoff,
)


class CriticProviderAdapterTests(unittest.TestCase):
    def test_nvidia_batch_complexity_scorer_parses_ordered_scores(self) -> None:
        env = os.environ
        old = {
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "SIMULA_COMPLEXITY_MODEL": env.get("SIMULA_COMPLEXITY_MODEL"),
        }
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            env["SIMULA_COMPLEXITY_MODEL"] = "complexity-model"
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
                    "choices": [
                        {
                            "message": {
                                "content": '[{"item_id":"i1","score":20},{"item_id":"i2","score":80}]'
                            }
                        }
                    ]
                }

            scorer = nvidia_batch_complexity_scorer(
                http_post_json=fake_post_json,
                max_retries=0,
            )
            result = scorer(
                [
                    {"instantiation_id": "i1", "text": "simple"},
                    {"instantiation_id": "i2", "text": "complex"},
                ]
            )
            self.assertEqual(result, [{"item_id": "i1", "score": 20.0}, {"item_id": "i2", "score": 80.0}])
            self.assertEqual(captured["model"], "complexity-model")
        finally:
            for key, value in old.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value

    def test_nvidia_batch_complexity_scorer_rejects_malformed_output_without_raw_content(self) -> None:
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
                return {"choices": [{"message": {"content": "not-json prompt-secret"}}]}

            scorer = nvidia_batch_complexity_scorer(
                http_post_json=fake_post_json,
                max_retries=0,
                event_log=events,
            )
            with self.assertRaises(RuntimeError):
                scorer([{"instantiation_id": "i1", "text": "prompt-secret"}])
            self.assertEqual(events[0]["error_code"], "nvidia_batch_complexity_request_failed")
            self.assertNotIn("prompt-secret", json.dumps(events))
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]

    def test_nvidia_batch_complexity_scorer_uses_api_key_for_default_transport(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"

            class _Response:
                def __enter__(self) -> "_Response":
                    return self

                def __exit__(self, *_args: object) -> None:
                    return None

                def read(self) -> bytes:
                    return b'{"choices":[{"message":{"content":"[{\\\"item_id\\\":\\\"i1\\\",\\\"score\\\":1}]"}}]}'

            with patch("urllib.request.urlopen", return_value=_Response()) as urlopen:
                scorer = nvidia_batch_complexity_scorer(max_retries=0)
                scorer([{"instantiation_id": "i1", "text": "sample"}])
            request = urlopen.call_args.args[0]
            self.assertEqual(
                request.get_header("Authorization"),
                "".join(("Bear", "er ")) + "test-key",
            )
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]

    def test_nvidia_batch_complexity_scorer_honors_retry_after(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        calls = {"n": 0}
        sleeps: list[float] = []
        try:
            env["NVIDIA_API_KEY"] = "test-key"

            def fake_post_json(
                *,
                url: str,
                headers: dict[str, str],
                payload: dict[str, object],
                timeout_s: float,
            ) -> dict[str, object]:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise urllib.error.HTTPError(
                        url,
                        429,
                        "Too Many Requests",
                        {"Retry-After": "7"},
                        None,
                    )
                return {
                    "choices": [
                        {
                            "message": {
                                "content": '[{"item_id":"i1","score":42}]'
                            }
                        }
                    ]
                }

            scorer = nvidia_batch_complexity_scorer(
                http_post_json=fake_post_json,
                max_retries=1,
                sleep_fn=sleeps.append,
            )
            self.assertEqual(
                scorer([{"instantiation_id": "i1", "text": "sample"}]),
                [{"item_id": "i1", "score": 42.0}],
            )
            self.assertEqual(calls["n"], 2)
            self.assertEqual(sleeps, [7.0])
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]

    def test_batch_complexity_provider_replay(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([["i1", 12], {"item_id": "i2", "score": 88}], f)
            path = f.name
        env = os.environ
        old = {
            "SIMULA_COMPLEXITY_BACKEND": env.get("SIMULA_COMPLEXITY_BACKEND"),
            "SIMULA_COMPLEXITY_REPLAY_JSON": env.get("SIMULA_COMPLEXITY_REPLAY_JSON"),
        }
        try:
            env["SIMULA_COMPLEXITY_BACKEND"] = "replay"
            env["SIMULA_COMPLEXITY_REPLAY_JSON"] = path
            scorer = batch_complexity_judgment_provider_from_env()
            assert scorer is not None
            self.assertEqual(
                scorer(
                    [
                        {"instantiation_id": "i1", "text": "one"},
                        {"instantiation_id": "i2", "text": "two"},
                    ]
                ),
                [{"item_id": "i1", "score": 12.0}, {"item_id": "i2", "score": 88.0}],
            )
        finally:
            Path(path).unlink(missing_ok=True)
            for key, value in old.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value

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
                self.assertEqual(headers["Authorization"], "Bearer test-key")
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

    def test_nvidia_evaluator_defaults_to_kimi_k3(self) -> None:
        env = os.environ
        old = {
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "SIMULA_NIM_MODEL": env.get("SIMULA_NIM_MODEL"),
            "SIMULA_NVIDIA_MODEL": env.get("SIMULA_NVIDIA_MODEL"),
            "SIMULA_CRITIC_MODEL_A": env.get("SIMULA_CRITIC_MODEL_A"),
        }
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            env.pop("SIMULA_NIM_MODEL", None)
            env.pop("SIMULA_NVIDIA_MODEL", None)
            env.pop("SIMULA_CRITIC_MODEL_A", None)
            captured: dict[str, object] = {}

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                captured.update(payload)
                return {"choices": [{"message": {"content": "reject"}}]}

            verdict = nvidia_critic_sample_evaluator(
                http_post_json=fake_post_json,
                max_retries=0,
            )({"instantiation_id": "i1", "text": "hello world"}, "critic_a")
            self.assertEqual(verdict, "reject")
            self.assertEqual(captured["model"], "moonshotai/kimi-k3")
            self.assertEqual(captured["max_tokens"], 16384)
            self.assertEqual(captured["reasoning_effort"], "max")
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

    def test_nvidia_evaluator_reads_dotenv_key_without_persisting_it(self) -> None:
        env = os.environ
        old = {
            "SIMULA_DOTENV_PATH": env.get("SIMULA_DOTENV_PATH"),
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "NVAPI_KEY": env.get("NVAPI_KEY"),
            "SIMULA_NIM_MODEL": env.get("SIMULA_NIM_MODEL"),
        }
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as f:
            f.write("NVIDIA_API_KEY=dotenv-key\nSIMULA_NIM_MODEL=dotenv-model\n")
            dotenv_path = f.name
        try:
            env["SIMULA_DOTENV_PATH"] = dotenv_path
            for key in ("NVIDIA_API_KEY", "NVAPI_KEY", "SIMULA_NIM_MODEL"):
                env.pop(key, None)

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                self.assertEqual(headers["Authorization"], "Bearer dotenv-key")
                self.assertEqual(payload["model"], "dotenv-model")
                return {"choices": [{"message": {"content": "accept"}}]}

            verdict = nvidia_critic_sample_evaluator(
                http_post_json=fake_post_json,
                max_retries=0,
            )({"instantiation_id": "i1", "text": "sample"}, "critic_a")
            self.assertEqual(verdict, "accept")
        finally:
            Path(dotenv_path).unlink(missing_ok=True)
            for key, value in old.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value

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

    def test_nvidia_evaluator_honors_retry_after_on_rate_limit(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            calls = {"n": 0}
            sleeps: list[float] = []

            def fake_post_json(
                *,
                url: str,
                headers: dict[str, str],
                payload: dict[str, object],
                timeout_s: float,
            ) -> dict[str, object]:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise urllib.error.HTTPError(
                        url,
                        429,
                        "Too Many Requests",
                        {"Retry-After": "7"},
                        None,
                    )
                return {"choices": [{"message": {"content": "accept"}}]}

            ev = nvidia_critic_sample_evaluator(
                http_post_json=fake_post_json,
                max_retries=1,
                sleep_fn=sleeps.append,
            )
            verdict = ev({"instantiation_id": "i1", "text": "sample"}, "critic_a")

            self.assertEqual(verdict, "accept")
            self.assertEqual(calls["n"], 2)
            self.assertEqual(sleeps, [7.0])
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]

    def test_nvidia_evaluator_records_exhausted_rate_limit(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            events: list[dict[str, object]] = []

            def fake_post_json(
                *,
                url: str,
                headers: dict[str, str],
                payload: dict[str, object],
                timeout_s: float,
            ) -> dict[str, object]:
                raise urllib.error.HTTPError(
                    url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "11"},
                    None,
                )

            ev = nvidia_critic_sample_evaluator(
                http_post_json=fake_post_json,
                max_retries=0,
                event_log=events,
            )
            verdict = ev({"instantiation_id": "i1", "text": "sample"}, "critic_a")

            self.assertEqual(verdict, "reject")
            self.assertEqual(events[0]["error_code"], "nvidia_critic_rate_limited")
            self.assertEqual(events[0]["http_status"], 429)
            self.assertEqual(events[0]["retry_after_s"], 11.0)
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]

    def test_nvidia_evaluator_enforces_minimum_request_interval(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            sleeps: list[float] = []

            def fake_post_json(
                *,
                url: str,
                headers: dict[str, str],
                payload: dict[str, object],
                timeout_s: float,
            ) -> dict[str, object]:
                return {"choices": [{"message": {"content": "accept"}}]}

            ev = nvidia_critic_sample_evaluator(
                http_post_json=fake_post_json,
                min_interval_s=0.1,
                max_retries=0,
                sleep_fn=sleeps.append,
            )
            self.assertEqual(ev({"instantiation_id": "i1", "text": "sample"}, "critic_a"), "accept")
            self.assertEqual(ev({"instantiation_id": "i2", "text": "sample"}, "critic_a"), "accept")

            self.assertEqual(len(sleeps), 1)
            self.assertGreaterEqual(sleeps[0], 0.09)
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]

    def test_nvidia_evaluator_missing_api_key_raises(self) -> None:
        env = os.environ
        old = {
            "NVIDIA_API_KEY": env.get("NVIDIA_API_KEY"),
            "NVAPI_KEY": env.get("NVAPI_KEY"),
            "SIMULA_DOTENV_PATH": env.get("SIMULA_DOTENV_PATH"),
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                env.pop("NVIDIA_API_KEY", None)
                env.pop("NVAPI_KEY", None)
                env["SIMULA_DOTENV_PATH"] = str(Path(tmp_dir) / "missing.env")
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
            events: list[dict[str, object]] = []

            def fake_post_json(*, url: str, headers: dict[str, str], payload: dict[str, object], timeout_s: float) -> dict[str, object]:
                return {"choices": [{"message": {"content": "maybe"}}]}

            ev = nvidia_critic_sample_evaluator(
                http_post_json=fake_post_json,
                max_retries=0,
                event_log=events,
            )
            verdict = ev({"instantiation_id": "i1", "text": "super secret sample"}, "critic_a")
            self.assertEqual(verdict, "reject")
            self.assertEqual(events[0]["instantiation_id"], "i1")
            # Ensure no prompt text is leaked into structured events.
            self.assertNotIn("super secret sample", json.dumps(events))
        finally:
            for k, v in old.items():
                if v is None:
                    env.pop(k, None)
                else:
                    env[k] = v

    def test_nvidia_evaluator_rejects_non_token_output(self) -> None:
        env = os.environ
        old = {"NVIDIA_API_KEY": env.get("NVIDIA_API_KEY")}
        try:
            env["NVIDIA_API_KEY"] = "test-key"
            for content in ("accept because it is valid", "accept.", "unacceptable"):
                def fake_post_json(
                    *,
                    url: str,
                    headers: dict[str, str],
                    payload: dict[str, object],
                    timeout_s: float,
                    content: str = content,
                ) -> dict[str, object]:
                    return {"choices": [{"message": {"content": content}}]}

                verdict = nvidia_critic_sample_evaluator(
                    http_post_json=fake_post_json,
                    max_retries=0,
                )({"instantiation_id": "i1", "text": "sample"}, "critic_a")
                self.assertEqual(verdict, "reject")
        finally:
            if old["NVIDIA_API_KEY"] is None:
                env.pop("NVIDIA_API_KEY", None)
            else:
                env["NVIDIA_API_KEY"] = old["NVIDIA_API_KEY"]


if __name__ == "__main__":
    unittest.main()
