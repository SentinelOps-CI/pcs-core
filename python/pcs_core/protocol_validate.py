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
            if isinstance(digest, str) and digest.startswith("sha256:") and digest.endswith(
                "0" * 64,
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


def validate_release_chain_validation_result_semantics(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _scan_commit_fields(data, "", errors)
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
    return errors
