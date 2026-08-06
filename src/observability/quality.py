from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json

# Keep aligned with cleaning: summaries shorter than this are treated as low quality.
_MIN_SUMMARY_CHARS = 100


def _is_blank(series: pd.Series) -> pd.Series:
    """True when a value is null or only whitespace."""
    as_str = series.fillna("").astype(str).str.strip()
    return series.isna() | (as_str == "") | (as_str.str.lower() == "nan")


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _check(name: str, success: bool, observed: Any, expectation: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "success": bool(success),
        "observed": observed,
        "expectation": expectation,
    }
    if details:
        payload["details"] = details
    return payload


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """TODO(student): tao bo data quality checks.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    total_rows = int(len(df))
    threshold = settings.freshness_threshold_days
    checks: list[dict[str, Any]] = []

    # 1. Non-empty corpus
    checks.append(
        _check(
            "row_count_positive",
            total_rows > 0,
            total_rows,
            "Dataset must contain at least 1 row.",
        )
    )

    # 2. paper_id present and unique
    if "paper_id" not in df.columns:
        null_paper_ids = total_rows
        duplicate_paper_ids = 0
    else:
        null_paper_ids = int(_is_blank(df["paper_id"]).sum())
        non_null_ids = df.loc[~_is_blank(df["paper_id"]), "paper_id"].astype(str).str.strip()
        duplicate_paper_ids = int(non_null_ids.duplicated().sum())

    checks.append(
        _check(
            "paper_id_not_null",
            null_paper_ids == 0 and total_rows > 0,
            {"null_count": null_paper_ids, "total_rows": total_rows},
            "Every row must have a non-empty paper_id.",
        )
    )
    checks.append(
        _check(
            "paper_id_unique",
            duplicate_paper_ids == 0 and total_rows > 0,
            {"duplicate_count": duplicate_paper_ids, "total_rows": total_rows},
            "paper_id values must be unique.",
        )
    )

    # 3. title present
    null_titles = int(_is_blank(df["title"]).sum()) if "title" in df.columns else total_rows
    checks.append(
        _check(
            "title_not_null",
            null_titles == 0 and total_rows > 0,
            {"null_count": null_titles, "total_rows": total_rows},
            "Every row must have a non-empty title.",
        )
    )

    # 4. summary length / empty text
    if "summary" in df.columns:
        summary_chars = df["summary"].fillna("").astype(str).str.strip().str.len()
    elif "summary_chars" in df.columns:
        summary_chars = pd.to_numeric(df["summary_chars"], errors="coerce").fillna(0).astype(int)
    else:
        summary_chars = pd.Series([0] * total_rows, dtype=int)

    empty_summaries = int((summary_chars == 0).sum())
    non_empty_short_summaries = int(((summary_chars > 0) & (summary_chars < _MIN_SUMMARY_CHARS)).sum())
    short_summaries = empty_summaries + non_empty_short_summaries
    checks.append(
        _check(
            "summary_min_length",
            short_summaries == 0 and total_rows > 0,
            {
                "empty_summaries": empty_summaries,
                "non_empty_short_summaries": non_empty_short_summaries,
                "short_summaries_total": short_summaries,
                "min_chars": _MIN_SUMMARY_CHARS,
                "total_rows": total_rows,
            },
            f"Every summary must have at least {_MIN_SUMMARY_CHARS} characters.",
        )
    )

    if "text_for_embedding" in df.columns:
        empty_embedding_text = int(_is_blank(df["text_for_embedding"]).sum())
    else:
        empty_embedding_text = total_rows
    checks.append(
        _check(
            "text_for_embedding_not_empty",
            empty_embedding_text == 0 and total_rows > 0,
            {"empty_count": empty_embedding_text, "total_rows": total_rows},
            "Every row must have non-empty text_for_embedding.",
        )
    )

    # 5. freshness via age_days
    # Lab contract: all papers must stay within freshness_threshold_days (demo-friendly for stale corruption).
    if "age_days" in df.columns and total_rows > 0:
        age = pd.to_numeric(df["age_days"], errors="coerce")
        missing_age_days = int(age.isna().sum())
        negative_age_rows = int((age < 0).fillna(False).sum())
        stale_rows = int((age > threshold).fillna(False).sum())
        max_age = None if age.dropna().empty else int(age.max())
        mean_age = None if age.dropna().empty else float(round(age.mean(), 2))
    else:
        missing_age_days = total_rows
        negative_age_rows = 0
        stale_rows = 0
        max_age = None
        mean_age = None

    checks.append(
        _check(
            "age_days_present",
            missing_age_days == 0 and total_rows > 0,
            {"missing_count": missing_age_days, "total_rows": total_rows},
            "Every row must have age_days for freshness monitoring.",
        )
    )
    checks.append(
        _check(
            "age_days_non_negative",
            negative_age_rows == 0 and total_rows > 0,
            {"negative_age_rows": negative_age_rows, "total_rows": total_rows},
            "age_days must be greater than or equal to 0.",
        )
    )
    stale_rate = _rate(stale_rows, total_rows)
    checks.append(
        _check(
            "freshness_within_threshold",
            stale_rows == 0 and total_rows > 0,
            {
                "stale_rows": stale_rows,
                "stale_rate": stale_rate,
                "threshold_days": threshold,
                "max_age_days": max_age,
                "mean_age_days": mean_age,
            },
            f"Lab contract: all rows should have age_days <= {threshold}.",
        )
    )

    success = all(item["success"] for item in checks)
    report = {
        "report_name": report_name,
        "success": success,
        "total_rows": total_rows,
        "failed_checks": [item["name"] for item in checks if not item["success"]],
        "metrics": {
            "null_paper_ids": null_paper_ids,
            "null_paper_id_rate": _rate(null_paper_ids, total_rows),
            "duplicate_paper_ids": duplicate_paper_ids,
            "duplicate_paper_id_rate": _rate(duplicate_paper_ids, total_rows),
            "null_titles": null_titles,
            "null_title_rate": _rate(null_titles, total_rows),
            "empty_summaries": empty_summaries,
            "empty_summary_rate": _rate(empty_summaries, total_rows),
            "non_empty_short_summaries": non_empty_short_summaries,
            "short_summaries": short_summaries,
            "short_summary_rate": _rate(short_summaries, total_rows),
            "empty_embedding_text": empty_embedding_text,
            "empty_embedding_text_rate": _rate(empty_embedding_text, total_rows),
            "missing_age_days": missing_age_days,
            "negative_age_rows": negative_age_rows,
            "stale_rows": stale_rows,
            "stale_rate": stale_rate,
            "freshness_threshold_days": threshold,
        },
        "checks": checks,
    }

    output_path = Path(settings.paths.quality_dir) / f"{report_name}.json"
    report["report_path"] = str(output_path)
    write_json(output_path, report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """TODO(student): tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    total_rows = int(len(df))
    threshold = settings.freshness_threshold_days

    published = (
        pd.to_datetime(df["published"], errors="coerce")
        if "published" in df.columns and total_rows
        else pd.Series(dtype="datetime64[ns]")
    )
    missing_published = int(published.isna().sum()) if total_rows else 0
    valid_published = published.dropna()
    latest_published = valid_published.max().date().isoformat() if not valid_published.empty else None
    oldest_published = valid_published.min().date().isoformat() if not valid_published.empty else None

    if "age_days" in df.columns and total_rows:
        age = pd.to_numeric(df["age_days"], errors="coerce")
        missing_age_days = int(age.isna().sum())
        negative_age_rows = int((age < 0).fillna(False).sum())
        stale_mask = (age > threshold).fillna(False)
        stale_rows = int(stale_mask.sum())
        mean_age_days = None if age.dropna().empty else float(round(age.mean(), 2))
        max_age_days = None if age.dropna().empty else int(age.max())
    else:
        missing_age_days = total_rows
        negative_age_rows = 0
        stale_rows = 0
        mean_age_days = None
        max_age_days = None

    stale_rate = _rate(stale_rows, total_rows)
    # Lab contract: zero stale rows within freshness_threshold_days, plus valid published/age fields.
    is_fresh = (
        total_rows > 0
        and stale_rows == 0
        and missing_age_days == 0
        and missing_published == 0
        and negative_age_rows == 0
    )

    report = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": stale_rows,
        "stale_rate": stale_rate,
        "total_rows": total_rows,
        "missing_published": missing_published,
        "missing_age_days": missing_age_days,
        "negative_age_rows": negative_age_rows,
        "mean_age_days": mean_age_days,
        "max_age_days": max_age_days,
        "freshness_threshold_days": threshold,
        "is_fresh": is_fresh,
    }

    output = Path(report_path)
    report["report_path"] = str(output)
    write_json(output, report)
    return report
