"""Tool-use profile release-chain validation (multi-domain PCS)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pcs_core.paths import examples_dir
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_chain_profiles import TOOL_USE_WORKFLOW_PROFILE_ID
from pcs_core.release_chain_report import build_release_chain_validation_result
from pcs_core.tool_use_release_chain import TOOL_USE_MANIFEST_ARTIFACTS
from pcs_core.tool_use_validate import validate_tool_use_invalid_case
from pcs_core.validate import validate_artifact

TOOL_USE_RELEASE = examples_dir() / "tool-use-release"
INVALID_ROOT = examples_dir() / "tool-use-release-invalid"


def test_tool_use_release_chain_passes() -> None:
    if not (TOOL_USE_RELEASE / "RELEASE_FIXTURE_MANIFEST.json").is_file():
        pytest.skip("run python/scripts/materialize_tool_use_fixtures.py")
    assert validate_release_chain(TOOL_USE_RELEASE) == []


def test_tool_use_release_manifest_declares_workflow_profile() -> None:
    manifest = json.loads(
        (TOOL_USE_RELEASE / "release_manifest.v0.json").read_text(encoding="utf-8"),
    )
    assert manifest["workflow_profile_id"] == TOOL_USE_WORKFLOW_PROFILE_ID
    assert manifest["validation_profile"] == TOOL_USE_WORKFLOW_PROFILE_ID


def test_tool_use_scientific_memory_report_exposes_workflow_profile() -> None:
    report = json.loads(
        (TOOL_USE_RELEASE / "scientific_memory_import_report.json").read_text(encoding="utf-8"),
    )
    assert report["workflow_profile_id"] == TOOL_USE_WORKFLOW_PROFILE_ID
    assert "workflow_profile_render_path" in report
    assert TOOL_USE_WORKFLOW_PROFILE_ID in report["workflow_profile_render_path"]


def test_build_release_chain_validation_result_for_tool_use() -> None:
    if not (TOOL_USE_RELEASE / "RELEASE_FIXTURE_MANIFEST.json").is_file():
        pytest.skip("run python/scripts/materialize_tool_use_fixtures.py")
    result = build_release_chain_validation_result(TOOL_USE_RELEASE)
    validate_artifact(result, "ReleaseChainValidationResult.v0")
    assert result["workflow_profile_id"] == TOOL_USE_WORKFLOW_PROFILE_ID
    assert result["status"] == "ProofChecked"
    assert result["artifacts_checked"] == len(TOOL_USE_MANIFEST_ARTIFACTS)


def test_tool_use_legacy_manifest_lists_profile_and_artifacts() -> None:
    manifest = json.loads(
        (TOOL_USE_RELEASE / "RELEASE_FIXTURE_MANIFEST.json").read_text(encoding="utf-8"),
    )
    assert manifest["workflow_profile_id"] == TOOL_USE_WORKFLOW_PROFILE_ID
    assert set(manifest["artifacts"]) == set(TOOL_USE_MANIFEST_ARTIFACTS)


@pytest.mark.parametrize(
    "case_name",
    [
        "unauthorized_tool_call",
        "missing_policy_hash",
        "trace_hash_mismatch",
        "policy_hash_mismatch",
        "rejected_certificate",
        "unknown_authorization_status",
    ],
)
def test_tool_use_invalid_cases_fail_semantic_validation(case_name: str) -> None:
    """Harness returns [] when the negative fixture correctly fails release semantics."""
    case_dir = INVALID_ROOT / case_name
    if not case_dir.is_dir():
        pytest.skip(f"missing invalid fixture {case_name}")
    harness_errors = validate_tool_use_invalid_case(case_dir)
    assert harness_errors == [], harness_errors
