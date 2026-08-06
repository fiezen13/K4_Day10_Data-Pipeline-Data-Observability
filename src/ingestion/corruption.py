from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import read_json, write_csv, write_json


def _text(value: Any) -> str:
    """Convert a dataframe value to a stable text value for derived fields."""
    if value is None or value is pd.NA:
        return ""
    if pd.api.types.is_scalar(value) and bool(pd.isna(value)):
        return ""
    return str(value).strip()


def _build_embedding_text(row: pd.Series) -> str:
    """Build the document text again after a corruption changes source fields.

    This follows the cleaned-data contract used by the starter project.  Keeping
    the rebuild here is important: corrupting only ``summary`` while retaining
    an old ``text_for_embedding`` would hide the corruption from the vector
    index and make the experiment invalid.
    """
    # Keep this layout identical to cleaning._text_for_embedding.  In
    # particular, ``Summary:`` must remain present when corruption blanks the
    # summary, otherwise corrupted documents would use a different schema.
    title = _text(row.get("title"))
    summary = _text(row.get("summary"))
    authors_joined = _text(row.get("authors_joined"))
    categories_joined = _text(row.get("categories_joined"))
    published = _text(row.get("published"))
    sections = [f"Title: {title}"]
    if authors_joined:
        sections.append(f"Authors: {authors_joined}")
    if categories_joined:
        sections.append(f"Categories: {categories_joined}")
    if published:
        sections.append(f"Published: {published}")
    sections.append(f"Summary: {summary}")
    return "\n".join(sections)


def _paper_id(row: pd.Series, row_index: Any) -> str:
    value = _text(row.get("paper_id"))
    return value or f"row:{row_index}"


