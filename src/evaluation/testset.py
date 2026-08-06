from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, safe_slug, write_json


_MIN_SAMPLES = 5
_MAX_SAMPLES = 10
_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def _required_text(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value).strip()


def _make_question(
    paper_id: str,
    question_type: str,
    question: str,
    ground_truth: str,
    ordinal: int,
) -> dict[str, Any]:
    return {
        "id": f"baseline-{safe_slug(paper_id)}-{question_type}-{ordinal:02d}",
        "question_type": question_type,
        "question": question,
        "ground_truth": ground_truth,
        "ground_truth_doc_ids": [paper_id],
    }


def _candidate_questions(df: pd.DataFrame) -> dict[str, deque[dict[str, Any]]]:
    """Create only factual prompts whose answers are fields in the clean dataframe."""
    candidates: dict[str, deque[dict[str, Any]]] = {
        "summary": deque(),
        "authors": deque(),
        "date": deque(),
        "categories": deque(),
    }
    for ordinal, (_, row) in enumerate(df.iterrows(), start=1):
        paper_id = _required_text(row, "paper_id")
        title = _required_text(row, "title")
        summary_truth = first_sentence(_required_text(row, "summary"))
        candidates["summary"].append(
            _make_question(
                paper_id,
                "summary",
                f"What does the paper '{title}' describe?",
                summary_truth,
                ordinal,
            )
        )

        authors = _required_text(row, "authors_joined")
        if authors:
            candidates["authors"].append(
                _make_question(
                    paper_id,
                    "authors",
                    f"Who authored '{title}'?",
                    authors,
                    ordinal,
                )
            )

        published = _required_text(row, "published")
        if published:
            candidates["date"].append(
                _make_question(
                    paper_id,
                    "date",
                    f"When was '{title}' published?",
                    published,
                    ordinal,
                )
            )

        categories = _required_text(row, "categories_joined")
        if categories:
            candidates["categories"].append(
                _make_question(
                    paper_id,
                    "categories",
                    f"What categories are assigned to '{title}'?",
                    categories,
                    ordinal,
                )
            )
    return candidates


def _validate_test_set(samples: list[dict[str, Any]], baseline_ids: set[str]) -> None:
    if not _MIN_SAMPLES <= len(samples) <= _MAX_SAMPLES:
        raise ValueError(f"Test set must contain {_MIN_SAMPLES}-{_MAX_SAMPLES} samples, got {len(samples)}.")

    required_keys = {"id", "question_type", "question", "ground_truth", "ground_truth_doc_ids"}
    sample_ids: set[str] = set()
    for sample in samples:
        missing = required_keys - set(sample)
        if missing:
            raise ValueError(f"Test-set sample is missing keys: {', '.join(sorted(missing))}")
        scalar_keys = required_keys - {"ground_truth_doc_ids"}
        if not all(isinstance(sample[key], str) and sample[key].strip() for key in scalar_keys):
            raise ValueError("Each test-set sample must have non-empty id, type, question, and ground truth.")
        if sample["id"] in sample_ids:
            raise ValueError(f"Duplicate test-set id: {sample['id']}")
        sample_ids.add(sample["id"])
        doc_ids = sample["ground_truth_doc_ids"]
        if not isinstance(doc_ids, list) or not doc_ids:
            raise ValueError("ground_truth_doc_ids must be a non-empty list.")
        unknown_ids = set(map(str, doc_ids)) - baseline_ids
        if unknown_ids:
            raise ValueError(f"Ground-truth IDs do not exist in baseline clean data: {sorted(unknown_ids)}")


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create and freeze a 5-10 sample factual evaluation set from baseline clean data.

    If ``output_path`` already exists, its contents are returned unchanged. This keeps
    corrupted and repaired evaluations on the same baseline questions instead of
    silently creating a new evaluation target.
    """
    destination = Path(output_path)
    if destination.exists():
        existing = read_json(destination)
        if not isinstance(existing, list):
            raise ValueError(f"Frozen test set must be a JSON list: {destination}")
        return existing

    missing_columns = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {', '.join(missing_columns)}")
    if len(df) < 2:
        raise ValueError("At least two clean papers are required to create a factual evaluation set.")

    baseline = df.copy()
    baseline["paper_id"] = baseline["paper_id"].astype(str).str.strip()
    baseline = baseline[baseline["paper_id"].ne("")].copy()
    if baseline["paper_id"].duplicated().any():
        raise ValueError("Baseline clean dataframe must have unique paper_id values.")
    baseline = baseline.sort_values(by=["paper_id", "title"], kind="stable").reset_index(drop=True)
    baseline_ids = set(baseline["paper_id"])

    candidates = _candidate_questions(baseline)
    samples: list[dict[str, Any]] = []
    # Round-robin avoids a test set made entirely of one question type or one paper.
    while len(samples) < _MAX_SAMPLES and any(candidates.values()):
        for question_type in ("summary", "authors", "date", "categories"):
            if candidates[question_type] and len(samples) < _MAX_SAMPLES:
                samples.append(candidates[question_type].popleft())

    _validate_test_set(samples, baseline_ids)
    write_json(destination, samples)
    return samples
