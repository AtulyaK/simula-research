from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from simula_research.dual_critic import adjudicate_samples
from simula_research.evaluation_metrics import build_gate_report, compute_quality_metrics
from simula_research.pipeline import run_pipeline
from simula_research.provider_protocols import (
    hash_based_critic_verdict,
    recorded_sample_evaluator,
    sample_evaluator_from_text_fn,
)


class Issue22DualCriticEvaluatorsTests(unittest.TestCase):
    def test_sample_evaluator_wrapped_hash_matches_default_adjudication(self) -> None:
        samples = [
            {
                "instantiation_id": "a",
                "taxonomy_node_id": "t1",
                "meta_prompt_id": "m1",
                "text": "hello",
                "is_complexified": True,
            },
            {
                "instantiation_id": "b",
                "taxonomy_node_id": "t2",
                "meta_prompt_id": "m2",
                "text": "world",
                "is_complexified": False,
            },
        ]
        default_adj = adjudicate_samples(samples=samples, policy={"disagreement_policy": "reject"})
        wrapped_adj = adjudicate_samples(
            samples=samples,
            policy={"disagreement_policy": "reject"},
            critic_sample_evaluator=sample_evaluator_from_text_fn(hash_based_critic_verdict),
        )
        self.assertEqual(default_adj["decisions"], wrapped_adj["decisions"])
        self.assertEqual(default_adj["accepted_samples"], wrapped_adj["accepted_samples"])
        self.assertEqual(default_adj["rejection_log"], wrapped_adj["rejection_log"])

    def test_recorded_sample_evaluator_is_stable_replay(self) -> None:
        sample = {
            "instantiation_id": "inst-x",
            "taxonomy_node_id": "tax-x",
            "meta_prompt_id": "mp-x",
            "text": "fixed-text",
        }
        table: dict[tuple[str, str, str], str] = {
            ("inst-x", "critic_a", "fixed-text"): "accept",
            ("inst-x", "critic_b", "fixed-text"): "accept",
        }
        first = adjudicate_samples(samples=[sample], critic_sample_evaluator=recorded_sample_evaluator(table))
        second = adjudicate_samples(samples=[sample], critic_sample_evaluator=recorded_sample_evaluator(table))
        self.assertEqual(first, second)
        self.assertEqual(first["decisions"][0]["critic_a_decision"], "accept")
        self.assertEqual(first["decisions"][0]["quality_status"], "accepted")

    def test_sample_evaluator_receives_regenerated_text_in_sample(self) -> None:
        seen_texts: list[str] = []

        def capture(sample: dict[str, Any], critic_id: str) -> str:
            seen_texts.append(f"{critic_id}:{sample.get('text', '')}")
            return "accept" if critic_id == "critic_a" else "reject"

        sample = {
            "instantiation_id": "r1",
            "taxonomy_node_id": "t1",
            "meta_prompt_id": "m1",
            "text": "base",
        }
        adjudicate_samples(
            samples=[sample],
            policy={"disagreement_policy": "regenerate", "max_regenerations_per_sample": 1},
            critic_sample_evaluator=capture,
        )
        self.assertTrue(any("[regen-1]" in entry for entry in seen_texts))

    def test_regenerated_acceptance_preserves_regenerated_text_and_final_decisions(self) -> None:
        def evaluator(sample: dict[str, Any], critic_id: str) -> str:
            text = str(sample.get("text", ""))
            if "[regen-1]" in text:
                return "accept"
            return "accept" if critic_id == "critic_a" else "reject"

        sample = {
            "instantiation_id": "r2",
            "taxonomy_node_id": "t1",
            "meta_prompt_id": "m1",
            "text": "base",
        }
        adjudication = adjudicate_samples(
            samples=[sample],
            policy={"disagreement_policy": "regenerate", "max_regenerations_per_sample": 1},
            critic_sample_evaluator=evaluator,
        )
        self.assertEqual(len(adjudication["accepted_samples"]), 1)
        accepted = adjudication["accepted_samples"][0]
        self.assertIn("[regen-1]", accepted["text"])
        self.assertEqual(accepted["critic_a_decision"], "accept")
        self.assertEqual(accepted["critic_b_decision"], "accept")
        decision = adjudication["decisions"][0]
        self.assertEqual(decision["critic_a_decision"], "accept")
        self.assertEqual(decision["critic_b_decision"], "accept")
        self.assertFalse(decision["disagreement"])

    def test_both_evaluator_hooks_rejected(self) -> None:
        with self.assertRaises(ValueError):

            def _t(_text: str, _cid: str) -> str:
                return "accept"

            def _s(_sample: dict[str, Any], _cid: str) -> str:
                return "accept"

            adjudicate_samples(
                samples=[
                    {
                        "instantiation_id": "i",
                        "taxonomy_node_id": "t",
                        "meta_prompt_id": "m",
                        "text": "x",
                    }
                ],
                critic_verdict=_t,
                critic_sample_evaluator=_s,
            )

    def test_pipeline_sample_evaluator_issue6_quality_and_gate_report(self) -> None:
        def accept_complexified_only(sample: dict[str, Any], critic_id: str) -> str:
            if bool(sample.get("is_complexified")):
                return "accept"
            return "reject"

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_pipeline(
                seed=42,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp_dir,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
                dual_critic_config={"disagreement_policy": "reject"},
                critic_sample_evaluator=accept_complexified_only,
            )

            stage4 = result["stage_outputs"]["stage_4_dual_critic_quality_verification"]
            self.assertEqual(stage4["status"], "completed")

            decisions_path = Path(stage4["stage4_artifacts"]["critic_decisions"])
            decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
            for row in decisions:
                self.assertIn("critic_a_decision", row)
                self.assertIn("critic_b_decision", row)
                self.assertIn("quality_status", row)

            quality = compute_quality_metrics(issue5_outputs=stage4)
            self.assertFalse(quality["requires_issue_5_outputs"])
            self.assertIsNotNone(quality["acceptance_rate"])
            self.assertIsNotNone(quality["critic_agreement"])

            gate = build_gate_report(
                run_identity={"run_id": result["manifest"]["run_id"], "seed": 42},
                protocol={"critic_adjudication_config": {"mode": "dual_critic"}},
                coverage_metrics={"node_coverage_ratio": 0.9, "depth_coverage_profile": {"0": 0.9}},
                complexity_metrics={"complexification_precision": 0.8},
                quality_metrics=quality,
            )
            self.assertIn("gate_decision", gate)
            self.assertIn("quality", gate)

    def test_run_pipeline_rejects_both_critic_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                run_pipeline(
                    seed=1,
                    model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                    artifact_root=tmp_dir,
                    taxonomy_config={"max_depth": 1, "branching_factor": 2},
                    critic_verdict=hash_based_critic_verdict,
                    critic_sample_evaluator=sample_evaluator_from_text_fn(hash_based_critic_verdict),
                )


if __name__ == "__main__":
    unittest.main()
