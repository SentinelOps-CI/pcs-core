"""ReleaseChainValidationResult.v0 builder for pcs validate-release-chain."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.protocol_fixtures import PCS_CORE_COMMIT, PCS_CORE_REPO, RELEASE_ID
from pcs_core.release_chain import ReleaseChainIssue, validate_release_chain
from pcs_core.release_chain_checks import (
    RELEASE_CHAIN_CHECK_COUNT,
    build_checks_from_issues,
)
from pcs_core.release_fixtures import MANIFEST_ARTIFACTS, MANIFEST_NAME

RELEASE_CANDIDATE_ID = "pcs-v0.1.0-rc1"
VALIDATOR = "pcs-core"
VALIDATOR_VERSION = "0.1.0"
VALIDATION_ID = "validation-pcs-v0.1-labtrust-qc-rc"


def _release_candidate(directory: Path) -> str:
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        return RELEASE_CANDIDATE_ID
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return RELEASE_CANDIDATE_ID
    if isinstance(manifest, dict):
        value = manifest.get("release_candidate")
        if isinstance(value, str) and value:
            return value
    return RELEASE_CANDIDATE_ID


def build_release_chain_validation_result(directory: Path) -> dict[str, Any]:
    """Build a schema-oriented ReleaseChainValidationResult.v0 document."""
    base = directory.resolve()
    issues = validate_release_chain(base)
    checks = build_checks_from_issues(issues)
    failure_codes = sorted({issue.code for issue in issues})
    has_failed = any(check["status"] == "failed" for check in checks)
    has_warning_only = (
        not has_failed
        and bool(issues) is False
        and any(check["status"] == "warning" for check in checks)
    )
    if not issues:
        status = "ProofChecked"
    elif has_failed:
        status = "Rejected"
    elif has_warning_only:
        status = "ProofChecked"
    else:
        status = "ProofChecked"

    body: dict[str, Any] = {
        "schema_version": "v0",
        "validation_id": VALIDATION_ID,
        "release_id": RELEASE_ID,
        "release_candidate": _release_candidate(base),
        "validator": VALIDATOR,
        "validator_version": VALIDATOR_VERSION,
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": status,
        "checks": checks,
        "artifacts_checked": len(MANIFEST_ARTIFACTS),
        "failure_codes": failure_codes,
        "source_repo": PCS_CORE_REPO,
        "source_commit": PCS_CORE_COMMIT,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    body["signature_or_digest"] = canonical_hash(body)
    return body


def build_release_chain_report(directory: Path) -> dict[str, Any]:
    """Backward-compatible summary derived from ReleaseChainValidationResult.v0."""
    result = build_release_chain_validation_result(directory)
    checks = result.get("checks")
    if not isinstance(checks, list):
        checks = []
    checks_passed = sum(1 for check in checks if check.get("status") == "passed")
    checks_failed = sum(1 for check in checks if check.get("status") == "failed")
    failure_codes = result.get("failure_codes")
    if isinstance(failure_codes, list) and failure_codes:
        summary: dict[str, Any] = {
            "status": "failed",
            "release_candidate": result.get("release_candidate", RELEASE_CANDIDATE_ID),
            "checked_artifacts": result.get("artifacts_checked", len(MANIFEST_ARTIFACTS)),
            "checks_passed": checks_passed,
            "checks_failed": checks_failed,
            "failure_code": failure_codes[0],
            "message": _first_failed_message(checks),
        }
        if len(failure_codes) > 1:
            summary["failures"] = [
                {"failure_code": code, "message": code} for code in failure_codes[1:]
            ]
        return summary
    return {
        "status": "passed",
        "release_candidate": result.get("release_candidate", RELEASE_CANDIDATE_ID),
        "checked_artifacts": result.get("artifacts_checked", len(MANIFEST_ARTIFACTS)),
        "checks_passed": RELEASE_CHAIN_CHECK_COUNT,
        "checks_failed": 0,
    }


def _first_failed_message(checks: list[dict[str, Any]]) -> str:
    for check in checks:
        if check.get("status") == "failed":
            details = check.get("details")
            if isinstance(details, dict) and details.get("message"):
                return str(details["message"])
    return "release chain validation failed"


def write_release_chain_validation_result(directory: Path, out_path: Path) -> dict[str, Any]:
    result = build_release_chain_validation_result(directory)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
