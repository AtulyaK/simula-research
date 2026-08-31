"""Reproducibility validators for on-disk runs (Issue #9).

``validate_manifest_schema`` applies the **full** manifest field set from
``docs/reproducibility-ops.md``. ``manifest.validate_manifest`` is the narrower
**boot** check used by ``run_pipeline`` before stages run.

Use ``validate_manifest_by_mode`` when operators need a single entry point with
explicit ``mode="boot"`` or ``mode="full"``.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from simula_research.manifest import validate_manifest

ManifestValidationMode = Literal["boot", "full"]

# Reproducibility-ops required manifest fields.
REQUIRED_MANIFEST_FIELDS: tuple[str, ...] = (
    "run_id",
    "created_at_utc",
    "owner",
    "branch",
    "commit_hash",
    "artifact_schema_version",
    "domain_objective",
    "seed",
    "model_ids",
    "pipeline_config",
    "protocol_version",
    "baseline_or_ablation_tag",
)

# Reproducibility-ops stable artifact layout conventions.
REQUIRED_ARTIFACT_STAGES: tuple[str, ...] = (
    "00_spec",
    "10_taxonomy",
    "20_local_diversification",
    "30_complexification",
    "40_dual_critic_quality",
    "50_curated_dataset",
    "60_evaluation",
    "70_diagnostics",
)

REQUIRED_MODEL_ID_FIELDS: tuple[str, ...] = ("generator", "critic_a", "critic_b")

REQUIRED_ARTIFACT_FILES: dict[str, tuple[str, ...]] = {
    "10_taxonomy": ("taxonomy_graph.json", "taxonomy_nodes.json"),
    "20_local_diversification": ("instantiations.json", "rejections.json"),
    "30_complexification": ("samples.json", "semantic_preservation_failures.json"),
    "40_dual_critic_quality": ("critic_decisions.json", "rejections.json", "regenerations.json"),
    "50_curated_dataset": ("accepted_samples.json", "dataset_manifest.json"),
    "60_evaluation": ("evaluation_handoff.json",),
    "70_diagnostics": ("diagnostics_summary.json",),
}

INTEGRITY_ALGORITHM = "sha256"
INTEGRITY_SCHEMA_VERSION = "0.1.0"


def _validation_result(kind: str, issues: list[str], assumptions: list[str]) -> dict[str, Any]:
    return {
        "ok": len(issues) == 0,
        "kind": kind,
        "issues": issues,
        "assumptions": assumptions,
    }


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_parseable_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_manifest_schema(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate manifest against the full reproducibility-ops field set.

    Returns a structured result dict (does not raise). Boot-only manifests from
    ``run_pipeline`` are expected to fail until Issue #9 fields are added on disk.
    """
    issues: list[str] = []
    assumptions = [
        "Manifest payload is already parsed as JSON object",
        "Model identifiers are represented as strings in model_ids",
        "pipeline_config can be any non-empty JSON object shape as long as it is present",
    ]

    if not isinstance(manifest, dict):
        issues.append("manifest must be an object")
        return _validation_result(kind="manifest", issues=issues, assumptions=assumptions)

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            issues.append(f"missing required field: {field}")

    if "run_id" in manifest and (not isinstance(manifest["run_id"], str) or not manifest["run_id"].strip()):
        issues.append("field run_id must be a non-empty string")

    if "seed" in manifest and (not isinstance(manifest["seed"], int) or isinstance(manifest["seed"], bool)):
        issues.append("field seed must be an integer")

    for field in ("created_at_utc", "owner", "branch", "commit_hash", "domain_objective"):
        if field in manifest and not _non_empty_string(manifest[field]):
            issues.append(f"field {field} must be a non-empty string")

    if "created_at_utc" in manifest and _non_empty_string(manifest["created_at_utc"]):
        if not _is_parseable_timestamp(str(manifest["created_at_utc"])):
            issues.append("field created_at_utc must be an ISO-8601 timestamp")

    if "model_ids" in manifest:
        model_ids = manifest["model_ids"]
        if not isinstance(model_ids, dict) or not model_ids:
            issues.append("field model_ids must be a non-empty object")
        else:
            if any(field not in model_ids for field in REQUIRED_MODEL_ID_FIELDS):
                missing = [field for field in REQUIRED_MODEL_ID_FIELDS if field not in model_ids]
                issues.append(f"field model_ids missing required model roles: {missing}")
            if any(not isinstance(value, str) or not value.strip() for value in model_ids.values()):
                issues.append("field model_ids must map to non-empty string identifiers")

    for field in ("protocol_version", "artifact_schema_version", "baseline_or_ablation_tag"):
        if field in manifest and (not isinstance(manifest[field], str) or not manifest[field].strip()):
            issues.append(f"field {field} must be a non-empty string")

    if "pipeline_config" in manifest:
        if not isinstance(manifest["pipeline_config"], dict):
            issues.append("field pipeline_config must be an object")
        elif not manifest["pipeline_config"]:
            issues.append("field pipeline_config must be a non-empty object")

    if "provider_runtime" in manifest:
        if not isinstance(manifest["provider_runtime"], dict):
            issues.append("field provider_runtime must be an object when present")

    return _validation_result(kind="manifest", issues=issues, assumptions=assumptions)


