"""Metric ID coercion and MetricSummary.v0 construction for benchmark reports."""

from __future__ import annotations

from typing import Any

from pcs_core.benchmark_metric_registry_data import benchmark_metric_entries
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.protocol_fixtures import PCS_CORE_REPO

PCS_CORE_COMMIT_PLACEHOLDER = "d444444444444444444444444444444444444444"

_LEGACY_TO_METRIC_ID: dict[str, str] = {
    entry["legacy_metric_name"]: metric_id
    for metric_id, entry in benchmark_metric_entries().items()
    if entry.get("legacy_metric_name")
}

_STANDARD_METRIC_IDS: tuple[str, ...] = (
    "release_reproducibility_score",
    "failure_localization_accuracy",
    "certificate_completeness_score",
    "registry_coverage_score",
    "formal_check_coverage_score",
    "scientific_memory_interpretability_score",
)

_SUMMARY_FIELD_TO_METRIC_ID: dict[str, str] = {
    entry.get("summary_field", ""): metric_id
    for metric_id, entry in benchmark_metric_entries().items()
    if entry.get("summary_field")
}

_COVERAGE_KEY_TO_METRIC_ID: dict[str, str] = {
    "release_reproducibility": "release_reproducibility_score",
    "certificate_completeness": "certificate_completeness_score",
    "registry": "registry_coverage_score",
    "formal_checks": "formal_check_coverage_score",
    "scientific_memory": "scientific_memory_interpretability_score",
}


def coerce_metric_ids(metrics: list[Any]) -> list[str]:
    """Normalize legacy benchmark_metric_name values to benchmark_metric_id."""
    out: list[str] = []
    for item in metrics:
        if not isinstance(item, str):
            continue
        if item in benchmark_metric_entries():
            out.append(item)
        elif item in _LEGACY_TO_METRIC_ID:
            out.append(_LEGACY_TO_METRIC_ID[item])
        else:
            out.append(item)
    return out


