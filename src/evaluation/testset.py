from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS_REQUIRED = 3
MAX_SAMPLE_PAPERS = 12


def _make_question(question_type: str, row: pd.Series) -> tuple[str, str] | None:
    title = row["title"]
    if question_type == "summary":
        ground_truth = first_sentence(row["summary"])
        if not ground_truth:
            return None
        return f"What is the paper '{title}' about?", ground_truth
    if question_type == "authors":
        if not row["authors_joined"]:
            return None
        return f"Who authored the paper '{title}'?", row["authors_joined"]
    if question_type == "date":
        if not row["published"]:
            return None
        return f"When was the paper '{title}' published?", row["published"]
    if question_type == "categories":
        if not row["categories_joined"]:
            return None
        return f"What categories does the paper '{title}' belong to?", row["categories_joined"]
    return None


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build an evaluation set of question/ground-truth pairs from the cleaned dataframe."""
    if len(df) < MIN_DOCUMENTS_REQUIRED:
        raise ValueError(
            f"Need at least {MIN_DOCUMENTS_REQUIRED} clean documents to build a test set, got {len(df)}."
        )

    sample_df = df.head(MAX_SAMPLE_PAPERS)
    question_types = ["summary", "authors", "date", "categories"]

    samples: list[dict[str, Any]] = []
    sample_id = 0
    for _, row in sample_df.iterrows():
        for question_type in question_types:
            made = _make_question(question_type, row)
            if made is None:
                continue
            question, ground_truth = made
            samples.append(
                {
                    "id": f"q{sample_id:04d}",
                    "question_type": question_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": [row["paper_id"]],
                }
            )
            sample_id += 1

    write_json(output_path, samples)
    return samples
