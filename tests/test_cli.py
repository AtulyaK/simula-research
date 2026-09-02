from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from simula_research.cli import main


class CliTests(unittest.TestCase):
    def test_verify_datasets_writes_local_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_manifest = {
                "schema_version": "0.1.0",
                "manifest_id": "test-splits",
                "splits": [
                    {
                        "dataset_id": "tiny",
                        "source": "https://example.test/tiny",
                        "revision": "abc123",
                        "source_path": "tiny.tsv",
                        "format": "tsv",
                        "split": "test",
                        "expected_records": 1,
                        "selection_status": "test",
                    }
                ],
            }
            split_path = root / "splits.json"
            source_path = root / "tiny.tsv"
            output_path = root / "local-manifest.json"
            split_path.write_text(json.dumps(split_manifest), encoding="utf-8")
            source_path.write_text("question\tanswer\nhello\tworld\n", encoding="utf-8")

            result = main(
                [
                    "verify-datasets",
                    "--split-manifest",
                    str(split_path),
                    "--output",
                    str(output_path),
                    "--dataset-path",
                    f"tiny={source_path}",
                ]
            )

            self.assertEqual(result, 0)
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["all_count_matches"])
            self.assertEqual(manifest["splits"][0]["observed_records"], 1)

    def test_verify_datasets_returns_nonzero_for_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            split_manifest = {
                "schema_version": "0.1.0",
                "manifest_id": "test-splits",
                "splits": [
                    {
                        "dataset_id": "tiny",
                        "source": "https://example.test/tiny",
                        "revision": "abc123",
                        "source_path": "tiny.tsv",
                        "format": "tsv",
                        "split": "test",
                        "expected_records": 2,
                        "selection_status": "test",
                    }
                ],
            }
            split_path = root / "splits.json"
            source_path = root / "tiny.tsv"
            output_path = root / "local-manifest.json"
            split_path.write_text(json.dumps(split_manifest), encoding="utf-8")
            source_path.write_text("question\tanswer\nhello\tworld\n", encoding="utf-8")

            result = main(
                [
                    "verify-datasets",
                    "--split-manifest",
                    str(split_path),
                    "--output",
                    str(output_path),
                    "--dataset-path",
                    f"tiny={source_path}",
                ]
            )

            self.assertEqual(result, 2)
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(manifest["all_count_matches"])

    def test_score_benchmark_writes_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset_path = root / "cti.tsv"
            predictions_path = root / "predictions.json"
            output_path = root / "result.json"
            dataset_path.write_text(
                "Question\tA\tB\tC\tD\tGT\n"
                "Which choice?\tfirst\tsecond\tthird\tfourth\tB\n",
                encoding="utf-8",
            )
            predictions_path.write_text(
                json.dumps({"cti-mcq-test-000000": "B"}),
                encoding="utf-8",
            )

            result = main(
                [
                    "score-benchmark",
                    "--dataset-id",
                    "CTI-MCQ",
                    "--dataset-path",
                    str(dataset_path),
                    "--predictions",
                    str(predictions_path),
                    "--dataset-size",
                    "1",
                    "--seed",
                    "0",
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(result, 0)
            scored = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(scored["accuracy"], 1.0)

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
