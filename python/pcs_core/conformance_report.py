"""Machine-readable conformance suite reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash


def build_conformance_report(
    *,
    suite: str,
    suite_results: list[dict[str, Any]],
) -> dict[str, Any]:
    failed = sum(1 for item in suite_results if item.get("status") == "failed")
    body: dict[str, Any] = {
        "schema_version": "v0",
        "report_id": f"conformance-{suite}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "suite": suite,
        "status": "failed" if failed else "passed",
        "suites_run": len(suite_results),
        "suites_failed": failed,
        "results": suite_results,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body


def suite_result(name: str, errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "suite": name,
        "status": "failed" if errors else "passed",
        "errors": errors,
        "warnings": warnings or [],
        "checks_run": 1,
    }
