# ADR 0001: Research-first validation scope

## Status

Accepted

## Context

This repository starts from a blank implementation and needs to validate Simula-style mechanism design before production integration work. Attempting to build production infrastructure in parallel would increase risk and blur experimental signal.

## Decision

Prioritize a research-first phase focused on:

- proving control over coverage, complexity, and quality
- running baseline/ablation experiments
- establishing reproducibility and validation gates

Defer production-scale concerns (serving, orchestration hardening, long-term storage optimizations) until validation criteria are met.

## Alternatives considered

- Build research and production tracks concurrently.
- Build production scaffolding first and backfill experiments later.

## Consequences

- Faster learning cycle on the core mechanism.
- Lower early engineering overhead.
- Some rework likely when transitioning to production architecture.

## Follow-up triggers

Revisit this ADR when:

- hypotheses and threshold gates stabilize across repeated runs, or
- integration requirements become blocking for research velocity.
