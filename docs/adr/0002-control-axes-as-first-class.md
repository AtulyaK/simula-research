# ADR 0002: Treat control axes as first-class architecture

## Status

Accepted

## Context

Simula-style generation quality depends on independent control of three properties:

- coverage (taxonomy and sampling space)
- complexity (difficulty distribution)
- quality (label and output correctness)

If these concerns are entangled, ablation results become hard to interpret and iteration slows.

## Decision

Architect the validation pipeline around explicit stage boundaries and contracts that preserve axis independence:

1. global diversification for coverage
2. local diversification for within-node variation
3. complexification for difficulty shaping
4. dual-critic checks for quality control
5. evaluation layer that reports per-axis outcomes

## Alternatives considered

- Single monolithic generation step with implicit controls.
- Optimize sample-level prompts without dataset-level control decomposition.

## Consequences

- Clearer diagnostics and stronger ablation interpretability.
- Slightly higher coordination overhead across stages.
- Better path to future integration because contracts already exist.

## Follow-up triggers

Revisit this ADR when:

- evidence shows strong cross-axis coupling that cannot be managed by current contracts, or
- a simpler architecture demonstrates equivalent validation fidelity.
