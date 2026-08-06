from __future__ import annotations

from typing import Any

from core.utils import write_text


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _checks_table(checks: list[dict[str, Any]]) -> str:
    lines = ["| Check | Status | Detail |", "| --- | --- | --- |"]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"| {check['name']} | {status} | {check['detail']} |")
    return "\n".join(lines)


def _metrics_table(metrics: dict[str, Any]) -> str:
    lines = ["| Metric | Value |", "| --- | --- |"]
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        if key in metrics:
            lines.append(f"| {key} | {_fmt(metrics[key])} |")
    return "\n".join(lines)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline (phase 1) markdown report."""
    lines = [
        "# Phase 1 Baseline Report",
        "",
        "## Source",
        "",
        f"- Source API: {source_summary.get('source_api')}",
        f"- Query: {source_summary.get('source_query')}",
        f"- Filter: {source_summary.get('source_filter')}",
        f"- Max results requested: {source_summary.get('max_results')}",
        f"- Raw records fetched: {source_summary.get('record_count')}",
        f"- Clean rows kept: {source_summary.get('clean_row_count')}",
        "",
        "## Evaluation Metrics",
        "",
        _metrics_table(metrics),
        "",
        f"Ragas: `{metrics.get('ragas')}`",
        "",
        "## Data Quality",
        "",
        f"Overall success: **{quality.get('success')}** (row_count={quality.get('row_count')})",
        "",
        _checks_table(quality.get("checks", [])),
        "",
        "## Freshness",
        "",
        f"- Latest published: {freshness.get('latest_published')}",
        f"- Oldest published: {freshness.get('oldest_published')}",
        f"- Stale rows: {freshness.get('stale_rows')} / {freshness.get('total_rows')} "
        f"({_fmt(freshness.get('stale_rate', 0.0), 2)} rate)",
        f"- Freshness threshold (days): {freshness.get('freshness_threshold_days')}",
        f"- Is fresh: **{freshness.get('is_fresh')}**",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def _delta(baseline: float | None, other: float | None) -> str:
    if baseline is None or other is None:
        return "n/a"
    return f"{other - baseline:+.4f}"


def _comparison_metrics_table(
    baseline_metrics: dict[str, Any], corrupted_metrics: dict[str, Any], repaired_metrics: dict[str, Any]
) -> str:
    keys = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]
    lines = [
        "| Metric | Baseline | Corrupted | Delta (Corrupted) | Repaired | Delta (Repaired) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for key in keys:
        base_val = baseline_metrics.get(key)
        corrupt_val = corrupted_metrics.get(key)
        repair_val = repaired_metrics.get(key)
        lines.append(
            f"| {key} | {_fmt(base_val)} | {_fmt(corrupt_val)} | {_delta(base_val, corrupt_val)} "
            f"| {_fmt(repair_val)} | {_delta(base_val, repair_val)} |"
        )
    return "\n".join(lines)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write the baseline vs corrupted vs repaired comparison markdown report."""
    lines = [
        "# Corruption Impact & Repair Comparison Report",
        "",
        "## Evaluation Metrics Comparison",
        "",
        _comparison_metrics_table(baseline_metrics, corrupted_metrics, repaired_metrics),
        "",
        "## Data Quality",
        "",
        "### Corrupted",
        "",
        f"Overall success: **{corrupted_quality.get('success')}** (row_count={corrupted_quality.get('row_count')})",
        "",
        _checks_table(corrupted_quality.get("checks", [])),
        "",
        "### Repaired",
        "",
        f"Overall success: **{repaired_quality.get('success')}** (row_count={repaired_quality.get('row_count')})",
        "",
        _checks_table(repaired_quality.get("checks", [])),
        "",
        "## Freshness",
        "",
        "| | Corrupted | Repaired |",
        "| --- | --- | --- |",
        f"| Latest published | {corrupted_freshness.get('latest_published')} | {repaired_freshness.get('latest_published')} |",
        f"| Stale rows | {corrupted_freshness.get('stale_rows')}/{corrupted_freshness.get('total_rows')} | "
        f"{repaired_freshness.get('stale_rows')}/{repaired_freshness.get('total_rows')} |",
        f"| Is fresh | {corrupted_freshness.get('is_fresh')} | {repaired_freshness.get('is_fresh')} |",
        "",
        "## Conclusion",
        "",
        "- Corruption reduces retrieval/answer quality relative to baseline (see deltas above; "
        "negative deltas in the Corrupted column indicate degraded performance).",
        "- Repairing from the trusted raw snapshot restores metrics back toward baseline levels "
        "(see the Repaired column deltas, which should be near zero).",
        "",
    ]
    write_text(report_path, "\n".join(lines))
