from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_SUMMARY_CHARS = 20


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run a battery of data quality checks and persist a pass/fail report."""
    row_count = len(df)
    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "row_count_positive",
            "passed": row_count > 0,
            "detail": f"row_count={row_count}",
        }
    )

    if row_count == 0:
        result = {
            "report_name": report_name,
            "generated_at": now_utc().isoformat(),
            "row_count": 0,
            "checks": checks,
            "success": False,
        }
        write_json(settings.paths.quality_dir / f"{report_name}_quality.json", result)
        return result

    paper_id_null_count = int(df["paper_id"].isna().sum() + (df["paper_id"] == "").sum())
    paper_id_duplicate_count = int(df["paper_id"].duplicated().sum())
    checks.append(
        {
            "name": "paper_id_not_null",
            "passed": paper_id_null_count == 0,
            "detail": f"null_or_empty_count={paper_id_null_count}",
        }
    )
    checks.append(
        {
            "name": "paper_id_unique",
            "passed": paper_id_duplicate_count == 0,
            "detail": f"duplicate_count={paper_id_duplicate_count}",
        }
    )

    title_null_count = int(df["title"].isna().sum() + (df["title"] == "").sum())
    checks.append(
        {
            "name": "title_not_null",
            "passed": title_null_count == 0,
            "detail": f"null_or_empty_count={title_null_count}",
        }
    )

    short_summary_count = int((df["summary"].fillna("").str.len() < MIN_SUMMARY_CHARS).sum())
    checks.append(
        {
            "name": "summary_min_length",
            "passed": short_summary_count == 0,
            "detail": f"rows_below_{MIN_SUMMARY_CHARS}_chars={short_summary_count}",
        }
    )

    empty_text_for_embedding = int(df["text_for_embedding"].fillna("").str.len().eq(0).sum())
    checks.append(
        {
            "name": "text_for_embedding_not_empty",
            "passed": empty_text_for_embedding == 0,
            "detail": f"empty_count={empty_text_for_embedding}",
        }
    )

    stale_mask = df["age_days"].apply(
        lambda value: value is not None and not pd.isna(value) and value > settings.freshness_threshold_days
    )
    stale_count = int(stale_mask.sum())
    stale_rate = stale_count / row_count
    checks.append(
        {
            "name": "freshness_within_threshold",
            "passed": stale_rate < 0.5,
            "detail": f"stale_count={stale_count}, stale_rate={stale_rate:.2%}, "
            f"threshold_days={settings.freshness_threshold_days}",
        }
    )

    success = all(check["passed"] for check in checks)
    result = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "row_count": row_count,
        "checks": checks,
        "success": success,
    }

    write_json(settings.paths.quality_dir / f"{report_name}_quality.json", result)
    return result


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize freshness signals (latest/oldest published date, stale row rate)."""
    total_rows = len(df)
    if total_rows == 0:
        payload = {
            "generated_at": now_utc().isoformat(),
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": 0,
            "stale_rate": 0.0,
            "freshness_threshold_days": settings.freshness_threshold_days,
            "is_fresh": False,
        }
        write_json(report_path, payload)
        return payload

    published_dates = pd.to_datetime(df["published"], errors="coerce")
    valid_dates = published_dates.dropna()

    stale_mask = df["age_days"].apply(
        lambda value: value is not None and not pd.isna(value) and value > settings.freshness_threshold_days
    )
    stale_rows = int(stale_mask.sum())
    stale_rate = stale_rows / total_rows

    payload = {
        "generated_at": now_utc().isoformat(),
        "latest_published": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
        "oldest_published": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_rate": stale_rate,
        "freshness_threshold_days": settings.freshness_threshold_days,
        "is_fresh": stale_rate < 0.5,
    }

    write_json(report_path, payload)
    return payload
