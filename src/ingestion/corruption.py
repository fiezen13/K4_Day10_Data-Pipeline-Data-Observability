from __future__ import annotations

import random

import pandas as pd

from core.utils import normalize_whitespace, now_utc, write_json

RANDOM_SEED = 42
DROP_LATEST_FRACTION = 0.10
BLANK_SUMMARY_FRACTION = 0.15
NOISE_SUMMARY_FRACTION = 0.15
TRUNCATE_TITLE_FRACTION = 0.15
STALE_DATE_FRACTION = 0.15
DUPLICATE_FRACTION = 0.10
STALE_DATE_YEARS_BACK = 5
TITLE_TRUNCATE_CHARS = 12
NOISE_SUFFIX = " asdkj##garbled$$1234 lorem-noise-injected"


def _rebuild_text_for_embedding(row: pd.Series) -> str:
    return normalize_whitespace(
        f"Title: {row['title']} | Authors: {row['authors_joined']} | Summary: {row['summary']}"
    )


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path,
    target_paper_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Simulate multiple realistic data corruption scenarios on a clean dataframe.

    Never mutates the baseline dataframe in place (caller passes a copy); this
    function only reads from it and returns a new, corrupted dataframe.

    When `target_paper_ids` is provided (typically the ground_truth_doc_ids
    referenced by the frozen evaluation test set), corruption is biased to hit
    those rows first so the impact is actually observable in retrieval/answer
    metrics instead of landing on documents no question ever touches.
    """
    rng = random.Random(RANDOM_SEED)
    df = df.reset_index(drop=True).copy(deep=True)
    target_paper_ids = target_paper_ids or set()
    original_row_count = len(df)
    manifest: dict[str, list] = {
        "dropped_latest_paper_ids": [],
        "blanked_summary_paper_ids": [],
        "noisy_summary_paper_ids": [],
        "truncated_title_paper_ids": [],
        "stale_date_paper_ids": [],
        "duplicated_paper_ids": [],
    }

    # 1. Drop a fraction of the most recently published records.
    # Excludes evaluation targets: dropping a target row entirely would make
    # every question about it an unconditional retrieval miss, which is a
    # degenerate (uninformative) way to demonstrate corruption impact.
    droppable = df[~df["paper_id"].isin(target_paper_ids)]
    sorted_by_recency = droppable.sort_values("published", ascending=False, na_position="last")
    n_drop = max(1, int(len(df) * DROP_LATEST_FRACTION)) if len(sorted_by_recency) > 0 else 0
    drop_ids = sorted_by_recency.head(n_drop)["paper_id"].tolist()
    manifest["dropped_latest_paper_ids"] = drop_ids
    df = df[~df["paper_id"].isin(drop_ids)].reset_index(drop=True)

    remaining_indices = list(df.index)
    rng.shuffle(remaining_indices)
    target_indices = [i for i in remaining_indices if df.at[i, "paper_id"] in target_paper_ids]
    non_target_indices = [i for i in remaining_indices if df.at[i, "paper_id"] not in target_paper_ids]
    prioritized_indices = target_indices + non_target_indices

    def _take(fraction: float) -> list[int]:
        count = max(1, int(len(df) * fraction)) if len(df) > 0 else 0
        return prioritized_indices[:count]

    # 2. Blank out summaries on a subset of rows.
    blank_idx = _take(BLANK_SUMMARY_FRACTION)
    for idx in blank_idx:
        manifest["blanked_summary_paper_ids"].append(df.at[idx, "paper_id"])
        df.at[idx, "summary"] = ""
        df.at[idx, "summary_chars"] = 0

    # 3. Inject noise into summaries on a different subset.
    remaining_for_noise = [i for i in prioritized_indices if i not in blank_idx]
    noise_idx = remaining_for_noise[: max(1, int(len(df) * NOISE_SUMMARY_FRACTION))] if df.shape[0] > 0 else []
    for idx in noise_idx:
        manifest["noisy_summary_paper_ids"].append(df.at[idx, "paper_id"])
        df.at[idx, "summary"] = normalize_whitespace(df.at[idx, "summary"] + NOISE_SUFFIX)
        df.at[idx, "summary_chars"] = len(df.at[idx, "summary"])

    # 4. Truncate titles on a subset of rows.
    truncate_idx = _take(TRUNCATE_TITLE_FRACTION)
    for idx in truncate_idx:
        manifest["truncated_title_paper_ids"].append(df.at[idx, "paper_id"])
        title = df.at[idx, "title"]
        df.at[idx, "title"] = title[:TITLE_TRUNCATE_CHARS].rstrip()

    # 5. Make publication dates stale (push them years into the past).
    stale_idx = _take(STALE_DATE_FRACTION)
    stale_date = (now_utc().date().replace(day=1) - pd.DateOffset(years=STALE_DATE_YEARS_BACK)).date().isoformat()
    for idx in stale_idx:
        manifest["stale_date_paper_ids"].append(df.at[idx, "paper_id"])
        df.at[idx, "published"] = stale_date
        df.at[idx, "age_days"] = (now_utc().date() - pd.Timestamp(stale_date).date()).days

    # 6. Add duplicate rows.
    n_dup = max(1, int(len(df) * DUPLICATE_FRACTION)) if len(df) > 0 else 0
    dup_source_idx = prioritized_indices[:n_dup]
    if dup_source_idx:
        dup_rows = df.loc[dup_source_idx].copy(deep=True)
        manifest["duplicated_paper_ids"] = dup_rows["paper_id"].tolist()
        df = pd.concat([df, dup_rows], ignore_index=True)

    # 7. Rebuild text_for_embedding to reflect all corrupted fields.
    df["text_for_embedding"] = df.apply(_rebuild_text_for_embedding, axis=1)

    manifest["generated_at"] = now_utc().isoformat()
    manifest["original_row_count"] = original_row_count
    manifest["corrupted_row_count"] = len(df)
    write_json(output_log_path, manifest)

    return df
