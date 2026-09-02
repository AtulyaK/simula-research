# Paper Replication Matrix

## Purpose

This document separates paper claims from the repository's current evidence. A
claim is **replicated** only when the implementation and persisted artifacts
match the paper's mechanism and evaluation protocol. A deterministic stand-in
is marked **approximated**, not silently counted as a paper result.

Primary reference: [`research_paper.pdf`](./research_paper.pdf), titled
"Reasoning-Driven Synthetic Data Generation and Evaluation" (arXiv
2603.29791v1). Section and appendix references below use that paper.

## Claim-to-evidence matrix

| Paper claim or protocol | Status | Repository evidence or gap |
| --- | --- | --- |
| Simula treats coverage, complexity, and quality as independent axes. | Replicated | ADR 0002, explicit Stage 1-4 boundaries, and per-axis reports in `src/simula_research/evaluation_metrics.py`. |
| Taxonomies expose factors of variation and provide actionable coverage control (Sec. 2.1). | Approximated | `taxonomy.py` persists a stable hierarchical taxonomy and coverage reports consume its eligible nodes. Factor discovery and human/LLM acceptance are not implemented. |
| Taxonomy expansion alternates best-of-N proposals, critic refinement, and optional per-level planning (Sec. 2.1, App. B.4). | Missing | Current taxonomy generation is deterministic and handcrafted; no proposal pool, critic refinement, or planning provider is wired. |
| Agentic synthesis samples compatible node mixes, generates multiple scenarios, complexifies a fraction, then performs generation and critic refinement (Sec. 2.2, App. C). | Approximated | Stages and lineage exist, but local diversification and complexification are deterministic text transforms and Stage 4 does not regenerate through an LLM refinement loop. |
| Paper system versions compare Baseline, Local, Global, Local + Global, and Full System (Table 1). | Approximated | The executable matrix now includes B0 plus A1-A5. B0 is the full reference; A1/A2 approximate removal of global/local controls; A3/A4/A5 are validation ablations and are not a one-to-one reproduction of Table 1. |
| Paper datasets include CTI-MCQ, CTI-RCM, LEXam, GSM8k, and selected Global MMLU subsets (Sec. 3.2). | Approximated | A local JSONL adapter and fixed task schema now support GSM8k records. Dataset downloads, licenses, the other four datasets, and benchmark-specific schemas remain incomplete. |
| Generated data is deduplicated and decontaminated against test sets using 13-gram Jaccard threshold 0.8 (Sec. 3.2). | Approximated | Deterministic duplicate removal and 13-gram Jaccard filtering are available as an opt-in pipeline step with persisted reports; full paper dataset splits and benchmark execution remain incomplete. |
| Intrinsic diversity uses embedding cosine distance globally and over k=10 nearest-neighbor groups; taxonomy assignment reports coverage (Sec. 3.3). | Approximated | Taxonomy coverage plus persisted global pairwise and local k-nearest-neighbor distance reports are implemented. A configurable OpenAI-compatible NIM embedding adapter and deterministic `hash_sha256_v1` fallback now exist; paper-scale embedding evidence and assignment-backed evaluation remain incomplete. |
| Complexity uses repeated batch-wise judgments and Elo calibration; BS=N=5 is the reported practical setting (Sec. 2.3, App. E). | Approximated | Pairwise judgments are injectable, validated, persisted, and gated by minimum comparisons. The deterministic cross-item `BS`/`N` scheduler, score-to-comparison conversion, NIM/Kimi batch scorer, and offline replay path now exist; live evidence on paper datasets is still missing. |
| Double-critic rejection sampling improves correctness and tracks rejection/accuracy effects (Sec. 3.1, App. D). | Approximated | Dual-critic decisions, agreement, rejection, and regeneration artifacts exist. Controlled corruption, benchmark correctness, and empirical accuracy lift are not implemented. |
| Downstream evaluation uses Gemma 3 4B students, Gemini 2.5 Flash teacher data, LoRA, ten seeds, and dataset-size scaling (Sec. 3.4, App. F.1). | Missing | No training, benchmark adapter, split policy, or downstream result artifact exists. |
| Full Simula generally dominates downstream scaling and complexity effects are domain-dependent (Sec. 4.3). | Missing | These are paper findings, not repository evidence. They require real datasets, generation, training, and repeated evaluations. |

## Executable matrix status

The current matrix preserves frozen comparability fields
(`domain_objective`, `seed`, model IDs, protocol versions, and artifact schema)
while changing only the documented ablation control:

| Run | Runtime change | Axis targeted |
| --- | --- | --- |
| B0 | All controls enabled | Reference |
| A1 | Taxonomy depth reduced to the root | Global coverage |
| A2 | One local instantiation per taxonomy node | Local diversity |
| A3 | Complexification fraction set to zero | Complexity |
| A4 | Single critic mode | Quality reliability |
| A5 | Dual critics accept disagreements | Critic strictness / quality trade-off |

These runs are mechanism validation, not paper result reproduction. Paper
Table 1's Baseline and Local variants still need explicit presets if exact
system-version reproduction is required.

## Priority order

1. Run the NIM/Kimi batch judge on fixed paper-dataset splits and persist
   `BS=N=5` evidence with provider metadata.
2. Validate a supported paper-compatible embedding endpoint/model and preserve
   the existing taxonomy coverage output.
3. Add adapters and fixed split manifests for the remaining paper datasets
   before attempting all five end-to-end.
4. Add a downstream evaluation seam with persisted split, training, seed, and
   benchmark-result metadata; execute real training only when compute and model
   access are available.
5. Replace deterministic Stage 1-3 stand-ins with provider-backed protocol
   implementations and retain deterministic replay fixtures for tests.

## Paper Alignment Check

- **Traceability/Auditability:** every current matrix run persists resolved configuration, lineage, stage artifacts, and integrity hashes; this matrix records the remaining evidence gaps explicitly.
- **Protocol/Comparability:** frozen comparability fields and ADR 0003 metric semantics remain unchanged. A2, A3, and A5 are documented ablations; they must not be interpreted as the paper's exact Table 1 labels.
- **Control-Axis Impact:** A1 targets coverage, A2 local diversity, A3 complexity, and A4/A5 quality policy independently; reporting continues to expose all three axes.
- **Deviation Log:** actual LLM-driven taxonomy/synthesis, complete paper datasets, validated paper-compatible embedding models, benchmark split manifests, and downstream training remain incomplete; configurable remote diversity, deterministic diversity, batch/pairwise Elo, and opt-in decontamination diagnostics are now persisted, with a live NIM/Kimi batch scorer available.
