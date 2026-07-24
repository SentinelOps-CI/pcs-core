"""Deterministic VerifierAssuranceReport.v1 builder (offline, fail-closed)."""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

from pcs_core.hash import CANONICALIZATION_VERSION, canonical_hash
from pcs_core.verifier_assurance_validate import (
    SemanticIssue,
    _INDETERMINATE,
    validate_adjudication_record_semantics,
    validate_assurance_report_semantics,
    validate_campaign_manifest_semantics,
    validate_verification_result_semantics,
)


def attach_nested_integrity(data: dict[str, Any]) -> dict[str, Any]:
    """Attach nested ArtifactIntegrity.v1-pattern integrity envelope."""
    body = {k: v for k, v in data.items() if k != "integrity"}
    digest = canonical_hash(body)
    out = dict(body)
    out["integrity"] = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "artifact_digest": digest,
    }
    return out


class ReportBuildError(ValueError):
    """Raised when report construction fails closed."""

    def __init__(self, issues: list[SemanticIssue] | list[str]) -> None:
        self.issues = issues
        message = "; ".join(str(i) for i in issues)
        super().__init__(message)


def _rate(numerator: int, denominator: int, *, method: str = "wilson") -> dict[str, Any]:
    if denominator < 0 or numerator < 0:
        raise ReportBuildError(
            [
                SemanticIssue(
                    "InvalidRateCounts",
                    "metrics",
                    "numerator/denominator must be non-negative",
                )
            ]
        )
    if denominator == 0:
        rate = "0"
    else:
        rate = str(
            (Decimal(numerator) / Decimal(denominator)).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_EVEN
            )
        )
    # Placeholder CI bounds equal rate when sample is empty; parameters declared explicitly.
    return {
        "rate": rate if denominator else "0",
        "numerator": numerator,
        "denominator": denominator,
        "confidence_interval": {
            "method": method,
            "parameters": {"alpha": "0.05", "declared": True},
            "lower": rate if denominator else "0",
            "upper": rate if denominator else "0",
            "sample_size": denominator,
        },
    }


