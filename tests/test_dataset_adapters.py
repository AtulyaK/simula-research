from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.dataset_adapters import (
    TASK_SCHEMA_VERSION,
    adapt_cti_bench_record,
    adapt_cti_rcm_record,
    adapt_global_mmlu_record,
    adapt_lexam_record,
    adapt_gsm8k_record,
    load_cti_bench_tsv,
    load_gsm8k_jsonl,
    load_split_manifest,
    validate_split_manifest,
    validate_task_record,
)


class DatasetAdapterTests(unittest.TestCase):
    def test_adapt_benchmark_multiple_choice_records_to_fixed_task_schema(self) -> None:
        cti_task = adapt_cti_bench_record(
            {
                "Question": "Which option is correct?",
                "Option A": "first",
                "Option B": "second",
                "Option C": "third",
                "Option D": "fourth",
                "GT": "B",
                "URL": "https://example.test/item",
            },
            dataset_id="CTI-MCQ",
            split="test",
            source_index=3,
        )
        mmlu_task = adapt_global_mmlu_record(
            {
                "sample_id": "mmlu-1",
                "question": "Which option is correct?",
                "option_a": "first",
                "option_b": "second",
                "option_c": "third",
                "option_d": "fourth",
                "answer": "B",
                "subject": "computer_security",
            },
            config="en",
            split="test",
            source_index=0,
        )
        lexam_task = adapt_lexam_record(
            {
                "question": "Which option is correct?",
                "choices": "['first', 'second']",
                "gold": 1,
            },
            config="mcq_4_choices",
            split="test",
            source_index=0,
        )

        self.assertEqual(cti_task["dataset_id"], "CTI-MCQ")
        self.assertEqual(cti_task["answer"], "B")
        self.assertEqual(mmlu_task["task_id"], "mmlu-1")
        self.assertEqual(lexam_task["answer"], "1")
        for task in (cti_task, mmlu_task, lexam_task):
            validate_task_record(task)

    def test_adapt_cti_rcm_record_preserves_benchmark_prompt_and_description(self) -> None:
        task = adapt_cti_rcm_record(
            {
                "URL": "https://nvd.nist.gov/vuln/detail/CVE-2024-23848",
                "Description": "A use-after-free vulnerability.",
                "Prompt": "Map this CVE to the appropriate CWE.",
                "GT": "CWE-416",
            },
            dataset_id="CTI-RCM",
            split="test",
            source_index=2,
        )

        self.assertEqual(task["prompt"], "Map this CVE to the appropriate CWE.")
        self.assertEqual(task["answer"], "CWE-416")
        self.assertEqual(task["metadata"]["description"], "A use-after-free vulnerability.")
        validate_task_record(task)

    def test_load_cti_bench_tsv_skips_blank_rows_and_preserves_source_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "cti-mcq.tsv"
            path.write_text(
                "Question\tOption A\tOption B\tOption C\tOption D\tGT\n"
                "one\ta\tb\tc\td\tA\n"
                "\n"
                "two\ta\tb\tc\td\tD\n",
                encoding="utf-8",
            )
            tasks = load_cti_bench_tsv(path, dataset_id="CTI-MCQ", split="test")

        self.assertEqual([task["task_id"] for task in tasks], ["cti-mcq-test-000000", "cti-mcq-test-000001"])
        self.assertEqual([task["metadata"]["source_index"] for task in tasks], [0, 1])

    def test_load_cti_rcm_tsv_uses_rcm_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "cti-rcm.tsv"
            path.write_text(
                "URL\tDescription\tPrompt\tGT\n"
                "https://example.test/cve\tA vulnerability.\tMap it to CWE.\tCWE-416\n",
                encoding="utf-8",
            )
            tasks = load_cti_bench_tsv(path, dataset_id="CTI-RCM", split="test")

        self.assertEqual(tasks[0]["prompt"], "Map it to CWE.")
        self.assertEqual(tasks[0]["answer"], "CWE-416")

    def test_fixed_paper_split_manifest_validates(self) -> None:
        path = Path(__file__).parents[1] / "configs" / "paper_dataset_splits.json"
        manifest = load_split_manifest(path)
        validate_split_manifest(manifest)
        self.assertEqual(manifest["schema_version"], "0.1.0")
        self.assertTrue(any(row["dataset_id"] == "CTI-RCM" for row in manifest["splits"]))
        self.assertEqual(
            {row["dataset_id"]: row["expected_records"] for row in manifest["splits"]},
            {
                "CTI-MCQ": 2500,
                "CTI-RCM": 1000,
                "LEXam": 1655,
                "GSM8k": 1319,
                "Global-MMLU": 14042,
            },
        )

    def test_paper_global_mmlu_selection_is_pinned(self) -> None:
        path = Path(__file__).parents[1] / "configs" / "paper_global_mmlu_selection.json"
        selection = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(selection["revision"], "0e619dbeb34206cd48705a1a0ea7fb21cae09993")
        self.assertEqual(
            [language["config"] for language in selection["languages"]],
            ["en", "ko", "ne"],
        )
        self.assertEqual(
            {language["config"]: language["expected_records"] for language in selection["languages"]},
            {"en": 1436, "ko": 1436, "ne": 1436},
        )
        self.assertEqual(
            set(selection["subjects"]),
            {"mathematics", "computer_science", "physics"},
        )

    def test_adapt_gsm8k_record_preserves_rationale_and_extracts_final_answer(self) -> None:
        task = adapt_gsm8k_record(
            {
                "question": "If there are 2 apples and 3 more, how many?",
                "answer": "Add the quantities.#### 5",
            },
            split="train",
            source_index=4,
        )

        self.assertEqual(task["schema_version"], TASK_SCHEMA_VERSION)
        self.assertEqual(task["dataset_id"], "GSM8k")
        self.assertEqual(task["task_id"], "gsm8k-train-000004")
        self.assertEqual(task["answer"], "5")
        self.assertEqual(task["rationale"], "Add the quantities.#### 5")
        validate_task_record(task)

    def test_load_gsm8k_jsonl_skips_blank_lines_and_uses_explicit_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "gsm8k.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"question": "one", "answer": "#### 1"}),
                        "",
                        json.dumps({"id": "custom-id", "question": "two", "answer": "#### 2"}),
                    ]
                ),
                encoding="utf-8",
            )

            tasks = load_gsm8k_jsonl(path, split="test")

        self.assertEqual([task["task_id"] for task in tasks], ["gsm8k-test-000000", "custom-id"])
        self.assertEqual([task["answer"] for task in tasks], ["1", "2"])

    def test_invalid_task_record_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing fields"):
            validate_task_record({"task_id": "missing-fields"})

        with self.assertRaisesRegex(ValueError, "question must be"):
            adapt_gsm8k_record({"question": "", "answer": "#### 1"}, split="train", source_index=0)


if __name__ == "__main__":
    unittest.main()
