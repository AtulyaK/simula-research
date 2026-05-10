from __future__ import annotations

from typing import Any, Literal, NotRequired, Required, TypedDict

# Stage handoff contracts aligned with docs/pipeline-spec.md (Stages 1–4).
# Validators raise ValueError on violation so refactors fail fast at boundaries.
#
# TypedDict shapes below are for static checking and API documentation; validators
# intentionally accept dict[str, Any] so JSON-like payloads stay compatible.


class Stage1TaxonomyNode(TypedDict):
    taxonomy_node_id: str
    parent_taxonomy_node_id: str | None
    label: str
    depth: int


class Stage1TaxonomyEdge(TypedDict):
    parent_taxonomy_node_id: str
    taxonomy_node_id: str


class Stage1TaxonomyOutput(TypedDict):
    domain_namespace: str
    root_taxonomy_node_id: str
    nodes: list[Stage1TaxonomyNode]
    edges: list[Stage1TaxonomyEdge]
    generation_policy: dict[str, Any]


class Stage2InstantiationLineage(TypedDict):
    taxonomy_node_id: str
    meta_prompt_id: str
    instantiation_id: str


class Stage2Instantiation(TypedDict):
    instantiation_id: str
    taxonomy_node_id: str
    meta_prompt_id: str
    text: str
    lineage: Stage2InstantiationLineage


class Stage2Rejection(TypedDict):
    reason: str
    taxonomy_node_id: str
    meta_prompt_id: str
    candidate_instantiation_id: NotRequired[str]


class Stage2AntiCollapseChecks(TypedDict):
    executed: bool
    check_name: str
    threshold: float


class Stage2LocalDiversificationOutput(TypedDict):
    instantiations: list[Stage2Instantiation]
    rejections: list[Stage2Rejection]
    anti_collapse_checks: Stage2AntiCollapseChecks


class Stage3Sample(TypedDict, total=False):
    instantiation_id: Required[str]
    taxonomy_node_id: Required[str]
    meta_prompt_id: Required[str]
    text: Required[str]
    is_complexified: Required[bool]
    complexity_source: Required[str]
    source_intent: NotRequired[str]


class Stage3SemanticPreservationFailure(TypedDict, total=False):
    instantiation_id: Required[str]
    taxonomy_node_id: Required[str]
    meta_prompt_id: Required[str]
    reason: Required[str]
    source_intent: NotRequired[str]
    candidate_text: NotRequired[str]
    semantic_overlap_ratio: NotRequired[float]


class Stage3ComplexificationOutput(TypedDict):
    samples: list[Stage3Sample]
    complexification_policy: dict[str, Any]
    semantic_preservation_failures: list[Stage3SemanticPreservationFailure]


CriticVerdictLiteral = Literal["accept", "reject"]
AdjudicationPolicyLiteral = Literal["reject", "accept", "regenerate"]


class Stage4DecisionRow(TypedDict):
    instantiation_id: str
    taxonomy_node_id: str
    meta_prompt_id: str
    critic_a_decision: CriticVerdictLiteral
    critic_b_decision: CriticVerdictLiteral
    disagreement: bool
    adjudication_policy: AdjudicationPolicyLiteral
    quality_status: str
    final_reason: str
    regeneration_count: int
    review_status: str


class Stage4AcceptedSample(TypedDict, total=False):
    instantiation_id: Required[str]
    taxonomy_node_id: Required[str]
    meta_prompt_id: Required[str]
    critic_a_decision: Required[CriticVerdictLiteral]
    critic_b_decision: Required[CriticVerdictLiteral]


class Stage4RejectionLogEntry(TypedDict):
    instantiation_id: str
    taxonomy_node_id: str
    meta_prompt_id: str
    reason: str
    critic_a_decision: CriticVerdictLiteral
    critic_b_decision: CriticVerdictLiteral
    regeneration_count: int


