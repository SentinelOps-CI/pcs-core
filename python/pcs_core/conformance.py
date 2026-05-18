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


SuiteFn = Callable[[], tuple[list[str], list[str]]]

SUITES: dict[str, SuiteFn] = {}


def _record(name: str) -> Callable[[SuiteFn], SuiteFn]:
    def decorator(fn: SuiteFn) -> SuiteFn:
        SUITES[name] = fn
        return fn

    return decorator


@_record("release-manifest")
def _suite_release_manifest() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    path = release_dir() / "release_manifest.v0.json"
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(str(exc))
        errors.extend(exc.errors)
    return errors, []


@_record("handoff-manifest")
def _suite_handoff_manifest() -> tuple[list[str], list[str]]:
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
    return errors, []


@_record("artifact-registry")
def _suite_artifact_registry() -> tuple[list[str], list[str]]:
    from pcs_core.registry import validate_registry_file

    return validate_registry_file(examples_dir() / "artifact_registry.valid.json")


@_record("release-chain-validation")
def _suite_release_chain_validation() -> tuple[list[str], list[str]]:
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
    return errors, []


@_record("release-chain")
def _suite_release_chain() -> tuple[list[str], list[str]]:
    return _suite_release_chain_validation()


@_record("hash")
def _suite_hash() -> tuple[list[str], list[str]]:
    return verify_shared_vectors(), []


@_record("migration")
def _suite_migration() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    path = examples_dir() / "migration_report.valid.json"
    try:
        validate_file(path)
    except ValidationError as exc:
        errors.append(str(exc))
    return errors, []


@_record("component-release-fragment")
def _suite_component_release_fragment() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    paths = (
        examples_dir() / "component_release_fragment.valid.json",
        release_dir() / "labtrust_release_fragment.json",
    )
    for path in paths:
        if not path.is_file():
            errors.append(f"missing {path}")
            continue
        try:
            validate_file(path)
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")
            errors.extend(f"{path.name}: {err}" for err in exc.errors)
    return errors, []


@_record("status-transition")
def _suite_status_transition() -> tuple[list[str], list[str]]:
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
    return errors, []


def list_suites() -> list[str]:
    return sorted(SUITES.keys())


def run_conformance(suite: str) -> tuple[int, list[str]]:
    """Run one suite or `all`. Returns (exit_code, human-readable error lines)."""
    report = build_conformance_report_data(suite)
    lines: list[str] = []
    if report["status"] == "failed":
        for result in report["results"]:
            if result.get("status") == "failed":
                lines.append(f"[{result['suite']}]")
                lines.extend(str(err) for err in result.get("errors", []))
    return (0 if report["status"] == "passed" else 1, lines)


def build_conformance_report_data(suite: str) -> dict:
    from pcs_core.conformance_report import build_conformance_report, suite_result

    names = list_suites() if suite == "all" else [suite]
    if suite != "all" and suite not in SUITES:
        return build_conformance_report(
            suite=suite,
            suite_results=[
                suite_result(
                    suite,
                    [f"unknown suite: {suite}", f"available: {', '.join(list_suites())}"],
                ),
            ],
        )

    results: list[dict] = []
    for name in names:
        errors, warnings = SUITES[name]()
        results.append(suite_result(name, errors, warnings))
    return build_conformance_report(suite=suite, suite_results=results)
