from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from simula_research.cli import main


class CliTests(unittest.TestCase):
    def test_matrix_command_runs_with_explicit_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = {
                "execution_id": "execution-id",
                "matrix_root": str(root / "reports"),
                "comparison_tables_path": str(root / "comparison.json"),
            }
            output = io.StringIO()
            with mock.patch("simula_research.cli.execute_issue7_matrix", return_value=expected) as run:
                with redirect_stdout(output):
                    result = main(
                        [
                            "matrix",
                            "--artifact-root",
                            str(root / "runs"),
                            "--report-root",
                            str(root / "reports"),
                            "--branch",
                            "test-branch",
                            "--commit",
                            "test-commit",
                        ]
                    )

            self.assertEqual(result, 0)
            run.assert_called_once_with(
                artifact_root=str(root / "runs"),
                report_root=str(root / "reports"),
                branch_name="test-branch",
                commit_hash="test-commit",
            )
            self.assertIn("execution_id execution-id", output.getvalue())

    def test_matrix_passes_reduced_size_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = {
                "execution_id": "execution-id",
                "matrix_root": str(root / "reports"),
                "comparison_tables_path": str(root / "comparison.json"),
            }
            with mock.patch("simula_research.cli.execute_issue7_matrix", return_value=expected) as run:
                result = main(
                    [
                        "matrix",
                        "--artifact-root",
                        str(root / "runs"),
                        "--report-root",
                        str(root / "reports"),
                        "--branch",
                        "test-branch",
                        "--commit",
                        "test-commit",
                        "--per-node-instantiations",
                        "1",
                    ]
                )

            self.assertEqual(result, 0)
            run.assert_called_once_with(
                artifact_root=str(root / "runs"),
                report_root=str(root / "reports"),
                branch_name="test-branch",
                commit_hash="test-commit",
                per_node_instantiation_count=1,
            )


if __name__ == "__main__":
    unittest.main()
