"""ConformanceRun.v0 bridge from pcs conformance suites."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pcs_core.conformance import SUITES, build_conformance_report_data
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.protocol_fixtures import PCS_CORE_REPO
from pcs_core.validate import validate_artifact

PCS_CORE_COMMIT_PLACEHOLDER = "d444444444444444444444444444444444444444"


def build_conformance_run(
    suite: str,
    *,
    report: dict[str, Any] | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> dict[str, Any]:
    """Build ConformanceRun.v0 from a conformance suite name or report payload."""
    if report is None:
        report = build_conformance_report_data(suite)
    if started_at is None:
        started_at = str(report.get("generated_at", datetime.now(UTC).isoformat()))
    if completed_at is None:
        completed_at = started_at
    failures = []
    for item in report.get("failures", []):
        if isinstance(item, dict):
            failures.append({"message": str(item.get("message", ""))})
        else:
            failures.append({"message": str(item)})
    run_id = f"conf-run-{suite}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    body: dict[str, Any] = {
        "schema_version": "v0",
        "run_id": run_id,
        "suite": suite if suite != "all" else str(report.get("suite", "all")),
        "status": str(report.get("status", "failed")),
        "checks_passed": int(report.get("checks_passed", 0)),
        "checks_failed": int(report.get("checks_failed", 0)),
        "failures": failures,
        "started_at": started_at,
        "completed_at": completed_at,
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_CORE_COMMIT_PLACEHOLDER,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(
        {k: v for k, v in body.items() if k != "signature_or_digest"},
    )
    validate_artifact(body, "ConformanceRun.v0")
    return body


def run_conformance_as_benchmark_input(suite: str) -> dict[str, Any]:
    if suite not in SUITES and suite != "all":
        raise ValueError(f"unknown conformance suite: {suite}")
    return build_conformance_run(suite)
