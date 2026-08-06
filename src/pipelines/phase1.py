from __future__ import annotations

import logging

from core.config import Settings, load_settings, require_llm_credentials
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_or_fetch_records(settings: Settings):
    paths = settings.paths
    if settings.refresh_source or not paths.raw_records_json.exists():
        logger.info("Fetching raw records from %s", settings.source_api)
        return fetch_source_records(settings)
    logger.info("Loading raw records from %s", paths.raw_records_json)
    return load_raw_records(paths.raw_records_json)


def _load_or_build_test_set(settings: Settings, df):
    paths = settings.paths
    if settings.refresh_test_set or not paths.eval_testset.exists():
        logger.info("Building evaluation test set")
        return build_test_set(df, paths.eval_testset)
    logger.info("Loading existing evaluation test set from %s", paths.eval_testset)
    return read_json(paths.eval_testset)


def main() -> None:
    settings = load_settings()
    require_llm_credentials(settings)
    paths = settings.paths

    records = _load_or_fetch_records(settings)
    logger.info("Loaded %d raw records", len(records))

    df = build_clean_dataframe(records, run_date=now_utc())
    logger.info("Cleaned dataframe has %d rows", len(df))
    write_csv(df, paths.clean_csv)
    write_json(paths.clean_json, df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=paths.embeddings_json)
    logger.info("Built baseline embedding index with collection '%s'", index.collection_name)

    _load_or_build_test_set(settings, df)

    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.baseline_metrics,
        answers_output_path=paths.baseline_answers,
    )
    logger.info("Baseline evaluation summary: %s", bundle.summary)

    quality = run_data_quality_checks(df, settings, report_name="baseline")
    freshness = build_freshness_report(df, settings, paths.freshness_report)

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "max_results": settings.max_results,
        "record_count": len(records),
        "clean_row_count": len(df),
    }

    generate_phase1_report(
        report_path=paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    logger.info("Baseline report written to %s", paths.baseline_report)


if __name__ == "__main__":
    main()
