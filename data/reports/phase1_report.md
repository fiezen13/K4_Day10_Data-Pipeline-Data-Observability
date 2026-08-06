# Phase 1 Baseline Report

## Source

- Source API: Crossref REST API
- Query: agentic retrieval augmented generation large language model
- Filter: from-pub-date:2026-02-07,has-abstract:true
- Max results requested: 24
- Raw records fetched: 24
- Clean rows kept: 24

## Evaluation Metrics

| Metric | Value |
| --- | --- |
| samples | 36 |
| retrieval_hit_rate | 1.0000 |
| mean_token_f1 | 1.0000 |
| judge_accuracy | 0.9722 |
| mean_judge_score | 4.8889 |

Ragas: `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}`

## Data Quality

Overall success: **True** (row_count=24)

| Check | Status | Detail |
| --- | --- | --- |
| row_count_positive | PASS | row_count=24 |
| paper_id_not_null | PASS | null_or_empty_count=0 |
| paper_id_unique | PASS | duplicate_count=0 |
| title_not_null | PASS | null_or_empty_count=0 |
| summary_min_length | PASS | rows_below_20_chars=0 |
| text_for_embedding_not_empty | PASS | empty_count=0 |
| freshness_within_threshold | PASS | stale_count=0, stale_rate=0.00%, threshold_days=180 |

## Freshness

- Latest published: 2026-08-01
- Oldest published: 2026-02-12
- Stale rows: 0 / 24 (0.00 rate)
- Freshness threshold (days): 180
- Is fresh: **True**
