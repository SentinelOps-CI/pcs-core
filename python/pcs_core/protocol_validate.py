"""Semantic validation for PCS Phase 2 protocol artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_PATTERN_PLACEHOLDER = re.compile(r"^(?:a{40}|b{40}|c{40}|d{40}|e{40})$")


def _forbidden_commit(commit: str) -> str | None:
    stripped = commit.strip()
    if stripped == "0" * 40:
        return "zero source_commit"
    if _PATTERN_PLACEHOLDER.fullmatch(stripped):
        return "pattern placeholder source_commit"
    return None


def _scan_commit_fields(obj: Any, path: str, errors: list[str]) -> None:
    if isinstance(obj, dict):
        if obj.get("local_dev") is True:
            errors.append(f"{path or 'root'}: local_dev=true forbidden in release mode")
        for field in ("source_commit", "commit"):
            commit = obj.get(field)
            if isinstance(commit, str):
                reason = _forbidden_commit(commit)
                if reason:
                    errors.append(f"{path or 'root'}: {field} {reason}: {commit}")
        for key, value in obj.items():
            child = f"{path}.{key}" if path else key
            _scan_commit_fields(value, child, errors)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _scan_commit_fields(item, f"{path}[{index}]", errors)


def validate_release_manifest_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _scan_commit_fields(data.get("producer_repos"), "producer_repos", errors)
    artifacts = data.get("artifacts")
    if isinstance(artifacts, dict):
        for name, entry in artifacts.items():
            if isinstance(entry, dict):
                _scan_commit_fields(entry, f"artifacts.{name}", errors)
    status = data.get("release_status")
    if status == "Validated":
        for name, entry in (artifacts or {}).items():
            if isinstance(entry, dict) and not entry.get("sha256"):
                errors.append(f"artifacts.{name}: sha256 required when release_status is Validated")
        for field in (
            "chain_root",
            "release_chain_validation_result",
            "canonical_signed_bundle",
            "canonical_claim_id",
            "limitations_notice",
        ):
            if field not in data:
                errors.append(f"{field} required when release_status is Validated")
        chain_root = data.get("chain_root")
        if isinstance(chain_root, dict):
            for key in (
                "trace_hash",
                "certificate_id",
                "certified_bundle_hash",
                "signed_bundle_hash",
            ):
                if not chain_root.get(key):
                    errors.append(f"chain_root.{key} required when release_status is Validated")
        ref = data.get("release_chain_validation_result")
        if isinstance(ref, dict):
            digest = ref.get("sha256")
            if (
                isinstance(digest, str)
                and digest.startswith("sha256:")
                and digest.endswith(
                    "0" * 64,
                )
            ):
                errors.append(
                    "release_chain_validation_result.sha256 is a placeholder; "
                    "run just materialize-labtrust-protocol",
                )
    return errors


def validate_release_manifest_fixture_refs(
    data: dict[str, Any],
    base_dir: Path,
) -> list[str]:
    """Ensure release_chain_validation_result path digest matches on-disk bytes."""
    errors: list[str] = []
    ref = data.get("release_chain_validation_result")
    if not isinstance(ref, dict):
        return errors
    rel_path = ref.get("path")
    expected = ref.get("sha256")
    if not isinstance(rel_path, str) or not isinstance(expected, str):
        return errors
    artifact_path = base_dir / rel_path
    if not artifact_path.is_file():
        errors.append(
            f"release_chain_validation_result.path missing on disk: {rel_path}",
        )
        return errors
    from pcs_core.release_fixtures import file_digest

    actual = file_digest(artifact_path.read_bytes())
    if actual != expected:
        errors.append(
            "release_chain_validation_result.sha256 does not match file bytes "
            f"(expected {expected}, got {actual})",
        )
    return errors


def validate_handoff_manifest_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _scan_commit_fields(data, "", errors)
    status = data.get("status")
    if status == "Validated":
        inputs = data.get("input_artifacts")
        if isinstance(inputs, dict):
            for name, entry in inputs.items():
                if isinstance(entry, dict) and not entry.get("sha256"):
                    errors.append(
                        f"input_artifacts.{name}: sha256 required when handoff status is Validated",
                    )
    return errors


def validate_artifact_registry_semantics(data: dict[str, Any]) -> list[str]:
    from pcs_core.registry_data import all_registry_semantic_check_refs

    errors: list[str] = []
    all_registry_semantic_check_refs()
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return errors
    for artifact_type, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        schema_owner = entry.get("schema_owner")
        runtime_producer = entry.get("runtime_producer")
        allowed = entry.get("allowed_runtime_producers")
        if isinstance(runtime_producer, str) and isinstance(allowed, list):
            if runtime_producer not in allowed:
                errors.append(
                    f"entries.{artifact_type}: runtime_producer {runtime_producer!r} "
                    f"not in allowed_runtime_producers",
                )
        if isinstance(schema_owner, str) and schema_owner != "pcs-core":
            errors.append(
                f"entries.{artifact_type}: schema_owner must be pcs-core for v0 registry",
            )
        checks = entry.get("semantic_checks")
        if isinstance(checks, list):
            for index, check in enumerate(checks):
                if not isinstance(check, dict):
                    continue
                if not check.get("responsible_component"):
                    errors.append(
                        f"entries.{artifact_type}.semantic_checks[{index}]: "
                        "responsible_component required",
                    )
                if not check.get("severity"):
                    errors.append(
                        f"entries.{artifact_type}.semantic_checks[{index}]: severity required",
                    )
    return errors


def validate_release_chain_validation_result_semantics(data: dict[str, Any]) -> list[str]:
    from pcs_core.registry_data import all_registry_semantic_check_refs

    errors: list[str] = []
    _scan_commit_fields(data, "", errors)
    known_refs = all_registry_semantic_check_refs()
    status = data.get("status")
    checks = data.get("checks")
    failed_checks = (
        [c for c in checks if isinstance(c, dict) and c.get("status") == "failed"]
        if isinstance(checks, list)
        else []
    )
    failure_codes = data.get("failure_codes")
    has_failures = bool(failed_checks) or (
        isinstance(failure_codes, list) and len(failure_codes) > 0
    )
    if status == "ProofChecked" and has_failures:
        errors.append(
            "ReleaseChainValidationResult.v0 cannot use status ProofChecked with failed checks "
            "or non-empty failure_codes",
        )
    if status == "Rejected" and not has_failures:
        errors.append(
            "ReleaseChainValidationResult.v0 with status Rejected requires failed checks "
            "or failure_codes",
        )
    if isinstance(checks, list):
        from pcs_core.registry_semantics import audit_release_chain_registry_coverage

        deferred = data.get("deferred_registry_checks")
        if deferred is None:
            errors.append("deferred_registry_checks required")
            deferred = []
        elif not isinstance(deferred, list):
            errors.append("deferred_registry_checks must be an array")
            deferred = []
        from pcs_core.workflow_profiles import required_release_blocking_refs_for_profile

        profile_id = data.get("workflow_profile_id")
        required_refs = required_release_blocking_refs_for_profile(
            str(profile_id) if isinstance(profile_id, str) else None,
        )
        errors.extend(
            audit_release_chain_registry_coverage(
                checks,
                deferred,
                required_refs=required_refs,
            ),
        )
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                continue
            refs = check.get("registry_check_refs")
            if refs is None:
                errors.append(f"checks[{index}]: registry_check_refs required")
                continue
            if not isinstance(refs, list):
                errors.append(f"checks[{index}]: registry_check_refs must be an array")
                continue
            for ref in refs:
                if isinstance(ref, str) and ref not in known_refs:
                    errors.append(f"checks[{index}]: unknown registry check ref {ref!r}")
    return errors


def validate_conformance_report_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = data.get("status")
    checks_failed = data.get("checks_failed")
    failures = data.get("failures")
    checks_passed = data.get("checks_passed")
    if not isinstance(checks_passed, int) or checks_passed < 0:
        errors.append("ConformanceReport.v0 checks_passed must be a non-negative integer")
    if not isinstance(checks_failed, int) or checks_failed < 0:
        errors.append("ConformanceReport.v0 checks_failed must be a non-negative integer")
    failure_items = failures if isinstance(failures, list) else []
    if status == "failed":
        if checks_failed == 0 and not failure_items:
            errors.append(
                "ConformanceReport.v0 with status failed requires checks_failed > 0 or failures",
            )
    if status == "passed":
        if checks_failed != 0:
            errors.append("ConformanceReport.v0 with status passed requires checks_failed == 0")
        if failure_items:
            errors.append("ConformanceReport.v0 with status passed requires empty failures")
    results = data.get("results")
    if (
        isinstance(results, list)
        and isinstance(checks_passed, int)
        and isinstance(checks_failed, int)
    ):
        run_total = sum(
            int(item.get("checks_run", 0)) for item in results if isinstance(item, dict)
        )
        if run_total != checks_passed + checks_failed:
            errors.append(
                "ConformanceReport.v0 checks_passed + checks_failed must equal "
                "sum(results[].checks_run)",
            )
    return errors
