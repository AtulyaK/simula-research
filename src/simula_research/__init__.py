from simula_research.pipeline import run_pipeline
from simula_research.validators import (
    validate_artifact_tree,
    validate_manifest_by_mode,
    validate_manifest_schema,
)
from simula_research.evaluation_metrics import (
    build_gate_report,
    compute_complexity_metrics,
    compute_coverage_metrics,
    compute_intrinsic_diversity_metrics,
    compute_quality_metrics,
)
from simula_research.decontamination import (
    deduplicate_and_decontaminate,
    ngram_jaccard_similarity,
)
from simula_research.complexity_judgments import (
    collect_batchwise_complexity_judgments,
    prepare_complexity_batch_schedule,
)
from simula_research.dataset_adapters import (
    adapt_cti_bench_record,
    adapt_cti_rcm_record,
    adapt_global_mmlu_record,
    adapt_gsm8k_record,
    adapt_lexam_record,
    load_cti_bench_tsv,
    load_global_mmlu_jsonl,
    load_global_mmlu_selection,
    load_gsm8k_jsonl,
    load_lexam_jsonl,
    load_split_manifest,
    validate_global_mmlu_selection,
    validate_task_record,
    validate_split_manifest,
)
from simula_research.downstream_evaluation import (
    aggregate_seed_accuracies,
    build_paper_downstream_evaluation_plan,
    score_exact_match_predictions,
    score_multiple_choice_predictions,
    validate_downstream_evaluation_plan,
    validate_downstream_evaluation_results,
)
from simula_research.generation_provider_adapter import (
    generation_providers_from_env,
    nvidia_complexification_provider,
    nvidia_local_diversification_provider,
    nvidia_regeneration_provider,
    nvidia_taxonomy_provider,
)
from simula_research.dataset_verification import (
    build_local_dataset_manifest,
    validate_local_dataset_manifest,
    verify_local_dataset_file,
    verify_local_split,
)
from simula_research.benchmark_evaluation import (
    predict_local_benchmark,
    load_prediction_artifact,
    score_local_benchmark,
)

__all__ = [
    "run_pipeline",
    "validate_manifest_schema",
    "validate_manifest_by_mode",
    "validate_artifact_tree",
    "compute_coverage_metrics",
    "compute_complexity_metrics",
    "compute_intrinsic_diversity_metrics",
    "compute_quality_metrics",
    "adapt_cti_bench_record",
    "adapt_cti_rcm_record",
    "adapt_global_mmlu_record",
    "adapt_gsm8k_record",
    "adapt_lexam_record",
    "load_cti_bench_tsv",
    "load_global_mmlu_jsonl",
    "load_global_mmlu_selection",
    "load_gsm8k_jsonl",
    "load_lexam_jsonl",
    "load_split_manifest",
    "validate_global_mmlu_selection",
    "validate_task_record",
    "validate_split_manifest",
    "build_paper_downstream_evaluation_plan",
    "validate_downstream_evaluation_plan",
    "validate_downstream_evaluation_results",
    "score_multiple_choice_predictions",
    "score_exact_match_predictions",
    "aggregate_seed_accuracies",
    "nvidia_taxonomy_provider",
    "nvidia_local_diversification_provider",
    "nvidia_complexification_provider",
    "nvidia_regeneration_provider",
    "generation_providers_from_env",
    "verify_local_split",
    "build_local_dataset_manifest",
    "validate_local_dataset_manifest",
    "verify_local_dataset_file",
    "load_prediction_artifact",
    "score_local_benchmark",
    "predict_local_benchmark",
    "ngram_jaccard_similarity",
    "deduplicate_and_decontaminate",
    "prepare_complexity_batch_schedule",
    "collect_batchwise_complexity_judgments",
    "build_gate_report",
]