def _metric_summary(
    *,
    metric_id: str,
    score: float,
    applicability: str,
    numerator: float,
    denominator: float,
    reason: str,
    details: dict[str, Any] | None = None,
    source_repo: str = PCS_CORE_REPO,
    source_commit: str = PCS_CORE_COMMIT_PLACEHOLDER,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "v0",
        "metric_id": metric_id,
        "score": min(1.0, max(0.0, score)),
        "applicability": applicability,
        "numerator": numerator,
        "denominator": denominator,
        "reason": reason,
        "details": details or {},
        "source_repo": source_repo,
        "source_commit": source_commit,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(
        {k: v for k, v in body.items() if k != "signature_or_digest"},
    )
    return body


def build_metric_summaries(
    *,
    metric_ids: list[str],
    summary: dict[str, Any],
    coverage: dict[str, Any],
    invalid_case_count: int,
    suite_id: str,
    source_repo: str = PCS_CORE_REPO,
    source_commit: str = PCS_CORE_COMMIT_PLACEHOLDER,
) -> list[dict[str, Any]]:
    """Build MetricSummary.v0 rows for a BenchmarkReport.v0."""
    summaries: list[dict[str, Any]] = []
    for metric_id in metric_ids:
        legacy = benchmark_metric_entries().get(metric_id, {}).get("legacy_metric_name")
        cov = None
        if legacy:
            cov = coverage.get(legacy)
        if not isinstance(cov, dict):
            for key, mid in _COVERAGE_KEY_TO_METRIC_ID.items():
                if mid == metric_id:
                    cov = coverage.get(key)
                    break

        if metric_id == "failure_localization_accuracy":
            denom = float(invalid_case_count)
            if denom <= 0:
                summaries.append(
                    _metric_summary(
                        metric_id=metric_id,
                        score=0.0,
                        applicability="insufficient_cases",
                        numerator=0.0,
                        denominator=0.0,
                        reason="no invalid benchmark cases in suite",
                        source_repo=source_repo,
                        source_commit=source_commit,
                    ),
                )
                continue
            score = float(summary.get("failure_localization_accuracy", 0.0))
            summaries.append(
                _metric_summary(
                    metric_id=metric_id,
                    score=score,
                    applicability="measured",
                    numerator=round(score * denom, 6),
                    denominator=denom,
                    reason="component alignment on invalid cases",
                    source_repo=source_repo,
                    source_commit=source_commit,
                ),
            )
            continue

        if metric_id == "repair_hint_quality_score":
            denom = float(invalid_case_count)
            if denom <= 0:
                summaries.append(
                    _metric_summary(
                        metric_id=metric_id,
                        score=0.0,
                        applicability="insufficient_cases",
                        numerator=0.0,
                        denominator=0.0,
                        reason="no invalid benchmark cases in suite",
                        source_repo=source_repo,
                        source_commit=source_commit,
                    ),
                )
                continue
            score = float(summary.get("repair_hint_accuracy", 0.0))
            summaries.append(
                _metric_summary(
                    metric_id=metric_id,
                    score=score,
                    applicability="measured",
                    numerator=round(score * denom, 6),
                    denominator=denom,
                    reason="repair hint alignment on invalid cases",
                    source_repo=source_repo,
                    source_commit=source_commit,
                ),
            )
            continue

        if metric_id == "cross_domain_portability_score":
            if suite_id != "cross-domain-release-chain-v0":
                summaries.append(
                    _metric_summary(
                        metric_id=metric_id,
                        score=0.0,
                        applicability="not_applicable",
                        numerator=0.0,
                        denominator=0.0,
                        reason=f"metric only measured for cross-domain-release-chain-v0 (suite={suite_id})",
                        source_repo=source_repo,
                        source_commit=source_commit,
                    ),
                )
                continue
            score = float(summary.get("cross_domain_portability_score", summary.get("registry_coverage", 0.0)))
            summaries.append(
                _metric_summary(
                    metric_id=metric_id,
                    score=score,
                    applicability="measured",
                    numerator=score,
                    denominator=1.0,
                    reason="cross-domain suite portability rollup",
                    source_repo=source_repo,
                    source_commit=source_commit,
                ),
            )
            continue

        if isinstance(cov, dict):
            num = float(cov.get("numerator", 0.0))
            den = float(cov.get("denominator", 0.0))
            ratio = float(cov.get("coverage_ratio", num / den if den else 0.0))
            summaries.append(
                _metric_summary(
                    metric_id=metric_id,
                    score=ratio,
                    applicability="measured" if den > 0 else "failed_to_measure",
                    numerator=num,
                    denominator=den,
                    reason=f"coverage from {cov.get('coverage_id', legacy or metric_id)}",
                    details={"coverage_id": cov.get("coverage_id")},
                    source_repo=str(cov.get("source_repo", source_repo)),
                    source_commit=str(cov.get("source_commit", source_commit)),
                ),
            )
            continue

        summary_key = benchmark_metric_entries().get(metric_id, {}).get("summary_field", "")
        if summary_key and summary_key in summary:
            score = float(summary[summary_key])
            summaries.append(
                _metric_summary(
                    metric_id=metric_id,
                    score=score,
                    applicability="measured",
                    numerator=score,
                    denominator=1.0,
                    reason=f"rollup from summary.{summary_key}",
                    source_repo=source_repo,
                    source_commit=source_commit,
                ),
            )
            continue

        summaries.append(
            _metric_summary(
                metric_id=metric_id,
                score=0.0,
                applicability="skipped",
                numerator=0.0,
                denominator=0.0,
                reason="no coverage or summary source for metric",
                source_repo=source_repo,
                source_commit=source_commit,
            ),
        )
    return summaries


def build_metric_summaries_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive metric summaries from an existing BenchmarkReport-shaped document."""
    suite_id = str(report.get("benchmark_suite_id", ""))
    metric_ids = coerce_metric_ids(report.get("metrics", []) if isinstance(report.get("metrics"), list) else [])
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    coverage = report.get("coverage") if isinstance(report.get("coverage"), dict) else {}
    invalid = int(summary.get("expected_failures_detected", 0)) + int(summary.get("unexpected_failures", 0))
    if invalid == 0:
        total = int(summary.get("total_cases", 0))
        passed = int(summary.get("passed_cases", 0))
        invalid = max(0, total - (total - passed))  # fallback
    return build_metric_summaries(
        metric_ids=metric_ids or list(_STANDARD_METRIC_IDS),
        summary=summary,
        coverage=coverage,
        invalid_case_count=invalid or max(0, int(summary.get("total_cases", 0)) - int(summary.get("passed_cases", 0))),
        suite_id=suite_id,
        source_repo=str(report.get("source_repo", PCS_CORE_REPO)),
        source_commit=str(report.get("source_commit", PCS_CORE_COMMIT_PLACEHOLDER)),
    )
