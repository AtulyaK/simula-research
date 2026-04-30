# Evaluation and Metrics Specification

## Purpose

Define how validation runs are scored and compared for Simula-style dataset generation. Metrics are organized by the three control axes:

- coverage
- complexity
- quality

## Evaluation object

A validation run is evaluated as:

- a curated dataset artifact
- full lineage metadata
- stage-level logs
- baseline or ablation tag

Comparisons are only valid when run protocol and domain objective match.

## Coverage metrics

### 1) Node coverage ratio

Measures how much of the designed taxonomy is represented.

`node_coverage_ratio = covered_nodes / eligible_nodes`

- `eligible_nodes`: nodes selected by run policy.
- `covered_nodes`: eligible nodes with at least one accepted sample.

### 2) Depth coverage profile

Coverage distribution by taxonomy depth.

`depth_coverage(d) = covered_nodes_at_depth_d / eligible_nodes_at_depth_d`

Use this to detect shallow-only sampling behavior.

### 3) Coverage balance score

Detects concentration in a small subset of taxonomy branches.

One practical form:

`coverage_balance = 1 - gini(samples_per_node)`

Higher is better (more evenly distributed).

## Complexity metrics

### 1) Calibrated complexity score (Elo-style)

Assign relative difficulty to samples using pairwise or batch comparison judgments.

Procedure:

1. Build comparison pairs (or mini-batches) under a fixed judging protocol.
2. Collect winner/loser outcomes (harder vs easier).
3. Fit Elo-style ratings with fixed K-factor and initialization.
4. Convert to normalized complexity scores for reporting.

Suggested defaults for reproducible first phase:

- initial rating: 1000
- K-factor: 32
- minimum comparisons per sample: 5

### 2) Complexity shift vs baseline

`complexity_shift = median_complexity(run) - median_complexity(baseline)`

Use with stratification by taxonomy depth to ensure shifts are not due only to coverage drift.

### 3) Complexification precision

How often complexified samples are actually scored harder than their non-complexified analogs.

`complexification_precision = successful_complexification_pairs / total_evaluated_pairs`

## Quality metrics

### 1) Dual-critic acceptance rate

`acceptance_rate = accepted_samples / reviewed_samples`

### 2) Critic agreement rate

`critic_agreement = agreements / total_reviews`

Where agreement means both critics accept or both reject.

### 3) Disagreement burden

`disagreement_rate = disagreements / total_reviews`

Track by taxonomy segment to diagnose problematic regions.

### 4) Regeneration burden

`regen_burden = regenerated_samples / accepted_samples`

High values indicate quality gate inefficiency.

## Composite decision signals

Primary gate is not a single scalar metric. Use a gate table:

- Coverage: `node_coverage_ratio`, `depth_coverage_profile`, `coverage_balance`
- Complexity: calibrated score distribution and `complexity_shift`
- Quality: `acceptance_rate`, `critic_agreement`, `regen_burden`

Run passes only if all required thresholds are met.

## Minimum threshold template (initial research defaults)

- `node_coverage_ratio >= 0.80`
- no depth level below `0.60` coverage
- `complexification_precision >= 0.70`
- `critic_agreement >= 0.75`
- `acceptance_rate >= 0.50`
- `regen_burden <= 1.00`

These are bootstrap thresholds and should be revised via ADR if domain behavior demands it.

## Reporting format

Each run report should include:

1. Run identity:
   - run_id, date, branch, commit hash, seed
2. Protocol:
   - domain objective, taxonomy policy, complexification policy, critic policy
3. Coverage table:
   - eligible vs covered nodes, depth profile, balance score
4. Complexity table:
   - score percentiles, shift vs baseline, complexification precision
5. Quality table:
   - acceptance, agreement, disagreement, regeneration
6. Gate decision:
   - pass/fail per threshold
7. Notes:
   - anomalies, known confounders, next experiment actions

## Comparability rules

Two runs are comparable only if all are fixed:

- domain objective
- taxonomy eligibility policy
- judgment protocol for complexity scoring
- critic configuration and adjudication policy
- artifact schema version

Any protocol change must be called out in the run report.