class Stage4RegenerationLogEntry(TypedDict):
    instantiation_id: str
    taxonomy_node_id: str
    meta_prompt_id: str
    regeneration_index: int
    regenerated_text: str
    critic_a_decision: CriticVerdictLiteral
    critic_b_decision: CriticVerdictLiteral


class Stage4AdjudicationOutput(TypedDict):
    decisions: list[Stage4DecisionRow]
    accepted_samples: list[Stage4AcceptedSample]
    rejection_log: list[Stage4RejectionLogEntry]
    regeneration_log: list[Stage4RegenerationLogEntry]
    policy: dict[str, Any]


def _require_keys(obj: dict[str, Any], keys: tuple[str, ...], *, context: str) -> None:
    missing = [key for key in keys if key not in obj]
    if missing:
        raise ValueError(f"{context}: missing keys {missing}")


def _require_non_empty_str(value: Any, *, field: str, context: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: field {field!r} must be a non-empty string")


def validate_taxonomy_output(taxonomy: dict[str, Any]) -> None:
    """Validate Stage 1 (global diversification) output shape and lineage fields."""
    ctx = "taxonomy"
    _require_keys(
        taxonomy,
        ("domain_namespace", "root_taxonomy_node_id", "nodes", "edges", "generation_policy"),
        context=ctx,
    )

    _require_non_empty_str(taxonomy["domain_namespace"], field="domain_namespace", context=ctx)
    _require_non_empty_str(taxonomy["root_taxonomy_node_id"], field="root_taxonomy_node_id", context=ctx)

    if not isinstance(taxonomy["nodes"], list) or not taxonomy["nodes"]:
        raise ValueError(f"{ctx}: nodes must be a non-empty list")

    if not isinstance(taxonomy["edges"], list):
        raise ValueError(f"{ctx}: edges must be a list")

    if not isinstance(taxonomy["generation_policy"], dict):
        raise ValueError(f"{ctx}: generation_policy must be an object")

    node_fields = ("taxonomy_node_id", "parent_taxonomy_node_id", "label", "depth")
    node_ids: set[str] = set()
    for index, node in enumerate(taxonomy["nodes"]):
        nctx = f"{ctx} nodes[{index}]"
        if not isinstance(node, dict):
            raise ValueError(f"{nctx}: must be an object")
        _require_keys(node, node_fields, context=nctx)
        node_id = str(node["taxonomy_node_id"])
        _require_non_empty_str(node_id, field="taxonomy_node_id", context=nctx)
        if node_id in node_ids:
            raise ValueError(f"{nctx}: duplicate taxonomy_node_id {node_id!r}")
        node_ids.add(node_id)
        if not isinstance(node["depth"], int):
            raise ValueError(f"{nctx}: depth must be an integer")

    root_id = str(taxonomy["root_taxonomy_node_id"])
    if root_id not in node_ids:
        raise ValueError(f"{ctx}: root_taxonomy_node_id {root_id!r} not found in nodes")

    roots = [n for n in taxonomy["nodes"] if n.get("parent_taxonomy_node_id") is None]
    if len(roots) != 1:
        raise ValueError(f"{ctx}: expected exactly one root node (parent_taxonomy_node_id is null), got {len(roots)}")

    for index, node in enumerate(taxonomy["nodes"]):
        parent = node.get("parent_taxonomy_node_id")
        if parent is None:
            continue
        parent_id = str(parent)
        if parent_id not in node_ids:
            raise ValueError(f"{ctx} nodes[{index}]: orphan parent_taxonomy_node_id {parent_id!r}")

    for index, edge in enumerate(taxonomy["edges"]):
        ectx = f"{ctx} edges[{index}]"
        if not isinstance(edge, dict):
            raise ValueError(f"{ectx}: must be an object")
        _require_keys(edge, ("parent_taxonomy_node_id", "taxonomy_node_id"), context=ectx)
        child = str(edge["taxonomy_node_id"])
        parent = str(edge["parent_taxonomy_node_id"])
        if child not in node_ids or parent not in node_ids:
            raise ValueError(f"{ectx}: edge endpoints must reference existing taxonomy_node_id values")


def validate_local_diversification_output(payload: dict[str, Any]) -> None:
    """Validate Stage 2 (local diversification) output."""
    ctx = "local_diversification"
    _require_keys(payload, ("instantiations", "rejections", "anti_collapse_checks"), context=ctx)

    if not isinstance(payload["instantiations"], list):
        raise ValueError(f"{ctx}: instantiations must be a list")
    if not isinstance(payload["rejections"], list):
        raise ValueError(f"{ctx}: rejections must be a list")

    checks = payload["anti_collapse_checks"]
    if not isinstance(checks, dict):
        raise ValueError(f"{ctx}: anti_collapse_checks must be an object")
    _require_keys(checks, ("executed", "check_name", "threshold"), context=f"{ctx}.anti_collapse_checks")

    inst_fields = ("instantiation_id", "taxonomy_node_id", "meta_prompt_id", "text", "lineage")
    for index, inst in enumerate(payload["instantiations"]):
        ictx = f"{ctx} instantiations[{index}]"
        if not isinstance(inst, dict):
            raise ValueError(f"{ictx}: must be an object")
        _require_keys(inst, inst_fields, context=ictx)
        for field in ("instantiation_id", "taxonomy_node_id", "meta_prompt_id"):
            _require_non_empty_str(inst[field], field=field, context=ictx)
        lineage = inst["lineage"]
        if not isinstance(lineage, dict):
            raise ValueError(f"{ictx}.lineage: must be an object")
        _require_keys(lineage, ("taxonomy_node_id", "meta_prompt_id", "instantiation_id"), context=f"{ictx}.lineage")
        if str(lineage["taxonomy_node_id"]) != str(inst["taxonomy_node_id"]):
            raise ValueError(f"{ictx}: lineage.taxonomy_node_id must match taxonomy_node_id")
        if str(lineage["meta_prompt_id"]) != str(inst["meta_prompt_id"]):
            raise ValueError(f"{ictx}: lineage.meta_prompt_id must match meta_prompt_id")
        if str(lineage["instantiation_id"]) != str(inst["instantiation_id"]):
            raise ValueError(f"{ictx}: lineage.instantiation_id must match instantiation_id")

    for index, rejection in enumerate(payload["rejections"]):
        rctx = f"{ctx} rejections[{index}]"
        if not isinstance(rejection, dict):
            raise ValueError(f"{rctx}: must be an object")
        _require_keys(rejection, ("reason", "taxonomy_node_id", "meta_prompt_id"), context=rctx)


def validate_complexification_output(payload: dict[str, Any]) -> None:
    """Validate Stage 3 (complexification) output."""
    ctx = "complexification"
    _require_keys(payload, ("samples", "complexification_policy", "semantic_preservation_failures"), context=ctx)

    if not isinstance(payload["samples"], list):
        raise ValueError(f"{ctx}: samples must be a list")
    if not isinstance(payload["complexification_policy"], dict):
        raise ValueError(f"{ctx}: complexification_policy must be an object")
    if not isinstance(payload["semantic_preservation_failures"], list):
        raise ValueError(f"{ctx}: semantic_preservation_failures must be a list")

    sample_fields = (
        "instantiation_id",
        "taxonomy_node_id",
        "meta_prompt_id",
        "text",
        "is_complexified",
        "complexity_source",
    )
    for index, sample in enumerate(payload["samples"]):
        sctx = f"{ctx} samples[{index}]"
        if not isinstance(sample, dict):
            raise ValueError(f"{sctx}: must be an object")
        _require_keys(sample, sample_fields, context=sctx)
        for field in ("instantiation_id", "taxonomy_node_id", "meta_prompt_id", "complexity_source"):
            _require_non_empty_str(sample[field], field=field, context=sctx)
        if not isinstance(sample["is_complexified"], bool):
            raise ValueError(f"{sctx}: is_complexified must be a boolean")

    for index, failure in enumerate(payload["semantic_preservation_failures"]):
        fctx = f"{ctx} semantic_preservation_failures[{index}]"
        if not isinstance(failure, dict):
            raise ValueError(f"{fctx}: must be an object")
        _require_keys(
            failure,
            (
                "instantiation_id",
                "taxonomy_node_id",
                "meta_prompt_id",
                "reason",
            ),
            context=fctx,
        )


def validate_adjudication_output(payload: dict[str, Any]) -> None:
    """Validate Stage 4 (dual-critic adjudication) output."""
    ctx = "adjudication"
    _require_keys(
        payload,
        ("decisions", "accepted_samples", "rejection_log", "regeneration_log", "policy"),
        context=ctx,
    )

    for key in ("decisions", "accepted_samples", "rejection_log", "regeneration_log"):
        if not isinstance(payload[key], list):
            raise ValueError(f"{ctx}: {key} must be a list")
    if not isinstance(payload["policy"], dict):
        raise ValueError(f"{ctx}: policy must be an object")

    decision_fields = (
        "instantiation_id",
        "taxonomy_node_id",
        "meta_prompt_id",
        "critic_a_decision",
        "critic_b_decision",
        "disagreement",
        "adjudication_policy",
        "quality_status",
        "final_reason",
        "regeneration_count",
        "review_status",
    )
    for index, row in enumerate(payload["decisions"]):
        dctx = f"{ctx} decisions[{index}]"
        if not isinstance(row, dict):
            raise ValueError(f"{dctx}: must be an object")
        _require_keys(row, decision_fields, context=dctx)
        for field in ("instantiation_id", "taxonomy_node_id", "meta_prompt_id", "quality_status", "final_reason"):
            _require_non_empty_str(row[field], field=field, context=dctx)
        for critic_field in ("critic_a_decision", "critic_b_decision"):
            val = row[critic_field]
            if val not in ("accept", "reject"):
                raise ValueError(f"{dctx}: {critic_field} must be 'accept' or 'reject'")
        if not isinstance(row["regeneration_count"], int) or row["regeneration_count"] < 0:
            raise ValueError(f"{dctx}: regeneration_count must be a non-negative integer")
        if not isinstance(row["disagreement"], bool):
            raise ValueError(f"{dctx}: disagreement must be a boolean")
        pol = row["adjudication_policy"]
        if pol not in ("reject", "accept", "regenerate"):
            raise ValueError(f"{dctx}: adjudication_policy must be reject|accept|regenerate")
        _require_non_empty_str(row["review_status"], field="review_status", context=dctx)

    for index, sample in enumerate(payload["accepted_samples"]):
        actx = f"{ctx} accepted_samples[{index}]"
        if not isinstance(sample, dict):
            raise ValueError(f"{actx}: must be an object")
        _require_keys(
            sample,
            ("instantiation_id", "taxonomy_node_id", "meta_prompt_id", "critic_a_decision", "critic_b_decision"),
            context=actx,
        )

    for index, rejection in enumerate(payload["rejection_log"]):
        rctx = f"{ctx} rejection_log[{index}]"
        if not isinstance(rejection, dict):
            raise ValueError(f"{rctx}: must be an object")
        _require_keys(
            rejection,
            (
                "instantiation_id",
                "taxonomy_node_id",
                "meta_prompt_id",
                "reason",
                "critic_a_decision",
                "critic_b_decision",
                "regeneration_count",
            ),
            context=rctx,
        )


def validate_stage_handoffs(
    *,
    taxonomy: dict[str, Any],
    local_diversification: dict[str, Any],
    complexification: dict[str, Any],
    adjudication: dict[str, Any],
) -> None:
    """Validate full Stage 1→4 handoff chain (docs/pipeline-spec.md)."""
    validate_taxonomy_output(taxonomy)
    validate_local_diversification_output(local_diversification)
    validate_complexification_output(complexification)
    validate_adjudication_output(adjudication)
