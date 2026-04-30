# ADR 0003: Standardize evaluation protocol and initial thresholds

## Status

Accepted

## Context

Validation decisions are only meaningful if runs are comparable. Without a fixed protocol and explicit thresholds, outcomes are vulnerable to metric drift and subjective interpretation.

## Decision

Adopt a standardized evaluation protocol with:

- coverage metrics (node coverage, depth profile, balance)
- complexity calibration (Elo-style relative scoring)
- quality metrics (dual-critic acceptance/agreement/disagreement, regeneration burden)
- explicit initial threshold gates for pass/fail decisions

Initial thresholds are bootstrap defaults documented in `docs/evaluation-metrics.md` and can be revised only with evidence and ADR updates.

## Alternatives considered

- Use only downstream model performance as validation signal.
- Keep thresholds informal per run.

## Consequences

- Better comparability across runs and researchers.
- Easier auditing and promotion decisions.
- Requires discipline to version protocol updates and avoid silent drift.

## Follow-up triggers

Revisit this ADR when:

- protocol changes are required by domain-specific constraints, or
- repeated evidence shows threshold values are miscalibrated.
