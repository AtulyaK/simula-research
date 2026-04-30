from __future__ import annotations


def make_taxonomy_node(
    node_slug: str,
    *,
    label: str | None = None,
    parent_node_id: str | None = None,
) -> dict[str, str]:
    taxonomy_node_id = f"tax-{node_slug}"
    node = {
        "taxonomy_node_id": taxonomy_node_id,
        "node_slug": node_slug,
        "label": label or node_slug.replace("-", " ").title(),
    }
    if parent_node_id is not None:
        node["parent_taxonomy_node_id"] = parent_node_id
    return node


def make_meta_prompt(
    meta_prompt_id: str,
    *,
    taxonomy_node_id: str,
    prompt_text: str | None = None,
) -> dict[str, str]:
    return {
        "meta_prompt_id": meta_prompt_id,
        "taxonomy_node_id": taxonomy_node_id,
        "prompt_text": prompt_text or f"Draft scenario for {taxonomy_node_id}",
    }


def make_instantiation(
    instantiation_id: str,
    *,
    meta_prompt_id: str,
    taxonomy_node_id: str | None = None,
    payload: str | None = None,
) -> dict[str, object]:
    lineage_taxonomy_node_id = taxonomy_node_id or _taxonomy_node_id_from_meta_prompt(meta_prompt_id)
    return {
        "instantiation_id": instantiation_id,
        "meta_prompt_id": meta_prompt_id,
        "payload": payload or f"Sample output for {meta_prompt_id}",
        "lineage": {
            "meta_prompt_id": meta_prompt_id,
            "taxonomy_node_id": lineage_taxonomy_node_id,
            "instantiation_id": instantiation_id,
        },
    }


def _taxonomy_node_id_from_meta_prompt(meta_prompt_id: str) -> str:
    if "-" not in meta_prompt_id:
        return "tax-unknown"
    _, suffix = meta_prompt_id.split("-", 1)
    return f"tax-{suffix}"
