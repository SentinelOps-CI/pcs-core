"""Declarative release-profile engine: UnknownWorkflowProfile + legacy parity."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from pcs_core.paths import examples_dir
from pcs_core.release_profile_engine import (
    UNKNOWN_WORKFLOW_PROFILE,
    compare_legacy_and_declarative,
    normalized_issue_codes,
    resolve_json_pointer,
    run_structural_release_profile_validation,
    validate_release_directory,
)
from pcs_core.release_profile_specs import (
    COMPUTATION_RELEASE_PROFILE,
    LABTRUST_RELEASE_PROFILE,
    TOOL_USE_RELEASE_PROFILE,
    computation_legacy_validator,
    labtrust_legacy_validator,
    parity_profile_specs,
    tool_use_legacy_validator,
)

LABTRUST = examples_dir() / "labtrust-release"
TOOL_USE = examples_dir() / "tool-use-release"
COMPUTATION = examples_dir() / "computation-release"
LABTRUST_INVALID = examples_dir() / "labtrust-release-invalid"
TOOL_USE_INVALID = examples_dir() / "tool-use-release-invalid"
COMPUTATION_INVALID = examples_dir() / "computation-release-invalid"

_VALID_ROOTS = {
    LABTRUST_RELEASE_PROFILE.workflow_profile_id: LABTRUST,
    TOOL_USE_RELEASE_PROFILE.workflow_profile_id: TOOL_USE,
    COMPUTATION_RELEASE_PROFILE.workflow_profile_id: COMPUTATION,
}

_INVALID_ROOTS = (
    (LABTRUST_INVALID, labtrust_legacy_validator, LABTRUST_RELEASE_PROFILE),
    (TOOL_USE_INVALID, tool_use_legacy_validator, TOOL_USE_RELEASE_PROFILE),
    (COMPUTATION_INVALID, computation_legacy_validator, COMPUTATION_RELEASE_PROFILE),
)


def test_resolve_json_pointer_rfc6901() -> None:
    doc = {"a": {"b": [{"c": 1}, {"c": 2}]}, "x/y": 3, "m~n": 4}
    assert resolve_json_pointer(doc, "") is doc
    assert resolve_json_pointer(doc, "/a/b/0/c") == 1
    assert resolve_json_pointer(doc, "/a/b/1/c") == 2
    assert resolve_json_pointer(doc, "/x~1y") == 3
    assert resolve_json_pointer(doc, "/m~0n") == 4
    assert resolve_json_pointer(doc, "/missing") is None
    assert resolve_json_pointer(doc, "a/b") is None


def test_unknown_workflow_profile_when_id_not_registered(tmp_path: Path) -> None:
    (tmp_path / "workflow_profile.v0.json").write_text(
        json.dumps(
            {
                "schema_version": "v0",
                "artifact_type": "WorkflowProfile.v0",
                "workflow_id": "domain.unknown_profile_v0",
                "name": "unknown",
            },
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "RELEASE_FIXTURE_MANIFEST.json").write_text(
        json.dumps(
            {
                "workflow_profile_id": "domain.unknown_profile_v0",
                "artifacts": {},
            },
        )
        + "\n",
        encoding="utf-8",
    )
    issues = validate_release_directory(tmp_path)
    assert any(issue.code == UNKNOWN_WORKFLOW_PROFILE for issue in issues)
    assert issues[0].actual == "domain.unknown_profile_v0"


def test_unknown_workflow_profile_not_labtrust_fallback(tmp_path: Path) -> None:
    """Directories with a manifest but no detectable registered profile fail closed."""
    (tmp_path / "RELEASE_FIXTURE_MANIFEST.json").write_text(
        json.dumps({"artifacts": {"only.json": "sha256:" + "ab" * 32}}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "only.json").write_text("{}\n", encoding="utf-8")
    issues = validate_release_directory(tmp_path)
    codes = {issue.code for issue in issues}
    assert UNKNOWN_WORKFLOW_PROFILE in codes
    assert "manifest_missing" not in codes


def test_empty_directory_still_reports_manifest_missing(tmp_path: Path) -> None:
    issues = validate_release_directory(tmp_path)
    assert {issue.code for issue in issues} == {"manifest_missing"}


def test_production_profiles_have_no_legacy_validator() -> None:
    assert LABTRUST_RELEASE_PROFILE.legacy_validator is None
    assert TOOL_USE_RELEASE_PROFILE.legacy_validator is None
    assert COMPUTATION_RELEASE_PROFILE.legacy_validator is None


@pytest.mark.parametrize(
    "spec",
    list(parity_profile_specs()),
    ids=lambda spec: spec.workflow_profile_id,
)
def test_legacy_declarative_parity_on_valid_fixtures(spec) -> None:
    path = _VALID_ROOTS[spec.workflow_profile_id]
    if not (path / "RELEASE_FIXTURE_MANIFEST.json").is_file():
        pytest.skip(f"missing release fixture {path}")
    legacy_codes, declarative_codes = compare_legacy_and_declarative(path, spec)
    assert legacy_codes == declarative_codes == frozenset()


@pytest.mark.parametrize(
    ("invalid_root", "legacy_fn", "base_spec"),
    _INVALID_ROOTS,
    ids=("labtrust", "tool-use", "computation"),
)
def test_legacy_declarative_parity_on_invalid_fixtures(
    invalid_root: Path,
    legacy_fn,
    base_spec,
) -> None:
    if not invalid_root.is_dir():
        pytest.skip(f"missing invalid root {invalid_root}")
    spec = replace(base_spec, legacy_validator=legacy_fn)
    cases = sorted(path for path in invalid_root.iterdir() if path.is_dir())
    assert cases, f"expected invalid fixtures under {invalid_root}"
    for case_dir in cases:
        legacy_codes, declarative_codes = compare_legacy_and_declarative(case_dir, spec)
        assert legacy_codes == declarative_codes, (
            f"{case_dir.name}: legacy={sorted(legacy_codes)} "
            f"declarative={sorted(declarative_codes)}"
        )


def test_structural_validation_passes_all_valid_domains() -> None:
    for path, spec in (
        (LABTRUST, LABTRUST_RELEASE_PROFILE),
        (TOOL_USE, TOOL_USE_RELEASE_PROFILE),
        (COMPUTATION, COMPUTATION_RELEASE_PROFILE),
    ):
        if not (path / "RELEASE_FIXTURE_MANIFEST.json").is_file():
            pytest.skip(f"missing {path}")
        assert run_structural_release_profile_validation(path, spec) == []
        assert validate_release_directory(path) == []


def test_labtrust_invalid_fixture_codes_via_declarative_engine() -> None:
    expected = {
        "placeholder_commit": "placeholder_commit_detected",
        "mismatched_certificate_id": "certificate_id_mismatch",
        "mismatched_trace_hash": "trace_hash_mismatch",
        "mismatched_certified_bundle_hash": "verified_input_hash_mismatch",
        "failed_scientific_memory_import": "scientific_memory_import_failed",
        "legacy_import_mode": "legacy_import_detected",
    }
    for name, code in expected.items():
        path = LABTRUST_INVALID / name
        if not path.is_dir():
            pytest.skip(f"missing {path}")
        codes = normalized_issue_codes(
            run_structural_release_profile_validation(path, LABTRUST_RELEASE_PROFILE),
        )
        assert code in codes
