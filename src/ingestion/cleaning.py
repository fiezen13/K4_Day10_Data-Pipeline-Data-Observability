from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
import html
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace, write_csv, write_json
from ingestion.crossref import PaperRecord


_CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _is_missing(value: Any) -> bool:
    """Return True for None, pandas NA, and NaN without treating containers as NA."""
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_text(value: Any) -> str:
    """Coerce a scalar to clean plain text, removing Crossref HTML/XML markup."""
    if _is_missing(value):
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = html.unescape(value)
    value = _HTML_TAG_RE.sub(" ", value)
    return normalize_whitespace(value)


def _clean_list(value: Any) -> list[str]:
    """Coerce malformed list-like fields while preserving useful text values."""
    if _is_missing(value):
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                decoded = json.loads(text)
                value = decoded if isinstance(decoded, list) else [value]
            except json.JSONDecodeError:
                value = [value]
        else:
            value = [value]
    elif isinstance(value, Mapping):
        value = list(value.values())
    elif not isinstance(value, Iterable):
        value = [value]

    cleaned: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            item = item.get("name") or item.get("literal") or item.get("family") or ""
        text = _clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _normalise_date(value: Any) -> str:
    """Return an ISO calendar date, or an empty string when a source value is invalid."""
    if _is_missing(value):
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        parsed = pd.to_datetime(_clean_text(value), errors="coerce", utc=True)
    except (TypeError, ValueError):
        return ""
    if pd.isna(parsed):
        return ""
    return parsed.date().isoformat()


def _age_days(published: str, run_date: datetime) -> int | None:
    if not published:
        return None
    published_date = datetime.strptime(published, "%Y-%m-%d").date()
    reference_date = run_date.astimezone(UTC).date() if run_date.tzinfo else run_date.date()
    # A future publication date is valid metadata; it is not "negative age" data.
    return max(0, (reference_date - published_date).days)


def _record_field(record: PaperRecord | Mapping[str, Any], field: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(field)
    return getattr(record, field, None)


def _text_for_embedding(
    title: str,
    summary: str,
    authors_joined: str,
    categories_joined: str,
    published: str,
) -> str:
    sections = [f"Title: {title}"]
    if authors_joined:
        sections.append(f"Authors: {authors_joined}")
    if categories_joined:
        sections.append(f"Categories: {categories_joined}")
    if published:
        sections.append(f"Published: {published}")
    sections.append(f"Summary: {summary}")
    return "\n".join(sections)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Build the canonical clean paper dataframe from raw ``PaperRecord`` values.

    Records are filtered in this order: missing paper_id, missing title, summary shorter
    than 100 cleaned characters, then duplicate paper_id. Cleaning statistics are kept
    in ``dataframe.attrs['cleaning_stats']`` for the pipeline/reporting layer.
    """
    stats = {
        "input_records": len(records),
        "dropped_missing_paper_id": 0,
        "dropped_missing_title": 0,
        "dropped_summary_too_short": 0,
        "duplicates_removed": 0,
        "output_records": 0,
    }
    cleaned_rows: list[dict[str, Any]] = []
    seen_paper_ids: set[str] = set()

    for record in records:
        # Do not derive or alter IDs here: ingestion owns the stable source identifier.
        paper_id = _clean_text(_record_field(record, "paper_id"))
        if not paper_id:
            stats["dropped_missing_paper_id"] += 1
            continue

        title = _clean_text(_record_field(record, "title"))
        if not title:
            stats["dropped_missing_title"] += 1
            continue

        summary = _clean_text(_record_field(record, "summary"))
        if len(summary) < 100:
            stats["dropped_summary_too_short"] += 1
            continue

        if paper_id in seen_paper_ids:
            stats["duplicates_removed"] += 1
            continue
        seen_paper_ids.add(paper_id)

        authors = _clean_list(_record_field(record, "authors"))
        categories = _clean_list(_record_field(record, "categories"))
        primary_category = _clean_text(_record_field(record, "primary_category"))
        if not primary_category and categories:
            primary_category = categories[0]
        published = _normalise_date(_record_field(record, "published"))
        updated = _normalise_date(_record_field(record, "updated"))
        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)

        cleaned_rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "abs_url": _clean_text(_record_field(record, "abs_url")),
                "pdf_url": _clean_text(_record_field(record, "pdf_url")),
                "comment": _clean_text(_record_field(record, "comment")),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": _age_days(published, run_date),
                "text_for_embedding": _text_for_embedding(
                    title, summary, authors_joined, categories_joined, published
                ),
            }
        )

    dataframe = pd.DataFrame(cleaned_rows, columns=_CLEAN_COLUMNS)
    if not dataframe.empty:
        dataframe["summary_chars"] = dataframe["summary_chars"].astype("int64")
        dataframe["age_days"] = dataframe["age_days"].astype("Int64")
        dataframe = dataframe.sort_values(
            by=["published", "paper_id"], ascending=[False, True], kind="stable"
        ).reset_index(drop=True)
    else:
        dataframe = dataframe.astype({"summary_chars": "int64", "age_days": "Int64"})

    stats["output_records"] = len(dataframe)
    dataframe.attrs["cleaning_stats"] = stats
    return dataframe


def save_clean_artifacts(df: pd.DataFrame, csv_path: Path | str, json_path: Path | str) -> None:
    """Persist clean artifacts with list fields intact in JSON for downstream reuse."""
    missing_columns = sorted(set(_CLEAN_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing_columns)}")

    write_csv(df, Path(csv_path))
    # ``to_json`` turns pandas nullable values into JSON null and preserves list columns.
    records = json.loads(df.to_json(orient="records"))
    write_json(Path(json_path), records)
