from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import write_text


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _lines_from_dict(payload: dict[str, Any] | None, empty_message: str) -> list[str]:
    if not payload:
        return [f"- {empty_message}"]
    return [f"- `{key}`: `{_fmt(value)}`" for key, value in payload.items()]


def _quality_lines(quality: dict[str, Any] | None) -> list[str]:
    if not quality:
        return ["- No quality report provided."]
    lines = [
        f"- Overall success: `{quality.get('success')}`",
        f"- Total rows: `{_fmt(quality.get('total_rows'))}`",
        f"- Failed checks: `{', '.join(quality.get('failed_checks') or []) or 'none'}`",
    ]
    metrics = quality.get("metrics") or {}
    for key in (
        "null_paper_ids",
        "null_paper_id_rate",
        "duplicate_paper_ids",
        "duplicate_paper_id_rate",
        "null_titles",
        "null_title_rate",
        "empty_summaries",
        "non_empty_short_summaries",
        "short_summaries",
        "short_summary_rate",
        "empty_embedding_text",
        "empty_embedding_text_rate",
        "negative_age_rows",
        "stale_rows",
        "stale_rate",
        "freshness_threshold_days",
    ):
        if key in metrics:
            lines.append(f"- `{key}`: `{_fmt(metrics[key])}`")
    return lines


def _freshness_lines(freshness: dict[str, Any] | None) -> list[str]:
    if not freshness:
        return ["- No freshness report provided."]
    keys = [
        "latest_published",
        "oldest_published",
        "stale_rows",
        "stale_rate",
        "total_rows",
        "missing_published",
        "missing_age_days",
        "negative_age_rows",
        "mean_age_days",
        "max_age_days",
        "freshness_threshold_days",
        "is_fresh",
    ]
    return [f"- `{key}`: `{_fmt(freshness.get(key))}`" for key in keys if key in freshness]


def _metric_lines(metrics: dict[str, Any] | None) -> list[str]:
    if not metrics:
        return ["- No evaluation metrics provided."]
    keys = [
        "samples",
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    ]
    lines = [f"- `{key}`: `{_fmt(metrics.get(key))}`" for key in keys if key in metrics]
    if "ragas" in metrics:
        lines.append(f"- `ragas`: `{metrics['ragas']}`")
    if not lines:
        lines = _lines_from_dict(metrics, "No evaluation metrics provided.")
    return lines


def _delta(before: Any, after: Any) -> str:
    try:
        return _fmt(float(after) - float(before))
    except (TypeError, ValueError):
        return "n/a"


def _quality_metric(quality: dict[str, Any] | None, key: str) -> Any:
    if not quality:
        return None
    if key in {"total_rows", "success"}:
        return quality.get(key)
    return (quality.get("metrics") or {}).get(key)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report cho baseline phase.

    Pseudo-code:
    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    quality_ok = bool(quality.get("success")) if quality else False
    freshness_ok = bool(freshness.get("is_fresh")) if freshness else False
    if quality_ok and freshness_ok:
        interpretation = [
            "- Baseline passed quality and freshness checks and can be frozen for corruption experiments.",
            "- Retrieval and answer metrics above are the reference for corrupted/repaired comparison.",
        ]
    else:
        interpretation = [
            "- Baseline did not pass all quality/freshness checks. Review failed checks before corruption.",
            "- Do not treat this run as a clean baseline until failed checks are fixed.",
        ]

    content = "\n".join(
        [
            "# Phase 1 Baseline Report",
            "",
            "## Source summary",
            *_lines_from_dict(source_summary, "No source summary provided."),
            "",
            "## Evaluation metrics",
            *_metric_lines(metrics),
            "",
            "## Data quality",
            *_quality_lines(quality),
            "",
            "## Freshness",
            *_freshness_lines(freshness),
            "",
            "## Interpretation",
            *interpretation,
            "",
        ]
    )
    write_text(Path(report_path), content)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    baseline_freshness: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report so sanh baseline/corrupted/repaired."""
    metric_keys = [
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    ]
    comparison_rows = [
        "| Metric | Baseline | Corrupted | Repaired | Corr-Base | Repair-Base | Repair-Corr |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in metric_keys:
        base = baseline_metrics.get(key) if baseline_metrics else None
        corr = corrupted_metrics.get(key) if corrupted_metrics else None
        rep = repaired_metrics.get(key) if repaired_metrics else None
        comparison_rows.append(
            f"| `{key}` | {_fmt(base)} | {_fmt(corr)} | {_fmt(rep)} | "
            f"{_delta(base, corr)} | {_delta(base, rep)} | {_delta(corr, rep)} |"
        )

    quality_keys = [
        ("total_rows", "Total rows"),
        ("duplicate_paper_ids", "Duplicate paper IDs"),
        ("short_summaries", "Short summaries"),
        ("empty_embedding_text", "Empty embedding text"),
        ("stale_rows", "Stale rows"),
        ("stale_rate", "Stale rate"),
    ]
    quality_rows = [
        "| Quality metric | Baseline | Corrupted | Repaired |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key, label in quality_keys:
        quality_rows.append(
            f"| {label} | {_fmt(_quality_metric(baseline_quality, key))} | "
            f"{_fmt(_quality_metric(corrupted_quality, key))} | "
            f"{_fmt(_quality_metric(repaired_quality, key))} |"
        )

    content = "\n".join(
        [
            "# Corruption Comparison Report",
            "",
            "## Evaluation metrics across states",
            *comparison_rows,
            "",
            "## Data quality across states",
            *quality_rows,
            "",
            "## Baseline quality",
            *_quality_lines(baseline_quality),
            "",
            "## Baseline freshness",
            *_freshness_lines(baseline_freshness),
            "",
            "## Corrupted quality",
            *_quality_lines(corrupted_quality),
            "",
            "## Corrupted freshness",
            *_freshness_lines(corrupted_freshness),
            "",
            "## Repaired quality",
            *_quality_lines(repaired_quality),
            "",
            "## Repaired freshness",
            *_freshness_lines(repaired_freshness),
            "",
            "## Interpretation",
            "- Corrupted data should degrade quality/freshness signals and usually retrieval/answer metrics.",
            "- Repaired data should move quality/freshness and evaluation metrics back toward baseline.",
            "- `Corr-Base` / `Repair-Base` compare each state to baseline; `Repair-Corr` shows recovery.",
            "- Keep the same frozen test set, ground truth, evaluator, and top-k across all three states.",
            "",
        ]
    )
    write_text(Path(report_path), content)
