# Evaluation context

## Purpose

Define how synthetic datasets are evaluated in the research reproduction workflow.

## Core evaluation dimensions

- Taxonomic coverage: breadth and depth realized against the designed taxonomy
- Local diversity: variation among instantiations within the same concept
- Calibrated complexity: relative difficulty estimation using pairwise or batch comparison
- Label quality: pass/fail behavior under dual-critic verification

## Reproducibility rules

- Every run stores config, seed, and model settings.
- Metrics are computed from persisted artifacts, not transient logs.
- Baseline and variant runs are comparable by fixed evaluation protocol.