def _refresh_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Refresh every field that must agree with the intentionally bad data."""
    refreshed = df.copy()
    if "summary" in refreshed.columns and "summary_chars" in refreshed.columns:
        refreshed["summary_chars"] = refreshed["summary"].map(lambda value: len(_text(value)))

    if "published" in refreshed.columns and "age_days" in refreshed.columns:
        published = pd.to_datetime(refreshed["published"], errors="coerce", utc=True)
        today = pd.Timestamp(datetime.now(UTC).date(), tz="UTC")
        refreshed["age_days"] = (today - published).dt.days

    if "text_for_embedding" in refreshed.columns:
        refreshed["text_for_embedding"] = refreshed.apply(_build_embedding_text, axis=1)
    return refreshed


def save_dataframe_artifacts(df: pd.DataFrame, csv_path, json_path) -> None:
    """Persist a dataset to its dedicated CSV and JSON artifact paths.

    The orchestration flow calls this helper once for corrupted data and once
    for repaired data.  It deliberately accepts explicit paths so it cannot
    overwrite baseline artifacts by accident.
    """
    write_csv(df, Path(csv_path))
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    write_json(Path(json_path), records)


def repair_from_raw_snapshot(raw_records_path, run_date: datetime) -> pd.DataFrame:
    """Rebuild clean data from the immutable raw snapshot, never from corruption.

    Keeping this operation in one named helper makes the repair provenance
    explicit in the corruption flow and prevents an accidental copy of the
    baseline or corrupted CSV from being presented as a repair.
    """
    from ingestion.cleaning import build_clean_dataframe
    from ingestion.crossref import load_raw_records

    snapshot_path = Path(raw_records_path)
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Trusted raw snapshot was not found: {snapshot_path}")
    raw_records = load_raw_records(snapshot_path)
    return build_clean_dataframe(raw_records, run_date=run_date)


def build_repair_evidence(
    baseline_df: pd.DataFrame,
    repaired_df: pd.DataFrame,
    raw_records_path,
    freshness_threshold_days: int,
) -> dict[str, Any]:
    """Produce auditable evidence that repair came from raw and is near baseline."""
    for name, frame in (("baseline", baseline_df), ("repaired", repaired_df)):
        if "paper_id" not in frame.columns:
            raise ValueError(f"Cannot build repair evidence; {name} data has no paper_id column.")

    def quality_snapshot(frame: pd.DataFrame) -> dict[str, Any]:
        paper_ids = frame["paper_id"].map(_text)
        snapshot: dict[str, Any] = {
            "rows": len(frame),
            "unique_paper_ids": int(paper_ids.nunique(dropna=True)),
            "duplicate_paper_id_rows": int(paper_ids.duplicated(keep=False).sum()),
        }
        if "summary" in frame.columns:
            snapshot["blank_summary_rows"] = int(frame["summary"].map(_text).eq("").sum())
        if "age_days" in frame.columns:
            ages = pd.to_numeric(frame["age_days"], errors="coerce")
            snapshot["stale_rows"] = int((ages > freshness_threshold_days).sum())
        return snapshot

    baseline_ids = set(baseline_df["paper_id"].map(_text)) - {""}
    repaired_ids = set(repaired_df["paper_id"].map(_text)) - {""}
    baseline_quality = quality_snapshot(baseline_df)
    repaired_quality = quality_snapshot(repaired_df)
    same_paper_ids = baseline_ids == repaired_ids
    same_row_count = len(baseline_df) == len(repaired_df)

    comparable_columns = [
        column
        for column in ("title", "summary", "published")
        if column in baseline_df.columns and column in repaired_df.columns
    ]
    baseline_by_id = baseline_df.assign(_paper_id=baseline_df["paper_id"].map(_text)).drop_duplicates("_paper_id")
    repaired_by_id = repaired_df.assign(_paper_id=repaired_df["paper_id"].map(_text)).drop_duplicates("_paper_id")
    baseline_by_id = baseline_by_id.set_index("_paper_id")
    repaired_by_id = repaired_by_id.set_index("_paper_id")
    common_ids = sorted(baseline_ids & repaired_ids)
    field_mismatch_counts: dict[str, int] = {}
    for column in comparable_columns:
        baseline_values = baseline_by_id.reindex(common_ids)[column].map(_text)
        repaired_values = repaired_by_id.reindex(common_ids)[column].map(_text)
        field_mismatch_counts[column] = int((baseline_values != repaired_values).sum())
    same_core_fields = all(count == 0 for count in field_mismatch_counts.values())

    repaired_is_clean = (
        repaired_quality["duplicate_paper_id_rows"] == 0
        and repaired_quality.get("blank_summary_rows", 0) == 0
    )

    return {
        "raw_snapshot_path": str(Path(raw_records_path)),
        "raw_snapshot_exists": Path(raw_records_path).is_file(),
        "repair_method": "load_raw_records(raw snapshot) -> build_clean_dataframe",
        "freshness_threshold_days": freshness_threshold_days,
        "baseline": baseline_quality,
        "repaired": repaired_quality,
        "missing_paper_ids_vs_baseline": sorted(baseline_ids - repaired_ids),
        "unexpected_paper_ids_vs_baseline": sorted(repaired_ids - baseline_ids),
        "same_row_count_as_baseline": same_row_count,
        "same_paper_id_set_as_baseline": same_paper_ids,
        "field_mismatch_counts_vs_baseline": field_mismatch_counts,
        "same_core_fields_as_baseline": same_core_fields,
        "repaired_is_clean": repaired_is_clean,
        "repaired_is_close_to_baseline": (
            same_row_count and same_paper_ids and same_core_fields and repaired_is_clean
        ),
    }


def append_repair_evidence(corruption_log_path, evidence: dict[str, Any]) -> None:
    """Attach actual raw-snapshot repair evidence to the corruption manifest."""
    log_path = Path(corruption_log_path)
    payload = read_json(log_path)
    payload["repair_evidence"] = evidence
    write_json(log_path, payload)


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Return a deterministic corrupted copy of a cleaned dataset.

    The input dataframe is never mutated.  The caller is responsible for
    persisting the returned dataframe to the dedicated *corrupted* paths; the
    manifest is persisted here because it is part of the corruption operation.
    Repair must be performed separately by re-cleaning the trusted raw snapshot,
    never by editing this returned dataframe.
    """
    required_columns = {"paper_id", "title", "summary", "published"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot corrupt cleaned data; missing columns: {', '.join(missing_columns)}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty cleaned dataframe.")

    # Work only on a deep copy: baseline data and the raw snapshot remain intact.
    corrupted = df.copy(deep=True)
    operations: list[dict[str, Any]] = []

    # 1. Remove up to two newest records, but retain at least three documents so
    # downstream retrieval/evaluation still has a corpus to inspect.
    published_for_sort = pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
    latest_indices = (
        corrupted.assign(_published_for_sort=published_for_sort)
        .sort_values(["_published_for_sort", "paper_id"], ascending=[False, True], na_position="last")
        .index.tolist()
    )
    drop_count = min(2, max(0, len(corrupted) - 3))
    for row_index in latest_indices[:drop_count]:
        row = corrupted.loc[row_index]
        operations.append(
            {
                "type": "drop_latest_record",
                "paper_id": _paper_id(row, row_index),
                "field": None,
                "old_value": {"published": _text(row["published"]), "title": _text(row["title"])},
                "new_value": None,
            }
        )
    if drop_count:
        corrupted = corrupted.drop(index=latest_indices[:drop_count]).copy()

    # Select remaining rows deterministically by paper_id, rather than randomly,
    # so a rerun produces an auditable and reproducible corruption manifest.
    stable_indices = corrupted.sort_values("paper_id", kind="stable").index.tolist()

    # 2. Remove summaries from two documents (or fewer for a tiny dataset).
    blank_count = min(2, len(stable_indices))
    for row_index in stable_indices[:blank_count]:
        old_summary = _text(corrupted.at[row_index, "summary"])
        corrupted.at[row_index, "summary"] = ""
        operations.append(
            {
                "type": "blank_summary",
                "paper_id": _paper_id(corrupted.loc[row_index], row_index),
                "field": "summary",
                "old_length": len(old_summary),
                "new_length": 0,
            }
        )

    # 3. Put obvious non-semantic noise into a different summary when possible.
    if len(stable_indices) >= 3:
        row_index = stable_indices[2]
        old_summary = _text(corrupted.at[row_index, "summary"])
        noise = " [CORRUPTED_NOISE: ### synthetic-indexing-noise ###]"
        corrupted.at[row_index, "summary"] = f"{old_summary}{noise}".strip()
        operations.append(
            {
                "type": "inject_summary_noise",
                "paper_id": _paper_id(corrupted.loc[row_index], row_index),
                "field": "summary",
                "old_length": len(old_summary),
                "new_length": len(_text(corrupted.at[row_index, "summary"])),
                "marker": "[CORRUPTED_NOISE]",
            }
        )

    # 4. Truncate a title to simulate a damaged metadata field.
    if len(stable_indices) >= 4:
        row_index = stable_indices[3]
        old_title = _text(corrupted.at[row_index, "title"])
        new_title = old_title[:20].rstrip() or "[truncated]"
        corrupted.at[row_index, "title"] = new_title
        operations.append(
            {
                "type": "truncate_title",
                "paper_id": _paper_id(corrupted.loc[row_index], row_index),
                "field": "title",
                "old_value": old_title,
                "new_value": new_title,
            }
        )

    # 5. Make one record unambiguously stale (two years old) and update its
    # derived age_days value below.
    if len(stable_indices) >= 1:
        row_index = stable_indices[-1]
        old_published = _text(corrupted.at[row_index, "published"])
        stale_timestamp = pd.Timestamp(datetime.now(UTC).date(), tz="UTC") - pd.Timedelta(days=730)
        if pd.api.types.is_datetime64_any_dtype(corrupted["published"]):
            new_published: Any = stale_timestamp
        else:
            new_published = stale_timestamp.date().isoformat()
        corrupted.at[row_index, "published"] = new_published
        operations.append(
            {
                "type": "make_publication_stale",
                "paper_id": _paper_id(corrupted.loc[row_index], row_index),
                "field": "published",
                "old_value": old_published,
                "new_value": _text(new_published),
                "stale_after_days": 730,
            }
        )

    # 6. Append an exact duplicate.  Keeping the same paper_id deliberately
    # triggers the uniqueness quality check while retaining an auditable source.
    duplicate_source_index = stable_indices[0]
    duplicate = corrupted.loc[[duplicate_source_index]].copy(deep=True)
    duplicate_paper_id = _paper_id(duplicate.iloc[0], duplicate_source_index)
    corrupted = pd.concat([corrupted, duplicate], ignore_index=True)
    operations.append(
        {
            "type": "duplicate_record",
            "paper_id": duplicate_paper_id,
            "field": "paper_id",
            "source_row_index": str(duplicate_source_index),
            "duplicate_count_added": 1,
        }
    )

    corrupted = _refresh_derived_fields(corrupted)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "input_rows": len(df),
        "output_rows": len(corrupted),
        "row_delta": len(corrupted) - len(df),
        "input_dataframe_mutated": False,
        "operations": operations,
        "affected_paper_ids": sorted({operation["paper_id"] for operation in operations}),
        "repair_evidence_requirement": {
            "source": "data/raw/crossref_records.json",
            "method": "load_raw_records(...) followed by build_clean_dataframe(...)",
            "prohibited": "Do not repair by editing the corrupted dataframe, test set, answers, or metrics.",
        },
    }
    write_json(Path(output_log_path), manifest)
    return corrupted