def validate_manifest_by_mode(
    manifest: dict[str, Any],
    *,
    mode: ManifestValidationMode = "boot",
) -> dict[str, Any]:
    """Validate manifest in boot or full reproducibility mode.

    - ``boot``: delegates to ``manifest.validate_manifest`` (pipeline default).
    - ``full``: delegates to ``validate_manifest_schema`` (Issue #9 / ops).
    """
    if mode == "full":
        result = validate_manifest_schema(manifest)
        result["validation_mode"] = "full"
        return result

    try:
        validate_manifest(manifest)
    except ValueError as exc:
        return {
            **_validation_result(
                kind="manifest",
                issues=[str(exc)],
                assumptions=[
                    "Boot mode uses manifest.validate_manifest (raises converted to issues)",
                ],
            ),
            "validation_mode": "boot",
        }

    return {
        **_validation_result(
            kind="manifest",
            issues=[],
            assumptions=[
                "Boot mode uses manifest.validate_manifest",
                "Does not require owner, branch, commit_hash, or baseline_or_ablation_tag",
            ],
        ),
        "validation_mode": "boot",
    }


def validate_artifact_tree(run_root: str | Path) -> dict[str, Any]:
    root_path = Path(run_root)
    issues: list[str] = []
    assumptions = [
        "run_root points to artifacts/runs/<run_id>",
        "Required stages are represented as directories directly under run_root",
        "The canonical manifest is stored at 00_spec/manifest.json",
        "Legacy trees may store manifest.json at the run root",
        "Canonical artifact files use FileSystemRunArtifactStore names",
    ]

    if not root_path.exists():
        issues.append(f"run root does not exist: {root_path}")
        return _validation_result(kind="artifacts", issues=issues, assumptions=assumptions)

    if not root_path.is_dir():
        issues.append(f"run root is not a directory: {root_path}")
        return _validation_result(kind="artifacts", issues=issues, assumptions=assumptions)

    for stage_dir in REQUIRED_ARTIFACT_STAGES:
        stage_path = root_path / stage_dir
        if not stage_path.exists() or not stage_path.is_dir():
            issues.append(f"missing required artifact stage directory: {stage_dir}")

    manifest_path = root_path / "00_spec" / "manifest.json"
    canonical_spec = manifest_path.exists()
    if not manifest_path.exists() and (root_path / "manifest.json").exists():
        manifest_path = root_path / "manifest.json"
    manifest = _read_json_object(manifest_path, issues, "manifest.json")
    if manifest is not None:
        manifest_result = validate_manifest_schema(manifest)
        issues.extend(f"manifest.json: {issue}" for issue in manifest_result["issues"])
        run_id = manifest.get("run_id")
        if isinstance(run_id, str) and run_id.strip() and root_path.name != run_id:
            issues.append(f"manifest.json: field run_id {run_id!r} does not match run root name {root_path.name!r}")

    loaded: dict[str, Any] = {}
    if canonical_spec:
        for filename in ("run_config.json", "stage_outputs.json", "artifact_integrity.json"):
            key = f"00_spec/{filename}"
            loaded[key] = _read_json_file(root_path / key, issues, key)
    for stage_dir, filenames in REQUIRED_ARTIFACT_FILES.items():
        for filename in filenames:
            key = f"{stage_dir}/{filename}"
            path = root_path / stage_dir / filename
            loaded[key] = _read_json_file(path, issues, key)

    _validate_taxonomy_artifacts(
        graph=loaded.get("10_taxonomy/taxonomy_graph.json"),
        nodes=loaded.get("10_taxonomy/taxonomy_nodes.json"),
        issues=issues,
    )
    _validate_cross_stage_artifacts(
        taxonomy_nodes=loaded.get("10_taxonomy/taxonomy_nodes.json"),
        instantiations=loaded.get("20_local_diversification/instantiations.json"),
        local_rejections=loaded.get("20_local_diversification/rejections.json"),
        samples=loaded.get("30_complexification/samples.json"),
        semantic_failures=loaded.get("30_complexification/semantic_preservation_failures.json"),
        decisions=loaded.get("40_dual_critic_quality/critic_decisions.json"),
        critic_rejections=loaded.get("40_dual_critic_quality/rejections.json"),
        regenerations=loaded.get("40_dual_critic_quality/regenerations.json"),
        issues=issues,
    )
    if canonical_spec:
        _validate_artifact_integrity(
            root_path=root_path,
            manifest=manifest,
            integrity=loaded.get("00_spec/artifact_integrity.json"),
            issues=issues,
        )

    return _validation_result(kind="artifacts", issues=issues, assumptions=assumptions)


