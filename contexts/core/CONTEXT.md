# Core context

## Purpose

Define the Simula-style synthetic data generation mechanism as a research reproduction:

- global diversification via hierarchical taxonomy construction
- local diversification via meta-prompt instantiation
- complexity control as an orthogonal tuning axis
- quality control through dual-critic validation

## Core terms

- Taxonomy node: a semantic category in the recursive domain tree
- Meta-prompt: scenario template generated from taxonomy nodes
- Instantiation: a concrete sample produced from a meta-prompt
- Complexification: controlled rewriting that increases task difficulty
- Dual-critic check: independent verification pass to validate labels and outputs

## Invariants

- Coverage, complexity, and quality are tracked as independent axes.
- Pipeline outputs are reproducible from run config and seed state.
- Regeneration paths are explicit when quality checks fail.
- Stage boundaries expose injectable seams (artifact store, critics; Stages 1–3 protocols per ADR **0004** / Issue **#60**) with **bit-identical** deterministic defaults unless comparability is formally waived.
