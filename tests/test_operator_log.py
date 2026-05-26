from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stderr
from unittest import mock

from simula_research import operator_log


class OperatorLogTests(unittest.TestCase):
    def test_is_verbose_false_by_default(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(operator_log.is_verbose())

    def test_is_verbose_accepts_simula_verbose_and_log(self) -> None:
        with mock.patch.dict(os.environ, {"SIMULA_VERBOSE": "1"}, clear=True):
            self.assertTrue(operator_log.is_verbose())
        with mock.patch.dict(os.environ, {"SIMULA_LOG": "true"}, clear=True):
            self.assertTrue(operator_log.is_verbose())

    def test_log_step_prints_to_stderr_when_verbose(self) -> None:
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"SIMULA_VERBOSE": "1"}, clear=True):
            with redirect_stderr(buf):
                operator_log.log_step("hello")
        self.assertIn("hello", buf.getvalue())
        self.assertIn("[simula", buf.getvalue())

    def test_log_step_silent_when_not_verbose(self) -> None:
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True):
            with redirect_stderr(buf):
                operator_log.log_step("hello")
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
