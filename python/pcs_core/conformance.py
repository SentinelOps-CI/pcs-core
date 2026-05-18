"""LabTrust fixture paths and PCS protocol conformance suite runner."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from pcs_core.paths import examples_dir, repo_root
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_fixtures import release_dir
from pcs_core.shared_hash_vectors import verify_shared_vectors
from pcs_core.validate import ValidationError, validate_file

LABTRUST_VALID_FIXTURES: tuple[str, ...] = (
    "science_claim_bundle.pending.valid.json",
    "trace_certificate.valid.json",
    "science_claim_bundle.certified.valid.json",
    "verification_result.valid.json",
    "signed_science_claim_bundle.valid.json",
)

LABTRUST_INVALID_FIXTURES: tuple[str, ...] = (
    "invalid_signed_schema_version_artifact_name.json",
    "invalid_singular_runtime_receipt_bundle.json",
    "invalid_failed_verification_result.json",
    "invalid_missing_trace_certificate.json",
)


def labtrust_examples_dir() -> Path:
    return examples_dir() / "labtrust"


def labtrust_fixture_path(name: str) -> Path:
    path = labtrust_examples_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"LabTrust conformance fixture not found: {path}")
    return path


SuiteFn = Callable[[], list[str]]

SUITES: dict[str, SuiteFn] = {}


def _record(name: str) -> Callable[[SuiteFn], SuiteFn]:
    def decorator(fn: SuiteFn) -> SuiteFn:
        SUITES[name] = fn
        return fn

    return decorator


@_record("release-manifest")
def _suite_release_manifest() -> list[str]:
    errors: list[str] = []
    path = release_dir() / "release_manifest.v0.json"
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(str(exc))
        errors.extend(exc.errors)
    return errors


@_record("handoff-manifest")
def _suite_handoff_manifest() -> list[str]:
    errors: list[str] = []
    for path in sorted(release_dir().glob("handoff_manifest.*.v0.json")):
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")
            errors.extend(f"{path.name}: {err}" for err in exc.errors)
    example = examples_dir() / "handoff_manifest.valid.json"
    try:
        validate_file(example)
    except ValidationError as exc:
        errors.append(f"{example.name}: {exc}")
    return errors


@_record("artifact-registry")
def _suite_artifact_registry() -> list[str]:
    from pcs_core.registry import validate_registry_file

    return validate_registry_file(examples_dir() / "artifact_registry.valid.json")


@_record("release-chain-validation")
def _suite_release_chain_validation() -> list[str]:
    errors: list[str] = []
    issues = validate_release_chain(release_dir())
    if issues:
        errors.extend(f"{issue.code}: {issue.message}" for issue in issues)
    result_path = release_dir() / "release_chain_validation_result.v0.json"
    try:
        validate_file(result_path)
    except ValidationError as exc:
        errors.append(str(exc))
        errors.extend(exc.errors)
    return errors


@_record("release-chain")
def _suite_release_chain() -> list[str]:
    return _suite_release_chain_validation()


@_record("hash")
def _suite_hash() -> list[str]:
    return verify_shared_vectors()


@_record("migration")
def _suite_migration() -> list[str]:
    errors: list[str] = []
    path = examples_dir() / "migration_report.valid.json"
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(str(exc))
    return errors


@_record("status-transition")
def _suite_status_transition() -> list[str]:
    from pcs_core.status_policy import check_status_transition

    errors: list[str] = []
    for old_status, new_status in (
        ("Rejected", "ProofChecked"),
        ("Stale", "ProofChecked"),
        ("RuntimeObserved", "ProofChecked"),
    ):
        verdict = check_status_transition(old_status, new_status)
        if verdict.allowed:
            errors.append(f"forbidden transition allowed: {old_status} -> {new_status}")
    return errors


def list_suites() -> list[str]:
    return sorted(SUITES.keys())


def run_conformance(suite: str) -> tuple[int, list[str]]:
    """Run one suite or `all`. Returns (exit_code, error_lines)."""
    names = list_suites() if suite == "all" else [suite]
    if suite != "all" and suite not in SUITES:
        return 2, [f"unknown suite: {suite}", f"available: {', '.join(list_suites())}"]

    all_errors: list[str] = []
    for name in names:
        errors = SUITES[name]()
        if errors:
            all_errors.append(f"[{name}]")
            all_errors.extend(errors)
    return (1 if all_errors else 0, all_errors)
