from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from simula_research.dataset_adapters import (
    TASK_SCHEMA_VERSION,
    adapt_gsm8k_record,
    load_gsm8k_jsonl,
    validate_task_record,
)


class DatasetAdapterTests(unittest.TestCase):
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
