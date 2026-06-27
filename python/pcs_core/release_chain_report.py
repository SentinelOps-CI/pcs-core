"""ReleaseChainValidationResult.v0 builder for pcs validate-release-chain."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pcs_core.computation_release_chain import COMPUTATION_MANIFEST_ARTIFACTS
from pcs_core.hash import PLACEHOLDER_DIGEST, canonical_hash
from pcs_core.protocol_fixtures import PCS_CORE_COMMIT, PCS_CORE_REPO, RELEASE_ID
from pcs_core.registry_semantics import (
    audit_release_chain_registry_coverage,
    build_deferred_registry_checks,
)
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_chain_checks import (
    RELEASE_CHAIN_CHECK_COUNT,
    build_checks_from_issues,
)
from pcs_core.release_chain_profiles import (
    COMPUTATION_WORKFLOW_PROFILE_ID,
    LABTRUST_WORKFLOW_PROFILE_ID,
    TOOL_USE_WORKFLOW_PROFILE_ID,
    detect_workflow_profile_id,
    is_computation_release_directory,
    is_tool_use_release_directory,
)
from pcs_core.release_fixtures import MANIFEST_ARTIFACTS, MANIFEST_NAME
from pcs_core.tool_use_release_chain import TOOL_USE_MANIFEST_ARTIFACTS

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


def _legacy_manifest_checked_at(directory: Path) -> str | None:
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(manifest, dict):
        generated_at = manifest.get("generated_at")
        if isinstance(generated_at, str) and generated_at:
            return generated_at
    return None


def _legacy_manifest_pcs_core_commit(directory: Path) -> str:
    manifest_path = directory / MANIFEST_NAME
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = None
        if isinstance(manifest, dict):
            commit = manifest.get("pcs_core_commit")
            if isinstance(commit, str) and commit:
                return commit
    return PCS_CORE_COMMIT


def build_release_chain_validation_result(
    directory: Path,
    *,
    checked_at: str | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Build a schema-oriented ReleaseChainValidationResult.v0 document."""
    base = directory.resolve()
    profile_id = detect_workflow_profile_id(base) or LABTRUST_WORKFLOW_PROFILE_ID
    issues = validate_release_chain(base)
    checks = build_checks_from_issues(issues)
    validation_id = VALIDATION_ID
    release_id = RELEASE_ID
    deferred_registry_checks: list[dict[str, Any]] | None = None
    if not issues:
        result_path = base / "release_chain_validation_result.v0.json"
        profile_matches_on_disk = (
            is_tool_use_release_directory(base) and profile_id == TOOL_USE_WORKFLOW_PROFILE_ID
        ) or (
            is_computation_release_directory(base) and profile_id == COMPUTATION_WORKFLOW_PROFILE_ID
        )
        if (
            profile_id == LABTRUST_WORKFLOW_PROFILE_ID
            and profile_matches_on_disk
            and result_path.is_file()
        ):
            try:
                on_disk = json.loads(result_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                on_disk = None
            if isinstance(on_disk, dict) and on_disk.get("workflow_profile_id") == profile_id:
                on_disk_checks = on_disk.get("checks")
                if isinstance(on_disk_checks, list) and on_disk_checks:
                    checks = on_disk_checks
                on_disk_deferred = on_disk.get("deferred_registry_checks")
                if isinstance(on_disk_deferred, list):
                    deferred_registry_checks = on_disk_deferred
                on_disk_id = on_disk.get("validation_id")
                if isinstance(on_disk_id, str) and on_disk_id:
                    validation_id = on_disk_id
                on_disk_release = on_disk.get("release_id")
                if isinstance(on_disk_release, str) and on_disk_release:
                    release_id = on_disk_release
    from pcs_core.workflow_profiles import required_release_blocking_refs_for_profile

    required_refs = required_release_blocking_refs_for_profile(profile_id)
    if deferred_registry_checks is None:
        deferred_registry_checks = build_deferred_registry_checks(
            checks,
            required_refs=required_refs,
        )
    coverage_errors = audit_release_chain_registry_coverage(
        checks,
        deferred_registry_checks,
        required_refs=required_refs,
    )
    failure_codes = sorted({issue.code for issue in issues})
    if coverage_errors:
        failure_codes = sorted(set(failure_codes) | {"registry_check_coverage_gap"})
    has_failed = any(check["status"] == "failed" for check in checks)
    has_warning_only = (
        not has_failed
        and bool(issues) is False
        and any(check["status"] == "warning" for check in checks)
    )
    if coverage_errors:
        status = "Rejected"
    elif not issues:
        status = "ProofChecked"
    elif has_failed:
        status = "Rejected"
    elif has_warning_only:
        status = "ProofChecked"
    else:
        status = "ProofChecked"

    if checked_at is None:
        checked_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if source_commit is None:
        source_commit = _legacy_manifest_pcs_core_commit(base)

    if profile_id == COMPUTATION_WORKFLOW_PROFILE_ID:
        artifacts_checked = len(COMPUTATION_MANIFEST_ARTIFACTS)
    elif profile_id == TOOL_USE_WORKFLOW_PROFILE_ID:
        artifacts_checked = len(TOOL_USE_MANIFEST_ARTIFACTS)
    else:
        artifacts_checked = len(MANIFEST_ARTIFACTS)

    formal_checks: list[dict[str, Any]] | None = None
    lean_result_path = base / "lean_check_result.v0.json"
    if lean_result_path.is_file():
        try:
            lean_result = json.loads(lean_result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            lean_result = None
        if isinstance(lean_result, dict):
            from pcs_core.lean_trust import formal_checks_from_lean_result

            mapped = formal_checks_from_lean_result(lean_result)
            if mapped:
                formal_checks = mapped

    body: dict[str, Any] = {
        "schema_version": "v0",
        "validation_id": validation_id,
        "release_id": release_id,
        "release_candidate": _release_candidate(base),
        "workflow_profile_id": profile_id,
        "validator": VALIDATOR,
        "validator_version": VALIDATOR_VERSION,
        "checked_at": checked_at,
        "status": status,
        "checks": checks,
        "deferred_registry_checks": deferred_registry_checks,
        "artifacts_checked": artifacts_checked,
        "failure_codes": failure_codes,
        "source_repo": PCS_CORE_REPO,
        "source_commit": source_commit,
        "signature_or_digest": PLACEHOLDER_DIGEST,
    }
    if formal_checks is not None:
        body["formal_checks"] = formal_checks
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
