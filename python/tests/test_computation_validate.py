"""Unit tests for scientific computation semantic validation."""

from __future__ import annotations

import json

import pytest

from pcs_core.computation_validate import (
    validate_computation_release_readiness,
    validate_computation_witness_alignment,
)
from pcs_core.paths import examples_dir
from pcs_core.workflow_profiles import load_workflow_profile

COMPUTATION_RELEASE = examples_dir() / "computation-release"


def _load(name: str) -> dict:
    return json.loads((COMPUTATION_RELEASE / name).read_text(encoding="utf-8"))


def test_load_workflow_profile_from_computation_release() -> None:
    if not (COMPUTATION_RELEASE / "workflow_profile.v0.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    profile = load_workflow_profile("scientific_computation.reproducibility_v0")
    assert profile is not None
    assert profile["workflow_id"] == "scientific_computation.reproducibility_v0"
    assert "ComputationWitness.v0" in profile["certificate_artifacts"]


def test_valid_computation_train_has_no_alignment_errors() -> None:
    if not (COMPUTATION_RELEASE / "computation_witness.json").is_file():
        pytest.skip("run python/scripts/materialize_computation_fixtures.py")
    errors = validate_computation_witness_alignment(
        dataset=_load("dataset_receipt.json"),
        environment=_load("environment_receipt.json"),
        run_receipt=_load("computation_run_receipt.json"),
        result=_load("result_artifact.json"),
        witness=_load("computation_witness.json"),
    )
    assert errors == [], errors


@pytest.mark.parametrize(
    ("case_name", "expected_token"),
    [
        ("dataset_hash_mismatch", "dataset_hash_matches_receipt"),
        ("result_hash_mismatch", "result_hashes_match_result_artifacts"),
        ("missing_code_commit", "must not be zero"),
        ("nonzero_exit_code", "nonzero_exit_code"),
        ("environment_digest_mismatch", "environment_hash_matches_receipt"),
        ("rejected_computation_witness", "CertificateChecked"),
    ],
)
def test_invalid_cases_emit_precise_failure_class(case_name: str, expected_token: str) -> None:
    root = examples_dir() / "computation-release-invalid" / case_name
    if not root.is_dir():
        pytest.skip(f"missing invalid fixture {case_name}")
    errors = validate_computation_release_readiness(
        dataset=json.loads((root / "dataset_receipt.json").read_text(encoding="utf-8")),
        environment=json.loads((root / "environment_receipt.json").read_text(encoding="utf-8")),
        run_receipt=json.loads((root / "computation_run_receipt.json").read_text(encoding="utf-8")),
        result=json.loads((root / "result_artifact.json").read_text(encoding="utf-8")),
        witness=json.loads((root / "computation_witness.json").read_text(encoding="utf-8")),
    )
    assert errors, f"{case_name} must fail validation"
    joined = " ".join(errors)
    assert expected_token in joined, joined
