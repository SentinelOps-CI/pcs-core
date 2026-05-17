"""JSON report for pcs validate-release-chain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pcs_core.release_chain import ReleaseChainIssue, validate_release_chain
from pcs_core.release_fixtures import MANIFEST_ARTIFACTS, MANIFEST_NAME

RELEASE_CANDIDATE_ID = "pcs-v0.1.0-rc1"
RELEASE_CHAIN_CHECK_COUNT = 30


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


def _issue_failure_payload(issue: ReleaseChainIssue) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "failure_code": issue.code,
        "message": issue.message,
    }
    if issue.artifact is not None:
        payload["artifact"] = issue.artifact
    if issue.expected is not None:
        payload["expected"] = issue.expected
    if issue.actual is not None:
        payload["actual"] = issue.actual
    return payload


def build_release_chain_report(directory: Path) -> dict[str, Any]:
    """Build machine-readable pass/fail summary for a release fixture directory."""
    base = directory.resolve()
    release_candidate = _release_candidate(base)
    checked_artifacts = len(MANIFEST_ARTIFACTS)
    issues = validate_release_chain(base)

    if not issues:
        return {
            "status": "passed",
            "release_candidate": release_candidate,
            "checked_artifacts": checked_artifacts,
            "checks_passed": RELEASE_CHAIN_CHECK_COUNT,
            "checks_failed": 0,
        }

    checks_failed = len(issues)
    checks_passed = max(0, RELEASE_CHAIN_CHECK_COUNT - checks_failed)
    report: dict[str, Any] = {
        "status": "failed",
        "release_candidate": release_candidate,
        "checked_artifacts": checked_artifacts,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        **_issue_failure_payload(issues[0]),
    }
    if len(issues) > 1:
        report["failures"] = [_issue_failure_payload(issue) for issue in issues[1:]]
    return report
