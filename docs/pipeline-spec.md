# Pipeline Specification

## Purpose

This document specifies the end-to-end Simula-style generation pipeline for initial research validation. It defines stage boundaries, contracts, and control knobs so experiments are comparable and repeatable.

## Design principles

- Treat dataset generation as mechanism design at dataset level.
- Keep coverage, complexity, and quality as independent control axes.
- Use explicit contracts between stages to enable ablations and diagnostics.

## Stage 0: Domain and run specification

### Inputs

- Domain objective and target task format.
- Run config (model settings, seeds, budgets, thresholds).
- Taxonomy depth and branching policies.

### Outputs

- Frozen run spec and run identifier.
- Validation plan metadata used by downstream stages.

## Stage 1: Global diversification (taxonomy construction)

### Objective

Construct a deep, hierarchical conceptual map of the target domain to control global coverage.

### Procedure

1. Propose candidate subcategories recursively.
2. Critique and filter for relevance, distinctness, and non-redundancy.
3. Merge equivalent or near-equivalent branches.
4. Continue expansion until depth/breadth constraints are met.

### Inputs

- Domain spec
- taxonomy expansion policy
- critic policy for merge/filter

### Outputs

- Taxonomy graph with node IDs and parent-child edges.
- Node metadata (depth, branch source, confidence, notes).

### Contracts

- Every node has a stable `taxonomy_node_id`.
- No orphan nodes.
- Taxonomy remains acyclic.

## Stage 2: Local diversification (meta-prompts and instantiations)

### Objective

Generate diverse samples within each concept so local mode collapse is reduced.

### Procedure

1. Derive meta-prompts from selected taxonomy nodes.
2. Generate N distinct instantiations per meta-prompt.
3. Enforce local diversity constraints before acceptance.

### Inputs

- Taxonomy graph and selected node set
- local diversification policy (`n_instantiations`, variation constraints)

### Outputs

- Candidate sample set with traceability to taxonomy and meta-prompt.

### Contracts

- Every sample links back to `taxonomy_node_id` and `meta_prompt_id`.
- Instantiations inside the same local set must pass diversity checks.

## Stage 3: Complexification

### Objective

Increase difficulty for a controlled fraction of samples without changing semantic target coverage.

### Procedure

1. Select sample subset by policy (`complexify_fraction`).
2. Apply complexification transforms (multi-step reasoning, ambiguity management, distractor handling).
3. Verify semantic equivalence to source intent.

### Inputs

- Candidate sample set
- complexification policy and target distribution

### Outputs

- Mixed-difficulty candidate set with complexity tags.

### Contracts

- `complexity_source` captured for each transformed sample.
- Coverage assignment (`taxonomy_node_id`) remains unchanged.

## Stage 4: Dual-critic quality verification

### Objective

Use independent critics to reduce sycophancy and improve label correctness.

### Procedure

1. Critic A evaluates correctness and constraints.
2. Critic B independently evaluates correctness and constraints.
3. Resolve outcomes:
   - both accept: sample passes
   - both reject: sample fails and can be regenerated
   - disagreement: send to tie-break policy or regenerate

### Inputs

- Candidate sample set after complexification
- critic models and adjudication policy

### Outputs

- Curated dataset
- Rejection log and disagreement log

### Contracts

- Every accepted sample has critic decisions recorded.
- Every rejected sample has machine-readable rejection reasons.

## Stage 5: Evaluation handoff

### Objective

Prepare artifacts for metric computation and validation gate decisions.

### Outputs

- Evaluation-ready dataset split(s)
- Run manifest with lineage from all prior stages
- Stage-level summaries (coverage, quality pass rate, complexity distribution)

## Canonical data model (minimum fields)

- `run_id`
- `sample_id`
- `taxonomy_node_id`
- `meta_prompt_id`
- `instantiation_id`
- `is_complexified`
- `complexity_source`
- `critic_a_decision`
- `critic_b_decision`
- `quality_status`
- `regeneration_count`
- `seed`
- `model_ids`
- `timestamp_utc`

## Machine-readable stage contracts (Stages 1–4)

Runtime validation of handoff dicts is implemented in `src/simula_research/stage_contracts.py` (`validate_taxonomy_output`, `validate_local_diversification_output`, `validate_complexification_output`, `validate_adjudication_output`, and `validate_stage_handoffs`). The default `run_pipeline` path invokes `validate_stage_handoffs` after adjudication so lineage and required-field regressions fail before artifacts are written. This layer does not alter evaluation metric definitions or threshold gates.

Filesystem persistence for Stages 1–4 uses `src/simula_research/run_artifact_store.py`: `RunArtifactStore` (protocol) and `FileSystemRunArtifactStore` (default layout under `artifacts/runs/<run_id>/`). `run_pipeline(..., artifact_store_factory=...)` accepts a factory `Callable[[Path], RunArtifactStore]` keyed to the resolved run root so tests or integrations can swap storage without changing stage logic.

Dual-critic adjudication accepts an optional `critic_verdict` callable (`CriticVerdictFn` in `src/simula_research/provider_protocols.py`); the default remains the deterministic hash-based stub used for research-phase replay.

Stages 1–3 accept optional provider callables (`TaxonomyProviderFn`, `LocalDiversificationProviderFn`, `ComplexificationProviderFn`) on `run_pipeline`; defaults (`default_taxonomy_provider`, `default_local_diversification_provider`, `default_complexification_provider`) delegate to the in-repo deterministic implementations with no behavior change when hooks are omitted (Issue #60).

## Configuration knobs by control axis

### Coverage

- taxonomy depth limits
- branching factor targets
- node sampling strategy

### Complexity

- complexify fraction
- transformation templates
- target complexity distribution

### Quality

- critic thresholds
- disagreement policy
- regeneration budget

## Failure modes and guardrails

- **Taxonomy collapse**: many nodes map to near-duplicates.  
  Guardrail: similarity-based merge audits and max overlap thresholds.
- **Local mode collapse**: instantiations too similar within a node.  
  Guardrail: local diversity checks before critic stage.
- **Over-complexification drift**: complexity increases but task semantics shift.  
  Guardrail: semantic-equivalence checks and selective rollback.
- **Critic deadlock**: high disagreement rates.  
  Guardrail: disagreement budget with fallback adjudication policy.
