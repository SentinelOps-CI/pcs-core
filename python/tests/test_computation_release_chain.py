"""Scientific computation profile release-chain validation."""

from __future__ import annotations

import json

import pytest

from pcs_core.computation_release_chain import COMPUTATION_MANIFEST_ARTIFACTS
from pcs_core.computation_validate import validate_computation_invalid_case
from pcs_core.paths import examples_dir
from pcs_core.release_chain import validate_release_chain
from pcs_core.release_chain_profiles import COMPUTATION_WORKFLOW_PROFILE_ID
from pcs_core.release_chain_report import build_release_chain_validation_result
from pcs_core.validate import validate_artifact

COMPUTATION_RELEASE = examples_dir() / "computation-release"
INVALID_ROOT = examples_dir() / "computation-release-invalid"


def test_computation_release_chain_passes() -> None:
    if not (COMPUTATION_RELEASE / "RELEASE_FIXTURE_MANIFEST.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    assert validate_release_chain(COMPUTATION_RELEASE) == []


def test_computation_legacy_manifest_lists_profile_and_artifacts() -> None:
    if not (COMPUTATION_RELEASE / "RELEASE_FIXTURE_MANIFEST.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    manifest = json.loads(
        (COMPUTATION_RELEASE / "RELEASE_FIXTURE_MANIFEST.json").read_text(encoding="utf-8"),
    )
    assert manifest["workflow_profile_id"] == COMPUTATION_WORKFLOW_PROFILE_ID
    assert set(manifest["artifacts"]) == set(COMPUTATION_MANIFEST_ARTIFACTS)


def test_computation_release_manifest_declares_workflow_profile() -> None:
    manifest = json.loads(
        (COMPUTATION_RELEASE / "release_manifest.v0.json").read_text(encoding="utf-8"),
    )
    assert manifest["workflow_profile_id"] == COMPUTATION_WORKFLOW_PROFILE_ID
    assert manifest["validation_profile"] == COMPUTATION_WORKFLOW_PROFILE_ID


def test_build_release_chain_validation_result_for_computation() -> None:
    if not (COMPUTATION_RELEASE / "RELEASE_FIXTURE_MANIFEST.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    result = build_release_chain_validation_result(COMPUTATION_RELEASE)
    validate_artifact(result, "ReleaseChainValidationResult.v0")
    assert result["workflow_profile_id"] == COMPUTATION_WORKFLOW_PROFILE_ID
    assert result["status"] == "ProofChecked"
    assert result["artifacts_checked"] == len(COMPUTATION_MANIFEST_ARTIFACTS)


@pytest.mark.parametrize(
    "case_name",
    [
        "dataset_hash_mismatch",
        "result_hash_mismatch",
        "missing_code_commit",
        "nonzero_exit_code",
        "environment_digest_mismatch",
        "rejected_computation_witness",
    ],
)
def test_computation_invalid_cases_fail_semantic_validation(case_name: str) -> None:
    case_dir = INVALID_ROOT / case_name
    if not case_dir.is_dir():
        pytest.skip(f"missing invalid fixture {case_name}")
    harness_errors = validate_computation_invalid_case(case_dir)
    assert harness_errors == [], harness_errors
