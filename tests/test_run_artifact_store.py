from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from simula_research.complexification import apply_complexification
from simula_research.dual_critic import adjudicate_samples
from simula_research.local_diversification import build_local_diversification
from simula_research.pipeline import run_pipeline
from simula_research.run_artifact_store import FileSystemRunArtifactStore
from simula_research.taxonomy import TaxonomyConfig, build_taxonomy


class FileSystemRunArtifactStoreTests(unittest.TestCase):
    def test_writes_expected_paths_and_round_trip_json(self) -> None:
        taxonomy = build_taxonomy("pilot", TaxonomyConfig(max_depth=1, branching_factor=2))
        local = build_local_diversification(taxonomy=taxonomy)
        comp = apply_complexification(samples=local["instantiations"])
        adj = adjudicate_samples(samples=comp["samples"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run-test"
            store = FileSystemRunArtifactStore(root)

            t_paths = store.persist_taxonomy(taxonomy)
            graph_path = Path(t_paths["taxonomy_graph"])
            self.assertEqual(graph_path.parent.parent, root)
            self.assertEqual(graph_path.parent.name, "10_taxonomy")

            l_paths = store.persist_local_diversification(local)
            self.assertEqual(Path(l_paths["instantiations"]).parent.name, "20_local_diversification")

            c_paths = store.persist_complexification(comp)
            self.assertEqual(Path(c_paths["samples"]).parent.name, "30_complexification")

            d_paths = store.persist_dual_critic(adj)
            self.assertEqual(Path(d_paths["critic_decisions"]).parent.name, "40_dual_critic_quality")

            loaded = json.loads(Path(t_paths["taxonomy_nodes"]).read_text(encoding="utf-8"))
            self.assertEqual(len(loaded), len(taxonomy["nodes"]))


class RunPipelineArtifactStoreFactoryTests(unittest.TestCase):
    def test_custom_factory_receives_run_root_and_can_noop_disk(self) -> None:
        seen: list[Path] = []

        class RecordingStore:
            def __init__(self, run_root: Path) -> None:
                self.run_root = run_root
                seen.append(run_root)

            def persist_taxonomy(self, taxonomy: dict[str, Any]) -> dict[str, str]:
                return {"taxonomy_graph": str(self.run_root / "g.json"), "taxonomy_nodes": str(self.run_root / "n.json")}

            def persist_local_diversification(self, local_diversification: dict[str, Any]) -> dict[str, str]:
                return {"instantiations": str(self.run_root / "i.json"), "rejections": str(self.run_root / "r.json")}

            def persist_complexification(self, complexification: dict[str, Any]) -> dict[str, str]:
                return {"samples": str(self.run_root / "s.json"), "semantic_preservation_failures": str(self.run_root / "f.json")}

            def persist_dual_critic(self, adjudication: dict[str, Any]) -> dict[str, str]:
                return {
                    "critic_decisions": str(self.run_root / "d.json"),
                    "rejections": str(self.run_root / "rj.json"),
                    "regenerations": str(self.run_root / "rg.json"),
                }

        with tempfile.TemporaryDirectory() as tmp:
            run_pipeline(
                seed=3,
                model_ids={"generator": "g", "critic_a": "a", "critic_b": "b"},
                domain_objective="pilot-domain",
                artifact_root=tmp,
                taxonomy_config={"max_depth": 1, "branching_factor": 2},
                artifact_store_factory=lambda root: RecordingStore(root),
            )

        self.assertEqual(len(seen), 1)
        self.assertTrue(str(seen[0]).startswith(tmp))


if __name__ == "__main__":
    unittest.main()
