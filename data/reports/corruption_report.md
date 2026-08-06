# Corruption Impact & Repair Comparison Report

## Evaluation Metrics Comparison

| Metric | Baseline | Corrupted | Delta (Corrupted) | Repaired | Delta (Repaired) |
| --- | --- | --- | --- | --- | --- |
| retrieval_hit_rate | 1.0000 | 0.9444 | -0.0556 | 1.0000 | +0.0000 |
| mean_token_f1 | 1.0000 | 0.7627 | -0.2373 | 1.0000 | +0.0000 |
| judge_accuracy | 0.9722 | 0.7500 | -0.2222 | 0.9722 | +0.0000 |
| mean_judge_score | 4.8889 | 4.1667 | -0.7222 | 4.8889 | +0.0000 |

## Data Quality

### Corrupted

Overall success: **False** (row_count=24)

| Check | Status | Detail |
| --- | --- | --- |
| row_count_positive | PASS | row_count=24 |
| paper_id_not_null | PASS | null_or_empty_count=0 |
| paper_id_unique | FAIL | duplicate_count=2 |
| title_not_null | PASS | null_or_empty_count=0 |
| summary_min_length | FAIL | rows_below_20_chars=5 |
| text_for_embedding_not_empty | PASS | empty_count=0 |
| freshness_within_threshold | PASS | stale_count=5, stale_rate=20.83%, threshold_days=180 |

### Repaired

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

| | Corrupted | Repaired |
| --- | --- | --- |
| Latest published | 2026-08-01 | 2026-08-01 |
| Stale rows | 5/24 | 0/24 |
| Is fresh | True | True |

## Conclusion

- Corruption reduces retrieval/answer quality relative to baseline (see deltas above; negative deltas in the Corrupted column indicate degraded performance).
- Repairing from the trusted raw snapshot restores metrics back toward baseline levels (see the Repaired column deltas, which should be near zero).
