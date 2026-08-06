# Corruption Comparison Report

## Evaluation metrics across states
| Metric | Baseline | Corrupted | Repaired | Corr-Base | Repair-Base | Repair-Corr |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | n/a | n/a | n/a | n/a | n/a | n/a |
| `mean_token_f1` | n/a | n/a | n/a | n/a | n/a | n/a |
| `judge_accuracy` | n/a | n/a | n/a | n/a | n/a | n/a |
| `mean_judge_score` | n/a | n/a | n/a | n/a | n/a | n/a |

## Data quality across states
| Quality metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Total rows | 24 | 23 | 24 |
| Duplicate paper IDs | 0 | 1 | 0 |
| Short summaries | 0 | 3 | 0 |
| Empty embedding text | 0 | 0 | 0 |
| Stale rows | 0 | 1 | 0 |
| Stale rate | 0.0000 | 0.0435 | 0.0000 |

## Baseline quality
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

## Baseline freshness
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

## Corrupted quality
- Overall success: `False`
- Total rows: `23`
- Failed checks: `paper_id_unique, summary_min_length, freshness_within_threshold`
- `null_paper_ids`: `0`
- `null_paper_id_rate`: `0.0000`
- `duplicate_paper_ids`: `1`
- `duplicate_paper_id_rate`: `0.0435`
- `null_titles`: `0`
- `null_title_rate`: `0.0000`
- `empty_summaries`: `3`
- `non_empty_short_summaries`: `0`
- `short_summaries`: `3`
- `short_summary_rate`: `0.1304`
- `empty_embedding_text`: `0`
- `empty_embedding_text_rate`: `0.0000`
- `negative_age_rows`: `0`
- `stale_rows`: `1`
- `stale_rate`: `0.0435`
- `freshness_threshold_days`: `180`

## Corrupted freshness
- `latest_published`: `2026-07-13`
- `oldest_published`: `2024-08-06`
- `stale_rows`: `1`
- `stale_rate`: `0.0435`
- `total_rows`: `23`
- `missing_published`: `0`
- `missing_age_days`: `0`
- `negative_age_rows`: `0`
- `mean_age_days`: `106.0000`
- `max_age_days`: `730`
- `freshness_threshold_days`: `180`
- `is_fresh`: `False`

## Repaired quality
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

## Repaired freshness
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
- Corrupted data should degrade quality/freshness signals and usually retrieval/answer metrics.
- Repaired data should move quality/freshness and evaluation metrics back toward baseline.
- `Corr-Base` / `Repair-Base` compare each state to baseline; `Repair-Corr` shows recovery.
- Keep the same frozen test set, ground truth, evaluator, and top-k across all three states.
