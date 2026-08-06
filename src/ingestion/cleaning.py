from __future__ import annotations

from datetime import datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

MIN_TITLE_LENGTH = 3
MIN_SUMMARY_LENGTH = 100


def _parse_date(value: str) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        return pd.Timestamp(value)
    except (ValueError, TypeError):
        return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw PaperRecord list into a dataframe ready for embedding.

    Invalid rows (missing paper_id/title or too-short summary) are dropped,
    text fields are normalized, and helper columns used by downstream
    indexing/evaluation/quality modules are derived.
    """
    rows: list[dict] = []
    run_ts = pd.Timestamp(run_date)
    if run_ts.tzinfo is not None:
        run_ts = run_ts.tz_localize(None)

    for record in records:
        paper_id = normalize_whitespace(record.paper_id)
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)

        if not paper_id or len(title) < MIN_TITLE_LENGTH:
            continue

        authors = [normalize_whitespace(a) for a in record.authors if normalize_whitespace(a)]
        categories = [normalize_whitespace(c) for c in record.categories if normalize_whitespace(c)]
        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)

        published_ts = _parse_date(record.published)
        updated_ts = _parse_date(record.updated) or published_ts

        age_days = (run_ts - published_ts).days if published_ts is not None else None

        text_for_embedding = normalize_whitespace(
            f"Title: {title} | Authors: {authors_joined} | Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "summary_chars": len(summary),
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": normalize_whitespace(record.primary_category),
                "published": published_ts.date().isoformat() if published_ts is not None else "",
                "updated": updated_ts.date().isoformat() if updated_ts is not None else "",
                "age_days": age_days,
                "abs_url": normalize_whitespace(record.abs_url),
                "pdf_url": normalize_whitespace(record.pdf_url),
                "comment": normalize_whitespace(record.comment),
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df[df["summary_chars"] >= MIN_SUMMARY_LENGTH]
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df.sort_values("published", ascending=False, na_position="last").reset_index(drop=True)
    return df
