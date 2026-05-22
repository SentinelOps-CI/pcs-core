"""Machine-readable conformance suite reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash


def suite_result(
    name: str,
    errors: list[str],
    warnings: list[str] | None = None,
    *,
    checks_run: int = 1,
) -> dict[str, Any]:
    return {
        "suite": name,
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": warnings or [],
        "checks_run": checks_run,
    }


def build_conformance_report(
    *,
    suite: str,
    suite_results: list[dict[str, Any]],
) -> dict[str, Any]:
    checks_passed = sum(
        int(item.get("checks_run", 1)) for item in suite_results if item.get("status") == "passed"
    )
    checks_failed = sum(
        int(item.get("checks_run", 1)) for item in suite_results if item.get("status") == "failed"
    )
    failures: list[dict[str, str]] = []
    for item in suite_results:
        if item.get("status") != "failed":
            continue
        suite_name = str(item.get("suite", suite))
        for error in item.get("errors", []):
            failures.append({"suite": suite_name, "message": str(error)})
    body: dict[str, Any] = {
        "schema_version": "v0",
        "suite": suite,
        "status": "failed" if failures else "passed",
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        "failures": failures,
        "report_id": f"conformance-{suite}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "suites_run": len(suite_results),
        "results": suite_results,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body
