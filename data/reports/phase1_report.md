# Phase 1 Baseline Report

## Source summary
- `source_api`: `Crossref REST API`
- `source_query`: `agentic retrieval augmented generation large language model`
- `source_filter`: `from-pub-date:2026-02-07,has-abstract:true`
- `max_results`: `24`
- `clean_rows`: `24`
- `freshness_threshold_days`: `180`
- `embedding_model`: `sentence-transformers/all-MiniLM-L6-v2`
- `top_k`: `4`

## Evaluation metrics
- No evaluation metrics provided.

## Data quality
- Overall success: `True`
- Total rows: `24`
- Failed checks: `none`
- `null_paper_ids`: `0`
- `null_paper_id_rate`: `0.0000`
- `duplicate_paper_ids`: `0`
- `duplicate_paper_id_rate`: `0.0000`
- `null_titles`: `0`
- `null_title_rate`: `0.0000`
- `empty_summaries`: `0`
- `non_empty_short_summaries`: `0`
- `short_summaries`: `0`
- `short_summary_rate`: `0.0000`
- `empty_embedding_text`: `0`
- `empty_embedding_text_rate`: `0.0000`
- `negative_age_rows`: `0`
- `stale_rows`: `0`
- `stale_rate`: `0.0000`
- `freshness_threshold_days`: `180`

## Freshness
- `latest_published`: `2026-08-01`
- `oldest_published`: `2026-02-12`
- `stale_rows`: `0`
- `stale_rate`: `0.0000`
- `total_rows`: `24`
- `missing_published`: `0`
- `missing_age_days`: `0`
- `negative_age_rows`: `0`
- `mean_age_days`: `76.5800`
- `max_age_days`: `175`
- `freshness_threshold_days`: `180`
- `is_fresh`: `True`

## Interpretation
- Baseline passed quality and freshness checks and can be frozen for corruption experiments.
- Retrieval and answer metrics above are the reference for corrupted/repaired comparison.