def _read_json_file(path: Path, issues: list[str], label: str) -> Any | None:
    if not path.exists():
        issues.append(f"missing required artifact file: {label}")
        return None
    if not path.is_file():
        issues.append(f"artifact path is not a file: {label}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(f"artifact file is not valid JSON: {label} ({exc.msg})")
    except OSError as exc:
        issues.append(f"artifact file cannot be read: {label} ({exc})")
    return None


def _read_json_object(path: Path, issues: list[str], label: str) -> dict[str, Any] | None:
    payload = _read_json_file(path, issues, label)
    if payload is None:
        return None
    if not isinstance(payload, dict):
        issues.append(f"artifact file must contain a JSON object: {label}")
        return None
    return payload


def _validate_artifact_integrity(
    *,
    root_path: Path,
    manifest: dict[str, Any] | None,
    integrity: Any,
    issues: list[str],
) -> None:
    if not isinstance(integrity, dict):
        return

    if integrity.get("schema_version") != INTEGRITY_SCHEMA_VERSION:
        issues.append("artifact_integrity.json: unsupported schema_version")
    if integrity.get("algorithm") != INTEGRITY_ALGORITHM:
        issues.append("artifact_integrity.json: algorithm must be sha256")
    if manifest is not None and integrity.get("run_id") != manifest.get("run_id"):
        issues.append("artifact_integrity.json: run_id does not match manifest.json")

    records = integrity.get("files")
    if not isinstance(records, dict):
        issues.append("artifact_integrity.json: files must be an object")
        return

    integrity_path = root_path / "00_spec" / "artifact_integrity.json"
    actual_paths = {
        path.relative_to(root_path).as_posix()
        for path in root_path.rglob("*")
        if path.is_file() and path != integrity_path
    }
    recorded_paths = {str(path) for path in records}
    for path in sorted(actual_paths - recorded_paths):
        issues.append(f"artifact_integrity.json: untracked file: {path}")
    for path in sorted(recorded_paths - actual_paths):
        issues.append(f"artifact_integrity.json: missing recorded file: {path}")

    for relative_path, record in records.items():
        if not isinstance(relative_path, str):
            issues.append("artifact_integrity.json: file paths must be strings")
            continue
        path_parts = Path(relative_path).parts
        if Path(relative_path).is_absolute() or ".." in path_parts:
            issues.append(f"artifact_integrity.json: invalid relative path: {relative_path}")
            continue
        if relative_path == integrity_path.relative_to(root_path).as_posix():
            issues.append("artifact_integrity.json: integrity file must not record itself")
            continue
        if not isinstance(record, dict):
            issues.append(f"artifact_integrity.json: record must be an object: {relative_path}")
            continue
        expected_hash = record.get("sha256")
        expected_size = record.get("size_bytes")
        if (
            not isinstance(expected_hash, str)
            or len(expected_hash) != 64
            or any(character not in "0123456789abcdef" for character in expected_hash.lower())
        ):
            issues.append(f"artifact_integrity.json: invalid sha256: {relative_path}")
            continue
        if (
            not isinstance(expected_size, int)
            or isinstance(expected_size, bool)
            or expected_size < 0
        ):
            issues.append(f"artifact_integrity.json: invalid size_bytes: {relative_path}")
            continue

        file_path = root_path / relative_path
        if not file_path.is_file():
            continue
        digest = sha256()
        size_bytes = 0
        try:
            with file_path.open("rb") as file_handle:
                for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size_bytes += len(chunk)
        except OSError as exc:
            issues.append(f"artifact_integrity.json: cannot read {relative_path}: {exc}")
            continue
        if size_bytes != expected_size:
            issues.append(f"artifact_integrity.json: size mismatch: {relative_path}")
        if digest.hexdigest() != expected_hash:
            issues.append(f"artifact_integrity.json: sha256 mismatch: {relative_path}")


def _string_id(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _duplicate_values(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _validate_taxonomy_artifacts(*, graph: Any, nodes: Any, issues: list[str]) -> None:
    if graph is None or nodes is None:
        return
    if not isinstance(graph, dict):
        issues.append("10_taxonomy/taxonomy_graph.json: must contain a JSON object")
        return
    if not isinstance(nodes, list) or not nodes:
        issues.append("10_taxonomy/taxonomy_nodes.json: must contain a non-empty JSON array")
        return

    root_id = _string_id(graph.get("root_taxonomy_node_id"))
    if root_id is None:
        issues.append("10_taxonomy/taxonomy_graph.json: root_taxonomy_node_id must be a non-empty string")
    if not _non_empty_string(graph.get("domain_namespace")):
        issues.append("10_taxonomy/taxonomy_graph.json: domain_namespace must be a non-empty string")
    if not isinstance(graph.get("generation_policy"), dict):
        issues.append("10_taxonomy/taxonomy_graph.json: generation_policy must be an object")

    node_by_id: dict[str, dict[str, Any]] = {}
    node_ids: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            issues.append(f"10_taxonomy/taxonomy_nodes.json[{index}]: must be an object")
            continue
        node_id = _string_id(node.get("taxonomy_node_id"))
        if node_id is None:
            issues.append(f"10_taxonomy/taxonomy_nodes.json[{index}]: taxonomy_node_id must be a non-empty string")
            continue
        node_ids.append(node_id)
        node_by_id[node_id] = node
        if not _non_empty_string(node.get("label")):
            issues.append(f"10_taxonomy/taxonomy_nodes.json[{index}]: label must be a non-empty string")
        if not isinstance(node.get("depth"), int) or isinstance(node.get("depth"), bool):
            issues.append(f"10_taxonomy/taxonomy_nodes.json[{index}]: depth must be an integer")

    for duplicate in _duplicate_values(node_ids):
        issues.append(f"10_taxonomy/taxonomy_nodes.json: duplicate taxonomy_node_id {duplicate!r}")
    if len(node_by_id) != len(node_ids):
        return

    if root_id is not None and root_id not in node_by_id:
        issues.append(f"10_taxonomy/taxonomy_graph.json: root_taxonomy_node_id {root_id!r} not found in nodes")

    roots = [node_id for node_id, node in node_by_id.items() if node.get("parent_taxonomy_node_id") is None]
    if root_id is not None and roots != [root_id]:
        issues.append(f"10_taxonomy/taxonomy_nodes.json: expected exactly root {root_id!r} with null parent")

    edges = graph.get("edges")
    if not isinstance(edges, list):
        issues.append("10_taxonomy/taxonomy_graph.json: edges must be a list")
        return

    edge_pairs: list[tuple[str, str]] = []
    child_edge_parents: dict[str, str] = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            issues.append(f"10_taxonomy/taxonomy_graph.json edges[{index}]: must be an object")
            continue
        parent_id = _string_id(edge.get("parent_taxonomy_node_id"))
        child_id = _string_id(edge.get("taxonomy_node_id"))
        if parent_id is None or child_id is None:
            issues.append(
                f"10_taxonomy/taxonomy_graph.json edges[{index}]: endpoints must be non-empty strings"
            )
            continue
        if parent_id == child_id:
            issues.append(f"10_taxonomy/taxonomy_graph.json edges[{index}]: self-cycle on {child_id!r}")
        if parent_id not in node_by_id or child_id not in node_by_id:
            issues.append(
                f"10_taxonomy/taxonomy_graph.json edges[{index}]: endpoints must reference existing taxonomy nodes"
            )
            continue
        edge_pairs.append((parent_id, child_id))
        previous_parent = child_edge_parents.get(child_id)
        if previous_parent is not None and previous_parent != parent_id:
            issues.append(f"10_taxonomy/taxonomy_graph.json: node {child_id!r} has multiple edge parents")
        child_edge_parents[child_id] = parent_id

    for duplicate in _duplicate_values([f"{p}\0{c}" for p, c in edge_pairs]):
        duplicate_parent, duplicate_child = duplicate.split("\0", 1)
        issues.append(
            "10_taxonomy/taxonomy_graph.json: duplicate edge "
            f"{duplicate_parent!r}->{duplicate_child!r}"
        )

    edge_set = set(edge_pairs)
    for node_id, node in node_by_id.items():
        parent = node.get("parent_taxonomy_node_id")
        if parent is None:
            if root_id is not None and node_id != root_id:
                issues.append(f"10_taxonomy/taxonomy_nodes.json: non-root node {node_id!r} has null parent")
            continue
        parent_id = _string_id(parent)
        if parent_id is None or parent_id not in node_by_id:
            issues.append(f"10_taxonomy/taxonomy_nodes.json: node {node_id!r} has unknown parent {parent!r}")
            continue
        if (parent_id, node_id) not in edge_set:
            issues.append(
                f"10_taxonomy/taxonomy_graph.json: missing edge for node {node_id!r} parent {parent_id!r}"
            )
        parent_depth = node_by_id[parent_id].get("depth")
        node_depth = node.get("depth")
        if isinstance(parent_depth, int) and isinstance(node_depth, int) and node_depth != parent_depth + 1:
            issues.append(f"10_taxonomy/taxonomy_nodes.json: node {node_id!r} depth must equal parent depth + 1")

    for parent_id, child_id in edge_set:
        child_parent = node_by_id[child_id].get("parent_taxonomy_node_id")
        if child_parent != parent_id:
            issues.append(
                f"10_taxonomy/taxonomy_graph.json: edge {parent_id!r}->{child_id!r} "
                f"does not match child parent {child_parent!r}"
            )

    _validate_taxonomy_acyclic_and_reachable(root_id=root_id, edge_pairs=edge_pairs, node_ids=set(node_by_id), issues=issues)


def _validate_taxonomy_acyclic_and_reachable(
    *,
    root_id: str | None,
    edge_pairs: list[tuple[str, str]],
    node_ids: set[str],
    issues: list[str],
) -> None:
    if root_id is None or root_id not in node_ids:
        return
    children: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for parent_id, child_id in edge_pairs:
        if parent_id in node_ids and child_id in node_ids:
            children[parent_id].append(child_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return False
        if node_id in visited:
            return True
        visiting.add(node_id)
        for child_id in children.get(node_id, []):
            if not visit(child_id):
                return False
        visiting.remove(node_id)
        visited.add(node_id)
        return True

    has_cycle = False
    for node_id in sorted(node_ids):
        if not visit(node_id):
            has_cycle = True
            break
    if has_cycle:
        issues.append("10_taxonomy/taxonomy_graph.json: taxonomy graph must be acyclic")
        return

    reachable: set[str] = set()
    stack = [root_id]
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        stack.extend(children.get(node_id, []))
    unreachable = sorted(node_ids - reachable)
    if unreachable:
        issues.append(f"10_taxonomy/taxonomy_graph.json: nodes not reachable from root: {unreachable}")


def _validate_cross_stage_artifacts(
    *,
    taxonomy_nodes: Any,
    instantiations: Any,
    local_rejections: Any,
    samples: Any,
    semantic_failures: Any,
    decisions: Any,
    critic_rejections: Any,
    regenerations: Any,
    issues: list[str],
) -> None:
    if not all(
        payload is not None
        for payload in (
            taxonomy_nodes,
            instantiations,
            local_rejections,
            samples,
            semantic_failures,
            decisions,
            critic_rejections,
            regenerations,
        )
    ):
        return

    named_lists = {
        "10_taxonomy/taxonomy_nodes.json": taxonomy_nodes,
        "20_local_diversification/instantiations.json": instantiations,
        "20_local_diversification/rejections.json": local_rejections,
        "30_complexification/samples.json": samples,
        "30_complexification/semantic_preservation_failures.json": semantic_failures,
        "40_dual_critic_quality/critic_decisions.json": decisions,
        "40_dual_critic_quality/rejections.json": critic_rejections,
        "40_dual_critic_quality/regenerations.json": regenerations,
    }
    for label, payload in named_lists.items():
        if not isinstance(payload, list):
            issues.append(f"{label}: must contain a JSON array")
            return

    taxonomy_ids = _ids_from_rows(taxonomy_nodes, "taxonomy_node_id", "10_taxonomy/taxonomy_nodes.json", issues)
    instantiation_ids = _ids_from_rows(
        instantiations,
        "instantiation_id",
        "20_local_diversification/instantiations.json",
        issues,
    )
    sample_ids = _ids_from_rows(samples, "instantiation_id", "30_complexification/samples.json", issues)
    decision_ids = _ids_from_rows(
        decisions,
        "instantiation_id",
        "40_dual_critic_quality/critic_decisions.json",
        issues,
    )

    instantiation_by_id = {
        str(row["instantiation_id"]): row
        for row in instantiations
        if isinstance(row, dict) and _string_id(row.get("instantiation_id")) is not None
    }
    sample_by_id = {
        str(row["instantiation_id"]): row
        for row in samples
        if isinstance(row, dict) and _string_id(row.get("instantiation_id")) is not None
    }
    decision_by_id = {
        str(row["instantiation_id"]): row
        for row in decisions
        if isinstance(row, dict) and _string_id(row.get("instantiation_id")) is not None
    }

    _require_equal_sets(
        instantiation_ids,
        sample_ids,
        left_label="20_local_diversification/instantiations.json",
        right_label="30_complexification/samples.json",
        id_label="instantiation_id",
        issues=issues,
    )
    _require_equal_sets(
        sample_ids,
        decision_ids,
        left_label="30_complexification/samples.json",
        right_label="40_dual_critic_quality/critic_decisions.json",
        id_label="instantiation_id",
        issues=issues,
    )

    for label, rows in (
        ("20_local_diversification/instantiations.json", instantiations),
        ("20_local_diversification/rejections.json", local_rejections),
        ("30_complexification/samples.json", samples),
        ("30_complexification/semantic_preservation_failures.json", semantic_failures),
        ("40_dual_critic_quality/critic_decisions.json", decisions),
        ("40_dual_critic_quality/rejections.json", critic_rejections),
        ("40_dual_critic_quality/regenerations.json", regenerations),
    ):
        _validate_lineage_references(label=label, rows=rows, taxonomy_ids=taxonomy_ids, issues=issues)

    for index, instantiation in enumerate(instantiations):
        if not isinstance(instantiation, dict):
            continue
        lineage = instantiation.get("lineage")
        if not isinstance(lineage, dict):
            issues.append(f"20_local_diversification/instantiations.json[{index}]: lineage must be an object")
            continue
        for field in ("taxonomy_node_id", "meta_prompt_id", "instantiation_id"):
            if str(lineage.get(field)) != str(instantiation.get(field)):
                issues.append(
                    f"20_local_diversification/instantiations.json[{index}]: lineage.{field} must match {field}"
                )

    for sample_id, sample in sample_by_id.items():
        instantiation = instantiation_by_id.get(sample_id)
        if instantiation is None:
            continue
        for field in ("taxonomy_node_id", "meta_prompt_id"):
            if str(sample.get(field)) != str(instantiation.get(field)):
                issues.append(
                    f"30_complexification/samples.json: sample {sample_id!r} {field} "
                    "does not match local instantiation"
                )

    rejected_decision_ids: set[str] = set()
    accepted_decision_ids: set[str] = set()
    regeneration_counts: Counter[str] = Counter()
    for index, row in enumerate(decisions):
        if not isinstance(row, dict):
            issues.append(f"40_dual_critic_quality/critic_decisions.json[{index}]: must be an object")
            continue
        decision_id = _string_id(row.get("instantiation_id"))
        if decision_id is None:
            continue
        sample = sample_by_id.get(decision_id)
        if sample is not None:
            for field in ("taxonomy_node_id", "meta_prompt_id"):
                if str(row.get(field)) != str(sample.get(field)):
                    issues.append(
                        f"40_dual_critic_quality/critic_decisions.json: decision {decision_id!r} {field} "
                        "does not match Stage 3 sample"
                    )
        status = row.get("quality_status")
        if status == "accepted":
            accepted_decision_ids.add(decision_id)
        elif status == "rejected":
            rejected_decision_ids.add(decision_id)
        else:
            issues.append(
                f"40_dual_critic_quality/critic_decisions.json: decision {decision_id!r} "
                "quality_status must be accepted or rejected"
            )
        if not isinstance(row.get("regeneration_count"), int) or isinstance(row.get("regeneration_count"), bool):
            issues.append(
                f"40_dual_critic_quality/critic_decisions.json: decision {decision_id!r} "
                "regeneration_count must be an integer"
            )

    critic_rejection_ids: set[str] = set()
    for index, rejection in enumerate(critic_rejections):
        if not isinstance(rejection, dict):
            issues.append(f"40_dual_critic_quality/rejections.json[{index}]: must be an object")
            continue
        rejection_id = _string_id(rejection.get("instantiation_id"))
        if rejection_id is None:
            issues.append(f"40_dual_critic_quality/rejections.json[{index}]: instantiation_id must be non-empty")
            continue
        critic_rejection_ids.add(rejection_id)
        if rejection_id in accepted_decision_ids:
            issues.append(
                f"40_dual_critic_quality/rejections.json: accepted decision {rejection_id!r} appears in rejection log"
            )

    if rejected_decision_ids != critic_rejection_ids:
        issues.append(
            "40_dual_critic_quality/rejections.json: rejected decision IDs must match rejection log IDs "
            f"(missing={sorted(rejected_decision_ids - critic_rejection_ids)}, "
            f"extra={sorted(critic_rejection_ids - rejected_decision_ids)})"
        )

    for index, regeneration in enumerate(regenerations):
        if not isinstance(regeneration, dict):
            issues.append(f"40_dual_critic_quality/regenerations.json[{index}]: must be an object")
            continue
        regeneration_id = _string_id(regeneration.get("instantiation_id"))
        if regeneration_id is None:
            issues.append(f"40_dual_critic_quality/regenerations.json[{index}]: instantiation_id must be non-empty")
            continue
        if regeneration_id not in decision_by_id:
            issues.append(
                f"40_dual_critic_quality/regenerations.json: unknown decision instantiation_id {regeneration_id!r}"
            )
        regeneration_counts[regeneration_id] += 1

    for decision_id, decision in decision_by_id.items():
        count = decision.get("regeneration_count")
        if isinstance(count, int) and not isinstance(count, bool) and regeneration_counts[decision_id] != count:
            issues.append(
                f"40_dual_critic_quality/regenerations.json: decision {decision_id!r} "
                f"regeneration_count {count} does not match {regeneration_counts[decision_id]} log entries"
            )


def _ids_from_rows(rows: list[Any], field: str, label: str, issues: list[str]) -> set[str]:
    ids: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append(f"{label}[{index}]: must be an object")
            continue
        row_id = _string_id(row.get(field))
        if row_id is None:
            issues.append(f"{label}[{index}]: {field} must be a non-empty string")
            continue
        ids.append(row_id)
    for duplicate in _duplicate_values(ids):
        issues.append(f"{label}: duplicate {field} {duplicate!r}")
    return set(ids)


def _validate_lineage_references(
    *,
    label: str,
    rows: list[Any],
    taxonomy_ids: set[str],
    issues: list[str],
) -> None:
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        taxonomy_node_id = _string_id(row.get("taxonomy_node_id"))
        if taxonomy_node_id is not None and taxonomy_node_id not in taxonomy_ids:
            issues.append(f"{label}[{index}]: taxonomy_node_id {taxonomy_node_id!r} not found in taxonomy nodes")
        if "meta_prompt_id" in row and not _non_empty_string(row.get("meta_prompt_id")):
            issues.append(f"{label}[{index}]: meta_prompt_id must be a non-empty string")


def _require_equal_sets(
    left: set[str],
    right: set[str],
    *,
    left_label: str,
    right_label: str,
    id_label: str,
    issues: list[str],
) -> None:
    if left == right:
        return
    issues.append(
        f"{left_label} and {right_label}: {id_label} sets must match "
        f"(left_only={sorted(left - right)}, right_only={sorted(right - left)})"
    )