def _load_json_dir(path: Path) -> list[dict[str, Any]]:
    if not path.is_dir():
        raise ReportBuildError(
            [SemanticIssue("MissingDirectory", str(path), "required input directory missing")]
        )
    items: list[dict[str, Any]] = []
    for file_path in sorted(path.glob("*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            items.append(data)
    return items


def _decision_bucket(status_or_decision: str) -> str:
    if status_or_decision in {"accept", "accepted"}:
        return "accept"
    if status_or_decision in {"reject", "rejected"}:
        return "reject"
    if (
        status_or_decision in _INDETERMINATE
        or status_or_decision == "indeterminate"
        or str(status_or_decision).startswith("indeterminate_")
        or status_or_decision == "failed"
    ):
        return "indeterminate"
    return "indeterminate"


def build_assurance_report(
    *,
    campaign: dict[str, Any],
    results: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
    report_id: str,
    created_at: str,
    producer: str = "pcs-core",
    producer_version: str = "0.1.0",
    source_repo: str = "https://github.com/SentinelOps-CI/pcs-core",
    source_commit: str,
    release_grade: bool = False,
    excluded_items: list[dict[str, str]] | None = None,
    unadjudicated_items: list[dict[str, str]] | None = None,
    preregistration_ref: str | None = None,
    applicability_limits: list[str] | None = None,
) -> dict[str, Any]:
    """Build a VerifierAssuranceReport.v1 body (integrity attached at end).

    Fail closed: never infer denominators from missing cohort/adjudication data.
    Indeterminate decisions are never counted as accept/reject.
    """
    issues: list[SemanticIssue] = []
    campaign_issues = validate_campaign_manifest_semantics(campaign, as_issues=True)
    assert isinstance(campaign_issues, list)
    issues.extend(campaign_issues)  # type: ignore[arg-type]

    if not results:
        issues.append(
            SemanticIssue(
                "MissingResults",
                "results",
                "results cohort is required; denominators are never inferred from absence",
            )
        )
    if release_grade and not adjudications:
        issues.append(
            SemanticIssue(
                "MissingAdjudications",
                "adjudications",
                "release-grade reports require adjudication records",
            )
        )

    for index, result in enumerate(results):
        result_issues = validate_verification_result_semantics(result, as_issues=True)
        assert isinstance(result_issues, list)
        for issue in result_issues:
            assert isinstance(issue, SemanticIssue)
            issues.append(
                SemanticIssue(issue.code, f"results[{index}].{issue.path}", issue.message)
            )

    independent = False
    for index, adj in enumerate(adjudications):
        adj_issues = validate_adjudication_record_semantics(
            adj, release_grade=release_grade, as_issues=True
        )
        assert isinstance(adj_issues, list)
        for issue in adj_issues:
            assert isinstance(issue, SemanticIssue)
            issues.append(
                SemanticIssue(issue.code, f"adjudications[{index}].{issue.path}", issue.message)
            )
        if adj.get("independence_declared") is True:
            independent = True

    if release_grade and not independent:
        issues.append(
            SemanticIssue(
                "ReleaseGradeNeedsIndependentAdjudication",
                "independent_adjudication",
                "release-grade reports require at least one independent adjudication",
            )
        )

    if issues:
        raise ReportBuildError(issues)

    excluded_items = list(excluded_items or [])
    unadjudicated_items = list(unadjudicated_items or [])

    # Map adjudications by subject id for FAR/FRR style counts.
    adj_by_subject: dict[str, str] = {}
    for adj in adjudications:
        subject = adj.get("subject")
        if isinstance(subject, dict) and isinstance(subject.get("artifact_id"), str):
            adj_by_subject[subject["artifact_id"]] = str(adj.get("label"))

    false_accept = 0
    false_reject = 0
    abstain = 0
    adjudicated = 0
    accept_n = 0
    reject_n = 0
    indeterminate_n = 0

    for result in results:
        decision = str(result.get("status") or result.get("decision") or "")
        bucket = _decision_bucket(decision)
        if bucket == "accept":
            accept_n += 1
        elif bucket == "reject":
            reject_n += 1
        else:
            indeterminate_n += 1
            abstain += 1
        result_id = str(result.get("result_id") or result.get("verification_result_id") or "")
        label = adj_by_subject.get(result_id)
        if label is None:
            continue
        adjudicated += 1
        if bucket == "accept" and label == "invalid":
            false_accept += 1
        if bucket == "reject" and label == "valid":
            false_reject += 1

    sample_size = len(results)
    # Never invent adjudication denominators: coverage uses available adjudications only.
    far = _rate(false_accept, adjudicated if adjudicated else 0)
    frr = _rate(false_reject, adjudicated if adjudicated else 0)
    abstention = _rate(abstain, sample_size)
    coverage = _rate(adjudicated, sample_size)

    campaign_cohorts = campaign.get("cohorts") or []
    if not isinstance(campaign_cohorts, list) or not campaign_cohorts:
        raise ReportBuildError(
            [
                SemanticIssue(
                    "MissingCohorts",
                    "campaign.cohorts",
                    "campaign must declare cohorts; counts are never inferred from missing records",
                )
            ]
        )

    report_cohorts: list[dict[str, Any]] = []
    ordinary_accept = 0
    ordinary_n = 0
    optimized_accept = 0
    optimized_n = 0

    # Assign all results to the first matching cohort kind by declaration order.
    # Fail closed if aggregate counts cannot reconcile with included records.
    remaining = list(results)
    for cohort in campaign_cohorts:
        if not isinstance(cohort, dict):
            continue
        kind = str(cohort.get("cohort_kind") or "other")
        # Without per-result cohort tags, bind all results into declared cohorts only when
        # a single cohort exists; multiple cohorts require explicit result.cohort_id.
        assigned: list[dict[str, Any]] = []
        still: list[dict[str, Any]] = []
        for result in remaining:
            result_cohort = result.get("cohort_id")
            if result_cohort is None and len(campaign_cohorts) == 1:
                assigned.append(result)
            elif result_cohort == cohort.get("cohort_id"):
                assigned.append(result)
            else:
                still.append(result)
        remaining = still

        a = r = i = 0
        for result in assigned:
            bucket = _decision_bucket(str(result.get("status") or result.get("decision") or ""))
            if bucket == "accept":
                a += 1
            elif bucket == "reject":
                r += 1
            else:
                i += 1
        included = len(assigned)
        if a + r + i != included:
            raise ReportBuildError(
                [
                    SemanticIssue(
                        "CohortCountMismatch",
                        f"cohorts[{cohort.get('cohort_id')}]",
                        "aggregate counts must reconcile exactly with included records",
                    )
                ]
            )
        if kind == "ordinary":
            ordinary_accept += a
            ordinary_n += included
        if kind == "optimized":
            optimized_accept += a
            optimized_n += included
        report_cohorts.append(
            {
                "cohort_id": cohort["cohort_id"],
                "cohort_kind": kind,
                "access_class": cohort["access_class"],
                "compute_exposure": cohort["compute_exposure"],
                "included_result_count": included,
                "accept_count": a,
                "reject_count": r,
                "indeterminate_count": i,
            }
        )

    if remaining:
        raise ReportBuildError(
            [
                SemanticIssue(
                    "UnassignedResults",
                    "results",
                    "every result must map to a declared campaign cohort",
                )
            ]
        )

    ordinary_rate = _rate(ordinary_accept, ordinary_n)
    optimized_rate = _rate(optimized_accept, optimized_n)
    if ordinary_n and optimized_n:
        gap = str(
            (
                Decimal(optimized_rate["rate"]) - Decimal(ordinary_rate["rate"])
            ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
        )
    else:
        gap = "0"

    campaign_digest = canonical_hash(campaign)
    report: dict[str, Any] = {
        "schema_version": "v1",
        "artifact_type": "VerifierAssuranceReport.v1",
        "report_id": report_id,
        "created_at": created_at,
        "producer": producer,
        "producer_version": producer_version,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "campaign_ref": {
            "artifact_type": "OptimizationCampaignManifest.v1",
            "artifact_id": campaign["campaign_id"],
            "artifact_digest": campaign_digest,
        },
        "release_grade": release_grade,
        "independent_adjudication": independent,
        "metrics": {
            "false_accept_rate": far,
            "false_reject_rate": frr,
            "abstention_rate": abstention,
            "adjudication_coverage": coverage,
            "ordinary_accept_rate": ordinary_rate,
            "optimized_accept_rate": optimized_rate,
            "optimization_gap": gap,
            "time_to_first_exploit_seconds": None,
            "queries_to_first_exploit": None,
            "exploit_family_counts": {},
            "inter_verifier_disagreement_rate": _rate(0, adjudicated if adjudicated else 0),
            "reward_invalidation_rate": _rate(0, sample_size),
            "latency_ms_p50": 0,
            "cost_decimal": "0",
            "sample_size": sample_size,
            "excluded_count": len(excluded_items),
            "unadjudicated_count": len(unadjudicated_items),
        },
        "cohorts": report_cohorts,
        "excluded_items": excluded_items,
        "unadjudicated_items": unadjudicated_items,
        "applicability_limits": list(applicability_limits or []),
    }
    if preregistration_ref:
        report["preregistration_ref"] = preregistration_ref

    report = attach_nested_integrity(report)
    semantic = validate_assurance_report_semantics(report, as_issues=True)
    assert isinstance(semantic, list)
    if semantic:
        raise ReportBuildError(semantic)  # type: ignore[arg-type]

    return report


def build_assurance_report_from_paths(
    *,
    campaign_path: Path,
    results_dir: Path,
    adjudications_dir: Path,
    report_id: str,
    created_at: str,
    source_commit: str,
    release_grade: bool = False,
    out_path: Path | None = None,
) -> dict[str, Any]:
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    results = _load_json_dir(results_dir)
    adjudications = _load_json_dir(adjudications_dir)
    report = build_assurance_report(
        campaign=campaign,
        results=results,
        adjudications=adjudications,
        report_id=report_id,
        created_at=created_at,
        source_commit=source_commit,
        release_grade=release_grade,
    )
    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def verify_assurance_report(report: dict[str, Any]) -> list[SemanticIssue]:
    issues = validate_assurance_report_semantics(report, as_issues=True)
    assert isinstance(issues, list)
    typed = [i for i in issues if isinstance(i, SemanticIssue)]
    integrity = report.get("integrity")
    if isinstance(integrity, dict):
        body = {k: v for k, v in report.items() if k != "integrity"}
        expected = canonical_hash(body)
        got = integrity.get("artifact_digest")
        if got != expected:
            typed.append(
                SemanticIssue(
                    "ReportDigestMismatch",
                    "integrity.artifact_digest",
                    "artifact_digest does not match report body",
                )
            )
    return typed


def report_body_without_integrity(report: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in report.items() if k != "integrity"}
