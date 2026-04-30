from __future__ import annotations


def assert_meta_prompt_traceability(
    meta_prompt: dict[str, object],
    *,
    expected_taxonomy_node_id: str,
) -> None:
    actual_taxonomy_node_id = meta_prompt.get("taxonomy_node_id")
    if actual_taxonomy_node_id != expected_taxonomy_node_id:
        raise AssertionError(
            "meta_prompt taxonomy_node_id mismatch: "
            f"expected={expected_taxonomy_node_id!r} actual={actual_taxonomy_node_id!r}"
        )


def assert_instantiation_traceability(
    instantiation: dict[str, object],
    *,
    expected_meta_prompt_id: str,
    expected_taxonomy_node_id: str,
) -> None:
    actual_meta_prompt_id = instantiation.get("meta_prompt_id")
    if actual_meta_prompt_id != expected_meta_prompt_id:
        raise AssertionError(
            "instantiation meta_prompt_id mismatch: "
            f"expected={expected_meta_prompt_id!r} actual={actual_meta_prompt_id!r}"
        )

    lineage = instantiation.get("lineage")
    if not isinstance(lineage, dict):
        raise AssertionError("instantiation lineage must be a mapping")

    lineage_meta_prompt_id = lineage.get("meta_prompt_id")
    if lineage_meta_prompt_id != expected_meta_prompt_id:
        raise AssertionError(
            "instantiation lineage meta_prompt_id mismatch: "
            f"expected={expected_meta_prompt_id!r} actual={lineage_meta_prompt_id!r}"
        )

    lineage_taxonomy_node_id = lineage.get("taxonomy_node_id")
    if lineage_taxonomy_node_id != expected_taxonomy_node_id:
        raise AssertionError(
            "instantiation lineage taxonomy_node_id mismatch: "
            f"expected={expected_taxonomy_node_id!r} actual={lineage_taxonomy_node_id!r}"
        )
