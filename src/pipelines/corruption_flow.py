from __future__ import annotations

import logging

import pandas as pd

from core.config import load_settings, require_llm_credentials
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = load_settings()
    require_llm_credentials(settings)
    paths = settings.paths

    if not paths.clean_json.exists() or not paths.baseline_metrics.exists():
        raise RuntimeError(
            "Baseline artifacts not found. Run script/run_phase1.py before the corruption flow."
        )

    baseline_metrics = read_json(paths.baseline_metrics)
    baseline_records = read_json(paths.clean_json)
    baseline_df = pd.DataFrame(baseline_records)
    logger.info("Loaded baseline clean dataset with %d rows", len(baseline_df))

    test_set = read_json(paths.eval_testset)
    target_paper_ids = {doc_id for item in test_set for doc_id in item["ground_truth_doc_ids"]}
    logger.info("Test set references %d distinct paper_ids to target for corruption", len(target_paper_ids))

    corrupted_df = corrupt_clean_dataframe(
        baseline_df.copy(deep=True),
        output_log_path=paths.corruption_log,
        target_paper_ids=target_paper_ids,
    )
    logger.info("Corrupted dataset has %d rows", len(corrupted_df))
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, embeddings_output_path=paths.corrupted_embeddings_json
    )
    logger.info("Built corrupted embedding index with collection '%s'", corrupted_index.collection_name)

    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.corrupted_metrics,
        answers_output_path=paths.corrupted_answers,
    )
    logger.info("Corrupted evaluation summary: %s", corrupted_bundle.summary)

    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, paths.corrupted_freshness_report)

    logger.info("Repairing dataset from raw source snapshot")
    raw_records = load_raw_records(paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date=now_utc())
    write_csv(repaired_df, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired_df.to_dict(orient="records"))

    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, embeddings_output_path=paths.repaired_embeddings_json
    )
    logger.info("Built repaired embedding index with collection '%s'", repaired_index.collection_name)

    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.repaired_metrics,
        answers_output_path=paths.repaired_answers,
    )
    logger.info("Repaired evaluation summary: %s", repaired_bundle.summary)

    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    repaired_freshness = build_freshness_report(repaired_df, settings, paths.repaired_freshness_report)

    generate_corruption_report(
        report_path=paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    logger.info("Comparison report written to %s", paths.comparison_report)


if __name__ == "__main__":
    main()
