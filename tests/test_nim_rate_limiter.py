from __future__ import annotations

import os
import unittest

from simula_research.critic_provider_adapter import (
    _NimRequestRateLimiter,
    _get_nim_rate_limiter,
    provider_runtime_from_env,
    reset_nim_rate_limiter_for_tests,
)


class NimRateLimiterTests(unittest.TestCase):
    def test_wait_turn_enforces_min_interval_for_40_rpm(self) -> None:
        sleeps: list[float] = []
        times = iter([0.0, 0.0, 1.0, 2.0])
        limiter = _NimRequestRateLimiter(
            40.0,
            sleep_fn=sleeps.append,
            monotonic=lambda: next(times),
        )
        limiter.wait_turn()
        limiter.wait_turn()
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 0.5, places=5)

    def test_provider_runtime_includes_max_rpm_for_nim_backend(self) -> None:
        env = os.environ
        old = {
            "SIMULA_CRITIC_BACKEND": env.get("SIMULA_CRITIC_BACKEND"),
            "SIMULA_NIM_MAX_RPM": env.get("SIMULA_NIM_MAX_RPM"),
        }
        try:
            env["SIMULA_CRITIC_BACKEND"] = "nim"
            env["SIMULA_NIM_MAX_RPM"] = "40"
            reset_nim_rate_limiter_for_tests()
            runtime = provider_runtime_from_env()
            self.assertEqual(runtime["nim_critic"]["max_rpm"], 40.0)
            self.assertEqual(
                runtime["nim_critic"]["default_model"],
                "mistralai/mistral-large-3-675b-instruct-2512",
            )
        finally:
            reset_nim_rate_limiter_for_tests()
            for key, val in old.items():
                if val is None:
                    env.pop(key, None)
                else:
                    env[key] = val

    def test_get_nim_rate_limiter_respects_env_change_after_reset(self) -> None:
        env = os.environ
        old = env.get("SIMULA_NIM_MAX_RPM")
        try:
            env["SIMULA_NIM_MAX_RPM"] = "60"
            reset_nim_rate_limiter_for_tests()
            _get_nim_rate_limiter()
            env["SIMULA_NIM_MAX_RPM"] = "30"
            reset_nim_rate_limiter_for_tests()
            limiter = _get_nim_rate_limiter()
            self.assertAlmostEqual(limiter._min_interval_s, 2.0, places=5)
        finally:
            reset_nim_rate_limiter_for_tests()
            if old is None:
                env.pop("SIMULA_NIM_MAX_RPM", None)
            else:
                env["SIMULA_NIM_MAX_RPM"] = old


if __name__ == "__main__":
    unittest.main()
